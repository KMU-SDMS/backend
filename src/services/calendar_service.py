import logging
from src.utils.supabase_client import get_supabase_client

# 로거 설정
logger = logging.getLogger(__name__)


def get_calendar(date: str = None):
    """
    Supabase 클라이언트를 사용하여 캘린더 데이터를 가져옵니다.
    date가 제공되면 특정 날짜의 데이터만 조회합니다.
    """
    try:
        supabase = get_supabase_client("core")
        if not supabase:
            return None, "Supabase client could not be initialized."

        logger.info(f"Supabase 'calendar' 테이블 조회 시작 - date: {date}")

        # 기본 쿼리 구성
        query = (
            supabase.postgrest.schema("core")
            .from_("calendar")
            .select("id, date, roll_call_type, payment_type, created_at")
        )

        # 특정 날짜 필터링 (선택적)
        if date:
            query = query.eq("date", date)

        # 날짜 순으로 정렬
        response = query.order("date").execute()

        calendar_data = response.data
        logger.info(
            f"✅ 캘린더 데이터 {len(calendar_data)}건을 성공적으로 가져왔습니다."
        )

        # 원시 데이터를 그대로 반환 (DTO 변환은 핸들러에서 처리)
        return calendar_data, None

    except Exception as e:
        logger.error(f"❌ Supabase API 호출 실패: {e}")
        error_message = getattr(e, "message", str(e))
        return None, error_message


def create_calendar(date: str, roll_call_type: str, payment_type: str):
    """
    Supabase 클라이언트를 사용하여 새로운 캘린더 데이터를 생성합니다.
    """
    try:
        supabase = get_supabase_client("core")
        if not supabase:
            return None, "Supabase client could not be initialized."

        logger.info("새 캘린더 데이터 생성 시작")

        # 캘린더 데이터 준비
        calendar_data = {
            "date": date,
            "roll_call_type": roll_call_type,
            "payment_type": payment_type,
        }

        response = (
            supabase.postgrest.schema("core")
            .from_("calendar")
            .insert(calendar_data)
            .execute()
        )

        if response.data:
            created_calendar = response.data[0]
            logger.info(
                f"✅ 캘린더 데이터가 성공적으로 생성되었습니다. ID: {created_calendar['id']}"
            )

            # 원시 데이터를 그대로 반환 (DTO 변환은 핸들러에서 처리)
            return created_calendar, None
        else:
            return None, "Failed to create calendar"

    except Exception as e:
        logger.error(f"❌ Supabase API 호출 실패: {e}")
        error_message = getattr(e, "message", str(e))
        return None, error_message


def update_calendar(id: int, fields: dict):
    """
    Supabase 클라이언트를 사용하여 특정 캘린더 데이터를 수정합니다.
    허용된 필드만 업데이트합니다: date, roll_call_type, payment_type
    """
    try:
        supabase = get_supabase_client("core")
        if not supabase:
            return None, "Supabase client could not be initialized."

        logger.info(f"Supabase 'calendar' 테이블에서 ID {id} 수정 시작")

        # 허용된 키만 필터링
        allowed_keys = {"date", "roll_call_type", "payment_type"}
        update_data = {k: v for k, v in fields.items() if k in allowed_keys}

        if not update_data:
            return None, "No valid fields to update"

        response = (
            supabase.postgrest.schema("core")
            .from_("calendar")
            .update(update_data)
            .eq("id", id)
            .execute()
        )

        # 수정된 데이터가 있는지 확인
        if not response.data:
            logger.warning(f"수정할 캘린더 ID {id}를 찾을 수 없습니다.")
            return None, "Not found"

        updated_calendar = response.data[0]
        logger.info(f"✅ 캘린더 ID {id}가 성공적으로 수정되었습니다.")

        # 원시 데이터를 그대로 반환 (DTO 변환은 핸들러에서 처리)
        return updated_calendar, None

    except Exception as e:
        logger.error(f"❌ Supabase API 호출 실패: {e}")
        error_message = getattr(e, "message", str(e))
        return None, error_message


def delete_calendar_by_id(id: int):
    """
    Supabase 클라이언트를 사용하여 특정 캘린더 데이터를 삭제합니다.
    """
    try:
        supabase = get_supabase_client("core")
        if not supabase:
            return None, "Supabase client could not be initialized."

        logger.info(f"Supabase 'calendar' 테이블에서 ID {id} 삭제 시작")

        response = (
            supabase.postgrest.schema("core")
            .from_("calendar")
            .delete()
            .eq("id", id)
            .execute()
        )

        # 삭제된 데이터가 있는지 확인
        if not response.data:
            logger.warning(f"삭제할 캘린더 ID {id}를 찾을 수 없습니다.")
            return None, "Not found"

        logger.info(f"✅ 캘린더 ID {id}가 성공적으로 삭제되었습니다.")

        # 삭제 성공 시 반환되는 데이터는 삭제된 레코드의 리스트
        return response.data, None

    except Exception as e:
        logger.error(f"❌ Supabase API 호출 실패: {e}")
        error_message = getattr(e, "message", str(e))
        return None, error_message
