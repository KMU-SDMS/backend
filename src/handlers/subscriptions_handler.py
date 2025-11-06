"""
FCM 구독 관리 핸들러
"""

import json
import logging
from src.utils.responses import create_success_response, create_error_response
from src.services.subscriptions_service import (
    create_subscription,
    get_subscription_status,
)
from src.dto.notification_dto import SubscriptionCreateRequestDTO

# 로거 설정
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def create_subscription_handler(event, context):
    """
    FCM 구독을 생성합니다.

    POST /subscriptions
    Body: {
        "fcm_token": "string",
        "platform": "web"
    }
    """
    try:
        logger.info("FCM 구독 생성 요청 수신")

        # 1. 세션에서 사용자 정보 추출
        user_info = event.get("user_info", {})
        username = user_info.get("username")

        if not username:
            logger.error("❌ 사용자 정보를 찾을 수 없습니다 (인증 필요)")
            return create_error_response(
                "Unauthorized: user information not found", 401
            )

        logger.info(f"📱 사용자 {username}의 FCM 구독 생성 요청")

        # 2. JSON 파싱
        try:
            body = json.loads(event.get("body", "{}"))
        except json.JSONDecodeError:
            logger.error("❌ 잘못된 JSON 형식")
            return create_error_response("Invalid JSON format.", 400)

        # 3. DTO 생성 (student_no는 세션에서 추출한 username 사용)
        try:
            request_dto = SubscriptionCreateRequestDTO(
                fcm_token=body.get("fcm_token"),
                platform=body.get("platform", "web"),
            )
        except Exception as e:
            logger.error(f"❌ DTO 생성 실패: {e}")
            return create_error_response(f"Invalid request data: {str(e)}", 400)

        # 4. 데이터 검증
        is_valid, error_msg = request_dto.validate()
        if not is_valid:
            logger.error(f"❌ 데이터 검증 실패: {error_msg}")
            return create_error_response(error_msg, 400)

        # 5. 서비스 호출 (student_no를 별도로 전달)
        subscription_dto, error = create_subscription(request_dto, username)
        if error:
            logger.error(f"❌ 구독 생성 실패: {error}")
            return create_error_response(error, 500)

        # 6. 성공 응답
        logger.info(
            f"✅ FCM 구독 생성 완료: id={subscription_dto.id}, student_no={username}"
        )
        return create_success_response(subscription_dto.to_dict())

    except Exception as e:
        logger.error(f"❌ 구독 생성 핸들러 오류: {e}")
        return create_error_response("Internal server error", 500)


def get_subscription_status_handler(event, context):
    """
    FCM 구독 상태를 조회합니다.

    GET /subscriptions/status?fcm_token=xxx
    """
    try:
        logger.info("FCM 구독 상태 조회 요청 수신")

        # 1. 쿼리 파라미터 추출
        query_params = event.get("queryStringParameters") or {}
        fcm_token = query_params.get("fcm_token")

        if not fcm_token:
            logger.error("❌ fcm_token 파라미터 누락")
            return create_error_response("fcm_token parameter is required", 400)

        # 2. 서비스 호출
        status_data, error = get_subscription_status(fcm_token)
        if error:
            if "not found" in error.lower():
                logger.info(f"⚠️ 구독을 찾을 수 없음: fcm_token={fcm_token[:20]}...")
                return create_error_response("Subscription not found", 404)
            else:
                logger.error(f"❌ 구독 상태 조회 실패: {error}")
                return create_error_response(error, 500)

        # 3. 성공 응답
        logger.info(f"✅ FCM 구독 상태 조회 완료: active={status_data['active']}")
        return create_success_response(status_data)

    except Exception as e:
        logger.error(f"❌ 구독 상태 조회 핸들러 오류: {e}")
        return create_error_response("Internal server error", 500)
