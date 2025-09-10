import logging
from src.services import students_service
from src.utils import responses

# 로거 설정
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_all(event, context):
    """
    GET /students API 요청을 처리하는 핸들러 (모든 학생 조회)
    """
    logger.info("✅ Processing get_all students request")
    # '실무자'에게 room_id 없이 업무 지시
    students, error = students_service.get_students()

    if error:
        return responses.create_error_response(error, 500)

    return responses.create_success_response(students)


def get_by_room(event, context):
    """
    GET /students/{roomId} API 요청을 처리하는 핸들러 (특정 방 학생 조회)
    """
    logger.info("✅ Processing get_by_room students request")

    # URL 경로에서 roomId 값을 추출
    path_params = event.get("pathParameters") or {}
    room_id = path_params.get("roomId")

    if not room_id:
        return responses.create_error_response("Room ID is required.", 400)

    # '실무자'에게 room_id를 포함하여 업무 지시
    students, error = students_service.get_students(room_id=room_id)

    if error:
        return responses.create_error_response(error, 500)

    return responses.create_success_response(students)
