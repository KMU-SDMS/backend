import json
import logging
import re

from src.services import bill_service
from src.utils import responses
from src.dto.bill_dto import BillPresignRequestDTO
from src.utils.cognito_auth import (
    is_admin_group,
    is_common_user_group,
    is_admin_group_from_access_token,
    is_common_user_group_from_access_token,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def presign(event, context):
    """
    POST /bill/presign

    Body JSON:
    {
      "contentType": "image/jpeg",
      "ext": "jpg",
      "roomId": "1",
      "type": "water" | "electricity" | "gas",
      "year": "2025",
      "month": "01"
    }
    """
    logger.info("✅ Processing bill presign request")

    try:
        if not is_admin_group(event.get("user_info")) and not is_common_user_group(
            event.get("user_info")
        ):
            return responses.create_error_response("Unauthorized.", 401)

        body = json.loads(event.get("body", "{}"))
        access_token = event.get("access_token") or ""

        if not access_token:
            return responses.create_error_response("access_token is required.", 400)

        # DTO를 사용하여 요청 데이터 검증
        try:
            request_dto = BillPresignRequestDTO.from_dict(body)
        except ValueError as e:
            return responses.create_error_response(str(e), 400)

        data, err = bill_service.create_presigned_put_url(
            request_dto.contentType,
            request_dto.ext,
            request_dto.roomId,
            request_dto.type,
            request_dto.year,
            request_dto.month,
            event.get("user_info"),
            access_token,
        )
        if err:
            return responses.create_error_response(err, 400)

        return responses.create_success_response(data)

    except json.JSONDecodeError:
        return responses.create_error_response("Invalid JSON format.", 400)
    except Exception as e:
        logger.error(f"❌ bill presign failed: {e}")
        return responses.create_error_response("Internal server error.", 500)


def get_image(event, context):
    """
    GET /bill/image?roomId={roomId}&type={type}&year={year}&month={month}

    Query Parameters:
    - roomId: 방 번호 (필수)
    - type: 관리비 유형 (water|electricity|gas) (필수)
    - year: 연도 (필수)
    - month: 월 (필수)
    """
    if not is_common_user_group(event.get("user_info")) and not is_admin_group(
        event.get("user_info")
    ):
        return responses.create_error_response("Unauthorized.", 401)

    try:
        # 쿼리 파라미터 추출
        query_params = event.get("queryStringParameters") or {}
        room_id = query_params.get("roomId")
        bill_type = query_params.get("type")
        year = query_params.get("year")
        month = query_params.get("month")

        # 필수 파라미터 검증
        if not room_id:
            return responses.create_error_response("roomId is required.", 400)
        if not bill_type or bill_type not in ["water", "electricity", "gas"]:
            return responses.create_error_response(
                "type is required, must be one of: water, electricity, gas", 400
            )
        if not year:
            return responses.create_error_response("year is required.", 400)
        if not month:
            return responses.create_error_response("month is required.", 400)

        # 서비스 호출
        data, err = bill_service.get_bill_image(room_id, bill_type, year, month)
        if err == "Not found" or data is None:
            return responses.create_error_response("Not found.", 404)

        return responses.create_success_response(data)

    except Exception as e:
        logger.error(f"❌ get bill image failed: {e}")
        return responses.create_error_response("Internal server error.", 500)


def get_paid_bill_image(event, context):
    """
    GET /bill/paid/image?roomId={roomId}&type={type}&year={year}&month={month}

    Query Parameters:
    - roomId: 방 번호 (필수)
    - type: 관리비 유형 (water|electricity|gas) (필수)
    - year: 연도 (필수)
    - month: 월 (필수)
    """
    if not is_common_user_group(event.get("user_info")) and not is_admin_group(
        event.get("user_info")
    ):
        return responses.create_error_response("Unauthorized.", 401)

    logger.info("✅ Processing get paid bill image request")

    try:
        # 쿼리 파라미터 추출
        query_params = event.get("queryStringParameters") or {}
        room_id = query_params.get("roomId", False)
        bill_type = query_params.get("type", False)
        year = query_params.get("year", False)
        month = query_params.get("month", False)
        student_no = query_params.get("studentNo", False)

        # 필수 파라미터 검증
        if not room_id:
            return responses.create_error_response("roomId is required.", 400)
        if not bill_type or bill_type not in ["water", "electricity", "gas"]:
            return responses.create_error_response(
                "type is required, must be one of: water, electricity, gas", 400
            )
        if not year:
            return responses.create_error_response("year is required.", 400)
        if not month:
            return responses.create_error_response("month is required.", 400)

        if (
            is_admin_group_from_access_token(event.get("access_token"))
            and not student_no
        ):
            return responses.create_error_response("studentNo is required.", 400)

        # 서비스 호출
        data, error = bill_service.get_paid_bill_image(
            room_id, bill_type, year, month, event.get("access_token"), student_no
        )
        if error == "Not found" or data is None:
            logger.info(f"❌ get paid bill image not found: {error}")
            return responses.create_error_response("Not found.", 404)

        logger.info(f"✅ get paid bill image success: {data}")
        return responses.create_success_response(data)
    except Exception as e:
        logger.error(f"❌ get paid bill image failed: {e}")
        return responses.create_error_response("Internal server error.", 500)


def get_bill(event, context):
    """
    GET /bill?studentNo={studentNo}

    Query Parameters:
    - studentNo: 학생 번호 (관리자만 필요)
    """
    if not is_admin_group(event.get("user_info")) and not is_common_user_group(
        event.get("user_info")
    ):
        return responses.create_error_response("Unauthorized.", 401)

    try:
        query_params = event.get("queryStringParameters") or {}
        student_no = query_params.get("studentNo")

        if is_admin_group(event.get("user_info")) and not student_no:
            return responses.create_error_response("studentNo is required.", 400)

        if is_admin_group(event.get("user_info")):
            data, error = bill_service.get_bill(student_no, event.get("access_token"))
        elif is_common_user_group(event.get("user_info")):
            data, error = bill_service.get_bill(None, event.get("access_token"))
        if error == "Not found" or data is None:
            return responses.create_error_response("Not found.", 404)
        if error:
            return responses.create_error_response(error, 400)

        return responses.create_success_response(data)
    except Exception as e:
        logger.error(f"❌ get bill from student number failed: {e}")
        return responses.create_error_response("Internal server error.", 500)


def update_bill(event, context):
    """
    PATCH /bill
    Body JSON:
    {
      "studentNo": "20243025",      # optional
      "type": "water" | "electricity" | "gas",
      "amount": 12345,               # optional
      "bankInfo": [ { ... } ],       # optional, list of objects
      "endDate": "2025-11-30"        # optional, YYYY-MM-DD
      "is_paid": true             # optional, true if the bill is checked by admin
    }
    """
    if not is_admin_group(event.get("user_info")) and not is_common_user_group(
        event.get("user_info")
    ):
        return responses.create_error_response("Unauthorized.", 401)

    try:
        body = json.loads(event.get("body", "{}"))
        student_no = body.get("studentNo", None)
        bill_type = body.get("type")
        amount = body.get("amount", None)
        bank_info = body.get("bankInfo", None)
        end_date = body.get("endDate", None)
        is_paid = body.get("is_paid", None)
        # required checks
        if is_admin_group(event.get("user_info")) and not student_no:
            return responses.create_error_response("studentNo is required.", 400)
        if not bill_type or bill_type not in ["water", "electricity", "gas"]:
            return responses.create_error_response(
                "type is required, must be one of: water, electricity, gas", 400
            )

        # at least one updatable field
        update_payload: dict = {}
        if amount is not None:
            update_payload["amount"] = amount
        if bank_info is not None:
            update_payload["bank_info"] = bank_info
        if end_date is not None:
            update_payload["end_date"] = end_date
        if is_paid is not None:
            update_payload["is_paid"] = is_paid

        if not update_payload:
            return responses.create_error_response(
                "At least one of amount, bankInfo, endDate, is_paid is required.",
                400,
            )

        success, error = bill_service.update_bill(
            student_no=student_no,
            bill_data=update_payload,
            bill_type=bill_type,
            access_token=event.get("access_token"),
        )

        if not success:
            if error == "Not found":
                return responses.create_error_response("Not found.", 404)
            return responses.create_error_response(error or "Update failed.", 500)

        return responses.create_success_response({"success": True})
    except json.JSONDecodeError:
        return responses.create_error_response("Invalid JSON format.", 400)
    except Exception as e:
        logger.error(f"❌ update bill failed: {e}")
        return responses.create_error_response("Internal server error.", 500)


def get_bills_from_end_date(event, context):
    """
    GET /bills/endDate?endDate={endDate}

    Query Parameters:
    - endDate: 종료 일자 (YYYY-MM-DD)
    """

    try:
        if not is_admin_group(event.get("user_info")) and not is_common_user_group(
            event.get("user_info")
        ):
            return responses.create_warning_response("Unauthorized.", 401)

        query_params = event.get("queryStringParameters") or {}
        end_date = query_params.get("endDate")

        if not end_date:
            return responses.create_warning_response("endDate is required.", 400)

        # 날짜 형식 검증 (YYYY-MM-DD)
        date_pattern = r"^\d{4}-\d{2}-\d{2}$"
        if not re.match(date_pattern, end_date):
            return responses.create_warning_response(
                "endDate must be in YYYY-MM-DD format.", 400
            )

        data, error = bill_service.get_bills_from_end_date(end_date)
        if error == "Not found" or data is None:
            return responses.create_warning_response(
                "get bills from end date not found.", 404
            )
        elif data:
            return responses.create_success_response(data)
        else:
            raise Exception(f"service error: Failed to get bills from end date: {data}")
    except Exception as e:
        return responses.create_error_response(
            f"bill handler error: get bills from end date failed: {e}.", 500
        )
