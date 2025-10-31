import json
import hashlib
import os
import time
import urllib.parse
import importlib
from functools import lru_cache
from typing import Any, Callable, Dict, Tuple

from src.utils.session_store import (
    get_session,
    refresh_access_token,
    put_session,
    build_user_agent_ip_hash,
)
from src.utils.routing import resolve_handler
from src.utils.cognito_auth import get_cognito_groups, get_user_info


COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "true").lower() == "true"
COOKIE_DOMAIN = os.environ.get("COOKIE_DOMAIN", None)
SESSION_COOKIE_TTL_SECONDS = int(
    os.environ.get("SESSION_COOKIE_TTL_SECONDS", "900") or 900
)


def _set_cookie(
    name: str,
    value: str,
    max_age: int | None = None,
    path: str = "/",
    same_site: str = "Lax",
):
    from http import cookies

    c = cookies.SimpleCookie()
    c[name] = value
    if COOKIE_DOMAIN:
        c[name]["domain"] = COOKIE_DOMAIN
    c[name]["path"] = path
    if max_age is not None:
        c[name]["max-age"] = str(max_age)
    if COOKIE_SECURE:
        c[name]["secure"] = True
    c[name]["httponly"] = True
    c[name]["samesite"] = same_site
    return ("Set-Cookie", c.output(header="").strip())


def _get_cookie_map(cookie_header: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for part in cookie_header.split(";"):
        k, _, v = part.strip().partition("=")
        if k:
            result[k] = urllib.parse.unquote(v)
    return result


def _build_response(
    status: int,
    body: Any,
    headers: Dict[str, Any] | None = None,
    cookies_out: list[str] | None = None,
):
    resp_headers: Dict[str, Any] = {"Content-Type": "application/json"}
    if headers:
        resp_headers.update(headers)
    result: Dict[str, Any] = {
        "statusCode": status,
        "headers": resp_headers,
        "body": json.dumps(body),
    }
    if cookies_out:
        result["cookies"] = cookies_out
    return result


@lru_cache(maxsize=256)
def _import_handler(module_name: str, func_name: str) -> Callable[..., Any] | None:
    module = importlib.import_module(f"src.handlers.{module_name}")
    return getattr(module, func_name, None)


def _resolve_handler(
    path: str, method: str
) -> Tuple[Callable[..., Any] | None, Dict[str, Any]]:
    # routing 모듈은 (module_name, func_name)를 돌려주고,
    # 실제 핸들러 임포트는 여기서 수행한다.
    pair, extra = resolve_handler(path, method)
    if not pair:
        return None, extra
    module_name, func_name = pair
    handler = _import_handler(module_name, func_name)
    return handler, extra


def proxy(event, context):
    headers_in = event.get("headers") or {}
    # Preflight(OPTIONS) 요청은 인증/세션 검증 없이 바로 204로 응답
    method = (
        ((event.get("requestContext") or {}).get("http") or {}).get("method")
        or headers_in.get("x-http-method-override")
        or event.get("httpMethod")
        or "GET"
    )
    if method == "OPTIONS":
        return {"statusCode": 204, "headers": {}, "body": ""}
    cookie_header = headers_in.get("cookie") or headers_in.get("Cookie") or ""
    cookies_array = event.get("cookies") or []
    if isinstance(cookies_array, list) and cookies_array:
        extra = "; ".join(cookies_array)
        cookie_header = f"{cookie_header}; {extra}" if cookie_header else extra
    cookie_map = _get_cookie_map(cookie_header)
    sid = cookie_map.get("session") or cookie_map.get("ps")
    if not sid:
        return _build_response(401, {"message": "Unauthorized"})

    session = get_session(sid)
    if not session:
        return _build_response(401, {"message": "Session not found"})

    # UA/IP 바인딩 확인
    ua = headers_in.get("user-agent", "")
    ip = (event.get("requestContext") or {}).get("http", {}).get("sourceIp", "")
    if session.get("ua_hash") != build_user_agent_ip_hash(ua, ip):
        return _build_response(401, {"message": "Session bind mismatch"})

    # 만료 직후 refresh
    cookies_out: list[str] = []
    now = int(time.time())
    expires_at = int(session.get("expires_at", now))
    refresh_token = session.get("refresh_token") or ""
    access_token = session.get("access_token") or ""
    if now >= expires_at and refresh_token:

        def _fp(token: str) -> str:
            try:
                return hashlib.sha256((token or "").encode("utf-8")).hexdigest()[:8]
            except Exception:
                return ""

        old_fp = _fp(session.get("access_token", ""))
        print(
            f"[refresh-check] now={now} expires_at={expires_at} do_refresh=True sid_fp={_fp(sid)} access_fp={old_fp}"
        )
        refreshed = refresh_access_token(refresh_token)
        if refreshed is not None:
            access_token, expires_in, new_refresh = refreshed
            session["access_token"] = access_token
            session["expires_at"] = now + int(expires_in)
            if new_refresh:
                session["refresh_token"] = new_refresh
            # 재저장
            put_session(
                sid,
                access_token=session["access_token"],
                refresh_token=session.get("refresh_token"),
                expires_at=session["expires_at"],
                ua_hash=session["ua_hash"],
                ip=session.get("ip", ""),
            )
            # 세션 쿠키 재발급(슬라이딩 윈도우)
            cookies_out.append(
                _set_cookie(
                    "session",
                    sid,
                    max_age=SESSION_COOKIE_TTL_SECONDS,
                    same_site=("None" if COOKIE_SECURE else "Lax"),
                )[1]
            )
            new_fp = _fp(session.get("access_token", ""))
            print(
                f"[refresh-done] old_fp={old_fp} new_fp={new_fp} same={old_fp==new_fp} new_expires_at={session['expires_at']} new_refresh={'yes' if bool(new_refresh) else 'no'}"
            )
        else:
            print("[refresh-failed] token endpoint returned None")

    # session 쿠키가 없고 ps로 인증된 경우, session 슬라이딩 발급
    if (cookie_map.get("session") is None) and (cookie_map.get("ps") == sid):
        cookies_out.append(
            _set_cookie(
                "session",
                sid,
                max_age=SESSION_COOKIE_TTL_SECONDS,
                same_site=("None" if COOKIE_SECURE else "Lax"),
            )[1]
        )

    # 내부 핸들러 연결 전, 토큰/그룹 컨텍스트 주입
    try:
        groups = get_cognito_groups(access_token) if access_token else []
        user_info = get_user_info(access_token) if access_token else {}
        event["access_token"] = access_token
        event["cognito_groups"] = groups
        event["user_info"] = user_info
    except Exception:
        # 주입 실패는 요청 차단 사유가 아님
        event["access_token"] = access_token
        event["cognito_groups"] = []
        event["user_info"] = {}

    # 내부 핸들러 연결
    path = (event.get("rawPath") or event.get("path") or "").rstrip("/")
    handler, extra = _resolve_handler(path, method)
    if not handler:
        return _build_response(404, {"message": "Not Found"})
    # 기존 핸들러 시그니처 유지: (event, context)
    try:
        result = handler(event, context)
    except Exception as ex:
        return _build_response(500, {"message": "Upstream error", "detail": str(ex)})

    # 핸들러가 이미 API GW v2 응답 형태라면 쿠키 병합 후 전달
    if isinstance(result, dict) and "statusCode" in result and "body" in result:
        if cookies_out:
            existing = list(result.get("cookies") or [])
            result["cookies"] = existing + cookies_out
        return result
    # 그렇지 않으면 JSON으로 래핑
    return _build_response(200, result)
