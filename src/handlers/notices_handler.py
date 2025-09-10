import logging
import json
from src.services import notices_service
from src.utils import responses

# 로거 설정
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_all(event, context):
    """
    GET /notices API 요청을 처리하는 핸들러
    """
    logger.info("✅ Processing get_all notices request")

    notices, error = notices_service.get_all_notices()

    if error:
        return responses.create_error_response(error, 500)

    return responses.create_success_response(notices)


def get_one(event, context):
    """
    GET /notices/{id} API 요청을 처리하는 핸들러
    """
    logger.info("✅ Processing get_one notice request")

    path_params = event.get("pathParameters") or {}
    notice_id = path_params.get("id")

    if not notice_id:
        return responses.create_error_response("Notice ID is required.", 400)

    notice, error = notices_service.get_notice_by_id(notice_id)

    if error:
        return responses.create_error_response(error, 500)

    return responses.create_success_response(notice)


def create(event, context):
    """
    POST /notice API 요청을 처리하는 핸들러
    """
    logger.info("✅ Processing create notice request")

    try:
        # 요청 본문 파싱
        body = json.loads(event.get("body", "{}"))

        # 필수 필드 검증
        title = body.get("title")
        content = body.get("content")
        is_important = body.get("is_important", False)

        if not title or not content:
            return responses.create_error_response(
                "Title and content are required.", 400
            )

        # 공지사항 생성
        notice, error = notices_service.create_notice(title, content, is_important)

        if error:
            return responses.create_error_response(error, 500)

        return responses.create_success_response(notice, 201)

    except json.JSONDecodeError:
        return responses.create_error_response("Invalid JSON format.", 400)
    except Exception as e:
        logger.error(f"❌ 공지사항 생성 실패: {e}")
        return responses.create_error_response("Internal server error.", 500)
