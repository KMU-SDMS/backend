import logging
from src.utils.supabase_client import get_supabase_client

# 로거 설정
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_students(room_number: int | None = None):
    """
    Supabase 클라이언트를 사용하여 학생 정보를 조회합니다.
    room_number가 주어지면 해당 방의 학생만 필터링합니다.
    """
    try:
        supabase = get_supabase_client("core")
        if not supabase:
            return None, "Supabase client could not be initialized."

        logger.info("Supabase 'students' 테이블 조회 시작")

        # room_number가 있으면 필터링, 없으면 전체 조회
        if room_number:
            response = (
                supabase.postgrest.schema("core")
                .from_("students")
                .select("studentNo, name, room_number, check_in_date, check_out_date")
                .eq("room_number", room_number)
                .order("name")
                .execute()
            )
        else:
            response = (
                supabase.postgrest.schema("core")
                .from_("students")
                .select("studentNo, name, room_number, check_in_date, check_out_date")
                .order("name")
                .execute()
            )

        students_data = response.data
        logger.info(
            f"✅ Supabase로부터 {len(students_data)}명의 학생 정보를 성공적으로 가져왔습니다."
        )

        # 원시 데이터를 그대로 반환 (DTO 변환은 핸들러에서 처리)
        return students_data, None

    except Exception as e:
        logger.error(f"❌ Supabase API 호출 실패: {e}")
        error_message = getattr(e, "message", str(e))
        return None, error_message


def get_student_by_student_no(student_no: str):
    """
    Supabase에서 studentNo로 단일 학생을 조회합니다.
    """
    try:
        supabase = get_supabase_client("core")
        if not supabase:
            return None, "Supabase client could not be initialized."

        logger.info(f"Supabase 'students' 테이블에서 studentNo={student_no} 조회 시작")

        response = (
            supabase.postgrest.schema("core")
            .from_("students")
            .select(
                "studentNo, name, room_number, check_in_date, check_out_date, created_at"
            )
            .eq("studentNo", student_no)
            .execute()
        )

        data = response.data
        if data:
            logger.info(
                f"✅ studentNo={student_no} 학생 정보를 성공적으로 조회했습니다."
            )
            return data[0], None
        else:
            logger.info(f"❌ studentNo={student_no} 학생을 찾을 수 없습니다.")
            return None, "Not found"

    except Exception as e:
        logger.error(f"❌ Supabase API 호출 실패: {e}")
        error_message = getattr(e, "message", str(e))
        return None, error_message


def create_student(
    name: str,
    student_no: str,
    room_number: int | None = None,
    check_in_date: str | None = None,
    check_out_date: str | None = None,
):
    """
    Supabase에 새 학생 데이터를 삽입합니다.
    """
    try:
        supabase = get_supabase_client("core")
        if not supabase:
            return None, "Supabase client could not be initialized."

        logger.info(
            f"Supabase 'students' 테이블에 새 학생 생성 시작: {name} ({student_no})"
        )

        # 삽입할 데이터 준비
        insert_data = {
            "name": name,
            "studentNo": student_no,
            "room_number": room_number,
            "check_in_date": check_in_date,
            "check_out_date": check_out_date,
        }

        response = (
            supabase.postgrest.schema("core")
            .from_("students")
            .insert(insert_data)
            .execute()
        )

        data = response.data
        if data:
            logger.info(f"✅ 학생 {name} ({student_no})이 성공적으로 생성되었습니다.")
            return data[0], None
        else:
            logger.error(f"❌ 학생 생성 실패: 응답 데이터가 없습니다.")
            return None, "Failed to create student"

    except Exception as e:
        logger.error(f"❌ Supabase API 호출 실패: {e}")
        error_message = getattr(e, "message", str(e))
        return None, error_message


def update_student(student_no: str, fields: dict):
    """
    Supabase에서 studentNo로 학생 정보를 업데이트합니다.
    """
    try:
        supabase = get_supabase_client("core")
        if not supabase:
            return None, "Supabase client could not be initialized."

        logger.info(
            f"Supabase 'students' 테이블에서 studentNo={student_no} 업데이트 시작"
        )

        # 허용된 키만 필터링
        allowed_keys = {"name", "room_number", "check_in_date", "check_out_date"}
        update_data = {k: v for k, v in fields.items() if k in allowed_keys}

        if not update_data:
            logger.warning("업데이트할 유효한 필드가 없습니다.")
            return None, "No valid fields to update"

        response = (
            supabase.postgrest.schema("core")
            .from_("students")
            .update(update_data)
            .eq("studentNo", student_no)
            .execute()
        )

        data = response.data
        if data:
            logger.info(
                f"✅ studentNo={student_no} 학생 정보가 성공적으로 업데이트되었습니다."
            )
            return data[0], None
        else:
            logger.info(f"❌ studentNo={student_no} 학생을 찾을 수 없습니다.")
            return None, "Not found"

    except Exception as e:
        logger.error(f"❌ Supabase API 호출 실패: {e}")
        error_message = getattr(e, "message", str(e))
        return None, error_message


def delete_student_by_student_no(student_no: str):
    """
    Supabase에서 studentNo로 학생을 삭제합니다.
    """
    try:
        supabase = get_supabase_client("core")
        if not supabase:
            return None, "Supabase client could not be initialized."

        logger.info(f"Supabase 'students' 테이블에서 studentNo={student_no} 삭제 시작")

        response = (
            supabase.postgrest.schema("core")
            .from_("students")
            .delete()
            .eq("studentNo", student_no)
            .execute()
        )

        data = response.data
        if data:
            logger.info(f"✅ studentNo={student_no} 학생이 성공적으로 삭제되었습니다.")
            return data[0], None
        else:
            logger.info(f"❌ studentNo={student_no} 학생을 찾을 수 없습니다.")
            return None, "Not found"

    except Exception as e:
        logger.error(f"❌ Supabase API 호출 실패: {e}")
        error_message = getattr(e, "message", str(e))
        return None, error_message
