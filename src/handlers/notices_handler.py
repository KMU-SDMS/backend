from src.services import notices_service
from src.utils import responses
import logging

# 로거 설정
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_all(event, context):
    """
    GET /notices API 요청을 받아 처리하는 핸들러(팀장)입니다.
    실제 로직은 notices_service(실무자)에 위임합니다.
    """
    logger.info("✅ Processing getNotices request")
    try:
        # 1. '호실' 실무자에게 "모든 호실 정보 가져와!" 라고 지시합니다.
        notices = notices_service.get_all_notices()

        # 2. '응답' 전문가에게 "성공했으니, 이 데이터로 응답 만들어줘!" 라고 지시합니다.
        return responses.create_success_response(notices)

    except Exception as e:
        # 3. 문제가 생기면, '응답' 전문가에게 "에러났으니, 에러 응답 만들어줘!" 라고 지시합니다.
        return responses.create_error_response(str(e), 500)
