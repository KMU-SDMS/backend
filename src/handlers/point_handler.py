"""
상벌점 관련 API 요청을 처리하는 핸들러입니다.
"""

import json
import logging
from src.services import point_service, students_service
from src.utils import responses
from src.dto import (
    PointListDTO,
    PointDTO,
    PointCreateRequestDTO,
    PointBulkCreateRequestDTO,
)

# 로거 설정
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_points(event, context):
    """
    GET /points API 요청을 처리하는 핸들러
    - 쿼리 파라미터: studentId, dateFrom, dateTo (모두 선택사항)
    """
    logger.info("✅ Processing get points request")

    try:
        query_params = event.get("queryStringParameters") or {}
        student_id = query_params.get("studentId")
        date_from = query_params.get("dateFrom")
        date_to = query_params.get("dateTo")

        # 서비스 호출
        result = point_service.get_points(
            student_id=student_id, date_from=date_from, date_to=date_to
        )

        # DTO를 사용하여 응답 데이터 변환
        point_list_dto = PointListDTO.from_supabase_data(result)
        return responses.create_success_response(point_list_dto.to_dict())

    except RuntimeError as e:
        logger.error(f"❌ 상벌점 조회 실패: {e}")
        return responses.create_error_response(str(e), 500)
    except Exception as e:
        logger.error(f"❌ 상벌점 조회 실패: {e}")
        return responses.create_error_response("Internal server error.", 500)


def create_point(event, context):
    """
    POST /points API 요청을 처리하는 핸들러
    - body: studentId, type, score, reason, date (모두 필수)
    """
    logger.info("✅ Processing create point request")

    try:
        body = json.loads(event.get("body", "{}"))

        # DTO를 사용한 요청 데이터 검증
        create_request = PointCreateRequestDTO.from_dict(body)

        # 필수 필드 검증
        if not create_request.studentId:
            return responses.create_error_response("studentId is required.", 400)
        if not create_request.type:
            return responses.create_error_response("type is required.", 400)
        if not create_request.reason:
            return responses.create_error_response("reason is required.", 400)
        if not create_request.date:
            return responses.create_error_response("date is required.", 400)

        # type 유효성 검사
        if create_request.type not in ["MERIT", "DEMERIT"]:
            return responses.create_error_response(
                "Invalid type. Must be 'MERIT' or 'DEMERIT'.", 400
            )

        # score 유효성 검사
        if create_request.score <= 0:
            return responses.create_error_response(
                "Score must be a positive integer.", 400
            )

        # 학생 존재 여부 확인 (students_service는 아직 tuple 반환 패턴)
        student, error = students_service.get_student_by_student_no(
            create_request.studentId
        )
        if error:
            if error == "Not found":
                return responses.create_error_response("Student not found.", 404)
            logger.error(f"❌ 학생 조회 실패: {error}")
            return responses.create_error_response("Internal server error.", 500)

        # 서비스 호출
        try:
            result = point_service.create_point(
                student_no=create_request.studentId,
                type=create_request.type,
                score=create_request.score,
                reason=create_request.reason,
                date=create_request.date,
            )
        except ValueError as e:
            logger.error(f"❌ 상벌점 생성 실패 (유효성 검사): {e}")
            return responses.create_error_response(str(e), 400)
        except RuntimeError as e:
            logger.error(f"❌ 상벌점 생성 실패: {e}")
            return responses.create_error_response(str(e), 500)
        except Exception as e:
            logger.error(f"❌ 상벌점 생성 실패: {e}")
            return responses.create_error_response("Internal server error.", 500)

        # DTO를 사용하여 응답 데이터 변환
        point_dto = PointDTO.from_supabase_data(result)
        return responses.create_success_response(point_dto.to_dict(), 201)

    except json.JSONDecodeError:
        return responses.create_error_response("Invalid JSON format.", 400)
    except ValueError as e:
        return responses.create_error_response(f"Validation error: {str(e)}", 400)


def bulk_create_points(event, context):
    """
    POST /points/bulk API 요청을 처리하는 핸들러
    - body: studentIds (배열), type, score, reason, date (모두 필수)
    """
    logger.info("✅ Processing bulk create points request")

    try:
        body = json.loads(event.get("body", "{}"))

        # DTO를 사용한 요청 데이터 검증
        bulk_request = PointBulkCreateRequestDTO.from_dict(body)

        # 필수 필드 검증
        if not bulk_request.studentIds:
            return responses.create_error_response("studentIds is required.", 400)
        if not isinstance(bulk_request.studentIds, list):
            return responses.create_error_response("studentIds must be an array.", 400)
        if len(bulk_request.studentIds) == 0:
            return responses.create_error_response(
                "studentIds array cannot be empty.", 400
            )
        if not bulk_request.type:
            return responses.create_error_response("type is required.", 400)
        if not bulk_request.reason:
            return responses.create_error_response("reason is required.", 400)
        if not bulk_request.date:
            return responses.create_error_response("date is required.", 400)

        # type 유효성 검사
        if bulk_request.type not in ["MERIT", "DEMERIT"]:
            return responses.create_error_response(
                "Invalid type. Must be 'MERIT' or 'DEMERIT'.", 400
            )

        # score 유효성 검사
        if bulk_request.score <= 0:
            return responses.create_error_response(
                "Score must be a positive integer.", 400
            )

        # 모든 학생 존재 여부 확인 (students_service는 아직 tuple 반환 패턴)
        for student_id in bulk_request.studentIds:
            student, error = students_service.get_student_by_student_no(student_id)
            if error:
                if error == "Not found":
                    return responses.create_error_response(
                        f"Student not found: {student_id}", 404
                    )
                logger.error(f"❌ 학생 조회 실패: {error}")
                return responses.create_error_response("Internal server error.", 500)

        # 서비스 호출
        try:
            result = point_service.bulk_create_points(
                student_ids=bulk_request.studentIds,
                type=bulk_request.type,
                score=bulk_request.score,
                reason=bulk_request.reason,
                date=bulk_request.date,
            )
        except ValueError as e:
            logger.error(f"❌ 상벌점 일괄 생성 실패 (유효성 검사): {e}")
            return responses.create_error_response(str(e), 400)
        except RuntimeError as e:
            logger.error(f"❌ 상벌점 일괄 생성 실패: {e}")
            return responses.create_error_response(str(e), 500)
        except Exception as e:
            logger.error(f"❌ 상벌점 일괄 생성 실패: {e}")
            return responses.create_error_response("Internal server error.", 500)

        # 응답 형식: {created: count, items: [...]}
        point_list = [PointDTO.from_supabase_data(item).to_dict() for item in result]
        response_data = {"created": len(point_list), "items": point_list}
        return responses.create_success_response(response_data, 201)

    except json.JSONDecodeError:
        return responses.create_error_response("Invalid JSON format.", 400)
    except ValueError as e:
        return responses.create_error_response(f"Validation error: {str(e)}", 400)
