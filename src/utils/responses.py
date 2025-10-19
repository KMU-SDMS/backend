import json
import logging

# 로거 설정
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def create_success_response(data, status_code=200):
    """성공적인 API 응답을 생성합니다."""
    # data가 리스트인지 단일 객체인지 확인
    if isinstance(data, list):
        logger.info(f"✅ Successfully prepared response with {len(data)} items.")
    else:
        logger.info("✅ Successfully prepared response with single item.")

    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
        },
        "body": json.dumps(data),
    }


def create_error_response(message, status_code):
    """에러 API 응답을 생성합니다."""
    logger.error(f"❌ ERROR: {message}")
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
        },
        "body": json.dumps({"error": message}),
    }
