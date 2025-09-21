import json
import logging

from src.services import bill_service
from src.utils import responses

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
        body = json.loads(event.get("body", "{}"))
        content_type = body.get("contentType", "application/octet-stream")
        file_ext = body.get("ext")
        room_id = body.get("roomId")
        bill_type = body.get("type")
        year = body.get("year")
        month = body.get("month")

        # Validate required fields
        if not room_id:
            return responses.create_error_response("roomId is required.", 400)
        if not bill_type:
            return responses.create_error_response("type is required.", 400)
        if not year:
            return responses.create_error_response("year is required.", 400)
        if not month:
            return responses.create_error_response("month is required.", 400)

        data, err = bill_service.create_presigned_put_url(
            content_type, file_ext, room_id, bill_type, year, month
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
    logger.info("✅ Processing get bill image request")

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
        if not bill_type:
            return responses.create_error_response("type is required.", 400)
        if not year:
            return responses.create_error_response("year is required.", 400)
        if not month:
            return responses.create_error_response("month is required.", 400)

        # 서비스 호출
        data, err = bill_service.get_bill_image(room_id, bill_type, year, month)
        if err:
            return responses.create_error_response(err, 400)

        # 이미지가 없는 경우 404 반환
        if data is None:
            return responses.create_error_response(
                "No image found for the specified criteria.", 404
            )

        return responses.create_success_response(data)

    except Exception as e:
        logger.error(f"❌ get bill image failed: {e}")
        return responses.create_error_response("Internal server error.", 500)
