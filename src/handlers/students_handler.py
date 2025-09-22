import json
import logging
from src.services import students_service
from src.utils import responses
from src.dto import (
    StudentListDTO,
    StudentDTO,
    StudentCreateRequestDTO,
    StudentUpdateRequestDTO,
)

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


def get_by_student_no(event, context):
    """
    GET /student API 요청을 처리하는 핸들러
    - 쿼리 파라미터: studentIdNum (필수)
    - 특정 학생 번호로 학생 조회
    """
    logger.info("✅ Processing get student by student number request")

    query_params = event.get("queryStringParameters") or {}
    student_no = query_params.get("studentIdNum")

    if not student_no:
        return responses.create_error_response(
            "studentIdNum parameter is required.", 400
        )

    # 서비스 호출
    result, error = students_service.get_student_by_student_no(student_no)

    if error:
        return responses.create_error_response(error, 500)

    if not result:
        return responses.create_error_response("Student not found.", 404)

    # DTO를 사용하여 응답 데이터 변환
    student_dto = StudentDTO.from_supabase_data(result)
    return responses.create_success_response(student_dto.to_dict())


def create(event, context):
    """
    POST /student API 요청을 처리하는 핸들러
    - body: name, studentIdNum (필수), roomNumber, checkInDate (선택)
    - 새 학생 생성
    """
    logger.info("✅ Processing create student request")

    try:
        body = json.loads(event.get("body", "{}"))

        # DTO를 사용한 요청 데이터 검증
        create_request = StudentCreateRequestDTO.from_dict(body)

        # 서비스 호출
        result, error = students_service.create_student(
            name=create_request.name,
            student_no=create_request.studentIdNum,
            room_number=create_request.roomNumber,
            check_in_date=create_request.checkInDate,
        )

        if error:
            return responses.create_error_response(error, 500)

        # DTO를 사용하여 응답 데이터 변환
        student_dto = StudentDTO.from_supabase_data(result)
        return responses.create_success_response(student_dto.to_dict(), 201)

    except json.JSONDecodeError:
        return responses.create_error_response("Invalid JSON format.", 400)
    except ValueError as e:
        return responses.create_error_response(f"Validation error: {str(e)}", 400)


def update(event, context):
    """
    PUT /student API 요청을 처리하는 핸들러
    - body: studentIdNum (필수), name, roomNumber, checkInDate (선택)
    - 학생 정보 수정
    """
    logger.info("✅ Processing update student request")

    try:
        body = json.loads(event.get("body", "{}"))

        # DTO를 사용한 요청 데이터 검증
        update_request = StudentUpdateRequestDTO.from_dict(body)

        # 업데이트할 필드 구성 (None이 아닌 값만)
        update_fields = {}
        if update_request.name is not None:
            update_fields["name"] = update_request.name
        if update_request.roomNumber is not None:
            update_fields["room_number"] = update_request.roomNumber
        if update_request.checkInDate is not None:
            update_fields["check_in_date"] = update_request.checkInDate

        # 서비스 호출
        result, error = students_service.update_student(
            update_request.studentIdNum, update_fields
        )

        if error:
            if error == "Not found":
                return responses.create_error_response("Student not found.", 404)
            return responses.create_error_response(error, 500)

        # DTO를 사용하여 응답 데이터 변환
        student_dto = StudentDTO.from_supabase_data(result)
        return responses.create_success_response(student_dto.to_dict())

    except json.JSONDecodeError:
        return responses.create_error_response("Invalid JSON format.", 400)
    except ValueError as e:
        return responses.create_error_response(f"Validation error: {str(e)}", 400)


def delete(event, context):
    """
    DELETE /student API 요청을 처리하는 핸들러
    - 쿼리 파라미터: studentIdNum (필수)
    - 학생 삭제
    """
    logger.info("✅ Processing delete student request")

    query_params = event.get("queryStringParameters") or {}
    student_id_num = query_params.get("studentIdNum")

    if not student_id_num:
        return responses.create_error_response(
            "studentIdNum parameter is required.", 400
        )

    # 서비스 호출
    result, error = students_service.delete_student_by_student_no(student_id_num)

    if error:
        if error == "Not found":
            return responses.create_error_response("Student not found.", 404)
        return responses.create_error_response(error, 500)

    return responses.create_success_response(
        {"message": "Student deleted successfully"}
    )
