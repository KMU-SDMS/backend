import logging
from src.services import students_service
from src.utils import responses
from src.dto import StudentListDTO

# 로거 설정
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_all(event, context):
    """
    GET /students API 요청을 처리하는 핸들러 (모든 학생 조회)
    """
    logger.info("✅ Processing get_all students request")
    # '실무자'에게 room_id 없이 업무 지시
    students_data, error = students_service.get_students()

    if error:
        return responses.create_error_response(error, 500)

    # DTO를 사용하여 응답 데이터 변환
    student_list_dto = StudentListDTO.from_supabase_data(students_data)
    return responses.create_success_response(student_list_dto.to_dict())


def get_by_room(event, context):
    """
    GET /students/{roomNumber} API 요청을 처리하는 핸들러 (특정 방 학생 조회)
    """
    logger.info("✅ Processing get_by_room students request")

    # URL 경로에서 roomNumber 값을 추출
    path_params = event.get("pathParameters") or {}
    room_number = path_params.get("roomNumber")

    if not room_number:
        return responses.create_error_response("Room Number is required.", 400)

    # 문자열을 정수로 변환 (DB에서 room_number는 int 타입)
    try:
        room_number_int = int(room_number)
    except ValueError:
        return responses.create_error_response(
            "Room Number must be a valid integer.", 400
        )

    # '실무자'에게 room_number를 포함하여 업무 지시
    students_data, error = students_service.get_students(room_number=room_number_int)

    if error:
        return responses.create_error_response(error, 500)

    # DTO를 사용하여 응답 데이터 변환
    student_list_dto = StudentListDTO.from_supabase_data(students_data)
    return responses.create_success_response(student_list_dto.to_dict())
