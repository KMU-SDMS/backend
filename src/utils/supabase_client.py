import os
from supabase import create_client, Client
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# 스키마별 클라이언트를 저장하는 딕셔너리 (클라이언트 매니저)
_supabase_clients: dict[str, Client] = {}


def get_supabase_client(schema: str) -> Client | None:
    """
    지정된 스키마에 대한 Supabase 클라이언트 인스턴스를 반환합니다.
    클라이언트를 캐싱하여 재사용함으로써 효율성을 높입니다.
    """
    # 캐시 재사용
    if schema in _supabase_clients:
        return _supabase_clients[schema]

    try:
        base_url = os.environ.get("SUPABASE_URL")
        api_key = os.environ.get("SUPABASE_API_KEY")

        if not base_url or not api_key:
            logger.error("Supabase URL 또는 API Key가 설정되지 않았습니다.")
            return None

        # v2: 옵션 없이 생성 (schema는 쿼리 시 지정)
        client = create_client(base_url, api_key)

        logger.info(f"✅ Supabase 클라이언트가 초기화되었습니다.")
        _supabase_clients[schema] = client
        return client

    except Exception as e:
        logger.error(f"❌ Supabase 클라이언트 초기화 실패: {e}")
        return None
