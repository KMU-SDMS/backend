import os
import json
import secrets
import time
import hashlib
import base64
import urllib.parse
import urllib.request
from http import cookies
from typing import Dict

from src.utils.session_store import (
    put_session,
    delete_session,
    build_user_agent_ip_hash,
)


COGNITO_DOMAIN = os.environ.get("COGNITO_DOMAIN", "").rstrip("/")
CLIENT_ID = os.environ.get("COGNITO_CLIENT_ID", "")
CALLBACK_URI = os.environ.get("CALLBACK_URI", "")
COOKIE_DOMAIN = os.environ.get("COOKIE_DOMAIN", None)
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "true").lower() == "true"
SESSION_COOKIE_TTL_SECONDS = int(
    os.environ.get("SESSION_COOKIE_TTL_SECONDS", "900") or 900
)
PERSIST_COOKIE_TTL_SECONDS = int(
    os.environ.get("PERSIST_COOKIE_TTL_SECONDS", "172800000") or 172800000
)

# 더 이상 기본 리다이렉트 환경변수는 사용하지 않음

# 동적 리다이렉트 화이트리스트(환경변수)
_ALLOWED_REDIRECT_ORIGINS_RAW = os.environ.get("ALLOWED_REDIRECT_ORIGINS", "")
_ALLOWED_LOGOUT_URLS_RAW = os.environ.get("ALLOWED_LOGOUT_URLS", "")


def _split_csv(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(",") if part.strip()]


def _build_origin(scheme: str, netloc: str) -> str:
    return f"{scheme}://{netloc}"


def _parse_origin(url: str) -> str | None:
    try:
        parsed = urllib.parse.urlparse(url)
        if not (parsed.scheme and parsed.netloc):
            return None
        return _build_origin(parsed.scheme.lower(), parsed.netloc.lower())
    except Exception:
        return None


ALLOWED_REDIRECT_ORIGINS: set[str] = set()
for item in _split_csv(_ALLOWED_REDIRECT_ORIGINS_RAW):
    origin = _parse_origin(item)
    if origin:
        ALLOWED_REDIRECT_ORIGINS.add(origin)

ALLOWED_LOGOUT_URLS: set[str] = set(_split_csv(_ALLOWED_LOGOUT_URLS_RAW))


def _is_absolute_url(url: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(url)
        return bool(parsed.scheme and parsed.netloc)
    except Exception:
        return False


def _is_allowed_origin(url: str) -> bool:
    if not _is_absolute_url(url):
        return False
    origin = _parse_origin(url)
    if not origin:
        return False
    return origin in ALLOWED_REDIRECT_ORIGINS


def _is_allowed_logout_url(url: str) -> bool:
    # Cognito는 정확한 logout_uri 매칭을 요구하므로 전체 URL 일치만 허용
    if not _is_absolute_url(url):
        return False
    return url in ALLOWED_LOGOUT_URLS


def _set_cookie(
    name: str,
    value: str,
    max_age: int | None = None,
    path: str = "/",
    http_only: bool = True,
    same_site: str = "Lax",
):
    c = cookies.SimpleCookie()
    c[name] = value
    if COOKIE_DOMAIN:
        c[name]["domain"] = COOKIE_DOMAIN
    c[name]["path"] = path
    if max_age is not None:
        c[name]["max-age"] = str(max_age)
    if COOKIE_SECURE:
        c[name]["secure"] = True
    if http_only:
        c[name]["httponly"] = True
    # 기본값 Lax: same-site 요청은 항상 전송, cross-site는 top-level GET만 전송
    c[name]["samesite"] = same_site
    return ("Set-Cookie", c.output(header="").strip())


def _base64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _get_cookie_map(cookie_header: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for part in cookie_header.split(";"):
        k, _, v = part.strip().partition("=")
        if k:
            val = urllib.parse.unquote(v)
            if len(val) >= 2 and val.startswith('"') and val.endswith('"'):
                val = val[1:-1]
            result[k] = val
    return result


def login(event, context):
    code_verifier = _base64url_encode(secrets.token_urlsafe(64).encode("utf-8"))[:128]
    code_challenge = _base64url_encode(
        hashlib.sha256(code_verifier.encode("utf-8")).digest()
    )

    # Nonce/state 저장은 쿠키로만. 리다이렉트 URL은 서버내 상수 사용
    set_cookie_headers: list[tuple[str, str]] = []
    set_cookie_headers.append(
        _set_cookie(
            "cv", urllib.parse.quote(code_verifier), max_age=600, same_site="Lax"
        )
    )
    state_nonce = _base64url_encode(secrets.token_bytes(16))
    set_cookie_headers.append(
        _set_cookie("st", urllib.parse.quote(state_nonce), max_age=600, same_site="Lax")
    )
    state_payload = {"s": state_nonce}

    # redirect 쿼리 수집 및 화이트리스트 검증 후 state에 포함
    query_params = event.get("queryStringParameters") or {}
    redirect_param = query_params.get("redirect")
    if redirect_param and _is_allowed_origin(redirect_param):
        state_payload["r"] = redirect_param
    state = _base64url_encode(json.dumps(state_payload).encode("utf-8"))

    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": CALLBACK_URI,
        "response_type": "code",
        "scope": "openid",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
    }
    authorization_url = (
        f"{COGNITO_DOMAIN}/oauth2/authorize?{urllib.parse.urlencode(params)}"
    )

    cookies_out = [v for _, v in set_cookie_headers]
    headers: dict[str, object] = {"Location": authorization_url}
    return {"statusCode": 302, "headers": headers, "cookies": cookies_out, "body": ""}


def callback(event, context):
    query_params = event.get("queryStringParameters") or {}
    code = query_params.get("code")
    state_param = query_params.get("state") or ""

    headers_in = event.get("headers") or {}
    cookie_header = headers_in.get("cookie") or headers_in.get("Cookie") or ""
    # HTTP API v2는 쿠키를 event.cookies 배열로도 전달한다. 둘을 병합해 안전하게 파싱한다.
    cookies_array = event.get("cookies") or []
    if isinstance(cookies_array, list) and cookies_array:
        # "a=b" 형태들이므로 세미콜론으로 이어 동일 파서 사용
        extra = "; ".join(cookies_array)
        cookie_header = f"{cookie_header}; {extra}" if cookie_header else extra
    cookie_map = _get_cookie_map(cookie_header)
    code_verifier = cookie_map.get("cv")
    state_cookie = cookie_map.get("st")

    if not state_param:
        return {"statusCode": 400, "body": "Missing state"}
    try:
        padded = state_param + "=" * (-len(state_param) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
        )
        state_nonce = payload.get("s")
        if not (state_cookie and state_cookie == state_nonce):
            return {"statusCode": 400, "body": "Invalid state"}
    except Exception:
        return {"statusCode": 400, "body": "Malformed state"}

    if not code:
        return {"statusCode": 400, "body": "Missing authorization code"}

    token_url = f"{COGNITO_DOMAIN}/oauth2/token"
    form = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "code": code,
        "redirect_uri": CALLBACK_URI,
    }
    if code_verifier:
        form["code_verifier"] = code_verifier
    data = urllib.parse.urlencode(form).encode("utf-8")
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    req = urllib.request.Request(token_url, data=data, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            err_text = (e.read() or b"").decode("utf-8")
        except Exception:
            err_text = ""
        # 디버깅 편의를 위해 상태코드/간략 메시지 반환 (민감정보 제외)
        snippet = err_text[:256]
        print(f"[token-exchange-http-error] status={e.code} body_snippet={snippet}")
        return {"statusCode": 500, "body": f"token_exchange_failed:{e.code}:{snippet}"}
    except Exception as e:
        print(f"[token-exchange-error] {getattr(e, 'message', str(e))}")
        return {"statusCode": 500, "body": "token_exchange_failed:unknown"}

    access_token = body.get("access_token")
    refresh_token = body.get("refresh_token")
    expires_in = int(body.get("expires_in", 3600))
    if not access_token:
        return {"statusCode": 500, "body": "token_missing"}

    # 세션 생성 및 sid 발급
    sid = _base64url_encode(secrets.token_bytes(24))

    ua = headers_in.get("user-agent", "")
    ip = (event.get("requestContext") or {}).get("http", {}).get("sourceIp", "")
    ua_hash = build_user_agent_ip_hash(ua, ip)

    expires_at = int(time.time()) + expires_in
    put_session(
        sid,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
        ua_hash=ua_hash,
        ip=ip,
    )

    set_cookie_headers: list[tuple[str, str]] = []
    # same-site(8080↔3000) 환경에서는 Lax/Strict 모두 전송됨. 로컬 HTTP에서도 동작하도록 Lax 사용
    set_cookie_headers.append(
        _set_cookie("session", sid, max_age=SESSION_COOKIE_TTL_SECONDS, same_site="Lax")
    )
    # 장기 자동 로그인을 위한 영구 쿠키(동일 sid 저장)
    set_cookie_headers.append(
        _set_cookie("ps", sid, max_age=PERSIST_COOKIE_TTL_SECONDS, same_site="Lax")
    )
    # 임시 쿠키 정리
    set_cookie_headers.append(_set_cookie("cv", "", max_age=0))
    set_cookie_headers.append(_set_cookie("st", "", max_age=0))

    cookies_out = [v for _, v in set_cookie_headers]
    # state의 r 값이 화이트리스트를 통과하면 해당 URL로 리다이렉트
    # redirect 누락 또는 미허용이면 400 반환
    target_redirect = None
    r = payload.get("r") if isinstance(payload, dict) else None
    if r and _is_allowed_origin(r):
        headers_out: dict[str, object] = {"Location": r}
        return {
            "statusCode": 302,
            "headers": headers_out,
            "cookies": cookies_out,
            "body": "",
        }
    return {"statusCode": 400, "body": "redirect_missing_or_not_allowed"}


def logout(event, context):
    """완전 로그아웃: 로컬 세션 삭제 후 Cognito Hosted UI 로그아웃으로 리다이렉트."""
    headers_in = event.get("headers") or {}
    cookie_header = headers_in.get("cookie") or headers_in.get("Cookie") or ""
    cookies_array = event.get("cookies") or []
    if isinstance(cookies_array, list) and cookies_array:
        extra = "; ".join(cookies_array)
        cookie_header = f"{cookie_header}; {extra}" if cookie_header else extra
    cookie_map = _get_cookie_map(cookie_header)
    sid = cookie_map.get("session")
    if sid:
        delete_session(sid)

    set_cookie_headers: list[tuple[str, str]] = []
    for name in ["session", "ps", "cv", "st"]:
        set_cookie_headers.append(_set_cookie(name, "", max_age=0))

    # 요청 redirect 파라미터 읽어 화이트리스트 및 등록 URL 검증
    query_params = event.get("queryStringParameters") or {}
    requested_redirect = query_params.get("redirect")
    logout_uri = None
    if (
        requested_redirect
        and _is_allowed_origin(requested_redirect)
        and _is_allowed_logout_url(requested_redirect)
    ):
        logout_uri = requested_redirect

    # Cognito 로그아웃 URL 구성
    if not (COGNITO_DOMAIN and CLIENT_ID):
        # 환경 미설정. redirect가 없으면 400, 있으면 그쪽으로 302
        cookies_out = [v for _, v in set_cookie_headers]
        if not logout_uri:
            return {"statusCode": 400, "body": "redirect_missing_or_not_allowed"}
        return {
            "statusCode": 302,
            "headers": {"Location": logout_uri},
            "cookies": cookies_out,
            "body": "",
        }

    if not logout_uri:
        return {"statusCode": 400, "body": "redirect_missing_or_not_allowed"}
    params = {"client_id": CLIENT_ID, "logout_uri": logout_uri}
    location = f"{COGNITO_DOMAIN}/logout?{urllib.parse.urlencode(params)}"
    cookies_out = [v for _, v in set_cookie_headers]
    return {
        "statusCode": 302,
        "headers": {"Location": location},
        "cookies": cookies_out,
        "body": "",
    }
