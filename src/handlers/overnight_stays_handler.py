import json
import logging
from typing import Tuple

from src.services import overnight_stays_service
from src.utils import responses
from src.dto import (
    OvernightStayDTO,
    OvernightStayCreateRequestDTO,
    OvernightStayStatusUpdateRequestDTO,
    OvernightStayStudentListDTO,
    OvernightStaySummaryDTO,
    OvernightStayAdminListDTO,
)


logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _map_service_error_to_status(error_message: str) -> Tuple[str, int]:
    """서비스 레이어의 에러 메시지를 HTTP 상태 코드로 매핑합니다."""
    if error_message in {"Student not found", "Overnight stay not found"}:
        return error_message, 404
    if error_message in {
        "Invalid date format. Use YYYY-MM-DD.",
        "End date cannot be earlier than start date.",
        "Overnight stay limit exceeded for this semester.",
        "Pending overnight stay request already exists.",
        "Invalid status. Must be 'approved' or 'rejected'.",
        "Page must be greater than 0",
    }:
        return error_message, 400
    return error_message, 500


def create(event, context):
    """POST /api/overnight-stay - 학생 외박 신청 생성"""

    logger.info("✅ Processing create overnight stay request")

    try:
        body = json.loads(event.get("body", "{}"))
        request_dto = OvernightStayCreateRequestDTO.from_dict(body)
        is_valid, validation_error = request_dto.validate()
        if not is_valid:
            return responses.create_error_response(validation_error, 400)

        user_info = event.get("user_info", {})
        student_no = user_info.get("username")
        if not student_no:
            logger.error("❌ Unauthorized request: student number missing in session")
            return responses.create_error_response("Unauthorized", 401)

        result, error = overnight_stays_service.create_overnight_stay(
            student_no=student_no,
            start_date=request_dto.startDate,
            end_date=request_dto.endDate,
            reason=request_dto.reason,
            semester=request_dto.semester,
        )

        if error:
            message, status = _map_service_error_to_status(error)
            return responses.create_error_response(message, status)

        response_dto = OvernightStayDTO.from_supabase_data(result)
        return responses.create_success_response(response_dto.to_dict(), 201)

    except json.JSONDecodeError:
        return responses.create_error_response("Invalid JSON format.", 400)
    except Exception as e:
        logger.error(f"❌ Failed to create overnight stay: {e}")
        return responses.create_error_response("Internal server error.", 500)


def get_student_requests(event, context):
    """GET /api/overnight-stay - 학생 외박 신청 목록 조회"""

    logger.info("✅ Processing get student overnight stays request")

    user_info = event.get("user_info", {})
    student_no = user_info.get("username")

    if not student_no:
        logger.error("❌ Unauthorized request: student number missing in session")
        return responses.create_error_response("Unauthorized", 401)

    try:
        data, summary, error = overnight_stays_service.get_student_overnight_stays(
            student_no
        )

        if error:
            message, status = _map_service_error_to_status(error)
            return responses.create_error_response(message, status)

        stays = [OvernightStayDTO.from_supabase_data(item) for item in data]
        summary_dto = OvernightStaySummaryDTO.from_dict(summary)
        response_dto = OvernightStayStudentListDTO(data=stays, summary=summary_dto)

        return responses.create_success_response(response_dto.to_dict())

    except Exception as e:
        logger.error(f"❌ Failed to fetch student overnight stays: {e}")
        return responses.create_error_response("Internal server error.", 500)


def get_admin_requests(event, context):
    """GET /api/overnight-stays - 사감 외박 신청 목록 조회"""

    logger.info("✅ Processing admin overnight stays list request")

    query_params = event.get("queryStringParameters") or {}

    semester = query_params.get("semester")
    student_no = query_params.get("studentIdNum")

    page_str = query_params.get("page", "1")
    page_size_str = query_params.get("pageSize", "10")

    try:
        page = int(page_str)
        page_size = int(page_size_str)
    except ValueError:
        return responses.create_error_response("Invalid page or pageSize format.", 400)

    try:
        data, total_count, resolved_page_size, error = (
            overnight_stays_service.get_overnight_stays(
                page=page,
                page_size=page_size,
                semester=semester,
                student_no=student_no,
            )
        )

        if error:
            message, status = _map_service_error_to_status(error)
            return responses.create_error_response(message, status)

        response_dto = OvernightStayAdminListDTO.from_supabase_data(
            data_list=data,
            total_items=total_count or 0,
            page=page,
            page_size=resolved_page_size or page_size,
        )

        return responses.create_success_response(response_dto.to_dict())

    except Exception as e:
        logger.error(f"❌ Failed to fetch admin overnight stays: {e}")
        return responses.create_error_response("Internal server error.", 500)


def update_status(event, context):
    """PATCH /api/overnight-stays - 외박 신청 상태 변경"""

    logger.info("✅ Processing overnight stay status update request")

    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return responses.create_error_response("Invalid JSON format.", 400)

    request_dto = OvernightStayStatusUpdateRequestDTO.from_dict(body)
    is_valid, validation_error = request_dto.validate()
    if not is_valid:
        return responses.create_error_response(validation_error, 400)

    try:
        result, error = overnight_stays_service.update_overnight_stay_status(
            request_dto.id, request_dto.status
        )

        if error:
            message, status = _map_service_error_to_status(error)
            return responses.create_error_response(message, status)

        response_dto = OvernightStayDTO.from_supabase_data(result)
        return responses.create_success_response(response_dto.to_dict())

    except Exception as e:
        logger.error(f"❌ Failed to update overnight stay status: {e}")
        return responses.create_error_response("Internal server error.", 500)
