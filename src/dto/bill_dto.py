"""
관리비(Bill) 관련 DTO 클래스들을 정의합니다.
"""

from typing import Optional, Any
from dataclasses import dataclass, fields
from .base_dto import BaseDTO


@dataclass
class BillDTO(BaseDTO):
    """단일 관리비 응답 DTO"""

    id: Optional[int]
    studentNo: str
    type: str
    amount: Optional[float]
    endDate: Optional[str]  # YYYY-MM-DD
    bankInfo: Optional[list[dict[str, Optional[str]]]]
    is_paid: Optional[bool]

    @classmethod
    def from_supabase_data(cls, data: dict) -> "BillDTO":
        """Supabase row(snake_case) -> DTO(camelCase) 매핑"""
        return cls(
            id=data.get("id"),
            studentNo=data.get("student_no", ""),
            type=data.get("type", ""),
            amount=data.get("amount"),
            endDate=data.get("calendar").get("date"),
            bankInfo=data.get("bank_info"),
            is_paid=data.get("is_paid"),
        )


@dataclass
class BillListDTO(BaseDTO):
    """관리비 목록 응답 DTO"""

    items: list[BillDTO]

    def to_dict(self) -> dict[str, list[dict[str, Any]]]:
        """학번을 키로 하는 딕셔너리 형태로 변환"""
        result: dict[str, list[dict[str, Any]]] = {}
        for item in self.items:
            student_no = item.studentNo
            if student_no not in result:
                result[student_no] = []
            result[student_no].append(item.to_dict())
        return result

    @classmethod
    def from_supabase_data(cls, rows: list[dict]) -> "BillListDTO":
        return cls(items=[BillDTO.from_supabase_data(row) for row in rows])


@dataclass
class BillPresignRequestDTO(BaseDTO):
    """관리비 이미지 업로드 presign 요청 DTO"""

    contentType: str
    ext: Optional[str] = None
    roomId: str = ""
    type: str = ""
    year: str = ""
    month: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "BillPresignRequestDTO":
        """딕셔너리에서 DTO 생성 및 검증"""
        # 허용된 필드만 있는지 검증
        allowed_fields = {field.name for field in fields(cls)}
        extra_fields = set(data.keys()) - allowed_fields
        if extra_fields:
            allowed_fields_str = ", ".join(sorted(allowed_fields))
            raise ValueError(
                f"Invalid fields: {', '.join(sorted(extra_fields))}. Allowed fields: {allowed_fields_str}."
            )

        # 부모 클래스의 from_dict를 호출하여 인스턴스 생성
        instance = super().from_dict(data)

        # 추가 검증 수행
        instance.validate()

        return instance

    def validate(self) -> None:
        """요청 데이터 검증"""
        import re

        # 필수 필드 검증
        if not self.contentType or not self.contentType.strip():
            raise ValueError("contentType is required.")

        if not self.roomId or not self.roomId.strip():
            raise ValueError("roomId is required.")

        if not self.type or not self.type.strip():
            raise ValueError("type is required.")

        if self.type not in ["water", "electricity", "gas"]:
            raise ValueError("type must be one of: water, electricity, gas")

        if not self.year or not self.year.strip():
            raise ValueError("year is required.")

        # 연도 형식 검증 (YYYY)
        year_pattern = r"^\d{4}$"
        if not re.match(year_pattern, self.year):
            raise ValueError("year must be in YYYY format.")

        if not self.month or not self.month.strip():
            raise ValueError("month is required.")

        # 월 형식 검증 (MM)
        month_pattern = r"^\d{2}$"
        if not re.match(month_pattern, self.month):
            raise ValueError("month must be in MM format.")

        # 월 범위 검증 (01-12)
        month_int = int(self.month)
        if month_int < 1 or month_int > 12:
            raise ValueError("month must be between 01 and 12.")
