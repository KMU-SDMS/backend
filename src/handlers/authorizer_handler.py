import os
import json
import urllib.request
import urllib.error
import urllib.parse


COGNITO_DOMAIN = os.environ.get("COGNITO_DOMAIN", "").rstrip("/")


def _parse_cookies(header_value: str) -> dict[str, str]:
    if not header_value:
        return {}
    result: dict[str, str] = {}
    for part in header_value.split(";"):
        k, _, v = part.strip().partition("=")
        if k:
            result[k] = urllib.parse.unquote(v)
    return result


def cookie_authorizer(event, context):
    headers = event.get("headers") or {}
    cookie_header = headers.get("cookie") or headers.get("Cookie") or ""

    cookies_map = _parse_cookies(cookie_header)
    access_token = cookies_map.get("atk")

    if not access_token or not COGNITO_DOMAIN:
        return {"isAuthorized": False}

    userinfo_url = f"{COGNITO_DOMAIN}/oauth2/userInfo"
    req = urllib.request.Request(
        userinfo_url,
        headers={"Authorization": f"Bearer {access_token}"},
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status != 200:
                return {"isAuthorized": False}
            body = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError):
        return {"isAuthorized": False}

    # Extract standard fields if available
    sub = body.get("sub")
    email = body.get("email")
    username = body.get("username") or body.get("cognito:username")

    ctx = {}
    if sub is not None:
        ctx["sub"] = sub
    if email is not None:
        ctx["email"] = email
    if username is not None:
        ctx["username"] = username

    return {"isAuthorized": True, "context": ctx}
