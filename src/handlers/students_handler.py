import logging
from src.services import students_service
from src.utils import responses
from src.dto import StudentListDTO

# 로거 설정
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_students(event, context):
    """
    GET /students API 요청을 처리하는 핸들러
    - 쿼리 파라미터 없음: 전체 학생 조회
    - roomNumber 쿼리 파라미터 있음: 해당 방 학생 조회
    """
    logger.info("✅ Processing get students request")

    query_params = event.get("queryStringParameters") or {}
    room_number = query_params.get("roomNumber")

    if room_number:
        # 특정 방 학생 조회
        try:
            room_number_int = int(room_number)
        except ValueError:
            return responses.create_error_response("Invalid room number format.", 400)

        result, error = students_service.get_students(room_number_int)
    else:
        # 전체 학생 조회
        result, error = students_service.get_students()

    if error:
        return responses.create_error_response(error, 500)

    # DTO를 사용하여 응답 데이터 변환
    student_list_dto = StudentListDTO.from_supabase_data(result)
    return responses.create_success_response(student_list_dto.to_dict())
