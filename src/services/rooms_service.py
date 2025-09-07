from src.utils import db_connect
import logging

# 로거 설정
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_all_rooms():
    """
    모든 호실 정보를 데이터베이스에서 조회하는 비즈니스 로직을 담당합니다.
    """
    conn = None
    try:
        # DB 연결 요청
        conn = db_connect.get_db_connection()
        cur = conn.cursor()

        cur.execute(
            "SELECT id, room_number, floor, capacity FROM core.rooms ORDER BY floor, room_number"
        )

        colnames = [desc[0] for desc in cur.description]

        rooms = []
        for row in cur.fetchall():
            room_data = dict(zip(colnames, row))
            room_data["name"] = room_data.pop("room_number")
            rooms.append(room_data)

        logger.info(f"✅ Retrieved {len(rooms)} rooms from DB")
        return rooms
    finally:
        if conn:
            conn.close()
