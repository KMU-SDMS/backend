"""
점호 관련 비즈니스 로직을 처리하는 서비스입니다.
"""

import logging
from typing import Optional
from src.utils.supabase_client import get_supabase_client

# 로거 설정
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_rollcalls(
    date: Optional[str] = None,
    room_id: Optional[int] = None,
    name: Optional[str] = None,
    present: Optional[bool] = None,
):
    """
    필터링된 점호 기록을 조회합니다.
    다른 스키마 간 JOIN이 불가능하므로, room_id나 name 필터가 있으면
    먼저 core.students에서 student_no 목록을 조회한 후 필터링합니다.
    """
    try:
        supabase_rollcall = get_supabase_client("rollcall")
        supabase_core = get_supabase_client("core")
        if not supabase_rollcall or not supabase_core:
            raise RuntimeError("Supabase client could not be initialized.")

        logger.info("점호 기록 조회 시작")

        # room_id나 name 필터가 있으면 먼저 학생 목록 조회
        student_nos = None
        if room_id or name:
            student_query = (
                supabase_core.postgrest.schema("core")
                .from_("students")
                .select("studentNo")
            )
            if room_id:
                student_query = student_query.eq("room_number", room_id)
            if name:
                student_query = student_query.ilike("name", f"%{name}%")

            student_response = student_query.execute()
            student_nos = [s["studentNo"] for s in student_response.data]

            if not student_nos:
                # 조건에 맞는 학생이 없으면 빈 결과 반환
                logger.info("조건에 맞는 학생이 없어 빈 결과를 반환합니다.")
                return []

        # rollcall.records 조회 (JOIN 제거)
        query = (
            supabase_rollcall.postgrest.schema("rollcall")
            .from_("records")
            .select("id, student_no, date, present, note, created_at, updated_at")
        )

        # 필터링 적용
        if date:
            query = query.eq("date", date)
        if present is not None:
            query = query.eq("present", present)
        if student_nos:
            query = query.in_("student_no", student_nos)

        response = query.order("date", desc=True).order("id", desc=True).execute()

        data = response.data
        logger.info(f"✅ {len(data)}개의 점호 기록을 조회했습니다.")

        return data

    except RuntimeError:
        # RuntimeError는 그대로 전파
        raise
    except Exception as e:
        # 기타 예외는 RuntimeError로 변환하여 전파
        raise RuntimeError(f"Failed to get rollcalls: {str(e)}")


def create_or_update_rollcall(
    student_no: str, date: str, present: bool, note: Optional[str] = None
):
    """
    점호 기록을 생성하거나 수정합니다 (Upsert).
    (student_no, date) 조합이 이미 존재하면 UPDATE, 없으면 INSERT합니다.
    """
    supabase = get_supabase_client("rollcall")
    if not supabase:
        raise RuntimeError("Supabase client could not be initialized.")

    logger.info(
        f"점호 기록 Upsert 시작: student_no={student_no}, date={date}, present={present}"
    )

    # Upsert 데이터 준비
    upsert_data = {
        "student_no": student_no,
        "date": date,
        "present": present,
        "note": note or "",
    }

    # Supabase의 upsert 메서드 사용 (ON CONFLICT 처리)
    response = (
        supabase.postgrest.schema("rollcall")
        .from_("records")
        .upsert(upsert_data, on_conflict="student_no,date")
        .execute()
    )

    data = response.data
    if not data:
        raise RuntimeError(
            "Failed to upsert rollcall record: No data returned from database"
        )

    logger.info(f"✅ 점호 기록 Upsert 성공: student_no={student_no}, date={date}")
    return data[0]


def update_rollcall(
    id: int, present: Optional[bool] = None, note: Optional[str] = None
):
    """
    점호 기록을 부분 수정합니다.
    """
    supabase = get_supabase_client("rollcall")
    if not supabase:
        raise RuntimeError("Supabase client could not be initialized.")

    logger.info(f"점호 기록 수정 시작: id={id}")

    # 업데이트할 필드만 구성
    update_data = {}
    if present is not None:
        update_data["present"] = present
    if note is not None:
        update_data["note"] = note

    if not update_data:
        raise ValueError("No valid fields to update")

    response = (
        supabase.postgrest.schema("rollcall")
        .from_("records")
        .update(update_data)
        .eq("id", id)
        .execute()
    )

    data = response.data
    if not data:
        raise RuntimeError(f"Rollcall not found: id={id}")

    logger.info(f"✅ 점호 기록 수정 성공: id={id}")
    return data[0]


def delete_rollcall(id: int):
    """
    점호 기록을 삭제합니다.
    """
    supabase = get_supabase_client("rollcall")
    if not supabase:
        raise RuntimeError("Supabase client could not be initialized.")

    logger.info(f"점호 기록 삭제 시작: id={id}")

    response = (
        supabase.postgrest.schema("rollcall")
        .from_("records")
        .delete()
        .eq("id", id)
        .execute()
    )

    data = response.data
    if not data:
        raise RuntimeError(f"Rollcall not found: id={id}")

    logger.info(f"✅ 점호 기록 삭제 성공: id={id}")
    return data[0]
