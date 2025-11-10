import json
import base64
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger()


def decode_jwt_payload(token: str) -> Optional[Dict[str, Any]]:
    """
    JWT 토큰의 payload를 디코딩합니다 (서명 검증 없이).

    Args:
        token: JWT access token

    Returns:
        Dict: JWT payload 또는 None (실패 시)
    """
    try:
        # JWT는 header.payload.signature 형태
        parts = token.split(".")
        if len(parts) != 3:
            logger.error("Invalid JWT format")
            return None

        # payload 부분 디코딩 (base64url)
        payload = parts[1]

        # base64url 패딩 추가
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += "=" * padding

        # base64 디코딩
        decoded_bytes = base64.urlsafe_b64decode(payload)
        payload_dict = json.loads(decoded_bytes.decode("utf-8"))

        return payload_dict

    except Exception as e:
        logger.error(f"Failed to decode JWT payload: {e}")
        return None


def get_cognito_groups(access_token: str) -> List[str]:
    """
    Cognito Access Token에서 사용자가 속한 그룹 목록을 추출합니다.

    Args:
        access_token: Cognito access token

    Returns:
        List[str]: 그룹 이름 목록 (예: ['admin', 'student'])
    """
    try:
        payload = decode_jwt_payload(access_token)
        if not payload:
            return []

        # Cognito에서 그룹 정보는 'cognito:groups' 클레임에 저장됨
        groups = payload.get("cognito:groups", [])

        # 그룹이 문자열 리스트인지 확인
        if isinstance(groups, list):
            return [str(group) for group in groups]
        else:
            return []

    except Exception as e:
        logger.error(f"Failed to extract Cognito groups: {e}")
        return []


def get_user_info(access_token: str) -> Dict[str, Any]:
    """
    Access Token에서 사용자 정보를 추출합니다.

    Args:
        access_token: Cognito access token

    Returns:
        Dict: 사용자 정보 (username, groups, sub 등)
    """
    try:
        payload = decode_jwt_payload(access_token)
        if not payload:
            return {}

        return {
            "sub": payload.get("sub"),  # 사용자 고유 ID
            "username": payload.get("username"),
            "groups": payload.get("cognito:groups", []),
            "token_use": payload.get("token_use"),  # 'access'
            "scope": payload.get("scope", "").split(),
            "client_id": payload.get("client_id"),
            "exp": payload.get("exp"),  # 만료 시간
            "iat": payload.get("iat"),  # 발급 시간
        }

    except Exception as e:
        logger.error(f"Failed to extract user info: {e}")
        return {}


def is_common_user_group(user_info: Dict[str, Any]) -> bool:
    return (
        "common_user" in user_info.get("groups")
        and user_info.get("token_use") == "access"
    ) or ("admin" in user_info.get("groups") and user_info.get("token_use") == "access")


def is_admin_group(user_info: Dict[str, Any]) -> bool:
    return "admin" in user_info.get("groups") and user_info.get("token_use") == "access"


def is_admin_group_from_access_token(access_token: str) -> bool:
    user_info = get_user_info(access_token)
    return "admin" in user_info.get("groups") and user_info.get("token_use") == "access"


def is_common_user_group_from_access_token(access_token: str) -> bool:
    user_info = get_user_info(access_token)
    return (
        "common_user" in user_info.get("groups")
        and user_info.get("token_use") == "access"
    )
