"""
상벌점 관련 비즈니스 로직을 처리하는 서비스입니다.
"""

import logging
from typing import Optional
from src.utils.supabase_client import get_supabase_client

# 로거 설정
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_points(
    student_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    """
    상벌점 이력을 조회합니다.
    날짜 범위 필터링이 가능하며, created_at 기준 내림차순 정렬합니다.
    """
    supabase = get_supabase_client("rollcall")
    if not supabase:
        raise RuntimeError("Supabase client could not be initialized.")

    logger.info("상벌점 이력 조회 시작")

    query = (
        supabase.postgrest.schema("rollcall")
        .from_("points")
        .select("id, student_no, type, score, reason, date, created_at")
    )

    # 필터링 적용
    if student_id:
        query = query.eq("student_no", student_id)
    if date_from:
        query = query.gte("date", date_from)
    if date_to:
        query = query.lte("date", date_to)

    response = query.order("created_at", desc=True).execute()

    data = response.data
    logger.info(f"✅ {len(data)}개의 상벌점 기록을 조회했습니다.")

    return data


def create_point(student_no: str, type: str, score: int, reason: str, date: str):
    """
    상벌점을 단건 부여합니다.
    type은 'MERIT' 또는 'DEMERIT'만 허용하며, score는 양수만 가능합니다.
    """
    # 유효성 검사
    if type not in ["MERIT", "DEMERIT"]:
        raise ValueError("Invalid type. Must be 'MERIT' or 'DEMERIT'")
    if score <= 0:
        raise ValueError("Score must be a positive integer")

    supabase = get_supabase_client("rollcall")
    if not supabase:
        raise RuntimeError("Supabase client could not be initialized.")

    logger.info(
        f"상벌점 부여 시작: student_no={student_no}, type={type}, score={score}"
    )

    insert_data = {
        "student_no": student_no,
        "type": type,
        "score": score,
        "reason": reason,
        "date": date,
    }

    response = (
        supabase.postgrest.schema("rollcall")
        .from_("points")
        .insert(insert_data)
        .execute()
    )

    data = response.data
    if not data:
        raise RuntimeError("Failed to create point: No data returned from database")

    logger.info(
        f"✅ 상벌점 부여 성공: student_no={student_no}, type={type}, score={score}"
    )
    return data[0]


def bulk_create_points(
    student_ids: list[str], type: str, score: int, reason: str, date: str
):
    """
    상벌점을 대량 부여합니다.
    트랜잭션 처리로 전체 성공 또는 전체 실패를 보장합니다.
    """
    # 유효성 검사
    if type not in ["MERIT", "DEMERIT"]:
        raise ValueError("Invalid type. Must be 'MERIT' or 'DEMERIT'")
    if score <= 0:
        raise ValueError("Score must be a positive integer")
    if not student_ids:
        raise ValueError("studentIds array cannot be empty")

    supabase = get_supabase_client("rollcall")
    if not supabase:
        raise RuntimeError("Supabase client could not be initialized.")

    logger.info(
        f"상벌점 대량 부여 시작: {len(student_ids)}명, type={type}, score={score}"
    )

    # 각 학생에 대해 동일한 정보로 레코드 생성
    insert_data_list = [
        {
            "student_no": student_id,
            "type": type,
            "score": score,
            "reason": reason,
            "date": date,
        }
        for student_id in student_ids
    ]

    # Supabase의 insert는 여러 레코드를 한 번에 처리할 수 있음
    # 트랜잭션은 Supabase가 자동으로 처리
    response = (
        supabase.postgrest.schema("rollcall")
        .from_("points")
        .insert(insert_data_list)
        .execute()
    )

    data = response.data
    if not data:
        raise RuntimeError(
            "Failed to bulk create points: No data returned from database"
        )

    logger.info(f"✅ 상벌점 대량 부여 성공: {len(data)}건 생성됨")
    return data
