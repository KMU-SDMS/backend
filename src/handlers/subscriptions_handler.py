"""
FCM 구독 관리 핸들러
"""

import json
import logging
from src.utils.responses import create_success_response, create_error_response
from src.services.subscriptions_service import (
    create_subscription,
    get_subscription_status,
    update_all_subscriptions_active_by_student_no,
)
from src.dto.notification_dto import (
    SubscriptionCreateRequestDTO,
    SubscriptionUpdateRequestDTO,
    SubscriptionUpdateResponseDTO,
)

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

        # Cognito username을 대문자로 변환 (DB의 studentNo와 일치시키기 위해)
        student_no = username.upper()

        logger.info(f"📱 사용자 {student_no}의 FCM 구독 생성 요청")

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
        subscription_dto, error = create_subscription(request_dto, student_no)
        if error:
            logger.error(f"❌ 구독 생성 실패: {error}")
            return create_error_response(error, 500)

        # 6. 성공 응답
        logger.info(
            f"✅ FCM 구독 생성 완료: id={subscription_dto.id}, student_no={student_no}"
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


def patch_subscription_handler(event, context):
    """
    FCM 구독의 활성 상태를 변경합니다.

    PATCH /subscriptions
    Body: {
        "active": true 또는 false
    }
    세션의 학번으로 모든 구독의 활성 상태를 변경합니다.
    """
    try:
        logger.info("FCM 구독 상태 변경 요청 수신")

        # 1. 세션에서 사용자 정보 추출
        user_info = event.get("user_info", {})
        username = user_info.get("username")

        if not username:
            logger.error("❌ 사용자 정보를 찾을 수 없습니다 (인증 필요)")
            return create_error_response(
                "Unauthorized: user information not found", 401
            )

        # Cognito username을 대문자로 변환 (DB의 studentNo와 일치시키기 위해)
        student_no = username.upper()

        # 2. JSON 파싱
        try:
            body = json.loads(event.get("body", "{}"))
        except json.JSONDecodeError:
            logger.error("❌ 잘못된 JSON 형식")
            return create_error_response("Invalid JSON format.", 400)

        # 3. active 필드 확인
        if "active" not in body:
            logger.error("❌ active 필드가 누락되었습니다")
            return create_error_response("active field is required", 400)

        # 4. DTO 생성 및 검증
        try:
            request_dto = SubscriptionUpdateRequestDTO(
                active=body.get("active"),
            )
        except Exception as e:
            logger.error(f"❌ DTO 생성 실패: {e}")
            return create_error_response(f"Invalid request data: {str(e)}", 400)

        # 5. 데이터 검증
        is_valid, error_msg = request_dto.validate()
        if not is_valid:
            logger.error(f"❌ 데이터 검증 실패: {error_msg}")
            return create_error_response(error_msg, 400)

        action = "활성화" if request_dto.active else "비활성화"
        logger.info(f"📱 사용자 {student_no}의 모든 FCM 구독 {action} 요청")

        # 6. 서비스 호출
        updated_count, error = update_all_subscriptions_active_by_student_no(
            student_no, request_dto.active
        )

        if error:
            logger.error(f"❌ 구독 상태 변경 실패: {error}")
            return create_error_response(error, 500)

        # 7. DTO로 응답 생성
        response_dto = SubscriptionUpdateResponseDTO(
            message=f"Subscription(s) {'activated' if request_dto.active else 'deactivated'} successfully",
            updated_count=updated_count,
            student_no=student_no,
            active=request_dto.active,
        )

        # 8. 성공 응답
        logger.info(
            f"✅ FCM 구독 상태 변경 완료: student_no={student_no}, updated_count={updated_count}, active={request_dto.active}"
        )
        return create_success_response(response_dto.to_dict())

    except Exception as e:
        logger.error(f"❌ 구독 상태 변경 핸들러 오류: {e}")
        return create_error_response("Internal server error", 500)
