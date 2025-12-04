import logging
import json
import re
from src.services import calendar_service
from src.utils import responses
from src.dto import (
    CalendarListDTO,
    CalendarDTO,
    CalendarCreateRequestDTO,
    CalendarUpdateRequestDTO,
)

# 로거 설정
logger = logging.getLogger(__name__)


def get_all(event, context):
    """
    GET /calendar API 요청을 처리하는 핸들러
    query parameter:
    - date(선택): YYYY-MM-DD 형식으로 특정 날짜 조회
    - year, month(선택): 특정 연도-월의 모든 일정 조회 (year와 month는 함께 제공되어야 함)
    """
    logger.info("✅ Processing get_all calendar request")

    try:
        # 쿼리 파라미터 추출
        query_params = event.get("queryStringParameters") or {}
        date = query_params.get("date")
        year_str = query_params.get("year")
        month_str = query_params.get("month")

        # date 파라미터가 있으면 기존 로직 사용 (우선순위 1)
        if date:
            date_pattern = r"^\d{4}-\d{2}-\d{2}$"
            if not re.match(date_pattern, date):
                return responses.create_error_response(
                    "Date must be in YYYY-MM-DD format.", 400
                )

            # 서비스 호출 (date만 사용)
            calendar_data, error = calendar_service.get_calendar(date=date)
            if error:
                return responses.create_error_response(error, 500)

            # DTO를 사용하여 응답 데이터 변환
            calendar_list_dto = CalendarListDTO.from_supabase_data(calendar_data)
            return responses.create_success_response(calendar_list_dto.to_dict())

        # year와 month 파라미터 처리 (우선순위 2)
        year = None
        month = None

        if year_str or month_str:
            # year와 month는 함께 제공되어야 함
            if not year_str or not month_str:
                return responses.create_error_response(
                    "Both year and month must be provided together.", 400
                )

            # year 검증
            try:
                year = int(year_str)
                if year <= 0:
                    return responses.create_error_response(
                        "Year must be a positive integer.", 400
                    )
            except (ValueError, TypeError):
                return responses.create_error_response("Invalid year format.", 400)

            # month 검증
            try:
                month = int(month_str)
                if not (1 <= month <= 12):
                    return responses.create_error_response(
                        "Month must be between 1 and 12.", 400
                    )
            except (ValueError, TypeError):
                return responses.create_error_response("Invalid month format.", 400)

        # 서비스 호출 (year, month 또는 둘 다 None)
        calendar_data, error = calendar_service.get_calendar(
            date=None, year=year, month=month
        )

        if error:
            return responses.create_error_response(error, 500)

        # DTO를 사용하여 응답 데이터 변환
        calendar_list_dto = CalendarListDTO.from_supabase_data(calendar_data)
        return responses.create_success_response(calendar_list_dto.to_dict())

    except Exception as e:
        logger.error(f"❌ 캘린더 조회 실패: {e}")
        return responses.create_error_response("Internal server error.", 500)


def create(event, context):
    """
    POST /calendar API 요청을 처리하는 핸들러
    body에 date/rollCallType/paymentType 필수
    """
    logger.info("✅ Processing create calendar request")

    try:
        # 요청 본문 파싱
        body = json.loads(event.get("body", "{}"))

        # DTO를 사용하여 요청 데이터 검증
        request_dto = CalendarCreateRequestDTO(
            date=body.get("date", ""),
            rollCallType=body.get("rollCallType"),  # None 허용
            paymentType=body.get("paymentType"),  # None 허용
        )

        # 요청 데이터 검증
        is_valid, error_message = request_dto.validate()
        if not is_valid:
            return responses.create_error_response(error_message, 400)

        # 캘린더 생성
        calendar_data, error = calendar_service.create_calendar(
            request_dto.date, request_dto.rollCallType, request_dto.paymentType
        )

        if error:
            return responses.create_error_response(error, 500)

        # DTO를 사용하여 응답 데이터 변환
        calendar_dto = CalendarDTO.from_supabase_data(calendar_data)
        return responses.create_success_response(calendar_dto.to_dict(), 201)

    except json.JSONDecodeError:
        return responses.create_error_response("Invalid JSON format.", 400)
    except Exception as e:
        logger.error(f"❌ 캘린더 생성 실패: {e}")
        return responses.create_error_response("Internal server error.", 500)


def update(event, context):
    """
    PUT /calendar API 요청을 처리하는 핸들러
    body에 id 필수, 나머지 필드는 선택
    """
    logger.info("✅ Processing update calendar request")

    try:
        # 요청 본문 파싱
        body = json.loads(event.get("body", "{}"))

        # DTO를 사용하여 요청 데이터 검증
        request_dto = CalendarUpdateRequestDTO(
            id=body.get("id"),
            date=body.get("date"),
            rollCallType=body.get("rollCallType"),
            paymentType=body.get("paymentType"),
        )

        # 요청 데이터 검증
        is_valid, error_message = request_dto.validate()
        if not is_valid:
            return responses.create_error_response(error_message, 400)

        # 업데이트할 필드 구성 - None 값도 포함
        fields = {}
        if "date" in body:  # 키 존재 여부로 확인
            fields["date"] = request_dto.date
        if "rollCallType" in body:  # null 값도 허용
            fields["roll_call_type"] = request_dto.rollCallType
        if "paymentType" in body:  # null 값도 허용
            fields["payment_type"] = request_dto.paymentType

        # 캘린더 수정
        calendar_data, error = calendar_service.update_calendar(request_dto.id, fields)

        if error:
            if error == "Not found":
                return responses.create_error_response(error, 404)
            return responses.create_error_response(error, 500)

        # DTO를 사용하여 응답 데이터 변환
        calendar_dto = CalendarDTO.from_supabase_data(calendar_data)
        return responses.create_success_response(calendar_dto.to_dict())

    except json.JSONDecodeError:
        return responses.create_error_response("Invalid JSON format.", 400)
    except Exception as e:
        logger.error(f"❌ 캘린더 수정 실패: {e}")
        return responses.create_error_response("Internal server error.", 500)


def delete(event, context):
    """
    DELETE /calendar API 요청을 처리하는 핸들러
    query parameter id 필수(int 변환)
    """
    logger.info("✅ Processing delete calendar request")

    try:
        # 쿼리 파라미터에서 id 추출
        query_params = event.get("queryStringParameters") or {}
        id_str = query_params.get("id")

        if not id_str:
            return responses.create_error_response("ID is required.", 400)

        # ID를 정수로 변환
        try:
            calendar_id = int(id_str)
            if calendar_id <= 0:
                return responses.create_error_response(
                    "ID must be a positive integer.", 400
                )
        except ValueError:
            return responses.create_error_response("Invalid ID format.", 400)

        # 캘린더 삭제
        _, error = calendar_service.delete_calendar_by_id(calendar_id)

        if error:
            if error == "Not found":
                return responses.create_error_response(error, 404)
            return responses.create_error_response(error, 500)

        # 성공 응답 반환
        return responses.create_success_response(
            {"message": "Calendar deleted successfully"}
        )

    except Exception as e:
        logger.error(f"❌ 캘린더 삭제 실패: {e}")
        return responses.create_error_response("Internal server error.", 500)
