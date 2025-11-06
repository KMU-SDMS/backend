"""
FCM 알림 발송 핸들러
"""

import json
import logging
import os
from src.utils.responses import create_success_response, create_error_response
from src.services.notifications_service import (
    send_notification_to_all,
    send_notification_to_student,
)
from src.dto.notification_dto import PersonalNotificationRequestDTO

# 로거 설정
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def send_notification_handler(event, context):
    """
    수동으로 알림을 발송합니다.

    POST /notifications
    Body: {
        "title": "string",
        "content": "string",
        "notice_id": 123
    }
    """
    try:
        logger.info("수동 알림 발송 요청 수신")

        # 1. JSON 파싱
        try:
            body = json.loads(event.get("body", "{}"))
        except json.JSONDecodeError:
            logger.error("❌ 잘못된 JSON 형식")
            return create_error_response("Invalid JSON format.", 400)

        # 2. 필수 필드 검증
        title = body.get("title")
        content = body.get("content")
        notice_id = body.get("notice_id")

        if not title or not content or not notice_id:
            logger.error("❌ 필수 필드 누락: title, content, notice_id")
            return create_error_response(
                "Missing required fields: title, content, notice_id", 400
            )

        # 3. 서비스 호출
        result, error = send_notification_to_all(title, content, notice_id)
        if error:
            logger.error(f"❌ 알림 발송 실패: {error}")
            return create_error_response(error, 500)

        # 4. 성공 응답
        logger.info(
            f"✅ 수동 알림 발송 완료: 성공={result['success_count']}, 실패={result['failure_count']}"
        )
        return create_success_response(result)

    except Exception as e:
        logger.error(f"❌ 수동 알림 발송 핸들러 오류: {e}")
        return create_error_response("Internal server error", 500)


def webhook_handler(event, context):
    """
    Supabase 웹훅을 처리합니다.

    POST /webhook/notify
    Headers: X-Webhook-Secret
    Body: Supabase webhook payload
    """
    try:
        logger.info("Supabase 웹훅 요청 수신")

        # 1. 웹훅 시크릿 검증
        headers = event.get("headers", {})
        webhook_secret = headers.get("x-webhook-secret")
        expected_secret = os.environ.get("WEBHOOK_SECRET")

        if not webhook_secret or webhook_secret != expected_secret:
            logger.error("❌ 잘못된 웹훅 시크릿")
            return create_error_response("Unauthorized", 401)

        # 2. 웹훅 페이로드 파싱
        try:
            payload = json.loads(event.get("body", "{}"))
        except json.JSONDecodeError:
            logger.error("❌ 잘못된 웹훅 JSON 형식")
            return create_error_response("Invalid JSON format.", 400)

        # 3. INSERT 이벤트 확인
        event_type = payload.get("type")
        if event_type != "INSERT":
            logger.info(f"⚠️ INSERT 이벤트가 아님: {event_type}")
            return create_success_response({"message": "Event ignored"})

        # 4. 공지사항 데이터 추출
        record = payload.get("record", {})
        notice_id = record.get("id")
        title = record.get("title")
        content = record.get("content")

        if not notice_id or not title or not content:
            logger.error("❌ 공지사항 데이터 누락")
            return create_error_response("Missing notice data", 400)

        # 5. 알림 발송
        logger.info(f"📢 새 공지사항 알림 발송: id={notice_id}, title={title}")
        result, error = send_notification_to_all(title, content, notice_id)
        if error:
            logger.error(f"❌ 웹훅 알림 발송 실패: {error}")
            return create_error_response(error, 500)

        # 6. 성공 응답
        logger.info(
            f"✅ 웹훅 알림 발송 완료: 성공={result['success_count']}, 실패={result['failure_count']}"
        )
        return create_success_response(result)

    except Exception as e:
        logger.error(f"❌ 웹훅 핸들러 오류: {e}")
        return create_error_response("Internal server error", 500)


def send_individual_notification_handler(event, context):
    """
    특정 학생에게 개인 알림을 발송합니다.

    POST /notifications/individual
    Body: {
        "student_no": "string",
        "title": "string",
        "content": "string"
    }
    """
    try:
        logger.info("개인 알림 발송 요청 수신")

        # 1. JSON 파싱
        try:
            body = json.loads(event.get("body", "{}"))
        except json.JSONDecodeError:
            logger.error("❌ 잘못된 JSON 형식")
            return create_error_response("Invalid JSON format.", 400)

        # 2. DTO 생성 및 검증
        try:
            request_dto = PersonalNotificationRequestDTO(
                student_no=body.get("student_no"),
                title=body.get("title"),
                content=body.get("content"),
            )
        except Exception as e:
            logger.error(f"❌ DTO 생성 실패: {e}")
            return create_error_response(f"Invalid request data: {str(e)}", 400)

        # 3. 데이터 검증
        is_valid, error_msg = request_dto.validate()
        if not is_valid:
            logger.error(f"❌ 데이터 검증 실패: {error_msg}")
            return create_error_response(error_msg, 400)

        # 4. 서비스 호출
        result, error = send_notification_to_student(
            request_dto.student_no, request_dto.title, request_dto.content
        )
        if error:
            logger.error(f"❌ 개인 알림 발송 실패: {error}")
            return create_error_response(error, 500)

        # 5. 성공 응답
        logger.info(
            f"✅ 개인 알림 발송 완료: student_no={request_dto.student_no}, 성공={result['success_count']}, 실패={result['failure_count']}"
        )
        return create_success_response(result)

    except Exception as e:
        logger.error(f"❌ 개인 알림 발송 핸들러 오류: {e}")
        return create_error_response("Internal server error", 500)
