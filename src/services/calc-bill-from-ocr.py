import json
import boto3
import os
import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from urllib.parse import unquote_plus

from src.utils.supabase_client import get_supabase_client
from io import BytesIO
from PIL import Image
import numpy as np
import json as _json
from paddleocr import PaddleOCR

# 로깅 설정
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS 클라이언트 초기화
s3_client = boto3.client("s3")

# 환경 변수
BILL_BUCKET_NAME = os.environ.get("BILL_BUCKET_NAME", "")

# Supabase 클라이언트 초기화
supabase_client = get_supabase_client("core")

# PaddleOCR 설정
PADDLE_LANG = os.environ.get("PADDLE_LANG", "korean")
_PADDLE_OCR = None
_PPSTRUCT = None


def _get_ppstructure():
    return None


def lambda_handler(event, context):
    """
    S3 트리거로 실행되는 OCR Lambda 함수

    S3 경로 구조: bills/{year}/{month}/{room_id}/{bill_type}
    """
    logger.info(f"📥 Received S3 event: {json.dumps(event, indent=2)}")

    try:
        # S3 이벤트에서 버킷과 키 정보 추출
        for record in event.get("Records", []):
            if record.get("eventSource") == "aws:s3":
                bucket_name = record["s3"]["bucket"]["name"]
                object_key = unquote_plus(record["s3"]["object"]["key"])
                event_name = record.get("eventName", "")

                # PUT 이벤트만 처리 (파일 업로드)
                if event_name.startswith("ObjectCreated"):
                    result = process_bill_image(bucket_name, object_key)
                    if result:
                        print(f"✅ OCR processing completed successfully")
                    else:
                        print(f"❌ OCR processing failed")
                else:
                    print(f"⏭️ Skipping non-creation event: {event_name}")

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
        # S3 경로 파싱
        path_info = parse_s3_path(object_key)

        year, month, room_id, bill_type = path_info

        # S3에서 이미지 바이트 가져오기 + 리사이즈
        obj = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        image_bytes = obj["Body"].read()
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        original_size = image.size
        image = resize_image(image)
        if image.size != original_size:
            _ = save_image_to_s3(
                image=image,
                bucket=bucket_name,
                key=object_key,
                original_size=original_size,
                content_type_hint=obj.get("ContentType"),
            )
        np_img = np.array(image)

        # PaddleOCR로 OCR 수행
        ocr_result = perform_ocr(np_img)

        if not ocr_result:
            print(f"❌ OCR failed for {object_key}")
            return False

        print(f"OCR 처리 완료: {object_key}")

        # 청구금액 파싱 결과 확인
        bill_amount = ocr_result.get("bill_amount")
        if bill_amount:
            print(
                f"✅ 청구금액 파싱 성공: {bill_amount['amount']}원 (신뢰도: {bill_amount['confidence']:.2f})"
            )
            print(f"   주변 텍스트: {bill_amount['context']}")
        else:
            print("⚠️ 청구금액을 자동으로 파싱하지 못했습니다")

        # OCR 결과에서 관리비 정보 추출 (기존 방식도 유지)
        # bill_data = extract_bill_data(ocr_result, bill_type)

        # # 결과 저장
        # save_result = save_ocr_result(
        #     year=year,
        #     month=month,
        #     room_id=room_id,
        #     type=bill_type,
        #     amount=bill_data.get("amount"),
        #     bank_name=bill_data.get("bank_name"),
        #     bank_number=bill_data.get("bank_number"),
        # )

        return True

    except Exception as e:
        logger.error(f"❌ Error processing {object_key}: {str(e)}")
        return False


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
            name_wo_ext = os.path.splitext(filename)[0]
            tokens = re.split(r"[\s+_\-]+", name_wo_ext.strip())
            bill_type = tokens[-1].lower() if tokens else ""

            # 기본 검증 (year, month 숫자 형식 확인)
            if (
                len(year) == 4
                and year.isdigit()
                and len(month) == 2
                and month.isdigit()
                and room_id
                and bill_type
            ):
                return year, month, room_id, bill_type

        return None

    except Exception as e:
        logger.error(f"❌ Path parsing error: {str(e)}")
        return None


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
        logger.info(
            f"🖼️ Resized image uploaded to s3://{bucket}/{key} ({original_size} -> {image.size})"
        )
        return True
    except Exception as e:
        logger.warning(f"⚠️ Failed to upload resized image: {str(e)}")
        return False


def find_nearby_texts(target_box, all_boxes, all_texts, threshold=100):
    """
    주변 텍스트들을 찾는 함수

    Args:
        target_box: 대상 텍스트의 박스 좌표 [x1, y1, x2, y2]
        all_boxes: 모든 텍스트 박스들의 좌표 리스트
        all_texts: 모든 텍스트들의 리스트
        threshold: 거리 임계값 (픽셀)

    Returns:
        List[Tuple[str, float]]: (텍스트, 거리) 튜플들의 리스트
    """
    target_center_x = (target_box[0] + target_box[2]) / 2
    target_center_y = (target_box[1] + target_box[3]) / 2

    nearby_texts = []
    for i, box in enumerate(all_boxes):
        if box == target_box:  # 자기 자신 제외
            continue

        center_x = (box[0] + box[2]) / 2
        center_y = (box[1] + box[3]) / 2

        distance = (
            (center_x - target_center_x) ** 2 + (center_y - target_center_y) ** 2
        ) ** 0.5

        if distance <= threshold:
            nearby_texts.append((all_texts[i], distance))

    # 거리순으로 정렬
    nearby_texts.sort(key=lambda x: x[1])
    return nearby_texts


def parse_bill_amount_from_ocr_data(json_data):
    """
    OCR 데이터에서 청구금액을 파싱하는 함수

    Args:
        json_data: OCR 결과 JSON 데이터

    Returns:
        Dict: {"amount": int, "confidence": float, "context": str}
    """
    try:
        rec_texts = json_data.get("rec_texts", [])
        rec_boxes = json_data.get("rec_boxes", [])

        if len(rec_texts) != len(rec_boxes):
            logger.warning("⚠️ rec_texts와 rec_boxes 길이가 다름")
            return None

        # 금액 패턴 정규식 (쉼표가 있는 숫자)
        amount_pattern = re.compile(r"^\d{1,3}(?:,\d{3})*$")

        # 청구금액 관련 키워드와 점수
        bill_keywords = {
            "청구금액": 100,
            "납부금액": 90,
            "총금액": 80,
            "당월요금": 85,
            "청구": 60,
            "납부": 50,
            "금액": 40,
            "요금": 30,
        }

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
            logger.info("💰 금액 후보를 찾을 수 없음")
            return None

        # 2. 각 금액 후보에 대해 주변 텍스트 분석
        best_candidate = None
        best_score = 0

        for candidate in amount_candidates:
            # 주변 텍스트 찾기 (거리 임계값 150px)
            nearby_texts = find_nearby_texts(
                candidate["box"], rec_boxes, rec_texts, threshold=150
            )

            # 키워드 매칭으로 점수 계산
            score = 0
            context_texts = []

            for nearby_text, distance in nearby_texts:
                nearby_clean = nearby_text.strip().lower()
                context_texts.append(nearby_text)

                # 키워드 매칭
                for keyword, keyword_score in bill_keywords.items():
                    if keyword in nearby_clean:
                        # 거리가 가까울수록 높은 점수 (최대 거리 150px 기준)
                        distance_factor = max(0, (150 - distance) / 150)
                        score += keyword_score * distance_factor
                        logger.info(
                            f"💰 키워드 '{keyword}' 발견 (거리: {distance:.1f}px, 점수: {keyword_score * distance_factor:.1f})"
                        )

            # 같은 줄에 있는 텍스트에 추가 점수 (y좌표 차이가 20px 이내)
            candidate_center_y = (candidate["box"][1] + candidate["box"][3]) / 2
            for nearby_text, distance in nearby_texts:
                if distance <= 50:  # 매우 가까운 텍스트
                    nearby_box_idx = None
                    for j, box in enumerate(rec_boxes):
                        if rec_texts[j] == nearby_text:
                            nearby_box_idx = j
                            break

                    if nearby_box_idx is not None:
                        nearby_center_y = (
                            rec_boxes[nearby_box_idx][1] + rec_boxes[nearby_box_idx][3]
                        ) / 2
                        if abs(candidate_center_y - nearby_center_y) <= 20:
                            score += 20  # 같은 줄 보너스

            logger.info(f"💰 금액 후보: {candidate['text']} (점수: {score:.1f})")

            if score > best_score:
                best_score = score
                best_candidate = candidate
                best_candidate["context"] = " ".join(
                    context_texts[:5]
                )  # 상위 5개 주변 텍스트
                best_candidate["confidence"] = min(
                    score / 100, 1.0
                )  # 0~1 사이로 정규화

        if best_candidate and best_score > 30:  # 최소 점수 임계값
            logger.info(
                f"💰 청구금액 파싱 성공: {best_candidate['amount']}원 (신뢰도: {best_candidate['confidence']:.2f})"
            )
            return {
                "amount": best_candidate["amount"],
                "confidence": best_candidate["confidence"],
                "context": best_candidate["context"],
            }
        else:
            logger.warning(f"⚠️ 청구금액 파싱 실패 - 최고 점수: {best_score}")
            return None

    except Exception as e:
        logger.error(f"❌ 청구금액 파싱 중 오류: {str(e)}")
        return None


def perform_ocr(np_img: np.ndarray) -> Optional[Dict[str, Any]]:
    """
    PaddleOCR로 텍스트 라인 OCR을 수행합니다 (angle 미사용, 구조 인식 OFF).

    Returns OCR dict with:
      - text: 전체 텍스트
      - boxes: 인식된 라인별 박스/텍스트/스코어
      - bill_amount: 파싱된 청구금액 정보
    """
    try:

        # result = PaddleOCR(
        #     use_doc_orientation_classify=False,  # 이미지 방향
        #     use_doc_unwarping=False,  # 글자 기울기 보정
        #     use_textline_orientation=False,  # 글자 방향 보정
        #     text_detection_model_name="PP-OCRv5_server_det",
        #     text_recognition_model_name="korean_PP-OCRv5_mobile_rec",
        # ).predict(np_img)

        # result[0].save_to_json("./test.json")
        content = json.load(open("./test.json"))

        # 청구금액 파싱
        bill_amount = parse_bill_amount_from_ocr_data(content)

        print(f"OCR 결과: {len(content.get('rec_texts', []))}개 텍스트 인식")
        if bill_amount:
            print(
                f"청구금액: {bill_amount['amount']}원 (신뢰도: {bill_amount['confidence']:.2f})"
            )
        else:
            print("청구금액을 찾을 수 없음")

        return {"text": content, "bill_amount": bill_amount}
    except Exception as e:
        logger.error(f"❌ OCR failed (PaddleOCR): {str(e)}")
        return None


def extract_bill_data(ocr_result: Dict[str, Any], bill_type: str) -> Dict[str, Any]:
    """
    OCR 텍스트에서 금액과 계좌(은행명, 계좌번호)만 추출합니다.

    Returns:
      {
        "amount": int | None,
        "bank_name": str | None,
        "bank_number": str | None,
      }
    """
    try:
        text = ocr_result.get("text", "") or ""

        import re as _re

        # 금액 추출: 키워드 우선, 그 외 보조 패턴
        amounts_found: list[int] = []
        keyword_amount_patterns = [
            r"(?:금액|합계|총금액|납부금액|청구금액|납부하실금액)\s*[:：]?\s*(\d{1,3}(?:,\d{3})*)\s*원?",
            r"₩\s*(\d{1,3}(?:,\d{3})*)",
        ]
        for pat in keyword_amount_patterns:
            for m in _re.findall(pat, text):
                try:
                    amounts_found.append(int(str(m).replace(",", "")))
                except Exception:
                    pass
        generic_amount_patterns = [
            r"(\d{1,3}(?:,\d{3})*)\s*원",
            r"(\d{1,3}(?:,\d{3})*)\s*KRW",
        ]
        for pat in generic_amount_patterns:
            for m in _re.findall(pat, text):
                try:
                    amounts_found.append(int(str(m).replace(",", "")))
                except Exception:
                    pass
        amount_value = max(amounts_found) if amounts_found else None

        # 계좌/은행 추출
        bank_name_value: Optional[str] = None
        bank_number_value: Optional[str] = None
        bank_names = "국민은행|우리은행|신한은행|하나은행|기업은행|경남은행|농협|새마을금고|신협|우체국|카카오뱅크|토스뱅크"
        bank_line_pattern = _re.compile(rf"({bank_names})\s*[:：]\s*([0-9\-\s]{{7,}})")
        account_pattern = _re.compile(r"(\d{2,4}(?:[- ]\d{2,6}){1,4})")
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            m = bank_line_pattern.search(line)
            if m:
                bank_name_value = m.group(1)
                bank_number_value = m.group(2).strip()
                break
            # 같은 라인에 은행명이 있으면 계좌 추출 시도
            name_match = _re.search(bank_names, line)
            if name_match:
                m2 = account_pattern.search(line)
                if m2:
                    bank_name_value = name_match.group(0)
                    bank_number_value = m2.group(1).strip()
                    break

        return {
            "amount": amount_value,
            "bank_name": bank_name_value,
            "bank_number": bank_number_value,
        }

    except Exception as e:
        logger.error(f"❌ Data extraction failed: {str(e)}")
        return {
            "amount": None,
            "bank_name": None,
            "bank_number": None,
            "error": str(e),
        }


def save_ocr_result(
    year: str,
    month: str,
    room_id: str,
    bill_type: str,
    amount: int,
    bank_name: str,
    bank_number: str,
) -> bool:
    """
    OCR 결과를 Supabase core.bill 테이블에 저장합니다.

    Args:
        year: 연도
        month: 월
        room_id: 호실
        bill_type: 관리비 타입
        ocr_text: OCR 추출 텍스트
        extracted_data: 추출된 관리비 데이터

    Returns:
        bool: 저장 성공 여부
    """
    try:
        if not supabase_client:
            logger.warning("⚠️ Supabase client not configured, skipping save")
            return False

        # OCR에서 추출된 데이터 파싱 (새 구조 우선)
        amount = (
            extracted_data.get("amount") if isinstance(extracted_data, dict) else None
        )
        if amount is None:
            extracted_values = (
                extracted_data.get("extracted_values", {})
                if isinstance(extracted_data, dict)
                else {}
            )
            amount = extracted_values.get("amount")

        # 계좌번호와 은행명: 추출 데이터 우선, 없을 경우 OCR 텍스트에서 추출
        bank_name = (
            extracted_data.get("bank_name")
            if isinstance(extracted_data, dict)
            else None
        )
        bank_number = (
            extracted_data.get("bank_number")
            if isinstance(extracted_data, dict)
            else None
        )
        if not bank_name or not bank_number:
            bn, bname = extract_bank_info(ocr_text)
            bank_number = bank_number or bn
            bank_name = bank_name or bname

        # 날짜 생성 (year-month 형태)
        bill_date = f"{year}-{month.zfill(2)}-01"  # 월의 첫날로 설정

        # core.bill 테이블에 저장할 데이터
        bill_data = {
            "date": bill_date,
            "type": bill_type,
            "bank_number": bank_number,
            "bank_name": bank_name,
        }
        print(f"💾 Saving OCR result to Supabase: {bill_data}")
        # Supabase에 데이터 삽입 (core 스키마 명시)
        result = (
            supabase_client.postgrest.schema("core")
            .from_("bill")
            .insert(bill_data)
            .execute()
        )

        if result.data:
            logger.info(f"💾 Saved OCR result to Supabase: {result.data[0]['id']}")
            return True
        else:
            logger.error(f"❌ Failed to save to Supabase: No data returned")
            return False

    except Exception as e:
        logger.error(f"❌ Failed to save result: {str(e)}")
        return False


def extract_bank_info(ocr_text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    OCR 텍스트에서 계좌번호와 은행명을 추출합니다.

    Args:
        ocr_text: OCR로 추출된 텍스트

    Returns:
        Tuple[bank_number, bank_name]: 계좌번호와 은행명
    """
    try:
        print(f"🏦 Extracting bank info from OCR text: {ocr_text}")
        bank_number = None
        bank_name = None

        # 계좌번호 패턴 (예: 123-456-789012, 1234-56-789012)
        account_patterns = [
            r"(\d{3,4}-\d{2,6}-\d{6,12})",  # 일반적인 계좌번호 형태
            r"(\d{10,14})",  # 숫자만 있는 계좌번호
        ]

        for pattern in account_patterns:
            matches = re.findall(pattern, ocr_text)
            if matches:
                bank_number = matches[0]
                break

        # 은행명 패턴
        bank_patterns = [
            r"(국민은행|신한은행|우리은행|하나은행|기업은행|농협|새마을금고|신협|우체국|카카오뱅크|토스뱅크)",
            r"(KB|NH|KEB|Woori|Hana|IBK)",
        ]

        for pattern in bank_patterns:
            matches = re.findall(pattern, ocr_text)
            if matches:
                bank_name = matches[0]
                break

        logger.info(
            f"🏦 Extracted bank info - Number: {bank_number}, Name: {bank_name}"
        )

        return bank_number, bank_name

    except Exception as e:
        logger.error(f"❌ Bank info extraction failed: {str(e)}")
        return None, None


# 테스트용 로컬 실행
if __name__ == "__main__":
    # 테스트 이벤트
    test_event = {
        "Records": [
            {
                "eventVersion": "2.1",
                "eventSource": "aws:s3",
                "awsRegion": "ap-northeast-2",
                "eventTime": "2025-11-05T00:12:01.414Z",
                "eventName": "ObjectCreated:Put",
                "userIdentity": {"principalId": "A1GXL1V1X4D2UB"},
                "requestParameters": {"sourceIPAddress": "1.209.174.122"},
                "responseElements": {
                    "x-amz-request-id": "6F2XG69B0CA0RTRA",
                    "x-amz-id-2": "ctzBkhDOjhP023D2doXS9UXv9rzkm6cpvkfgm9gh1ngE4D9Ce5+zg++BZievHstm84TbFALZHD1xHqWTzo4sAOiA7pd9gDK9TgBVWYy4utM=",
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
                        "key": "bills/2025/10/101/electronic.jpeg",
                        "size": 3076453,
                        "eTag": "447e0514ab8578c0c2d21e554d93314c",
                        "sequencer": "00690A96514FBFA4D0",
                    },
                },
            }
        ]
    }

    result = lambda_handler(test_event, None)
    print(f"Test result: {result}")
