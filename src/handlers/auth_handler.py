import os
import json
import urllib.parse
import urllib.request
from http import cookies
import base64
import hashlib
import secrets


COGNITO_DOMAIN = os.environ.get("COGNITO_DOMAIN", "").rstrip("/")
CLIENT_ID = os.environ.get("COGNITO_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("COGNITO_CLIENT_SECRET", "")
CALLBACK_URI = os.environ.get("CALLBACK_URI", "")
SIGNED_OUT_URI = os.environ.get("SIGNED_OUT_URI", "")
COOKIE_DOMAIN = os.environ.get("COOKIE_DOMAIN", None)
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "true").lower() == "true"
_ALLOWED_ORIGINS_RAW = os.environ.get("ALLOWED_REDIRECT_ORIGINS", "")
ALLOW_ALL_REDIRECT_ORIGINS = _ALLOWED_ORIGINS_RAW.strip() == "*"
ALLOWED_REDIRECT_ORIGINS = (
    set()
    if ALLOW_ALL_REDIRECT_ORIGINS
    else {o.strip().rstrip("/") for o in _ALLOWED_ORIGINS_RAW.split(",") if o.strip()}
)


def _set_cookie(
    name: str,
    value: str,
    max_age: int | None = None,
    path: str = "/",
    http_only: bool = True,
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
    c[name]["samesite"] = "Lax"
    return ("Set-Cookie", c.output(header="").strip())


def _base64url_encode(raw: bytes) -> str:
    # RFC 7636/7515: base64url without padding
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _get_origin(url: str) -> str:
    try:
        p = urllib.parse.urlparse(url)
        return f"{p.scheme}://{p.netloc}" if p.scheme and p.netloc else ""
    except Exception:
        return ""


def _is_allowed_redirect(url: str) -> bool:
    if not url:
        return False
    try:
        p = urllib.parse.urlparse(url)
        if not p.scheme or not p.netloc:
            return False
        origin = f"{p.scheme}://{p.netloc}"
        if ALLOW_ALL_REDIRECT_ORIGINS:
            return True
        return origin.rstrip("/") in ALLOWED_REDIRECT_ORIGINS
    except Exception:
        return False


def _get_cookie_map(cookie_header: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for part in cookie_header.split(";"):
        k, _, v = part.strip().partition("=")
        if k:
            val = urllib.parse.unquote(v)
            # Some browsers quote cookie values when special chars exist
            if len(val) >= 2 and val.startswith('"') and val.endswith('"'):
                val = val[1:-1]
            result[k] = val
    return result


def login(event, context):
    # Generate PKCE code_verifier and code_challenge (S256)
    code_verifier = _base64url_encode(secrets.token_urlsafe(64).encode("utf-8"))[:128]
    code_challenge = _base64url_encode(
        hashlib.sha256(code_verifier.encode("utf-8")).digest()
    )

    # Client-provided post-login redirect (absolute URL, origin whitelisted)
    query_params = event.get("queryStringParameters") or {}
    requested_redirect = (query_params.get("redirect") or "").strip()
    if not _is_allowed_redirect(requested_redirect):
        return {"statusCode": 400, "body": "Invalid or missing redirect"}
    redirect_after_login = requested_redirect

    # Set code_verifier in cookie (cv)
    set_cookie_headers: list[tuple[str, str]] = []
    # HttpOnly not strictly required for PKCE verifier; keep HttpOnly true as it only needs to be read by server callback
    set_cookie_headers.append(
        _set_cookie("cv", urllib.parse.quote(code_verifier), max_age=600)
    )

    # State param with nonce + intended redirect
    state_nonce = _base64url_encode(secrets.token_bytes(16))
    # store nonce in cookie for verification
    set_cookie_headers.append(
        _set_cookie("st", urllib.parse.quote(state_nonce), max_age=600)
    )
    state_payload = {"s": state_nonce, "r": redirect_after_login}
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
    error = query_params.get("error")
    state_param = query_params.get("state") or ""

    headers_in = event.get("headers") or {}
    cookie_header = headers_in.get("cookie") or headers_in.get("Cookie") or ""

    cookie_map = _get_cookie_map(cookie_header)
    code_verifier = cookie_map.get("cv")
    state_cookie = cookie_map.get("st")

    # Determine post-login redirect from state; error if invalid
    if not state_param:
        return {"statusCode": 400, "body": "Missing state"}
    try:
        padded = state_param + "=" * (-len(state_param) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
        )
        state_nonce = payload.get("s")
        redirect_candidate = payload.get("r")
        if not (
            state_cookie
            and state_cookie == state_nonce
            and _is_allowed_redirect(redirect_candidate)
        ):
            return {"statusCode": 400, "body": "Invalid state or redirect"}
        post_login_redirect = redirect_candidate
    except Exception:
        return {"statusCode": 400, "body": "Malformed state"}

    if error:
        location = f"{post_login_redirect}?login_error={urllib.parse.quote(error)}"
        return {"statusCode": 302, "headers": {"Location": location}, "body": ""}

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
    if CLIENT_SECRET:
        basic = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode("utf-8")).decode(
            "utf-8"
        )
        headers["Authorization"] = f"Basic {basic}"

    req = urllib.request.Request(token_url, data=data, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except Exception:
        location = f"{post_login_redirect}?login_error=token_exchange_failed"
        return {"statusCode": 302, "headers": {"Location": location}, "body": ""}

    access_token = body.get("access_token")
    id_token = body.get("id_token")
    refresh_token = body.get("refresh_token")
    expires_in = body.get("expires_in", 3600)

    if not access_token or not id_token:
        location = f"{post_login_redirect}?login_error=token_missing"
        return {"statusCode": 302, "headers": {"Location": location}, "body": ""}

    set_cookie_headers: list[tuple[str, str]] = []
    set_cookie_headers.append(_set_cookie("atk", access_token, max_age=expires_in))
    set_cookie_headers.append(_set_cookie("idk", id_token, max_age=expires_in))
    if refresh_token:
        set_cookie_headers.append(
            _set_cookie("rtk", refresh_token, max_age=30 * 24 * 3600)
        )
    set_cookie_headers.append(_set_cookie("cv", "", max_age=0))
    set_cookie_headers.append(_set_cookie("st", "", max_age=0))

    cookies_out = [v for _, v in set_cookie_headers]
    headers: dict[str, object] = {"Location": post_login_redirect}
    return {"statusCode": 302, "headers": headers, "cookies": cookies_out, "body": ""}


def signed_out(event, context):
    query_params = event.get("queryStringParameters") or {}
    requested_redirect = (query_params.get("redirect") or "").strip()

    headers_in = event.get("headers") or {}
    cookie_header = headers_in.get("cookie") or headers_in.get("Cookie") or ""
    cookie_map = _get_cookie_map(cookie_header)
    last_redirect = cookie_map.get("lr")

    print("requested_redirect: ", requested_redirect)
    print("last_redirect: ", last_redirect)

    # Step 1: client initiates logout with desired redirect
    if requested_redirect:
        if not _is_allowed_redirect(requested_redirect):
            return {"statusCode": 400, "body": "Invalid or missing redirect"}
        if not (COGNITO_DOMAIN and CLIENT_ID and SIGNED_OUT_URI):
            return {"statusCode": 500, "body": "Logout not configured"}

        set_cookie_headers: list[tuple[str, str]] = []
        # store desired redirect temporarily
        set_cookie_headers.append(
            _set_cookie("lr", urllib.parse.quote(requested_redirect), max_age=600)
        )

        cookies_out = [v for _, v in set_cookie_headers]
        cognito_logout = f"{COGNITO_DOMAIN}/logout?{urllib.parse.urlencode({'client_id': CLIENT_ID, 'logout_uri': SIGNED_OUT_URI})}"

        print("cognito_logout: ", cognito_logout)

        return {
            "statusCode": 302,
            "headers": {"Location": cognito_logout},
            "cookies": cookies_out,
            "body": "",
        }

    # Step 2: returned from Cognito; finalize by clearing cookies and redirecting
    target = (
        last_redirect
        if (last_redirect and _is_allowed_redirect(last_redirect))
        else None
    )

    print("target: ", target)

    if not target:
        return {"statusCode": 400, "body": "Missing redirect"}

    set_cookie_headers: list[tuple[str, str]] = []
    for name in ["atk", "idk", "rtk", "cv", "st", "lr"]:
        set_cookie_headers.append(_set_cookie(name, "", max_age=0))

    cookies_out = [v for _, v in set_cookie_headers]
    headers: dict[str, object] = {"Location": target}
    print("headers: ", headers)
    print("cookies_out: ", cookies_out)
    return {"statusCode": 302, "headers": headers, "cookies": cookies_out, "body": ""}
