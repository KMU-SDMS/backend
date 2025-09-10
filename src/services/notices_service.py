import logging
from src.utils.supabase_client import get_supabase_client

# 로거 설정
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_all_notices():
    """
    Supabase 클라이언트를 사용하여 모든 공지사항을 가져옵니다.
    """
    try:
        supabase = get_supabase_client("core")
        if not supabase:
            return None, "Supabase client could not be initialized."

        logger.info("Supabase 'notice' 테이블 조회 시작")

        response = (
            supabase.postgrest.schema("core")
            .from_("notice")
            .select("id, title, content, created_at, is_important")
            .order("created_at", desc=True)
            .execute()
        )

        notices_data = response.data
        logger.info(
            f"✅ Supabase로부터 {len(notices_data)}개의 공지사항을 성공적으로 가져왔습니다."
        )

        # 원시 데이터를 그대로 반환 (DTO 변환은 핸들러에서 처리)
        return notices_data, None

    except Exception as e:
        logger.error(f"❌ Supabase API 호출 실패: {e}")
        error_message = getattr(e, "message", str(e))
        return None, error_message


def get_notice_by_id(notice_id: str):
    """
    Supabase 클라이언트를 사용하여 특정 공지사항을 가져옵니다.
    """
    try:
        supabase = get_supabase_client("core")
        if not supabase:
            return None, "Supabase client could not be initialized."

        logger.info(f"Supabase 'notice' 테이블에서 ID {notice_id} 조회 시작")

        response = (
            supabase.postgrest.schema("core")
            .from_("notice")
            .select("id, title, content, created_at, is_important")
            .eq("id", notice_id)
            .execute()
        )

        notices_data = response.data
        if not notices_data:
            return None, "Notice not found"

        notice = notices_data[0]
        logger.info(f"✅ 공지사항 ID {notice_id}를 성공적으로 가져왔습니다.")

        # 원시 데이터를 그대로 반환 (DTO 변환은 핸들러에서 처리)
        return notice, None

    except Exception as e:
        logger.error(f"❌ Supabase API 호출 실패: {e}")
        error_message = getattr(e, "message", str(e))
        return None, error_message


def create_notice(title: str, content: str, is_important: bool = False):
    """
    Supabase 클라이언트를 사용하여 새로운 공지사항을 생성합니다.
    """
    try:
        supabase = get_supabase_client("core")
        if not supabase:
            return None, "Supabase client could not be initialized."

        logger.info("새 공지사항 생성 시작")

        # 공지사항 데이터 준비
        notice_data = {"title": title, "content": content, "is_important": is_important}

        response = (
            supabase.postgrest.schema("core")
            .from_("notice")
            .insert(notice_data)
            .execute()
        )

        if response.data:
            created_notice = response.data[0]
            logger.info(
                f"✅ 공지사항이 성공적으로 생성되었습니다. ID: {created_notice['id']}"
            )

            # 원시 데이터를 그대로 반환 (DTO 변환은 핸들러에서 처리)
            return created_notice, None
        else:
            return None, "Failed to create notice"

    except Exception as e:
        logger.error(f"❌ Supabase API 호출 실패: {e}")
        error_message = getattr(e, "message", str(e))
        return None, error_message
