import logging
from src.utils.supabase_client import get_supabase_client


# 로거 설정
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_all_rooms():
    """
    Supabase 클라이언트를 사용하여 모든 호실 정보를 가져옵니다.
    """
    try:
        supabase = get_supabase_client("core")
        if not supabase:
            return None, "Supabase client could not be initialized."

        logger.info("Supabase 'rooms' 테이블 조회 시작")

        response = (
            supabase.postgrest.schema("core").from_("rooms").select("*").execute()
        )
        rooms_data = response.data

        logger.info(
            f"✅ Supabase로부터 {len(rooms_data)}개의 호실 정보를 성공적으로 가져왔습니다."
        )

        # 프론트엔드 데이터 모델에 맞게 변환 (필요한 필드만)
        result = []
        for room in rooms_data:
            result.append(
                {
                    "id": room["id"],
                    "name": room["room_number"],  # room_number → name
                    "floor": room["floor"],
                    "capacity": room["capacity"],
                }
            )

        return result, None

    except Exception as e:
        logger.error(f"❌ Supabase API 호출 실패: {e}")
        error_message = getattr(e, "message", str(e))
        return None, error_message
