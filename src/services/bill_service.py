import json
import os
import uuid
import calendar
from datetime import date
from typing import Any, Dict, Tuple
import boto3
from botocore.exceptions import ClientError
from src.utils.supabase_client import get_supabase_client
from src.dto.bill_dto import BillDTO, BillListDTO
from src.utils.cognito_auth import (
    get_user_info,
    is_admin_group,
    is_common_user_group,
    is_admin_group_from_access_token,
    is_common_user_group_from_access_token,
)

S3 = boto3.client("s3")


def _load_env() -> Tuple[str, set[str], int, str, str]:
    """Load bucket from environment and return hardcoded config for the rest."""
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

        allow_origin = "*"
        return bucket, allowed, expires, allow_origin
    except Exception as e:
        raise e


def _get_key_prefix_to_upload(
    access_token: str, year: str, month: str, room_id: str, bill_type: str
) -> str:
    try:
        user_info = get_user_info(access_token)
        user_name = user_info.get("username")
        user_groups = user_info.get("groups")
        if "admin" in user_groups:
            return f"bills/{year}/{month}/{room_id}/{bill_type}"
        elif "common_user" in user_groups:
            return f"paid/{year}/{month}/{room_id}/{bill_type}/{user_name}"
    except Exception as e:
        raise e


def _get_paid_key_prefix(
    access_token: str,
    year: str,
    month: str,
    room_id: str,
    bill_type: str,
    student_no: str = False,
) -> str:
    try:
        if student_no is not False:
            return f"paid/{year}/{month}/{room_id}/{student_no}/{bill_type}"
        else:
            user_info = get_user_info(access_token)
            user_name = user_info.get("username")
            return f"paid/{year}/{month}/{room_id}/{user_name}/{bill_type}"
    except Exception as e:
        raise e


def create_presigned_put_url(
    content_type: str,
    file_ext: str | None,
    room_id: str,
    bill_type: str,
    year: str,
    month: str,
    user_info: Dict[str, Any],
    access_token: str,
) -> Tuple[Dict[str, Any] | None, str | None]:
    try:
        bucket, allowed, expires, allow_origin = _load_env()

        if allowed and content_type not in allowed:
            return None, f"contentType '{content_type}' not allowed"

        # 관리자가 요청할 때 납부 마감일 검증
        if is_admin_group(user_info):
            bill_year = int(year)
            bill_month = int(month)

            # 해당 월의 시작일과 마지막일 계산
            month_start = date(bill_year, bill_month, 1)
            month_end = date(
                bill_year, bill_month, calendar.monthrange(bill_year, bill_month)[1]
            )

            # calendar 테이블에서 해당 년, 월, 관리비 타입에 맞는 레코드 조회
            supabase = get_supabase_client("core")
            calendar_result = (
                supabase.postgrest.schema("core")
                .from_("calendar")
                .select("id, date, payment_type")
                .eq("payment_type", bill_type)
                .gte("date", str(month_start))
                .lte("date", str(month_end))
                .execute()
            )

            # calendar 레코드가 없으면 에러 반환
            if not calendar_result.data or len(calendar_result.data) == 0:
                return (
                    None,
                    "관리비 이미지를 업로드하기전에 캘린더의 납부 마감일을 기재해주세요",
                )

        # Create S3 key with roomId and type: bills/{roomId}/{type}
        key = _get_key_prefix_to_upload(access_token, year, month, room_id, bill_type)

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
        bucket, allowed, expires, allow_origin = _load_env()

        # S3 key 생성: bills/{year}/{month}/{room_id}/{bill_type}
        key = f"bills/{year}/{month}/{room_id}/{bill_type}"

        # head_object로 파일 존재 확인 (list_objects_v2보다 빠름, 메타데이터만 가져옴)

        response = S3.head_object(Bucket=bucket, Key=key)

        # 파일이 존재하면 presigned URL 생성
        get_url = S3.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires,
        )

        result = {
            "key": key,
            "url": get_url,
        }

        return result, None

    except ClientError as s3_error:
        error_code = s3_error.response.get("Error", {}).get("Code", "")

        # 파일이 없는 경우
        if error_code == "404" or error_code == "NoSuchKey":
            return None, "Not found"

        # S3 스로틀링 에러 감지
        if error_code in ["SlowDown", "ServiceUnavailable", "503"]:
            raise Exception("S3 service temporarily unavailable. Please retry.")

        raise Exception(f"S3 error: {error_code}")

    except Exception as e:
        raise Exception(f"Failed to get bill image: {e}")


def get_paid_bill_image(
    room_id: str,
    bill_type: str,
    year: str,
    month: str,
    access_token: str,
    student_no: str = "",
) -> Tuple[Dict[str, Any] | None, str | None]:
    """
    관리비 납부 완료 이미지를 조회합니다.

    Args:
        room_id: 방 번호
        bill_type: 관리비 유형
        year: 연도
        month: 월
        access_token: 액세스 토큰
        student_no: 학생 번호 (관리자용, 선택사항)

    Returns:
        Tuple[Dict, str | None]: (이미지 데이터, 에러 메시지)
    """
    try:
        bucket, allowed, expires, allow_origin = _load_env()

        if is_admin_group_from_access_token(access_token):
            prefix = _get_paid_key_prefix(
                access_token, year, month, room_id, bill_type, student_no
            )
        elif is_common_user_group_from_access_token(access_token):
            prefix = _get_paid_key_prefix(access_token, year, month, room_id, bill_type)

        # head_object로 파일 존재 확인 (list_objects_v2보다 빠름, 메타데이터만 가져옴)
        response = S3.head_object(Bucket=bucket, Key=prefix)

        # 파일이 존재하면 presigned URL 생성
        get_url = S3.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": bucket, "Key": prefix},
            ExpiresIn=expires,
        )

        result = {
            "key": prefix,
            "url": get_url,
        }

        return result, None

    except ClientError as s3_error:
        error_code = s3_error.response.get("Error", {}).get("Code", "")

        # 파일이 없는 경우
        if error_code == "404" or error_code == "NoSuchKey":
            return None, "Not found"

        # S3 스로틀링 에러 감지
        if error_code in ["SlowDown", "ServiceUnavailable", "503"]:
            raise Exception("S3 service temporarily unavailable. Please retry.")

        raise Exception(f"S3 error: {error_code}")

    except Exception as e:
        raise Exception(f"Failed to get paid bill image: {e}")


def get_bill(
    student_no: str | None,
    access_token: str,
) -> Tuple[Dict[str, Any] | None, str | None]:
    """
    관리자가 학생 번호를 입력하면 Supabase에서 studentNo로 단일 학생의 관리비를 조회합니다.
    일반 사용자는 자신의 관리비를 조회합니다.

    Args:
        student_no: 학생 번호
        access_token: 액세스 토큰

    Returns:
        Tuple[Dict[str, Any] | None, str | None]: (관리비 목록, 에러 메시지)
    """
    try:
        if student_no is None:
            student_no = get_user_info(access_token).get("username")

        supabase = get_supabase_client("core")
        response = (
            supabase.postgrest.schema("core")
            .from_("bill")
            .select("*")
            .eq("student_no", student_no)
            .execute()
        )
        data = response.data
        if data:
            dto_list = BillListDTO.from_supabase_data(data)
            return dto_list.to_dict(), None
        else:
            return None, "Not found"
    except Exception as e:
        return None, str(e)


def update_bill(
    student_no: str | None,
    bill_data: Dict[str, Any],
    bill_type: str,
    access_token: str,
) -> Tuple[Dict[str, Any] | None, str | None]:
    """
    Supabase에서 studentNo로 단일 학생의 관리비를 수정합니다.
    """
    try:
        if student_no is None:
            student_no = get_user_info(access_token).get("username")
            bill_data = {"is_paid": bill_data["is_paid"]}

        supabase = get_supabase_client("core")

        response = (
            supabase.postgrest.schema("core")
            .from_("bill")
            .update(bill_data)
            .eq("student_no", student_no)
            .eq("type", bill_type)
            .execute()
        )
        if response.data:
            return True, None
        else:
            return False, "Not found"
    except Exception as e:
        return False, str(e)


def get_bills_from_end_date(end_date: str) -> Tuple[Dict[str, Any] | None, str | None]:
    """
    Supabase에서 end_date로 관리비를 조회합니다.
    """
    try:
        supabase = get_supabase_client("core")
        response = (
            supabase.postgrest.schema("core")
            .from_("bill")
            .select("*")
            .eq("end_date", end_date)
            .execute()
        )
        data = response.data
        if data:
            dto_list = BillListDTO.from_supabase_data(data)
            return dto_list.to_dict(), None
        elif data is None or len(data) == 0:
            return None, "Not found"
        else:
            raise Exception(f"service error: Failed to get bills from end date: {data}")
    except Exception as e:
        raise Exception(f"service error: Failed to get bills from end date: {e}")
