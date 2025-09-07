import json
import logging

# 로거 설정
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def create_success_response(data):
    """성공적인 API 응답을 생성합니다 (상태 코드 200)."""
    logger.info(f"✅ Successfully prepared response with {len(data)} items.")
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
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
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps({"error": message}),
    }
