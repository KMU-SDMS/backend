import logging
from src.utils.supabase_client import get_supabase_client


logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _map_notice_fields(notice: dict) -> dict:
    """
    내부 컬럼명을 API 스펙에 맞게 변환합니다.
    - created_at → date(YYYY-MM-DD)
    - is_important 필드는 그대로 유지
    """
    mapped = dict(notice)
    if "created_at" in mapped and mapped["created_at"]:
        try:
            mapped["date"] = str(mapped["created_at"])[:10]
        except Exception:
            mapped["date"] = None
    # id, title, content, date, is_important 유지
    return {k: mapped.get(k) for k in ["id", "title", "content", "date", "is_important"] if k in mapped}


def get_all_notices() -> tuple[list[dict] | None, str | None]:
    try:
        supabase = get_supabase_client("core")
        if not supabase:
            return None, "Supabase client could not be initialized."

        logger.info("Supabase 'notice' 테이블 조회 시작")
        response = (
            supabase.postgrest
            .schema("core")
            .from_("notice")
            .select("id,title,content,created_at,is_important")
            .order("created_at", desc=True)
            .execute()
        )
        notices_raw = response.data or []
        notices = [_map_notice_fields(n) for n in notices_raw]
        return notices, None
    except Exception as e:
        logger.error(f"❌ 공지 조회 실패: {e}")
        return None, str(e)


def get_notice_by_id(notice_id: int) -> tuple[dict | None, str | None]:
    try:
        supabase = get_supabase_client("core")
        if not supabase:
            return None, "Supabase client could not be initialized."

        logger.info(f"Supabase 'notice' 단건 조회: id={notice_id}")
        response = (
            supabase.postgrest
            .schema("core")
            .from_("notice")
            .select("id,title,content,created_at,is_important")
            .eq("id", notice_id)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if not rows:
            return None, "공지사항을 찾을 수 없습니다."
        return _map_notice_fields(rows[0]), None
    except Exception as e:
        logger.error(f"❌ 공지 단건 조회 실패: {e}")
        return None, str(e)


