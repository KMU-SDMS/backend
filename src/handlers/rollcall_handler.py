"""
점호 관련 API 요청을 처리하는 핸들러입니다.
"""

import json
import logging
from src.services import rollcall_service, students_service
from src.utils import responses
from src.dto import (
    RollcallListDTO,
    RollcallDTO,
    RollcallCreateRequestDTO,
    RollcallUpdateRequestDTO,
)

# 로거 설정
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_rollcalls(event, context):
    """
    GET /rollcalls API 요청을 처리하는 핸들러
    - 쿼리 파라미터: date, roomId, name, present (모두 선택사항)
    """
    logger.info("✅ Processing get rollcalls request")

    query_params = event.get("queryStringParameters") or {}
    date = query_params.get("date")
    room_id = query_params.get("roomId")
    name = query_params.get("name")
    present = query_params.get("present")

    # roomId 파싱
    room_id_int = None
    if room_id:
        try:
            room_id_int = int(room_id)
        except ValueError:
            return responses.create_error_response("Invalid roomId format.", 400)

    # present 파싱
    present_bool = None
    if present is not None:
        if present.lower() == "true":
            present_bool = True
        elif present.lower() == "false":
            present_bool = False
        else:
            return responses.create_error_response(
                "Invalid present format. Must be 'true' or 'false'.", 400
            )

    # 필터가 하나라도 있는지 확인
    has_filters = any([date, room_id_int, name, present is not None])

    # 서비스 호출
    try:
        result = rollcall_service.get_rollcalls(
            date=date, room_id=room_id_int, name=name, present=present_bool
        )
    except RuntimeError as e:
        logger.error(f"❌ 점호 기록 조회 실패: {e}")
        return responses.create_error_response(str(e), 500)
    except Exception as e:
        logger.error(f"❌ 점호 기록 조회 실패: {e}")
        return responses.create_error_response("Internal server error.", 500)

    # 필터가 있고 결과가 비어있으면 404 반환
    if has_filters and not result:
        return responses.create_error_response("No rollcall records found.", 404)

    # DTO를 사용하여 응답 데이터 변환
    rollcall_list_dto = RollcallListDTO.from_supabase_data(result)
    return responses.create_success_response(rollcall_list_dto.to_dict())


def create_or_update_rollcall(event, context):
    """
    POST /rollcall API 요청을 처리하는 핸들러
    - body: studentId, date, present, note (선택)
    - Upsert 로직: 기존 레코드 있으면 UPDATE, 없으면 INSERT
    """
    logger.info("✅ Processing create or update rollcall request")

    try:
        body = json.loads(event.get("body", "{}"))

        # DTO를 사용한 요청 데이터 검증 (from_dict에서 검증 수행)
        create_request = RollcallCreateRequestDTO.from_dict(body)

        # 학생 존재 여부 확인
        student, error = students_service.get_student_by_student_no(
            create_request.studentId
        )
        if error:
            if error == "Not found":
                return responses.create_error_response("Student not found.", 404)
            return responses.create_error_response(error, 500)

        # 서비스 호출 (Upsert)
        try:
            result = rollcall_service.create_or_update_rollcall(
                student_no=create_request.studentId,
                date=create_request.date,
                present=create_request.present,
                note=create_request.note,
            )
        except RuntimeError as e:
            logger.error(f"❌ 점호 기록 Upsert 실패: {e}")
            return responses.create_error_response(str(e), 500)
        except Exception as e:
            logger.error(f"❌ 점호 기록 Upsert 실패: {e}")
            return responses.create_error_response("Internal server error.", 500)

        # 기존 레코드인지 확인하여 상태 코드 결정
        # Supabase upsert는 항상 업데이트된 레코드를 반환하므로,
        # created_at과 updated_at을 비교하여 생성/수정 여부 판단
        # 단순화: 항상 200 반환 (실제로는 created_at == updated_at이면 201)
        rollcall_dto = RollcallDTO.from_supabase_data(result)
        return responses.create_success_response(rollcall_dto.to_dict(), 200)

    except json.JSONDecodeError:
        return responses.create_error_response("Invalid JSON format.", 400)
    except ValueError as e:
        return responses.create_error_response(f"Validation error: {str(e)}", 400)


def update_rollcall(event, context):
    """
    PATCH /api/rollcall API 요청을 처리하는 핸들러
    - body: id (필수), present, note (선택사항)
    """
    logger.info("✅ Processing update rollcall request")

    try:
        body = json.loads(event.get("body", "{}"))

        # DTO를 사용한 요청 데이터 검증 (from_dict에서 검증 수행)
        update_request = RollcallUpdateRequestDTO.from_dict(body)

        # 서비스 호출
        try:
            result = rollcall_service.update_rollcall(
                id=update_request.id,
                present=update_request.present,
                note=update_request.note,
            )
        except ValueError as e:
            logger.error(f"❌ 점호 기록 수정 실패 (유효성 검사): {e}")
            return responses.create_error_response(str(e), 400)
        except RuntimeError as e:
            logger.error(f"❌ 점호 기록 수정 실패: {e}")
            error_str = str(e)
            if "not found" in error_str.lower():
                return responses.create_error_response("Rollcall not found.", 404)
            return responses.create_error_response(error_str, 500)
        except Exception as e:
            logger.error(f"❌ 점호 기록 수정 실패: {e}")
            return responses.create_error_response("Internal server error.", 500)

        # DTO를 사용하여 응답 데이터 변환
        rollcall_dto = RollcallDTO.from_supabase_data(result)
        return responses.create_success_response(rollcall_dto.to_dict())

    except json.JSONDecodeError:
        return responses.create_error_response("Invalid JSON format.", 400)
    except ValueError as e:
        return responses.create_error_response(f"Validation error: {str(e)}", 400)


def delete_rollcall(event, context):
    """
    DELETE /api/rollcall API 요청을 처리하는 핸들러
    - 쿼리 파라미터: id (필수)
    """
    logger.info("✅ Processing delete rollcall request")

    # 쿼리 파라미터에서 id 추출
    query_params = event.get("queryStringParameters") or {}
    id_str = query_params.get("id")

    if not id_str:
        return responses.create_error_response("ID is required.", 400)

    # ID를 정수로 변환
    try:
        rollcall_id = int(id_str)
        if rollcall_id <= 0:
            return responses.create_error_response(
                "ID must be a positive integer.", 400
            )
    except ValueError:
        return responses.create_error_response("Invalid ID format.", 400)

    # 서비스 호출
    try:
        result = rollcall_service.delete_rollcall(id=rollcall_id)
    except RuntimeError as e:
        logger.error(f"❌ 점호 기록 삭제 실패: {e}")
        error_str = str(e)
        if "not found" in error_str.lower():
            return responses.create_error_response("Rollcall not found.", 404)
        return responses.create_error_response(error_str, 500)
    except Exception as e:
        logger.error(f"❌ 점호 기록 삭제 실패: {e}")
        return responses.create_error_response("Internal server error.", 500)

    # 성공 응답 반환
    return responses.create_success_response(
        {"message": "Rollcall deleted successfully"}
    )
