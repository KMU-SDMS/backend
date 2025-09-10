import logging
from src.utils.supabase_client import get_supabase_client

# 로거 설정
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_students(room_id: str | None = None):
    """
    Supabase 클라이언트를 사용하여 학생 정보를 조회합니다.
    room_id가 주어지면 해당 방의 학생만 필터링합니다.
    """
    try:
        supabase = get_supabase_client("core")
        if not supabase:
            return None, "Supabase client could not be initialized."

        logger.info("Supabase 'students' 테이블 조회 시작")

        # room_id가 있으면 필터링, 없으면 전체 조회
        if room_id:
            response = (
                supabase.postgrest.schema("core")
                .from_("students")
                .select("room_id, name, studentNo")
                .eq("room_id", room_id)
                .order("name")
                .execute()
            )
        else:
            response = (
                supabase.postgrest.schema("core")
                .from_("students")
                .select("id, name, studentNo, affiliation, major, room_id")
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
