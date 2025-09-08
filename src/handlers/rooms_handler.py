import logging
from src.services import rooms_service
from src.utils import responses

# 로거 설정
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_all(event, context):
    """
    GET /rooms API 요청을 처리하는 핸들러
    """
    logger.info("✅ get_all 핸들러 시작")

    # 서비스 레이어를 호출하여 비즈니스 로직을 수행합니다.
    rooms, err = rooms_service.get_all_rooms()

    if err:
        return responses.create_error_response(
            f"호실 정보를 가져오는 데 실패했습니다: {err}", 500
        )

    return responses.create_success_response(rooms)
