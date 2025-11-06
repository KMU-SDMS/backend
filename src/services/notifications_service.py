"""
FCM 알림 발송 서비스
"""

import logging
from typing import List, Tuple, Optional
from src.utils.supabase_client import get_supabase_client
from src.utils.fcm_client import send_multicast_notification
from src.dto.notification_dto import (
    SubscriptionDTO,
    NotificationLogDTO,
    PersonalNotificationDTO,
)

# 로거 설정
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_active_subscriptions() -> Tuple[List[SubscriptionDTO], Optional[str]]:
    """
    활성화된 모든 FCM 구독을 조회합니다.

    Returns:
        (SubscriptionDTO 리스트, 에러 메시지)
    """
    try:
        supabase = get_supabase_client("notify")
        if not supabase:
            return [], "Supabase client could not be initialized."

        logger.info("활성화된 FCM 구독 조회 중...")

        response = (
            supabase.postgrest.schema("notify")
            .from_("subscriptions")
            .select(
                "id, fcm_token, student_no, is_active, platform, created_at, updated_at"
            )
            .eq("is_active", True)
            .execute()
        )

        if response.data:
            subscriptions = [
                SubscriptionDTO.from_supabase_data(sub_data)
                for sub_data in response.data
            ]
            logger.info(f"✅ 활성화된 FCM 구독 {len(subscriptions)}개 조회 완료")
            return subscriptions, None
        else:
            logger.info("⚠️ 활성화된 FCM 구독이 없습니다.")
            return [], None

    except Exception as e:
        logger.error(f"❌ 활성화된 FCM 구독 조회 실패: {e}")
        error_message = getattr(e, "message", str(e))
        return [], error_message


def send_notification_to_all(
    title: str, content: str, notice_id: int
) -> Tuple[dict, Optional[str]]:
    """
    모든 활성화된 구독자에게 알림을 발송합니다.

    Args:
        title: 알림 제목
        content: 알림 내용
        notice_id: 공지사항 ID

    Returns:
        (발송 결과 딕셔너리, 에러 메시지)
    """
    try:
        logger.info(f"전체 알림 발송 시작: title={title}, notice_id={notice_id}")

        # 1. 활성화된 구독 조회
        subscriptions, error = get_active_subscriptions()
        if error:
            return {"success": False, "error": error}, error

        if not subscriptions:
            logger.info("⚠️ 발송할 활성 구독이 없습니다.")
            return {
                "success": True,
                "total_subscriptions": 0,
                "success_count": 0,
                "failure_count": 0,
                "invalid_tokens": [],
                "failed_tokens": [],
            }, None

        # 2. FCM 토큰 추출
        fcm_tokens = [sub.fcm_token for sub in subscriptions]
        logger.info(f"📤 {len(fcm_tokens)}개 토큰으로 알림 발송 시작")

        # 3. FCM 멀티캐스트 발송
        data = {"notice_id": str(notice_id)}
        success_count, failure_count, failed_tokens, invalid_tokens = (
            send_multicast_notification(fcm_tokens, title, content, data)
        )

        # 4. 무효 토큰 구독 비활성화 및 로그 기록
        if invalid_tokens:
            logger.info(f"🔄 무효 토큰 {len(invalid_tokens)}개 구독 비활성화 시작")
            from src.services.subscriptions_service import (
                deactivate_invalid_subscription,
            )

            for subscription in subscriptions:
                if subscription.fcm_token in invalid_tokens:
                    deactivate_success, deactivate_error = (
                        deactivate_invalid_subscription(subscription.id)
                    )
                    if deactivate_success:
                        logger.info(
                            f"✅ 구독 {subscription.id} 비활성화 완료 (무효 토큰)"
                        )
                    else:
                        logger.warning(
                            f"⚠️ 구독 {subscription.id} 비활성화 실패: {deactivate_error}"
                        )

        # 5. 각 구독별 발송 결과 로그 기록
        logger.info("📝 알림 발송 결과 로그 기록 시작")
        for subscription in subscriptions:
            if subscription.fcm_token in invalid_tokens:
                # 무효 토큰
                log_success, log_error = log_notification_result(
                    notice_id, subscription.id, "invalid_token", "Invalid FCM token"
                )
            elif subscription.fcm_token in failed_tokens:
                # 발송 실패
                log_success, log_error = log_notification_result(
                    notice_id, subscription.id, "failed", "FCM send failed"
                )
            else:
                # 발송 성공
                log_success, log_error = log_notification_result(
                    notice_id, subscription.id, "success"
                )

            if log_success:
                logger.info(f"✅ 구독 {subscription.id} 로그 기록 완료")
            else:
                logger.warning(f"⚠️ 구독 {subscription.id} 로그 기록 실패: {log_error}")

        # 6. 결과 반환
        result = {
            "success": True,
            "total_subscriptions": len(subscriptions),
            "success_count": success_count,
            "failure_count": failure_count,
            "invalid_tokens": invalid_tokens,
            "failed_tokens": failed_tokens,
        }

        logger.info(
            f"✅ 전체 알림 발송 완료: 성공={success_count}, 실패={failure_count}, 무효={len(invalid_tokens)}"
        )

        return result, None

    except Exception as e:
        logger.error(f"❌ 전체 알림 발송 실패: {e}")
        error_message = getattr(e, "message", str(e))
        return {"success": False, "error": error_message}, error_message


def log_notification_result(
    notice_id: int,
    subscription_id: int,
    status: str,
    error_message: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    """
    알림 발송 결과를 로그에 기록합니다.

    Args:
        notice_id: 공지사항 ID
        subscription_id: 구독 ID
        status: 발송 상태 (success, failed, invalid_token)
        error_message: 에러 메시지 (실패 시)

    Returns:
        (성공 여부, 에러 메시지)
    """
    try:
        supabase = get_supabase_client("notify")
        if not supabase:
            return False, "Supabase client could not be initialized."

        logger.info(
            f"알림 발송 결과 로깅: notice_id={notice_id}, subscription_id={subscription_id}, status={status}"
        )

        insert_data = {
            "notice_id": notice_id,
            "subscription_id": subscription_id,
            "status": status,
            "error_message": error_message,
        }

        response = (
            supabase.postgrest.schema("notify")
            .from_("notice_logs")
            .insert(insert_data)
            .execute()
        )

        if response.data:
            logger.info(f"✅ 알림 발송 결과 로깅 완료: id={response.data[0].get('id')}")
            return True, None
        else:
            logger.error("❌ 알림 발송 결과 로깅 실패: 응답 데이터가 없습니다.")
            return False, "Failed to log notification result"

    except Exception as e:
        logger.error(f"❌ 알림 발송 결과 로깅 실패: {e}")
        error_message = getattr(e, "message", str(e))
        return False, error_message


def send_notification_to_student(
    student_no: str, title: str, content: str
) -> Tuple[Optional[dict], Optional[str]]:
    """
    특정 학생에게 개인 알림을 발송합니다.

    Args:
        student_no: 학생 번호
        title: 알림 제목
        content: 알림 내용

    Returns:
        (발송 결과 딕셔너리, 에러 메시지)
    """
    try:
        supabase = get_supabase_client("notify")
        if not supabase:
            return None, "Supabase client could not be initialized."

        logger.info(f"개인 알림 발송 시작: student_no={student_no}, title={title}")

        # 1. 개인 알림 원본 데이터를 personal_notifications 테이블에 저장
        insert_data = {
            "student_no": student_no,
            "title": title,
            "content": content,
            # sent_by는 NULL (나중에 인증 시스템 개선 시 추가)
        }

        response = (
            supabase.postgrest.schema("notify")
            .from_("personal_notifications")
            .insert(insert_data)
            .execute()
        )

        if not response.data:
            logger.error("❌ 개인 알림 데이터 저장 실패: 응답 데이터가 없습니다.")
            return None, "Failed to save personal notification"

        personal_notification = PersonalNotificationDTO.from_supabase_data(
            response.data[0]
        )
        personal_notification_id = personal_notification.id

        logger.info(
            f"✅ 개인 알림 데이터 저장 완료: personal_notification_id={personal_notification_id}"
        )

        # 2. 해당 학생의 모든 활성 구독을 조회
        subscriptions_response = (
            supabase.postgrest.schema("notify")
            .from_("subscriptions")
            .select(
                "id, fcm_token, student_no, is_active, platform, created_at, updated_at"
            )
            .eq("student_no", student_no)
            .eq("is_active", True)
            .execute()
        )

        if not subscriptions_response.data:
            logger.info(f"⚠️ 학생 {student_no}의 활성 구독이 없습니다.")
            return {
                "success": True,
                "personal_notification_id": personal_notification_id,
                "student_no": student_no,
                "total_devices": 0,
                "success_count": 0,
                "failure_count": 0,
                "invalid_tokens": [],
                "failed_tokens": [],
                "message": "No active subscriptions found for this student",
            }, None

        subscriptions = [
            SubscriptionDTO.from_supabase_data(sub_data)
            for sub_data in subscriptions_response.data
        ]

        logger.info(f"📱 학생 {student_no}의 활성 구독 {len(subscriptions)}개 발견")

        # 3. FCM 토큰 추출
        fcm_tokens = [sub.fcm_token for sub in subscriptions]

        # 4. FCM 멀티캐스트 발송
        data = {"personal_notification_id": str(personal_notification_id)}
        success_count, failure_count, failed_tokens, invalid_tokens = (
            send_multicast_notification(fcm_tokens, title, content, data)
        )

        # 5. 무효 토큰 구독 비활성화
        if invalid_tokens:
            logger.info(f"🔄 무효 토큰 {len(invalid_tokens)}개 구독 비활성화 시작")
            from src.services.subscriptions_service import (
                deactivate_invalid_subscription,
            )

            for subscription in subscriptions:
                if subscription.fcm_token in invalid_tokens:
                    deactivate_success, deactivate_error = (
                        deactivate_invalid_subscription(subscription.id)
                    )
                    if deactivate_success:
                        logger.info(
                            f"✅ 구독 {subscription.id} 비활성화 완료 (무효 토큰)"
                        )
                    else:
                        logger.warning(
                            f"⚠️ 구독 {subscription.id} 비활성화 실패: {deactivate_error}"
                        )

        # 6. 각 구독별 발송 결과를 personal_notification_logs에 기록
        logger.info("📝 개인 알림 발송 결과 로그 기록 시작")
        for subscription in subscriptions:
            if subscription.fcm_token in invalid_tokens:
                # 무효 토큰
                log_success, log_error = log_personal_notification_result(
                    personal_notification_id,
                    subscription.id,
                    "invalid_token",
                    "Invalid FCM token",
                )
            elif subscription.fcm_token in failed_tokens:
                # 발송 실패
                log_success, log_error = log_personal_notification_result(
                    personal_notification_id,
                    subscription.id,
                    "failed",
                    "FCM send failed",
                )
            else:
                # 발송 성공
                log_success, log_error = log_personal_notification_result(
                    personal_notification_id, subscription.id, "success"
                )

            if log_success:
                logger.info(f"✅ 구독 {subscription.id} 로그 기록 완료")
            else:
                logger.warning(f"⚠️ 구독 {subscription.id} 로그 기록 실패: {log_error}")

        # 7. 결과 반환
        result = {
            "success": True,
            "personal_notification_id": personal_notification_id,
            "student_no": student_no,
            "total_devices": len(subscriptions),
            "success_count": success_count,
            "failure_count": failure_count,
            "invalid_tokens": invalid_tokens,
            "failed_tokens": failed_tokens,
        }

        logger.info(
            f"✅ 개인 알림 발송 완료: student_no={student_no}, 성공={success_count}, 실패={failure_count}, 무효={len(invalid_tokens)}"
        )

        return result, None

    except Exception as e:
        logger.error(f"❌ 개인 알림 발송 실패: {e}")
        error_message = getattr(e, "message", str(e))
        return None, error_message


def log_personal_notification_result(
    personal_notification_id: int,
    subscription_id: int,
    status: str,
    error_message: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    """
    개인 알림 발송 결과를 로그에 기록합니다.

    Args:
        personal_notification_id: 개인 알림 ID
        subscription_id: 구독 ID
        status: 발송 상태 (success, failed, invalid_token)
        error_message: 에러 메시지 (실패 시)

    Returns:
        (성공 여부, 에러 메시지)
    """
    try:
        supabase = get_supabase_client("notify")
        if not supabase:
            return False, "Supabase client could not be initialized."

        logger.info(
            f"개인 알림 발송 결과 로깅: personal_notification_id={personal_notification_id}, subscription_id={subscription_id}, status={status}"
        )

        insert_data = {
            "personal_notification_id": personal_notification_id,
            "subscription_id": subscription_id,
            "status": status,
            "error_message": error_message,
        }

        response = (
            supabase.postgrest.schema("notify")
            .from_("personal_notification_logs")
            .insert(insert_data)
            .execute()
        )

        if response.data:
            logger.info(
                f"✅ 개인 알림 발송 결과 로깅 완료: id={response.data[0].get('id')}"
            )
            return True, None
        else:
            logger.error("❌ 개인 알림 발송 결과 로깅 실패: 응답 데이터가 없습니다.")
            return False, "Failed to log personal notification result"

    except Exception as e:
        logger.error(f"❌ 개인 알림 발송 결과 로깅 실패: {e}")
        error_message = getattr(e, "message", str(e))
        return False, error_message
