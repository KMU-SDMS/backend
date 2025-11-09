import json
import os
import uuid
from typing import Any, Dict, Tuple
from datetime import datetime
import boto3

S3 = boto3.client("s3")


def _load_env() -> Tuple[str, set[str], int, str, str]:
    """Load bucket from environment and return hardcoded config for the rest."""
<<<<<<< HEAD
    try:
        bucket = os.environ["BILL_BUCKET_NAME"]
        allowed = {
            "image/jpeg",
            "image/jpg",
            "image/png",
            "image/gif",
            "image/webp",
            "image/bmp",
            "image/tiff",
            "image/svg+xml",
        }
        expires = 300
        if is_admin_group(user_info):
            key_prefix = "bills"
        elif is_common_user_group(user_info):
            key_prefix = "paid"
        elif user_info.get("token_use") == "default":
            key_prefix = "bills"
        else:
            raise Exception("Unauthorized")

        allow_origin = "*"
        return bucket, allowed, expires, key_prefix, allow_origin
    except Exception as e:
        raise e
=======
    bucket = os.environ["BILL_BUCKET_NAME"]
    allowed = {
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/gif",
        "image/webp",
        "image/bmp",
        "image/tiff",
        "image/svg+xml",
    }
    expires = 300
    key_prefix = "bills"
    allow_origin = "*"
    return bucket, allowed, expires, key_prefix, allow_origin
>>>>>>> 54aa9434cf3737d72ed2234c570cb22692745434


def create_presigned_put_url(
    content_type: str,
    file_ext: str | None,
    room_id: str,
    bill_type: str,
    year: str,
    month: str,
) -> Tuple[Dict[str, Any] | None, str | None]:
    try:
        bucket, allowed, expires, key_prefix, allow_origin = _load_env()

        if allowed and content_type not in allowed:
            return None, f"contentType '{content_type}' not allowed"

        # Validate bill_type
        valid_types = {"water", "electricity", "gas"}
        if bill_type not in valid_types:
            return None, f"Invalid bill type. Must be one of: {', '.join(valid_types)}"

        # Create S3 key with roomId and type: bills/{roomId}/{type}
        key = f"{key_prefix}/{year}/{month}/{room_id}/{bill_type}"

        url = S3.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": bucket,
                "Key": key,
                "ContentType": content_type,
            },
            ExpiresIn=expires,
        )

        resp = {
            "url": url,
            "key": key,
            "headers": {"Content-Type": content_type},
        }
        return resp, None
    except Exception as e:
        return None, str(e)


def get_bill_image(
    room_id: str, bill_type: str, year: str, month: str
) -> Tuple[Dict[str, Any] | None, str | None]:
    """
    S3에서 지정된 경로의 관리비 이미지를 조회하고 presigned GET URL을 생성합니다.

    Args:
        room_id: 방 번호
        bill_type: 관리비 유형 (water, electricity, gas)
        year: 연도
        month: 월

    Returns:
        Tuple[Dict, str | None]: (이미지 데이터, 에러 메시지)
    """
    try:
        bucket, allowed, expires, key_prefix, allow_origin = _load_env()

        # S3 prefix 생성: bills/{year}/{month}/{room_id}/{bill_type} (파일명으로 사용)
        prefix = f"{key_prefix}/{year}/{month}/{room_id}/{bill_type}"

        # S3에서 객체 목록 조회
        response = S3.list_objects_v2(Bucket=bucket, Prefix=prefix)

        # bill_type으로 시작하는 파일 중에서 정확한 매칭 찾기
        if "Contents" in response and len(response["Contents"]) > 0:
            obj = response["Contents"][0]

            # presigned GET URL 생성
            get_url = S3.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": bucket, "Key": obj["Key"]},
                ExpiresIn=expires,
            )

            result = {
                "key": obj["Key"],
                "url": get_url,
                "lastModified": obj["LastModified"].isoformat(),
                "size": obj["Size"],
            }
        else:
            # 객체가 없는 경우
            result = None

        return result, None

    except Exception as e:
        return None, str(e)
<<<<<<< HEAD


def get_paid_bill_image(
    room_id: str, bill_type: str, year: str, month: str
) -> Tuple[Dict[str, Any] | None, str | None]:
    try:
        bucket, allowed, expires, key_prefix, allow_origin = _load_env()
        key_prefix = "paid"
        prefix = f"{key_prefix}/{year}/{month}/{room_id}/{bill_type}"
        response = S3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        if "Contents" in response and len(response["Contents"]) > 0:
            obj = response["Contents"][0]
            get_url = S3.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": bucket, "Key": obj["Key"]},
                ExpiresIn=expires,
            )
            result = {
                "key": obj["Key"],
                "url": get_url,
                "lastModified": obj["LastModified"].isoformat(),
                "size": obj["Size"],
            }
        else:
            result = None
        return result, None
    except Exception as e:
        return None, str(e)
=======
>>>>>>> 54aa9434cf3737d72ed2234c570cb22692745434
