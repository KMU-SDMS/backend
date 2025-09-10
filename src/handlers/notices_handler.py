import logging
import json
from src.services import notices_service
from src.utils import responses
from src.dto import NoticeListDTO, NoticeDTO, NoticeCreateRequestDTO

# 로거 설정
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_all(event, context):
    """
    GET /notices API 요청을 처리하는 핸들러
    """
    logger.info("✅ Processing get_all notices request")

    notices_data, error = notices_service.get_all_notices()

    if error:
        return responses.create_error_response(error, 500)

    # DTO를 사용하여 응답 데이터 변환
    notice_list_dto = NoticeListDTO.from_supabase_data(notices_data)
    return responses.create_success_response(notice_list_dto.to_dict())


def get_one(event, context):
    """
    GET /notices/{id} API 요청을 처리하는 핸들러
    """
    logger.info("✅ Processing get_one notice request")

    path_params = event.get("pathParameters") or {}
    notice_id = path_params.get("id")

    if not notice_id:
        return responses.create_error_response("Notice ID is required.", 400)

    notice_data, error = notices_service.get_notice_by_id(notice_id)

    if error:
        return responses.create_error_response(error, 500)

    # DTO를 사용하여 응답 데이터 변환
    notice_dto = NoticeDTO.from_supabase_data(notice_data)
    return responses.create_success_response(notice_dto.to_dict())


def create(event, context):
    """
    POST /notice API 요청을 처리하는 핸들러
    """
    logger.info("✅ Processing create notice request")

    try:
        # 요청 본문 파싱
        body = json.loads(event.get("body", "{}"))

        # DTO를 사용하여 요청 데이터 검증
        request_dto = NoticeCreateRequestDTO(
            title=body.get("title", ""),
            content=body.get("content", ""),
            is_important=body.get("is_important", False)
        )

        # 요청 데이터 검증
        is_valid, error_message = request_dto.validate()
        if not is_valid:
            return responses.create_error_response(error_message, 400)

        # 공지사항 생성
        notice_data, error = notices_service.create_notice(
            request_dto.title, 
            request_dto.content, 
            request_dto.is_important
        )

        if error:
            return responses.create_error_response(error, 500)

        # DTO를 사용하여 응답 데이터 변환
        notice_dto = NoticeDTO.from_supabase_data(notice_data)
        return responses.create_success_response(notice_dto.to_dict(), 201)

    except json.JSONDecodeError:
        return responses.create_error_response("Invalid JSON format.", 400)
    except Exception as e:
        logger.error(f"❌ 공지사항 생성 실패: {e}")
        return responses.create_error_response("Internal server error.", 500)
