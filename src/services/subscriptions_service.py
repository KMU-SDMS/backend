"""
FCM 구독 관리 서비스
"""

import logging
from typing import Optional, Tuple
from src.utils.supabase_client import get_supabase_client
from src.dto.notification_dto import SubscriptionDTO, SubscriptionCreateRequestDTO

# 로거 설정
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def create_subscription(
    request_dto: SubscriptionCreateRequestDTO,
) -> Tuple[Optional[SubscriptionDTO], Optional[str]]:
    """
    FCM 구독을 생성하거나 업데이트합니다.

    Args:
        request_dto: 구독 생성 요청 DTO

    Returns:
        (SubscriptionDTO, 에러 메시지)
    """
    try:
        supabase = get_supabase_client("notify")
        if not supabase:
            return None, "Supabase client could not be initialized."

        logger.info(
            f"FCM 구독 생성/업데이트: fcm_token={request_dto.fcm_token[:20]}..."
        )

        # 데이터 검증
        is_valid, error_msg = request_dto.validate()
        if not is_valid:
            return None, error_msg

        # UPSERT로 중복 방지 (fcm_token UNIQUE 제약 활용)
        insert_data = {
            "fcm_token": request_dto.fcm_token,
            "student_no": request_dto.student_no,
            "platform": request_dto.platform,
            "is_active": True,
        }

        response = (
            supabase.postgrest.schema("notify")
            .from_("subscriptions")
            .upsert(insert_data, on_conflict="fcm_token", returning="representation")
            .execute()
        )

        if response.data:
            subscription_dto = SubscriptionDTO.from_supabase_data(response.data[0])
            logger.info(
                f"✅ FCM 구독이 성공적으로 생성/업데이트되었습니다: id={subscription_dto.id}"
            )
            return subscription_dto, None
        else:
            logger.error("❌ FCM 구독 생성/업데이트 실패: 응답 데이터가 없습니다.")
            return None, "Failed to create/update subscription"

    except Exception as e:
        logger.error(f"❌ FCM 구독 생성/업데이트 실패: {e}")
        error_message = getattr(e, "message", str(e))
        return None, error_message


def get_subscription_status(fcm_token: str) -> Tuple[Optional[dict], Optional[str]]:
    """
    FCM 구독 상태를 조회합니다.

    Args:
        fcm_token: FCM 토큰

    Returns:
        (구독 상태 딕셔너리, 에러 메시지)
    """
    try:
        supabase = get_supabase_client("notify")
        if not supabase:
            return None, "Supabase client could not be initialized."

        logger.info(f"FCM 구독 상태 조회: fcm_token={fcm_token[:20]}...")

        if not fcm_token or not fcm_token.strip():
            return None, "fcm_token is required"

        response = (
            supabase.postgrest.schema("notify")
            .from_("subscriptions")
            .select(
                "id, fcm_token, student_no, is_active, platform, created_at, updated_at"
            )
            .eq("fcm_token", fcm_token)
            .execute()
        )

        if response.data:
            subscription_data = response.data[0]
            status = {
                "active": subscription_data.get("is_active", False),
                "subscription_id": subscription_data.get("id"),
                "student_no": subscription_data.get("student_no"),
                "platform": subscription_data.get("platform"),
                "created_at": subscription_data.get("created_at"),
                "updated_at": subscription_data.get("updated_at"),
            }
            logger.info(f"✅ FCM 구독 상태 조회 완료: active={status['active']}")
            return status, None
        else:
            logger.info(
                f"❌ FCM 구독을 찾을 수 없습니다: fcm_token={fcm_token[:20]}..."
            )
            return None, "Subscription not found"

    except Exception as e:
        logger.error(f"❌ FCM 구독 상태 조회 실패: {e}")
        error_message = getattr(e, "message", str(e))
        return None, error_message


def deactivate_invalid_subscription(subscription_id: int) -> Tuple[bool, Optional[str]]:
    """
    무효한 구독을 비활성화합니다.

    Args:
        subscription_id: 구독 ID

    Returns:
        (성공 여부, 에러 메시지)
    """
    try:
        supabase = get_supabase_client("notify")
        if not supabase:
            return False, "Supabase client could not be initialized."

        logger.info(f"구독 비활성화: subscription_id={subscription_id}")

        response = (
            supabase.postgrest.schema("notify")
            .from_("subscriptions")
            .update({"is_active": False})
            .eq("id", subscription_id)
            .select()
            .execute()
        )

        if response.data:
            logger.info(f"✅ 구독 {subscription_id}이 성공적으로 비활성화되었습니다.")
            return True, None
        else:
            logger.warning(f"⚠️ 구독 {subscription_id}을 찾을 수 없습니다.")
            return False, "Subscription not found"

    except Exception as e:
        logger.error(f"❌ 구독 비활성화 실패: {e}")
        error_message = getattr(e, "message", str(e))
        return False, error_message
