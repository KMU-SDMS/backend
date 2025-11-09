import json
import boto3
import os
import re
from typing import Dict, Any, Optional, Tuple
from urllib.parse import unquote_plus

from src.utils.supabase_client import get_supabase_client
from io import BytesIO
from PIL import Image
import numpy as np
import json as _json
from paddleocr import PaddleOCR
from datetime import datetime, date
import calendar

# AWS 클라이언트 초기화
s3_client = boto3.client("s3")

# 환경 변수
BILL_BUCKET_NAME = os.environ.get("BILL_BUCKET_NAME", "")

# Supabase 클라이언트 초기화
supabase_client = get_supabase_client("core")


def lambda_handler(event, context):
    """
    S3 트리거로 실행되는 OCR Lambda 함수

    S3 경로 구조: bills/{year}/{month}/{room_id}/{bill_type}
    """

    try:
        # S3 이벤트에서 버킷과 키 정보 추출
        for record in event.get("Records", []):
            if record.get("eventSource") == "aws:s3":
                bucket_name = record["s3"]["bucket"]["name"]
                object_key = unquote_plus(record["s3"]["object"]["key"])
                event_name = record.get("eventName", "")

                # PUT 이벤트만 처리 (파일 업로드)
                result = process_bill_image(bucket_name, object_key)

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "OCR processing completed",
                    "processed_records": len(event.get("Records", [])),
                }
            ),
        }

    except Exception as e:
        print(f"❌ Lambda execution failed: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"message": "OCR processing failed", "error": str(e)}),
        }


def process_bill_image(bucket_name: str, object_key: str) -> bool:
    """
    S3에서 이미지를 가져와 OCR 처리를 수행합니다.

    Args:
        bucket_name: S3 버킷 이름
        object_key: S3 객체 키 (경로)

    Returns:
        bool: 처리 성공 여부
    """
    try:
        # # S3 경로 파싱
        path_info = parse_s3_path(object_key)

        year, month, room_id, bill_type = path_info
        # S3에서 이미지 바이트 가져오기 + 리사이즈
        obj = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        image_bytes = obj["Body"].read()
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        original_size = image.size
        image = resize_image(image)

        # 이미지 리사이즈 후 저장
        if image.size[0] * image.size[1] < original_size[0] * original_size[1]:
            _ = save_image_to_s3(
                image=image,
                bucket=bucket_name,
                key=object_key,
                original_size=original_size,
                content_type_hint=obj.get("ContentType"),
            )
        np_img = np.array(image)

        # PaddleOCR로 OCR 수행
        ocr_json = perform_ocr(np_img)

        # 청구금액 파싱
        total_bill_amount = parse_bill_amount_from_ocr_data(ocr_json, bill_type)
        bank_info = extract_bank_info(ocr_json.get("rec_texts", []))

        # 학생 정보 조회
        students_info = get_student_info_use_room_id(room_id)

        # 호실 내 모든 학생들의 관리비 비례 배분 계산
        bill_calculations = calculate_room_bill_distribution(
            students_info=students_info,
            total_bill_amount=total_bill_amount,
            year=year,
            month=month,
        )

        # 결과 저장
        save_result = save_ocr_result(
            year=year,
            month=month,
            room_id=room_id,
            bill_type=bill_type,
            bill_calculations=bill_calculations,
            bank_info=bank_info,
        )

        return True

    except Exception as e:
        raise e


def parse_s3_path(object_key: str) -> Optional[Tuple[str, str, str, str]]:
    """
    S3 경로를 파싱하여 년도, 월, 호실, 타입을 추출합니다.

    형식 예시:
      - bills/{year}/{month}/{room_id}/{filename}
      - filename 예: "2025 10 Water.png" 또는 "2025+10+Water.png" 등

    Returns:
        Tuple[year, month, room_id, bill_type] 또는 None
    """
    try:
        import re

        parts = object_key.split("/")

        if len(parts) >= 5 and parts[0] == "bills":
            year = parts[1]
            month = parts[2]
            room_id = parts[3]
            filename = parts[4]

            # 파일명에서 확장자 제거 후 구분자(공백/+/_/ -)로 분리하여 마지막 토큰을 타입으로 사용
            name_wo_ext = filename.split(".")[0]
            bill_type = name_wo_ext.lower()

            return year, month, room_id, bill_type

        return None

    except Exception as e:
        print(f"❌ Path parsing error: {str(e)}")
        return None


def calculate_room_bill_distribution(
    students_info: list, total_bill_amount: int, year: str, month: str
) -> list:
    """
    호실 내 모든 학생들의 거주 기간을 고려하여 관리비를 비례 배분합니다.

    계산 공식: 한 학생이 내야할 금액 = 총금액 / (해당 호실의 학생들의 총 거주 기간) * 한학생의 거주기간

    Args:
        students_info: 호실 내 모든 학생들의 정보 리스트
        total_bill_amount: 해당 월의 총 관리비
        year: 청구 년도
        month: 청구 월

    Returns:
        list: 각 학생별 계산 결과 리스트
    """
    try:

        # 청구 월의 시작일과 마지막일
        bill_year = int(year)
        bill_month = int(month)
        month_start = date(bill_year, bill_month, 1)
        month_end = date(
            bill_year, bill_month, calendar.monthrange(bill_year, bill_month)[1]
        )

        # 1단계: 각 학생의 거주 일수 계산
        student_calculations = []
        total_room_days = 0  # 호실 내 모든 학생들의 총 거주 일수

        for student in students_info:
            # 입실일 파싱
            check_in_date = datetime.strptime(
                student["check_in_date"], "%Y-%m-%d"
            ).date()

            # 퇴실일 파싱 (없으면 현재 거주 중으로 간주)
            check_out_date = datetime.strptime(
                student["check_out_date"], "%Y-%m-%d"
            ).date()

            # 실제 거주 시작일과 종료일 계산
            actual_start = max(
                check_in_date, month_start
            )  # 청구월 시작일과 입실일 중 늦은 날
            actual_end = min(
                check_out_date, month_end
            )  # 청구월 마지막일과 퇴실일 중 빠른 날

            # 거주 일수 계산
            if actual_start > actual_end:
                days_stayed = 0
            else:
                days_stayed = (actual_end - actual_start).days + 1

            total_room_days += days_stayed

            student_calculations.append(
                {
                    "student_no": student["studentNo"],
                    "days_stayed": days_stayed,
                    "student_amount": 0,
                }
            )

        # 2단계: 비례 배분으로 각 학생의 청구 금액 계산
        for item in student_calculations:
            student_no = item["student_no"]
            days_stayed = item["days_stayed"]
            student_amount = item["student_amount"]

            if total_room_days > 0:
                student_amount = int(total_bill_amount * days_stayed / total_room_days)
            else:
                student_amount = 0

            # 결과 업데이트
            item["student_amount"] = student_amount

        return student_calculations
    except Exception as e:
        print(f"❌ 호실 관리비 배분 계산 중 오류: {str(e)}")
        return []


def get_student_info_use_room_id(room_id: str) -> dict:
    """
    room_id를 사용하여 학생 정보를 조회합니다.
    """
    try:
        response = (
            supabase_client.postgrest.schema("core")
            .from_("students")
            .select("*")
            .eq("room_number", room_id)
            .execute()
        )
        return response.data
    except Exception as e:
        print(f"❌ Error getting student info: {str(e)}")
        return []


def resize_image(
    image: Image.Image, min_side: int = 960, max_side: int = 1280
) -> Image.Image:
    """
    긴 변 기준으로 960~1280px 범위 유지.
    - 1280px 초과: 비율 유지하여 1280px로 축소
    - 960~1280px: 그대로 유지
    - 960px 미만: 업스케일하지 않고 그대로 유지
    """
    try:
        width, height = image.size
        long_side = max(width, height)
        # 범위 내면 그대로
        if min_side <= long_side <= max_side:
            return image
        # 너무 크면 줄임
        if long_side > max_side:
            scale = max_side / float(long_side)
            new_size = (int(width * scale), int(height * scale))
            return image.resize(new_size, Image.LANCZOS)
        # 너무 작으면 그대로 (업스케일 금지)
        return image
    except Exception:
        return image


def _infer_content_type_from_key(object_key: str) -> str:
    ext = os.path.splitext(object_key.lower())[1]
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
    }.get(ext, "image/jpeg")


def _pil_format_from_content_type(content_type: str) -> str:
    mapping = {
        "image/jpeg": "JPEG",
        "image/png": "PNG",
        "image/webp": "WEBP",
        "image/bmp": "BMP",
        "image/tiff": "TIFF",
    }
    return mapping.get(content_type.lower(), "JPEG")


def save_image_to_s3(
    *,
    image: Image.Image,
    bucket: str,
    key: str,
    original_size: tuple,
    content_type_hint: Optional[str] = None,
) -> bool:
    """
    이미지(PIL)를 S3에 업로드합니다. JPEG/PNG 등 Content-Type에 맞춰 저장 포맷을 결정합니다.
    반환: 성공 여부
    """
    try:
        content_type = content_type_hint or _infer_content_type_from_key(key)
        pil_format = _pil_format_from_content_type(content_type)
        buf = BytesIO()
        save_kwargs = {"format": pil_format}
        if pil_format == "JPEG":
            save_kwargs.update({"quality": 90, "optimize": True})
        image.save(buf, **save_kwargs)
        buf.seek(0)
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=buf.getvalue(),
            ContentType=content_type,
        )
        print(
            f"🖼️ Resized image uploaded to s3://{bucket}/{key} ({original_size} -> {image.size})"
        )
        return True
    except Exception as e:
        print(f"⚠️ Failed to upload resized image: {str(e)}")
        raise e


def find_nearby_amount(target_boxs, bill_keyword_box, threshold=100):
    """
    총 관리비 키워드 주변 금액을 찾는 함수

    Args:
        target_box: 대상 텍스트의 박스 좌표 [x1, y1, x2, y2]
        all_boxes: 모든 텍스트 박스들의 좌표 리스트
        all_texts: 모든 텍스트들의 리스트
        threshold: 거리 임계값 (픽셀)
    Returns:
        List[Tuple[str, float]]: (텍스트, 거리) 튜플들의 리스트
    """

    bill_keyword_center_x = (bill_keyword_box[0] + bill_keyword_box[2]) / 2
    bill_keyword_center_y = (bill_keyword_box[1] + bill_keyword_box[3]) / 2

    nearest_distance = 1e9
    nearest_amount = None

    for target_box in target_boxs:
        target_center_x = (target_box.get("box")[0] + target_box.get("box")[2]) / 2
        target_center_y = (target_box.get("box")[1] + target_box.get("box")[3]) / 2

        distance = (
            (bill_keyword_center_x - target_center_x) ** 2
            + (bill_keyword_center_y - target_center_y) ** 2
        ) ** 0.5

        if distance <= nearest_distance:
            nearest_distance = distance
            nearest_amount = target_box.get("amount")

    return nearest_amount


def parse_bill_amount_from_ocr_data(json_data, bill_type: str):
    """
    OCR 데이터에서 청구금액을 파싱하는 함수

    Args:
        json_data: OCR 결과 JSON 데이터

    Returns:
        int: 청구금액
    """
    try:
        rec_texts = json_data.get("rec_texts", [])
        rec_boxes = json_data.get("rec_boxes", [])

        if len(rec_texts) != len(rec_boxes):
            print("⚠️ rec_texts와 rec_boxes 길이가 다름")
            raise Exception("rec_texts와 rec_boxes 길이가 다름")

        # 금액 패턴 정규식 (쉼표가 있는 숫자)
        amount_pattern = re.compile(r"^\d{1,3}(?:,\d{3})*$")

        # 청구금액 관련 키워드와 점수
        bill_keywords = ""

        if bill_type == "electricity":
            bill_keywords = "청구요금"
        elif bill_type == "water":
            bill_keywords = "합계"
        elif bill_type == "gas":
            bill_keywords = "금액"

        # 청구금액 키워드 박스 찾기
        bill_keyword_box = None
        for i, text in enumerate(rec_texts):
            if text == bill_keywords:
                bill_keyword_box = rec_boxes[i]
                break

        if bill_keyword_box is None:
            raise Exception("청구금액 키워드를 찾을 수 없음")

        amount_candidates = []

        # 1. 금액 후보들 찾기
        for i, text in enumerate(rec_texts):
            text_clean = text.strip()
            if amount_pattern.match(text_clean):
                try:
                    # 쉼표 제거하고 숫자로 변환
                    amount_value = int(text_clean.replace(",", ""))

                    # 너무 작거나 큰 금액은 제외 (1,000원 ~ 1,000,000원)
                    if 100 <= amount_value <= 1000000:
                        amount_candidates.append(
                            {
                                "index": i,
                                "text": text_clean,
                                "amount": amount_value,
                                "box": rec_boxes[i],
                            }
                        )
                except ValueError:
                    continue

        if not amount_candidates:
            raise Exception("금액 후보를 찾을 수 없음")

        # 주변 텍스트 찾기 (거리 임계값 150px)
        nearest_amount = find_nearby_amount(
            amount_candidates, bill_keyword_box, threshold=150
        )
        return nearest_amount

    except Exception as e:
        raise e


def perform_ocr(np_img: np.ndarray) -> dict:
    """
    PaddleOCR로 텍스트 라인 OCR을 수행합니다 (angle 미사용, 구조 인식 OFF).

    Returns OCR dict with:
      - text: 전체 텍스트
      - boxes: 인식된 라인별 박스/텍스트/스코어
      - bill_amount: 파싱된 청구금액 정보
    """
    try:

        result = PaddleOCR(
            use_doc_orientation_classify=False,  # 이미지 방향
            use_doc_unwarping=False,  # 글자 기울기 보정
            use_textline_orientation=False,  # 글자 방향 보정
            text_detection_model_name="PP-OCRv5_server_det",
            text_detection_model_dir="./ocr_models/PP-OCRv5_server_det_infer",
            text_recognition_model_name="korean_PP-OCRv5_mobile_rec",
            text_recognition_model_dir="./ocr_models/korean_PP-OCRv5_mobile_rec_infer",
        ).predict(np_img)

        result[0].save_to_json("/tmp/test.json")
        content_json = json.load(open("/tmp/test.json"))

        return content_json
    except Exception as e:
        raise e


def save_ocr_result(
    year: str,
    month: str,
    room_id: str,
    bill_type: str,
    bill_calculations: list,
    bank_info: list,
) -> bool:
    """
    OCR 결과를 Supabase core.bill 테이블에 upsert로 저장합니다.

    Args:
        year: 연도
        month: 월
        room_id: 호실
        bill_type: 관리비 타입
        bill_calculations: 학생별 관리비 계산 결과 리스트
        bank_info: 은행 정보 리스트

    Returns:
        bool: 저장 성공 여부
    """
    try:

        # 마감일 생성 (해당 월의 마지막 날)
        bill_year = int(year)
        bill_month = int(month)
        end_date = date(
            bill_year, bill_month, calendar.monthrange(bill_year, bill_month)[1]
        )

        # upsert용 데이터 준비
        upsert_data = []

        for calc in bill_calculations:
            student_no = calc["student_no"]
            student_amount = calc["student_amount"]

            bill_record = {
                "end_date": str(end_date),
                "type": bill_type,
                "student_no": student_no,
                "bank_info": bank_info,  # JSON 형태로 저장
                "amount": student_amount,
            }

            upsert_data.append(bill_record)

        # 벌크 upsert 수행
        # on_conflict 파라미터로 중복 시 업데이트할 컬럼 지정
        # student_no, type 조합이 유니크하다고 가정
        result = (
            supabase_client.postgrest.schema("core")
            .from_("bill")
            .upsert(upsert_data, on_conflict="student_no,type")
            .execute()
        )

        return True

    except Exception as e:
        raise e


def extract_bank_info(ocr_texts: list) -> list[dict[str, Optional[str]]]:
    """
    OCR 텍스트 리스트에서 "은행명 + 계좌번호" 패턴을 찾아 분리합니다.

    Args:
        ocr_texts: OCR로 추출된 텍스트들의 리스트

    Returns:
        Dict: {"bank_name": str, "bank_number": str} 또는 {"bank_name": None, "bank_number": None}
    """
    try:

        result = []
        # 은행명과 계좌번호가 함께 있는 패턴들
        # 패턴: 은행명 + 공백/콜론/기타구분자 + 계좌번호
        bank_account_pattern = (
            r"(국민|신한|우리|하나|기업|농협|새마을금고|신협|우체국|카카오뱅크|토스뱅크|경남|부산|대구|광주|전북|제주|산업|KB|NH|KEB|Woori|Hana|IBK|SC제일|씨티|iM뱅크)"
            r"(?:은행)?\s*[:：]?\s*(\d[\d\-]*)"
        )

        # OCR 텍스트들을 순회하면서 은행명+계좌번호 패턴 찾기
        for ocr_text in ocr_texts:
            text_clean = str(ocr_text).strip()

            matches = re.findall(bank_account_pattern, text_clean)
            if matches:
                bank_name, bank_number = matches[0]
                result.append({"bank_name": bank_name, "bank_number": bank_number})

        return result
    except Exception as e:
        raise e


if __name__ == "__main__":

    gas_event = {
        "Records": [
            {
                "eventVersion": "2.1",
                "eventSource": "aws:s3",
                "awsRegion": "ap-northeast-2",
                "eventTime": "2025-11-09T05:11:41.252Z",
                "eventName": "ObjectCreated:Put",
                "userIdentity": {"principalId": "A1GXL1V1X4D2UB"},
                "requestParameters": {"sourceIPAddress": "1.209.175.101"},
                "responseElements": {
                    "x-amz-request-id": "13AZV8Z7GKTMTRWZ",
                    "x-amz-id-2": "aIvQjgxsFQTe1OaX2PEhf6DuXN8JHQ6dhjjbbc/7TBeE9Fy6V6pkmNVpXpE+o9FnxJl/pf9MF5d9Z+/QD4Hwx2GkL4sOaE3IevgmpI/lhiY=",
                },
                "s3": {
                    "s3SchemaVersion": "1.0",
                    "configurationId": "4e308ea0-eb7c-42b6-84aa-2d9d0986d81f",
                    "bucket": {
                        "name": "bill-images-169615918165",
                        "ownerIdentity": {"principalId": "A1GXL1V1X4D2UB"},
                        "arn": "arn:aws:s3:::bill-images-169615918165",
                    },
                    "object": {
                        "key": "bills/2025/10/101/gas.png",
                        "size": 112790,
                        "eTag": "93b3a1597820f386191c766b31d75d8c",
                        "sequencer": "006910228D38A3EF2C",
                    },
                },
            }
        ]
    }

    water_event = {
        "Records": [
            {
                "eventVersion": "2.1",
                "eventSource": "aws:s3",
                "awsRegion": "ap-northeast-2",
                "eventTime": "2025-11-09T05:28:21.949Z",
                "eventName": "ObjectCreated:Put",
                "userIdentity": {"principalId": "A1GXL1V1X4D2UB"},
                "requestParameters": {"sourceIPAddress": "1.209.175.101"},
                "responseElements": {
                    "x-amz-request-id": "EDQ913BC1B9XKCZ8",
                    "x-amz-id-2": "EuvYy3oZjfWfkp6rFBdj6pnwmPgCCn1QgF4EfoNrNhp59zDX85dryTxDvKntJajHue77802R4+oimvQwtFumhD6d3eDaBOEr",
                },
                "s3": {
                    "s3SchemaVersion": "1.0",
                    "configurationId": "4e308ea0-eb7c-42b6-84aa-2d9d0986d81f",
                    "bucket": {
                        "name": "bill-images-169615918165",
                        "ownerIdentity": {"principalId": "A1GXL1V1X4D2UB"},
                        "arn": "arn:aws:s3:::bill-images-169615918165",
                    },
                    "object": {
                        "key": "bills/2025/10/101/water.png",
                        "size": 10466056,
                        "eTag": "0a593cc3875736c5186613469a7f3932",
                        "sequencer": "0069102675CD437BCF",
                    },
                },
            }
        ]
    }

    electricity_event = {
        "Records": [
            {
                "eventVersion": "2.1",
                "eventSource": "aws:s3",
                "awsRegion": "ap-northeast-2",
                "eventTime": "2025-11-09T05:33:16.093Z",
                "eventName": "ObjectCreated:Put",
                "userIdentity": {"principalId": "A1GXL1V1X4D2UB"},
                "requestParameters": {"sourceIPAddress": "1.209.175.101"},
                "responseElements": {
                    "x-amz-request-id": "SM0TVVMTBXH2N6F2",
                    "x-amz-id-2": "X8g46rTRYwGvfUCnuAQG8F04FP+YlCVNJXh5zb3kSRUn3x2MEq/1b9OWaelfVZZfzYJT70zQmmIy/WubteXJWzshlYPdoGDGZdsgLqAWgw4=",
                },
                "s3": {
                    "s3SchemaVersion": "1.0",
                    "configurationId": "4e308ea0-eb7c-42b6-84aa-2d9d0986d81f",
                    "bucket": {
                        "name": "bill-images-169615918165",
                        "ownerIdentity": {"principalId": "A1GXL1V1X4D2UB"},
                        "arn": "arn:aws:s3:::bill-images-169615918165",
                    },
                    "object": {
                        "key": "bills/2025/10/101/electricity.png",
                        "size": 10998937,
                        "eTag": "b962b6ff0aa66c6d2663965ba575c5fa",
                        "sequencer": "006910279BEEB1575E",
                    },
                },
            }
        ]
    }

    lambda_handler(water_event, None)
