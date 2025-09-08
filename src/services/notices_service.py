from src.utils import db_connect
import logging
import psycopg2.extras

# 로거 설정
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_all_notices():
    """
    모든 호실 정보를 데이터베이스에서 조회하는 비즈니스 로직을 담당합니다.
    """
    conn = None
    try:
        # DB 연결 요청
        conn = db_connect.get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute(
            "SELECT id, title, content FROM core.notice ORDER BY created_at DESC"
        )
        notices = cur.fetchall()

        logger.info(f"✅ Retrieved {len(notices)} notices from DB")
        return notices
    finally:
        if conn:
            conn.close()
