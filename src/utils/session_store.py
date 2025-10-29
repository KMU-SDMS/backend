import os
import time
import hashlib
import json
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional, Tuple

import boto3
from botocore.exceptions import ClientError


SESSION_TABLE = os.environ.get("SESSION_TABLE", "")
# DynamoDB TTL: 기본 2000일 + 7일 버퍼(환경변수 우선)
SESSION_TTL_SECONDS = int(
    os.environ.get("SESSION_TTL_SECONDS", "173404800") or 173404800
)
COGNITO_DOMAIN = os.environ.get("COGNITO_DOMAIN", "").rstrip("/")
COGNITO_CLIENT_ID = os.environ.get("COGNITO_CLIENT_ID", "")


_dynamodb = boto3.resource("dynamodb")
_table = _dynamodb.Table(SESSION_TABLE) if SESSION_TABLE else None


def _now_epoch() -> int:
    return int(time.time())


def build_user_agent_ip_hash(user_agent: str, ip: str) -> str:
    base = (user_agent or "") + "|" + (ip or "")
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def put_session(
    sid: str,
    *,
    access_token: str,
    refresh_token: Optional[str],
    expires_at: int,
    ua_hash: str,
    ip: str,
) -> None:
    if not _table:
        raise RuntimeError("SESSION_TABLE not configured")
    ttl = _now_epoch() + SESSION_TTL_SECONDS
    item: Dict[str, Any] = {
        "sid": sid,
        "access_token": access_token,
        "refresh_token": refresh_token or "",
        "expires_at": int(expires_at),
        "ua_hash": ua_hash,
        "ip": ip,
        "created_at": _now_epoch(),
        "ttl": ttl,
    }
    _table.put_item(Item=item)


def get_session(sid: str) -> Optional[Dict[str, Any]]:
    if not _table:
        raise RuntimeError("SESSION_TABLE not configured")
    try:
        res = _table.get_item(Key={"sid": sid}, ConsistentRead=True)
        return res.get("Item")
    except ClientError:
        return None


def delete_session(sid: str) -> None:
    if not _table:
        raise RuntimeError("SESSION_TABLE not configured")
    try:
        _table.delete_item(Key={"sid": sid})
    except ClientError:
        pass


def refresh_access_token(
    refresh_token: str,
) -> Optional[Tuple[str, int, Optional[str]]]:
    """
    Returns (access_token, expires_in, new_refresh_token|None) or None on failure.
    """
    if not (COGNITO_DOMAIN and COGNITO_CLIENT_ID):
        return None
    token_url = f"{COGNITO_DOMAIN}/oauth2/token"
    form = {
        "grant_type": "refresh_token",
        "client_id": COGNITO_CLIENT_ID,
        "refresh_token": refresh_token,
    }
    data = urllib.parse.urlencode(form).encode("utf-8")
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    req = urllib.request.Request(token_url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None
    access_token = body.get("access_token")
    expires_in = int(body.get("expires_in", 3600))
    new_refresh = body.get("refresh_token")
    # 최소 로그: 액세스 토큰 지문 및 만료값
    try:
        import hashlib as _h

        _fp = _h.sha256((access_token or "").encode("utf-8")).hexdigest()[:8]
        print(
            f"[token-endpoint] access_fp={_fp} expires_in={expires_in} new_refresh={'yes' if bool(new_refresh) else 'no'}"
        )
    except Exception:
        pass
    if not access_token:
        return None
    return access_token, expires_in, new_refresh


def base64_encode(data: bytes) -> str:
    import base64

    return base64.b64encode(data).decode("utf-8")


def validate_session_security(existing_sid, headers_in, request_context):
    """완전한 세션 보안 검증"""

    session_data = get_session(existing_sid)

    if not session_data:
        return None, "session_not_found_in_db"

    # 2. 세션 데이터 무결성 검증
    required_fields = ["access_token", "expires_at", "ua_hash", "ip", "created_at"]
    for field in required_fields:
        if field not in session_data or not session_data[field]:
            return None, f"session_data_corrupted_missing_{field}"

    # 3. 만료 시간 검증
    current_time = int(time.time())
    expires_at = session_data.get("expires_at", 0)

    if expires_at <= current_time:
        # 만료된 세션은 삭제
        delete_session(existing_sid)
        return None, "session_expired"

    # 4. User-Agent + IP 해시 검증 (세션 하이재킹 방지)
    ua = headers_in.get("user-agent", "")
    ip = request_context.get("http", {}).get("sourceIp", "")
    current_ua_hash = build_user_agent_ip_hash(ua, ip)
    stored_ua_hash = session_data.get("ua_hash", "")

    if stored_ua_hash != current_ua_hash:
        print(
            f"[security] Session hijacking detected! stored_hash={stored_ua_hash[:8]}... current_hash={current_ua_hash[:8]}..."
        )
        # 하이재킹 감지 시 즉시 세션 삭제
        delete_session(existing_sid)
        return None, "session_hijacking_detected"

    # 5. 토큰 갱신 필요 여부 확인
    token_refresh_threshold = 300  # 5분 전에 미리 갱신
    if expires_at - current_time < token_refresh_threshold:
        refresh_token = session_data.get("refresh_token")
        if refresh_token:

            refresh_result = refresh_access_token(refresh_token)

            if refresh_result:
                new_access_token, expires_in, new_refresh_token = refresh_result
                new_expires_at = current_time + expires_in

                # 세션 업데이트 (보안 정보 유지)
                put_session(
                    existing_sid,
                    access_token=new_access_token,
                    refresh_token=new_refresh_token or refresh_token,
                    expires_at=new_expires_at,
                    ua_hash=stored_ua_hash,  # 기존 해시 유지
                    ip=session_data.get("ip", ""),
                )

                print(f"[login] Token refreshed successfully")
                return session_data, "valid"
            else:
                # 토큰 갱신 실패
                delete_session(existing_sid)
                return None, "token_refresh_failed"

    return session_data, "valid"
