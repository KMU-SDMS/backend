import logging
from src.utils.supabase_client import get_supabase_client

# 로거 설정
logger = logging.getLogger()
logger.setLevel(logging.INFO)


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


def get_notices_with_pagination(page: int = 1):
    """
    Supabase 클라이언트를 사용하여 페이지네이션된 공지사항을 가져옵니다.
    페이지당 10개의 공지사항을 반환합니다.

    Returns:
        tuple: (notices_data, total_count, page_size, error)
    """
    PAGE_SIZE = 10

    try:
        supabase = get_supabase_client("core")
        if not supabase:
            return None, None, None, "Supabase client could not be initialized."

        logger.info(
            f"Supabase 'notice' 테이블 페이지네이션 조회 시작 - 페이지: {page}, 크기: {PAGE_SIZE}"
        )

        # 페이지네이션 계산
        offset = (page - 1) * PAGE_SIZE

        # 단일 쿼리로 데이터와 전체 개수를 함께 조회 (성능 최적화)
        response = (
            supabase.postgrest.schema("core")
            .from_("notice")
            .select("id, title, content, created_at, is_important", count="exact")
            .order("created_at", desc=True)
            .range(offset, offset + PAGE_SIZE - 1)
            .execute()
        )

        notices_data = response.data
        total_count = response.count if response.count is not None else 0
        logger.info(
            f"✅ Supabase로부터 페이지 {page}의 {len(notices_data)}개 공지사항을 성공적으로 가져왔습니다. (전체: {total_count}개)"
        )

        # 원시 데이터와 페이지 크기 정보를 반환 (DTO 변환은 핸들러에서 처리)
        return notices_data, total_count, PAGE_SIZE, None

    except Exception as e:
        logger.error(f"❌ Supabase API 호출 실패: {e}")
        error_message = getattr(e, "message", str(e))
        return None, None, None, error_message


def delete_notice_by_id(notice_id: int):
    """
    Supabase 클라이언트를 사용하여 특정 공지사항을 삭제합니다.
    """
    try:
        supabase = get_supabase_client("core")
        if not supabase:
            return None, "Supabase client could not be initialized."

        logger.info(f"Supabase 'notice' 테이블에서 ID {notice_id} 삭제 시작")

        response = (
            supabase.postgrest.schema("core")
            .from_("notice")
            .delete()
            .eq("id", notice_id)
            .execute()
        )

        # 삭제된 데이터가 있는지 확인
        if not response.data:
            logger.warning(f"삭제할 공지사항 ID {notice_id}를 찾을 수 없습니다.")
            return None, "Notice not found"

        logger.info(f"✅ 공지사항 ID {notice_id}가 성공적으로 삭제되었습니다.")

        # 삭제 성공 시 반환되는 데이터는 삭제된 레코드의 리스트
        return response.data, None

    except Exception as e:
        logger.error(f"❌ Supabase API 호출 실패: {e}")
        error_message = getattr(e, "message", str(e))
        return None, error_message


def update_notice_by_id(
    notice_id: int, title: str, content: str, is_important: bool = False
):
    """
    Supabase 클라이언트를 사용하여 특정 공지사항을 수정합니다.
    """
    try:
        supabase = get_supabase_client("core")
        if not supabase:
            return None, "Supabase client could not be initialized."

        logger.info(f"Supabase 'notice' 테이블에서 ID {notice_id} 수정 시작")

        # 수정할 데이터 준비
        update_data = {"title": title, "content": content, "is_important": is_important}

        response = (
            supabase.postgrest.schema("core")
            .from_("notice")
            .update(update_data)
            .eq("id", notice_id)
            .execute()
        )

        # 수정된 데이터가 있는지 확인
        if not response.data:
            logger.warning(f"수정할 공지사항 ID {notice_id}를 찾을 수 없습니다.")
            return None, "Notice not found"

        updated_notice = response.data[0]
        logger.info(f"✅ 공지사항 ID {notice_id}가 성공적으로 수정되었습니다.")

        # 원시 데이터를 그대로 반환 (DTO 변환은 핸들러에서 처리)
        return updated_notice, None

    except Exception as e:
        logger.error(f"❌ Supabase API 호출 실패: {e}")
        error_message = getattr(e, "message", str(e))
        return None, error_message
