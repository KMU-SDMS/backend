import logging
from datetime import datetime, date
from typing import Optional, Tuple

from src.utils.supabase_client import get_supabase_client


logger = logging.getLogger()
logger.setLevel(logging.INFO)

MAX_APPROVED_PER_SEMESTER = 3
MAX_PENDING_REQUESTS = 1


def _parse_date(date_str: str) -> date:
    """문자열을 날짜로 파싱합니다."""
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def _ensure_student_exists(
    supabase, student_no: str
) -> Tuple[Optional[dict], Optional[str]]:
    """학생 존재 여부를 확인하고 학생 정보를 반환합니다."""
    response = (
        supabase.postgrest.schema("core")
        .from_("students")
        .select("studentNo, name, room_number")
        .eq("studentNo", student_no)
        .limit(1)
        .execute()
    )

    if not response.data:
        logger.info(f"❌ studentNo={student_no} 학생을 찾을 수 없습니다.")
        return None, "Student not found"

    return response.data[0], None


def _get_current_semester(reference_date: Optional[date] = None) -> str:
    """현재 날짜 기준으로 학기를 계산합니다."""
    today = reference_date or date.today()
    year = today.year

    if 3 <= today.month <= 8:
        return f"{year}-1"
    if today.month >= 9:
        return f"{year}-2"
    # 1월, 2월은 이전 해 2학기
    return f"{year - 1}-2"


def _build_joined_row(row: dict) -> dict:
    """조인된 학생 정보를 평탄화합니다."""
    student_info = row.pop("students", None)
    if student_info:
        row["student_name"] = student_info.get("name")
        row["room_number"] = student_info.get("room_number")
    return row


def create_overnight_stay(
    student_no: str,
    start_date: str,
    end_date: str,
    reason: str,
    semester: str,
):
    """새 외박 신청을 생성합니다."""

    try:
        start = _parse_date(start_date)
        end = _parse_date(end_date)
    except ValueError:
        return None, "Invalid date format. Use YYYY-MM-DD."

    if end < start:
        return None, "End date cannot be earlier than start date."

    try:
        supabase = get_supabase_client("core")
        if not supabase:
            return None, "Supabase client could not be initialized."

        student_info, error = _ensure_student_exists(supabase, student_no)
        if error:
            return None, error

        # 학기당 승인 횟수 제한 확인
        approved_response = (
            supabase.postgrest.schema("core")
            .from_("overnight_stays")
            .select("id", count="exact")
            .eq("student_no", student_no)
            .eq("semester", semester)
            .eq("status", "approved")
            .execute()
        )

        approved_count = approved_response.count or 0
        if approved_count >= MAX_APPROVED_PER_SEMESTER:
            logger.info(
                f"❌ studentNo={student_no} 학기 {semester} 외박 승인 횟수 초과"
            )
            return None, "Overnight stay limit exceeded for this semester."

        # 대기중 신청 개수 제한 확인
        pending_response = (
            supabase.postgrest.schema("core")
            .from_("overnight_stays")
            .select("id", count="exact")
            .eq("student_no", student_no)
            .eq("status", "pending")
            .execute()
        )

        pending_count = pending_response.count or 0
        if pending_count >= MAX_PENDING_REQUESTS:
            logger.info(f"❌ studentNo={student_no} 기존 대기중 외박 신청 존재")
            return None, "Pending overnight stay request already exists."

        insert_data = {
            "student_no": student_no,
            "start_date": start_date,
            "end_date": end_date,
            "reason": reason,
            "semester": semester,
        }

        response = (
            supabase.postgrest.schema("core")
            .from_("overnight_stays")
            .insert(insert_data, returning="representation")
            .execute()
        )

        if not response.data:
            logger.error("❌ 외박 신청 생성 실패: 응답 데이터 없음")
            return None, "Failed to create overnight stay"

        created = response.data[0]
        created["student_name"] = student_info.get("name")
        created["room_number"] = student_info.get("room_number")

        logger.info(
            f"✅ 외박 신청 생성 완료: id={created['id']}, student_no={student_no}, semester={semester}"
        )

        return created, None

    except Exception as e:
        logger.error(f"❌ 외박 신청 생성 실패: {e}")
        error_message = getattr(e, "message", str(e))
        return None, error_message


def get_student_overnight_stays(student_no: str):
    """학생의 현재 학기 외박 신청 목록과 요약 정보를 반환합니다."""

    try:
        supabase = get_supabase_client("core")
        if not supabase:
            return None, None, "Supabase client could not be initialized."

        student_info, error = _ensure_student_exists(supabase, student_no)
        if error:
            return None, None, error

        current_semester = _get_current_semester()

        response = (
            supabase.postgrest.schema("core")
            .from_("overnight_stays")
            .select(
                "id, student_no, start_date, end_date, reason, status, semester, created_at"
            )
            .eq("student_no", student_no)
            .eq("semester", current_semester)
            .order("created_at", desc=True)
            .execute()
        )

        data = response.data or []

        approved_response = (
            supabase.postgrest.schema("core")
            .from_("overnight_stays")
            .select("id", count="exact")
            .eq("student_no", student_no)
            .eq("semester", current_semester)
            .eq("status", "approved")
            .execute()
        )

        approved_count = approved_response.count or 0
        remaining_count = max(0, MAX_APPROVED_PER_SEMESTER - approved_count)

        summary = {
            "currentSemester": current_semester,
            "approvedCount": approved_count,
            "remainingCount": remaining_count,
        }

        logger.info(
            f"✅ 학생 외박 신청 조회 완료: student_no={student_no}, 학기={current_semester}, 건수={len(data)}"
        )

        return data, summary, None

    except Exception as e:
        logger.error(f"❌ 학생 외박 신청 조회 실패: {e}")
        error_message = getattr(e, "message", str(e))
        return None, None, error_message


def get_overnight_stays(
    page: int = 1,
    page_size: int = 10,
    semester: Optional[str] = None,
    student_no: Optional[str] = None,
):
    """사감용 외박 신청 목록을 조회합니다."""

    if page < 1:
        return None, None, None, "Page must be greater than 0"

    try:
        supabase = get_supabase_client("core")
        if not supabase:
            return None, None, None, "Supabase client could not be initialized."

        offset = (page - 1) * page_size

        query = (
            supabase.postgrest.schema("core")
            .from_("overnight_stays")
            .select(
                "id, student_no, start_date, end_date, reason, status, semester, created_at, students(name, room_number)",
                count="exact",
            )
            .order("created_at", desc=True)
        )

        if semester:
            query = query.eq("semester", semester)
        if student_no:
            query = query.eq("student_no", student_no)

        query = query.range(offset, offset + page_size - 1)

        response = query.execute()

        data = response.data or []
        total_count = response.count or 0

        processed_data = [_build_joined_row(row) for row in data]

        logger.info(
            f"✅ 사감 외박 목록 조회 완료: page={page}, page_size={page_size}, total={total_count}"
        )

        return processed_data, total_count, page_size, None

    except Exception as e:
        logger.error(f"❌ 사감 외박 목록 조회 실패: {e}")
        error_message = getattr(e, "message", str(e))
        return None, None, None, error_message


def update_overnight_stay_status(overnight_id: int, status: str):
    """외박 신청 상태를 업데이트합니다."""

    if status not in {"approved", "rejected"}:
        return None, "Invalid status. Must be 'approved' or 'rejected'."

    try:
        supabase = get_supabase_client("core")
        if not supabase:
            return None, "Supabase client could not be initialized."

        # 기존 데이터 조회
        existing_response = (
            supabase.postgrest.schema("core")
            .from_("overnight_stays")
            .select(
                "id, student_no, start_date, end_date, reason, status, semester, created_at, students(name, room_number)"
            )
            .eq("id", overnight_id)
            .limit(1)
            .execute()
        )

        if not existing_response.data:
            logger.info(f"❌ 외박 신청을 찾을 수 없음: id={overnight_id}")
            return None, "Overnight stay not found"

        existing_row = _build_joined_row(existing_response.data[0])

        if existing_row["status"] == status:
            logger.info(
                f"⚠️ 외박 신청 상태 변경 불필요: id={overnight_id}, status={status}"
            )
            return existing_row, None

        update_response = (
            supabase.postgrest.schema("core")
            .from_("overnight_stays")
            .update({"status": status}, returning="representation")
            .eq("id", overnight_id)
            .execute()
        )

        if not update_response.data:
            logger.error("❌ 외박 신청 상태 업데이트 실패: 응답 데이터 없음")
            return None, "Failed to update overnight stay status"

        updated_row = existing_row
        updated_row["status"] = status

        logger.info(
            f"✅ 외박 신청 상태 변경 완료: id={overnight_id}, new_status={status}"
        )

        # 승인/거부 알림 발송
        try:
            from src.services.notifications_service import send_notification_to_student

            title = "외박 신청 결과 안내"
            if status == "approved":
                content = f"{updated_row['start_date']} ~ {updated_row['end_date']} 외박 신청이 승인되었습니다."
            else:
                content = f"{updated_row['start_date']} ~ {updated_row['end_date']} 외박 신청이 거부되었습니다."

            notification_result, notification_error = send_notification_to_student(
                updated_row["student_no"], title, content
            )

            if notification_error:
                logger.warning(
                    f"⚠️ 외박 신청 상태 변경 알림 발송 실패: id={overnight_id}, error={notification_error}"
                )
            else:
                logger.info(
                    f"📢 외박 신청 상태 변경 알림 발송 성공: id={overnight_id}, result={notification_result}"
                )

        except Exception as notify_error:
            logger.warning(f"⚠️ 외박 신청 상태 변경 알림 처리 중 오류: {notify_error}")

        return updated_row, None

    except Exception as e:
        logger.error(f"❌ 외박 신청 상태 업데이트 실패: {e}")
        error_message = getattr(e, "message", str(e))
        return None, error_message
