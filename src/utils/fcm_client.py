"""
Firebase Cloud Messaging HTTP v1 API 클라이언트
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List, Tuple
import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account

# 로거 설정
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# FCM HTTP v1 API 엔드포인트
FCM_API_URL = "https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"

# OAuth 2.0 인증 정보 캐시
_credentials = None
_access_token = None


def get_fcm_credentials():
    """Firebase 서비스 계정 인증 정보를 가져옵니다."""
    global _credentials

    if _credentials is None:
        try:
            # 환경변수에서 서비스 계정 JSON 파일 경로 가져오기
            service_account_path = os.environ.get("FCM_SERVICE_ACCOUNT_PATH")
            if not service_account_path:
                raise ValueError(
                    "FCM_SERVICE_ACCOUNT_PATH environment variable is required"
                )

            # 서비스 계정 JSON 파일 읽기
            with open(service_account_path, "r") as f:
                service_account_info = json.load(f)

            # 서비스 계정 인증 정보 생성
            _credentials = service_account.Credentials.from_service_account_info(
                service_account_info,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )

            logger.info("✅ Firebase 서비스 계정 인증 정보가 로드되었습니다.")

        except Exception as e:
            logger.error(f"❌ Firebase 서비스 계정 인증 정보 로드 실패: {e}")
            raise

    return _credentials


def get_access_token():
    """OAuth 2.0 액세스 토큰을 가져옵니다."""
    global _access_token

    credentials = get_fcm_credentials()

    # 토큰이 없거나 만료된 경우 새로 발급
    if not _access_token or credentials.expired:
        try:
            credentials.refresh(Request())
            _access_token = credentials.token
            logger.info("✅ FCM 액세스 토큰이 갱신되었습니다.")
        except Exception as e:
            logger.error(f"❌ FCM 액세스 토큰 발급 실패: {e}")
            raise

    return _access_token


def send_notification(
    fcm_token: str, title: str, body: str, data: Optional[Dict[str, str]] = None
) -> Tuple[bool, Optional[str]]:
    """
    단일 FCM 토큰으로 알림을 발송합니다.

    Args:
        fcm_token: FCM 토큰
        title: 알림 제목
        body: 알림 내용
        data: 추가 데이터 (옵션)

    Returns:
        (성공 여부, 에러 메시지)
    """
    try:
        project_id = os.environ.get("FCM_PROJECT_ID")
        if not project_id:
            return False, "FCM_PROJECT_ID environment variable is required"

        access_token = get_access_token()

        # FCM HTTP v1 API 메시지 구성
        message = {
            "message": {
                "token": fcm_token,
                "notification": {"title": title, "body": body},
                "data": data or {},
                "webpush": {
                    "fcm_options": {
                        "link": (
                            f"https://yourdomain.com/notice/{data.get('notice_id', '')}"
                            if data
                            else None
                        )
                    }
                },
            }
        }

        # HTTP 요청 헤더
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        # FCM API 호출
        url = FCM_API_URL.format(project_id=project_id)
        response = requests.post(url, headers=headers, json=message)

        if response.status_code == 200:
            logger.info(f"✅ FCM 메시지 발송 성공: {fcm_token[:20]}...")
            return True, None
        else:
            error_data = response.json()
            error_message = error_data.get("error", {}).get("message", "Unknown error")
            logger.error(f"❌ FCM 메시지 발송 실패: {error_message}")
            return False, error_message

    except Exception as e:
        logger.error(f"❌ FCM 메시지 발송 중 오류: {e}")
        return False, str(e)


def send_multicast_notification(
    fcm_tokens: List[str], title: str, body: str, data: Optional[Dict[str, str]] = None
) -> Tuple[int, int, List[str], List[str]]:
    """
    여러 FCM 토큰으로 멀티캐스트 알림을 발송합니다.

    Args:
        fcm_tokens: FCM 토큰 리스트
        title: 알림 제목
        body: 알림 내용
        data: 추가 데이터 (옵션)

    Returns:
        (성공 수, 실패 수, 실패한 토큰 리스트, 무효 토큰 리스트)
    """
    try:
        project_id = os.environ.get("FCM_PROJECT_ID")
        if not project_id:
            logger.error("FCM_PROJECT_ID environment variable is required")
            return 0, len(fcm_tokens), fcm_tokens, []

        access_token = get_access_token()

        success_count = 0
        failure_count = 0
        failed_tokens = []
        invalid_tokens = []

        # HTTP 요청 헤더
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        # 각 토큰에 대해 개별 메시지 전송
        for fcm_token in fcm_tokens:
            try:
                # FCM HTTP v1 API 개별 메시지 구성
                message = {
                    "message": {
                        "token": fcm_token,
                        "notification": {"title": title, "body": body},
                        "data": data or {},
                        "webpush": {
                            "fcm_options": {
                                "link": (
                                    f"https://yourdomain.com/notice/{data.get('notice_id', '')}"
                                    if data
                                    else None
                                )
                            }
                        },
                    }
                }

                # FCM API 호출
                url = FCM_API_URL.format(project_id=project_id)
                response = requests.post(url, headers=headers, json=message)

                if response.status_code == 200:
                    # 성공
                    success_count += 1
                    logger.info(f"✅ FCM 발송 성공: {fcm_token[:20]}...")
                else:
                    # 실패
                    error_data = response.json()
                    error = error_data.get("error", {})
                    error_code = error.get("code")
                    error_message = error.get("message", "Unknown error")

                    failed_tokens.append(fcm_token)

                    # 무효 토큰 판정
                    if _is_invalid_token_error(error_code, error_message):
                        invalid_tokens.append(fcm_token)
                        logger.warning(
                            f"❌ 무효 토큰: {fcm_token[:20]}... - {error_message}"
                        )
                    else:
                        logger.warning(
                            f"❌ FCM 발송 실패: {fcm_token[:20]}... - {error_message}"
                        )

                    failure_count += 1

            except Exception as e:
                logger.error(f"❌ FCM 토큰 {fcm_token[:20]}... 발송 중 오류: {e}")
                failed_tokens.append(fcm_token)
                failure_count += 1

        logger.info(
            f"📊 FCM 멀티캐스트 발송 완료: 성공 {success_count}개, 실패 {failure_count}개, 무효 {len(invalid_tokens)}개"
        )

        return success_count, failure_count, failed_tokens, invalid_tokens

    except Exception as e:
        logger.error(f"❌ FCM 멀티캐스트 발송 중 오류: {e}")
        return 0, len(fcm_tokens), fcm_tokens, []


def _is_invalid_token_error(error_code: str, error_message: str) -> bool:
    """
    에러가 무효 토큰 에러인지 판정합니다.

    Args:
        error_code: FCM API 에러 코드
        error_message: 에러 메시지

    Returns:
        무효 토큰 여부
    """
    # 에러 코드 기반 판정
    invalid_codes = ["INVALID_ARGUMENT", "UNREGISTERED", "SENDER_ID_MISMATCH"]

    if error_code in invalid_codes:
        return True

    # 에러 메시지 기반 판정
    invalid_keywords = [
        "registration-token-not-registered",
        "Invalid registration token",
        "Sender ID mismatch",
        "Unregistered",
    ]

    error_message_lower = error_message.lower()
    for keyword in invalid_keywords:
        if keyword.lower() in error_message_lower:
            return True

    return False
