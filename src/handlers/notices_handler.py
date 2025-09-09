import logging
from src.services import notices_service
from src.utils import responses


logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_all(event, context):
    logger.info("📋 GET /notices")
    notices, err = notices_service.get_all_notices()
    if err:
        return responses.create_error_response(err, 500)
    return responses.create_success_response(notices)


def get_one(event, context):
    logger.info("📋 GET /notice/{id}")
    path_params = (event or {}).get("pathParameters") or {}
    notice_id_str = path_params.get("id")
    try:
        notice_id = int(notice_id_str)
    except Exception:
        return responses.create_error_response("잘못된 공지 ID입니다.", 400)

    notice, err = notices_service.get_notice_by_id(notice_id)
    if err:
        status = 404 if "찾을 수 없습니다" in err else 500
        return responses.create_error_response(err, status)
    return responses.create_success_response(notice)


