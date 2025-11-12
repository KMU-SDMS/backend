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
    NoticeFilterRequestDTO,
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
            status=body.get("status", "PUBLISHED"),
        )

        # 요청 데이터 검증
        is_valid, error_message = request_dto.validate()
        if not is_valid:
            return responses.create_error_response(error_message, 400)

        # 공지사항 생성
        notice_data, error = notices_service.create_notice(
            request_dto.title,
            request_dto.content,
            request_dto.is_important,
            request_dto.status,
        )

        if error:
            # 고정공지 개수 제한 에러는 400 Bad Request
            if "Maximum 10 pinned notices" in error:
                return responses.create_error_response(error, 400)
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
            status=body.get("status"),
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
            request_dto.status,
        )

        if error:
            if error == "Notice not found":
                return responses.create_error_response(error, 404)
            # 고정공지 개수 제한 에러는 400 Bad Request
            if "Maximum 10 pinned notices" in error:
                return responses.create_error_response(error, 400)
            return responses.create_error_response(error, 500)

        # DTO를 사용하여 응답 데이터 변환
        notice_dto = NoticeDTO.from_supabase_data(notice_data)
        return responses.create_success_response(notice_dto.to_dict())

    except json.JSONDecodeError:
        return responses.create_error_response("Invalid JSON format.", 400)
    except Exception as e:
        logger.error(f"❌ 공지사항 수정 실패: {e}")
        return responses.create_error_response("Internal server error.", 500)


def filter(event, context):
    """
    GET /notices/filter API 요청을 처리하는 핸들러 (필터링 및 정렬)
    """
    logger.info("✅ Processing filter notices request")

    try:
        # 쿼리 파라미터 추출
        query_params = event.get("queryStringParameters") or {}
        multi_params = event.get("multiValueQueryStringParameters") or {}

        # 디버깅용 로깅
        logger.info(f"queryStringParameters: {query_params}")
        logger.info(f"multiValueQueryStringParameters: {multi_params}")

        # status 파라미터 추출 (여러 개 선택 가능)
        status = None

        # 1순위: multiValueQueryStringParameters 확인 (HTTP API v2에서는 없을 수 있음)
        if multi_params and "status" in multi_params:
            status_list = multi_params.get("status", [])
            if isinstance(status_list, list) and len(status_list) > 0:
                status = status_list
                logger.info(f"Status from multiValueQueryStringParameters: {status}")

        # 2순위: queryStringParameters에서 리스트인 경우
        if status is None and "status" in query_params:
            status_value = query_params.get("status")
            if isinstance(status_value, list):
                status = status_value
                logger.info(f"Status from queryStringParameters (list): {status}")
            elif isinstance(status_value, str):
                # 쉼표로 구분된 문자열 처리 (예: "DRAFT,SCHEDULED")
                if "," in status_value:
                    status = [s.strip() for s in status_value.split(",") if s.strip()]
                    logger.info(
                        f"Status from queryStringParameters (comma-separated): {status}"
                    )
                else:
                    status = [status_value]
                    logger.info(f"Status from queryStringParameters (single): {status}")

        # 3순위: rawQueryString에서 직접 파싱 (fallback)
        if status is None:
            raw_query = event.get("rawQueryString", "")
            if raw_query and "status=" in raw_query:
                # rawQueryString에서 status 파라미터 추출
                import urllib.parse

                parsed = urllib.parse.parse_qs(raw_query)
                if "status" in parsed:
                    status = parsed["status"]
                    logger.info(f"Status from rawQueryString: {status}")

        # 빈 리스트나 빈 문자열 제거
        if status:
            status = [s for s in status if s and s.strip()]
            if len(status) == 0:
                status = None

        # is_important 파싱 (문자열 "true"/"false"를 boolean으로 변환)
        is_important = None
        if "is_important" in query_params:
            is_important_str = query_params.get("is_important")
            if is_important_str.lower() == "true":
                is_important = True
            elif is_important_str.lower() == "false":
                is_important = False

        # 날짜 파라미터 추출
        start_date = query_params.get("start_date")
        end_date = query_params.get("end_date")

        # 단일 날짜 파라미터 추출 및 변환
        year = None
        month = None
        day = None
        if "year" in query_params:
            try:
                year = int(query_params.get("year"))
            except (ValueError, TypeError):
                return responses.create_error_response("Invalid year format.", 400)
        if "month" in query_params:
            try:
                month = int(query_params.get("month"))
            except (ValueError, TypeError):
                return responses.create_error_response("Invalid month format.", 400)
        if "day" in query_params:
            try:
                day = int(query_params.get("day"))
            except (ValueError, TypeError):
                return responses.create_error_response("Invalid day format.", 400)

        # 정렬 파라미터 (기본값: latest)
        sort = query_params.get("sort", "latest")

        # 페이지 파라미터 추출 및 변환
        page_str = query_params.get("page", "1")
        try:
            page = int(page_str)
            if page < 1:
                return responses.create_error_response(
                    "Page number must be greater than 0.", 400
                )
        except ValueError:
            return responses.create_error_response("Invalid page number format.", 400)

        # 검색어 파라미터 추출
        search_term = query_params.get("search")

        # DTO 생성 및 검증
        filter_dto = NoticeFilterRequestDTO(
            status=status,
            is_important=is_important,
            start_date=start_date,
            end_date=end_date,
            year=year,
            month=month,
            day=day,
            sort=sort,
            page=page,
            search=search_term,
        )

        is_valid, error_message = filter_dto.validate()
        if not is_valid:
            return responses.create_error_response(error_message, 400)

        # 필터링된 공지사항 조회
        notices_data, total_count, page_size, error = (
            notices_service.get_notices_with_filters(
                status=filter_dto.status,
                is_important=filter_dto.is_important,
                start_date=filter_dto.start_date,
                end_date=filter_dto.end_date,
                year=filter_dto.year,
                month=filter_dto.month,
                day=filter_dto.day,
                sort=filter_dto.sort,
                page=filter_dto.page,
                search=filter_dto.search,
            )
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
        logger.error(f"❌ 필터링 공지사항 조회 실패: {e}")
        return responses.create_error_response("Internal server error.", 500)
