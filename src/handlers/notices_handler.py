import logging
import json
from src.services import notices_service
from src.utils import responses
from src.dto import (
    NoticeListDTO,
    NoticeDTO,
    NoticeCreateRequestDTO,
    NoticeDeleteRequestDTO,
    NoticeUpdateRequestDTO,
    NoticeListWithPageInfoDTO,
)

# 로거 설정
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_one(event, context):
    """
    GET /notice?id={id} API 요청을 처리하는 핸들러
    """
    logger.info("✅ Processing get_one notice request")

    query_params = event.get("queryStringParameters") or {}
    notice_id = query_params.get("id")

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
            is_important=body.get("is_important", False),
        )

        # 요청 데이터 검증
        is_valid, error_message = request_dto.validate()
        if not is_valid:
            return responses.create_error_response(error_message, 400)

        # 공지사항 생성
        notice_data, error = notices_service.create_notice(
            request_dto.title, request_dto.content, request_dto.is_important
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


def get_paginated(event, context):
    """
    GET /notices?page={page} API 요청을 처리하는 핸들러 (페이지네이션)
    """
    logger.info("✅ Processing get_paginated notices request")

    try:
        # 쿼리 파라미터에서 페이지 번호 추출
        query_params = event.get("queryStringParameters") or {}
        page_str = query_params.get("page", "1")

        # 페이지 번호 검증 및 변환
        try:
            page = int(page_str)
            if page < 1:
                return responses.create_error_response(
                    "Page number must be greater than 0.", 400
                )
        except ValueError:
            return responses.create_error_response("Invalid page number format.", 400)

        # 페이지네이션된 공지사항 조회
        notices_data, total_count, page_size, error = (
            notices_service.get_notices_with_pagination(page=page)
        )

        if error:
            return responses.create_error_response(error, 500)

        # DTO를 사용하여 응답 데이터 변환 (페이지 정보 포함)
        notice_list_with_page_info_dto = NoticeListWithPageInfoDTO.from_supabase_data(
            notices_data, total_count, page, page_size
        )

        return responses.create_success_response(
            notice_list_with_page_info_dto.to_dict()
        )

    except Exception as e:
        logger.error(f"❌ 페이지네이션 공지사항 조회 실패: {e}")
        return responses.create_error_response("Internal server error.", 500)


def delete(event, context):
    """
    DELETE /notices API 요청을 처리하는 핸들러
    """
    logger.info("✅ Processing delete notice request")

    try:
        # 요청 본문 파싱
        body = json.loads(event.get("body", "{}"))

        # DTO를 사용하여 요청 데이터 검증
        request_dto = NoticeDeleteRequestDTO(id=body.get("id"))

        # 요청 데이터 검증
        is_valid, error_message = request_dto.validate()
        if not is_valid:
            return responses.create_error_response(error_message, 400)

        # 공지사항 삭제
        _, error = notices_service.delete_notice_by_id(request_dto.id)

        if error:
            if error == "Notice not found":
                return responses.create_error_response(error, 404)
            return responses.create_error_response(error, 500)

        # 성공 응답 반환
        return responses.create_success_response(
            {"message": "Notice deleted successfully"}
        )

    except json.JSONDecodeError:
        return responses.create_error_response("Invalid JSON format.", 400)
    except Exception as e:
        logger.error(f"❌ 공지사항 삭제 실패: {e}")
        return responses.create_error_response("Internal server error.", 500)


def update(event, context):
    """
    PUT /notice API 요청을 처리하는 핸들러
    """
    logger.info("✅ Processing update notice request")

    try:
        # 요청 본문 파싱
        body = json.loads(event.get("body", "{}"))

        # DTO를 사용하여 요청 데이터 검증
        request_dto = NoticeUpdateRequestDTO(
            id=body.get("id"),
            title=body.get("title", ""),
            content=body.get("content", ""),
            is_important=body.get("is_important", False),
        )

        # 요청 데이터 검증
        is_valid, error_message = request_dto.validate()
        if not is_valid:
            return responses.create_error_response(error_message, 400)

        # 공지사항 수정
        notice_data, error = notices_service.update_notice_by_id(
            request_dto.id,
            request_dto.title,
            request_dto.content,
            request_dto.is_important,
        )

        if error:
            if error == "Notice not found":
                return responses.create_error_response(error, 404)
            return responses.create_error_response(error, 500)

        # DTO를 사용하여 응답 데이터 변환
        notice_dto = NoticeDTO.from_supabase_data(notice_data)
        return responses.create_success_response(notice_dto.to_dict())

    except json.JSONDecodeError:
        return responses.create_error_response("Invalid JSON format.", 400)
    except Exception as e:
        logger.error(f"❌ 공지사항 수정 실패: {e}")
        return responses.create_error_response("Internal server error.", 500)
