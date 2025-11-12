import logging
from typing import Optional, List
from datetime import datetime, date
from src.utils.supabase_client import get_supabase_client

# 로거 설정
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def check_pinned_notices_limit(is_important: bool, notice_id: Optional[int] = None) -> tuple[bool, Optional[str]]:
    """
    고정공지 개수 제한 검증 (최대 10개)
    
    Args:
        is_important: 고정공지로 설정하려는지 여부
        notice_id: 수정 시 자기 자신의 ID (생성 시에는 None)
    
    Returns:
        (is_valid, error_message)
    """
    if not is_important:
        return True, None
    
    try:
        supabase = get_supabase_client("core")
        if not supabase:
            return False, "Supabase client could not be initialized."
        
        # 현재 고정공지 개수 조회
        query = (
            supabase.postgrest.schema("core")
            .from_("notice")
            .select("id", count="exact")
            .eq("status", "PUBLISHED")
            .eq("is_important", True)
        )
        
        # 수정 시에는 자기 자신 제외
        if notice_id:
            query = query.neq("id", notice_id)
        
        response = query.execute()
        current_count = response.count if response.count is not None else 0
        
        if current_count >= 10:
            return False, "Maximum 10 pinned notices allowed. Please unpin another notice first."
        
        return True, None
    
    except Exception as e:
        logger.error(f"❌ 고정공지 개수 검증 실패: {e}")
        return False, "Failed to validate pinned notices limit"


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
            .select("id, title, content, created_at, is_important, status")
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


def create_notice(
    title: str, content: str, is_important: bool = False, status: str = "PUBLISHED"
):
    """
    Supabase 클라이언트를 사용하여 새로운 공지사항을 생성합니다.
    """
    try:
        # 고정공지 개수 검증 (애플리케이션 레벨)
        if is_important:
            is_valid, error_message = check_pinned_notices_limit(is_important)
            if not is_valid:
                return None, error_message

        supabase = get_supabase_client("core")
        if not supabase:
            return None, "Supabase client could not be initialized."

        logger.info("새 공지사항 생성 시작")

        # 공지사항 데이터 준비
        notice_data = {
            "title": title,
            "content": content,
            "is_important": is_important,
            "status": status,
        }

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
        # DB 제약 조건 에러 메시지 확인
        if "Maximum 10 pinned notices" in str(error_message):
            return None, "Maximum 10 pinned notices allowed. Please unpin another notice first."
        return None, error_message


def get_notices_with_pagination(page: int = 1):
    """
    Supabase 클라이언트를 사용하여 페이지네이션된 공지사항을 가져옵니다.
    - 1페이지: 고정공지 N개 + 일반공지 (10-N)개
    - 2페이지부터: 일반공지만

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

        if page == 1:
            # 1페이지: 고정공지 + 일반공지
            # 1) 고정공지 조회
            pinned_response = (
                supabase.postgrest.schema("core")
                .from_("notice")
                .select("id, title, content, created_at, is_important, status")
                .eq("status", "PUBLISHED")
                .eq("is_important", True)
                .order("created_at", desc=True)
                .execute()
            )
            
            pinned_notices = pinned_response.data
            pinned_count = len(pinned_notices)
            
            # 2) 일반공지 조회 (나머지 개수만큼)
            normal_count = PAGE_SIZE - pinned_count
            normal_response = (
                supabase.postgrest.schema("core")
                .from_("notice")
                .select("id, title, content, created_at, is_important, status", count="exact")
                .eq("status", "PUBLISHED")
                .eq("is_important", False)
                .order("created_at", desc=True)
                .limit(normal_count)
                .execute()
            )
            
            # 3) 합치기: 고정공지 + 일반공지
            all_notices = pinned_notices + normal_response.data
            
            # 4) 페이지 정보 (일반공지 기준)
            total_count = normal_response.count if normal_response.count is not None else 0
            
            logger.info(
                f"✅ Supabase로부터 페이지 {page}의 {len(all_notices)}개 공지사항을 성공적으로 가져왔습니다. (고정공지: {pinned_count}개, 일반공지: {len(normal_response.data)}개, 전체 일반공지: {total_count}개)"
            )
            
            return all_notices, total_count, PAGE_SIZE, None
        
        else:
            # 2페이지부터: 일반공지만
            offset = (page - 1) * PAGE_SIZE
            response = (
                supabase.postgrest.schema("core")
                .from_("notice")
                .select(
                    "id, title, content, created_at, is_important, status", count="exact"
                )
                .eq("status", "PUBLISHED")
                .eq("is_important", False)
                .order("created_at", desc=True)
                .range(offset, offset + PAGE_SIZE - 1)
                .execute()
            )
            
            notices_data = response.data
            total_count = response.count if response.count is not None else 0
            
            logger.info(
                f"✅ Supabase로부터 페이지 {page}의 {len(notices_data)}개 공지사항을 성공적으로 가져왔습니다. (전체 일반공지: {total_count}개)"
            )
            
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

        # 1) 연관 로그 선삭제 (notify.notice_logs -> FK: notice_id)
        try:
            notify_client = get_supabase_client("notify")
            if not notify_client:
                return None, "Supabase client could not be initialized."

            logger.info(
                f"관련 알림 로그 선삭제 시작: schema=notify, table=notice_logs, notice_id={notice_id}"
            )
            _ = (
                notify_client.postgrest.schema("notify")
                .from_("notice_logs")
                .delete()
                .eq("notice_id", notice_id)
                .execute()
            )
        except Exception as log_delete_error:
            logger.error(f"❌ notice_logs 선삭제 실패: {log_delete_error}")
            error_message = getattr(log_delete_error, "message", str(log_delete_error))
            return None, error_message

        # 2) 원 공지 삭제
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
    notice_id: int,
    title: str,
    content: str,
    is_important: bool = False,
    status: Optional[str] = None,
):
    """
    Supabase 클라이언트를 사용하여 특정 공지사항을 수정합니다.
    """
    try:
        # 고정공지로 변경하려는 경우 검증 (애플리케이션 레벨)
        if is_important:
            is_valid, error_message = check_pinned_notices_limit(is_important, notice_id)
            if not is_valid:
                return None, error_message

        supabase = get_supabase_client("core")
        if not supabase:
            return None, "Supabase client could not be initialized."

        logger.info(f"Supabase 'notice' 테이블에서 ID {notice_id} 수정 시작")

        # 수정할 데이터 준비
        update_data = {"title": title, "content": content, "is_important": is_important}
        if status is not None:
            update_data["status"] = status

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
        # DB 제약 조건 에러 메시지 확인
        if "Maximum 10 pinned notices" in str(error_message):
            return None, "Maximum 10 pinned notices allowed. Please unpin another notice first."
        return None, error_message


def get_notices_with_filters(
    status: Optional[List[str]] = None,
    is_important: Optional[bool] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    day: Optional[int] = None,
    sort: str = "latest",
    page: int = 1,
    search: Optional[str] = None,
):
    """
    Supabase 클라이언트를 사용하여 필터링 및 검색된 공지사항을 가져옵니다.
    - 1페이지: 고정공지 N개 + 일반공지 (10-N)개 (필터 적용 시에도 동일)
    - 2페이지부터: 일반공지만

    Returns:
        tuple: (notices_data, total_count, page_size, error)
    """
    PAGE_SIZE = 10

    try:
        supabase = get_supabase_client("core")
        if not supabase:
            return None, None, None, "Supabase client could not be initialized."

        logger.info(
            f"Supabase 'notice' 테이블 필터링 조회 시작 - 페이지: {page}, 크기: {PAGE_SIZE}"
        )

        if page == 1:
            # 1페이지: 고정공지 + 일반공지
            # 1) 고정공지 조회 (필터 적용)
            pinned_query = (
                supabase.postgrest.schema("core")
                .from_("notice")
                .select("id, title, content, created_at, is_important, status")
                .eq("status", "PUBLISHED")
                .eq("is_important", True)
            )
            
            # 검색 필터링
            if search:
                search_pattern = f"%{search}%"
                pinned_query = pinned_query.or_(
                    f"title.ilike.{search_pattern},content.ilike.{search_pattern}"
                )
            
            # 날짜 필터링
            if start_date and end_date:
                pinned_query = pinned_query.gte("created_at", start_date).lte("created_at", end_date)
            elif year is not None and month is not None and day is not None:
                single_date_start = f"{year:04d}-{month:02d}-{day:02d}T00:00:00"
                single_date_end = f"{year:04d}-{month:02d}-{day:02d}T23:59:59"
                pinned_query = pinned_query.gte("created_at", single_date_start).lte("created_at", single_date_end)
            
            # 정렬
            if sort == "oldest":
                pinned_query = pinned_query.order("created_at", desc=False)
            else:
                pinned_query = pinned_query.order("created_at", desc=True)
            
            pinned_response = pinned_query.execute()
            pinned_notices = pinned_response.data
            pinned_count = len(pinned_notices)
            
            # 2) 일반공지 조회 (나머지 개수만큼, 필터 적용)
            normal_count = PAGE_SIZE - pinned_count
            normal_query = (
                supabase.postgrest.schema("core")
                .from_("notice")
                .select("id, title, content, created_at, is_important, status", count="exact")
                .eq("status", "PUBLISHED")
                .eq("is_important", False)
            )
            
            # 검색 필터링
            if search:
                search_pattern = f"%{search}%"
                normal_query = normal_query.or_(
                    f"title.ilike.{search_pattern},content.ilike.{search_pattern}"
                )
            
            # 날짜 필터링
            if start_date and end_date:
                normal_query = normal_query.gte("created_at", start_date).lte("created_at", end_date)
            elif year is not None and month is not None and day is not None:
                single_date_start = f"{year:04d}-{month:02d}-{day:02d}T00:00:00"
                single_date_end = f"{year:04d}-{month:02d}-{day:02d}T23:59:59"
                normal_query = normal_query.gte("created_at", single_date_start).lte("created_at", single_date_end)
            
            # 정렬
            if sort == "oldest":
                normal_query = normal_query.order("created_at", desc=False)
            else:
                normal_query = normal_query.order("created_at", desc=True)
            
            normal_query = normal_query.limit(normal_count)
            normal_response = normal_query.execute()
            
            # 3) 합치기: 고정공지 + 일반공지
            all_notices = pinned_notices + normal_response.data
            
            # 4) 페이지 정보 (일반공지 기준)
            total_count = normal_response.count if normal_response.count is not None else 0
            
            logger.info(
                f"✅ Supabase로부터 필터링된 페이지 {page}의 {len(all_notices)}개 공지사항을 성공적으로 가져왔습니다. (고정공지: {pinned_count}개, 일반공지: {len(normal_response.data)}개, 전체 일반공지: {total_count}개)"
            )
            
            return all_notices, total_count, PAGE_SIZE, None
        
        else:
            # 2페이지부터: 일반공지만 (필터 적용)
            offset = (page - 1) * PAGE_SIZE
            
            query = (
                supabase.postgrest.schema("core")
                .from_("notice")
                .select(
                    "id, title, content, created_at, is_important, status", count="exact"
                )
                .eq("status", "PUBLISHED")
                .eq("is_important", False)
            )
            
            # 검색 필터링
            if search:
                search_pattern = f"%{search}%"
                query = query.or_(
                    f"title.ilike.{search_pattern},content.ilike.{search_pattern}"
                )
                logger.info(f"검색어 적용: {search}")
            
            # 날짜 필터링
            if start_date and end_date:
                query = query.gte("created_at", start_date).lte("created_at", end_date)
                logger.info(f"날짜 범위 필터 적용: {start_date} ~ {end_date}")
            elif year is not None and month is not None and day is not None:
                single_date_start = f"{year:04d}-{month:02d}-{day:02d}T00:00:00"
                single_date_end = f"{year:04d}-{month:02d}-{day:02d}T23:59:59"
                query = query.gte("created_at", single_date_start).lte("created_at", single_date_end)
                logger.info(f"단일 날짜 필터 적용: {year}-{month:02d}-{day:02d}")
            
            # 정렬
            if sort == "oldest":
                query = query.order("created_at", desc=False)
                logger.info("정렬: 오래된순 (created_at ASC)")
            else:
                query = query.order("created_at", desc=True)
                logger.info("정렬: 최신순 (created_at DESC)")
            
            # 페이지네이션 적용
            query = query.range(offset, offset + PAGE_SIZE - 1)
            
            # 쿼리 실행
            response = query.execute()
            
            notices_data = response.data
            total_count = response.count if response.count is not None else 0
            
            logger.info(
                f"✅ Supabase로부터 필터링된 페이지 {page}의 {len(notices_data)}개 공지사항을 성공적으로 가져왔습니다. (전체 일반공지: {total_count}개)"
            )
            
            return notices_data, total_count, PAGE_SIZE, None

    except Exception as e:
        logger.error(f"❌ Supabase API 호출 실패: {e}")
        error_message = getattr(e, "message", str(e))
        return None, None, None, error_message
