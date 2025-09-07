import os
import psycopg2
import logging

# 로거 설정
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_db_connection():
    """
    환경 변수에서 연결 문자열을 가져와 DB 커넥션을 생성하고 반환합니다.
    이 함수는 프로젝트 전역에서 재사용됩니다.
    """
    conn_string = os.environ.get("DB_CONNECTION_STRING")
    if not conn_string:
        logger.error("❌ DB_CONNECTION_STRING environment variable is not set.")
        raise ValueError("DB connection string is not set.")

    try:
        conn = psycopg2.connect(conn_string)
        logger.info("✅ Database connection successful.")
        return conn
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        raise
