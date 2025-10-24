"""
캘린더 관련 DTO 클래스들을 정의합니다.
"""

from typing import Optional
from dataclasses import dataclass
from .base_dto import BaseDTO


@dataclass
class CalendarDTO(BaseDTO):
    """캘린더 응답 DTO"""

    id: int
    date: str  # YYYY-MM-DD 형식
    rollCallType: Optional[str]  # roll_call_type -> rollCallType 변환
    paymentType: Optional[str]  # payment_type -> paymentType 변환

    @classmethod
    def from_supabase_data(cls, data: dict) -> "CalendarDTO":
        """Supabase 데이터에서 CalendarDTO 생성"""
        return cls(
            id=data["id"],
            date=str(data["date"]),  # date는 문자열로 유지
            rollCallType=data.get("roll_call_type"),  # roll_call_type -> rollCallType
            paymentType=data.get("payment_type"),  # payment_type -> paymentType
        )


@dataclass
class CalendarListDTO(BaseDTO):
    """캘린더 목록 응답 DTO"""

    items: list[CalendarDTO]

    def to_dict(self) -> list:
        """캘린더 목록을 딕셔너리 리스트로 변환"""
        return [item.to_dict() for item in self.items]

    @classmethod
    def from_supabase_data(cls, data_list: list[dict]) -> "CalendarListDTO":
        """Supabase 데이터 리스트에서 CalendarListDTO 생성"""
        items = [CalendarDTO.from_supabase_data(data) for data in data_list]
        return cls(items=items)


@dataclass
class CalendarCreateRequestDTO(BaseDTO):
    """캘린더 생성 요청 DTO"""

    date: str  # YYYY-MM-DD 형식
    rollCallType: Optional[str] = None  # nullable로 변경
    paymentType: Optional[str] = None  # nullable로 변경

    def validate(self) -> tuple[bool, Optional[str]]:
        """요청 데이터 검증"""
        if not self.date or not self.date.strip():
            return False, "Date is required."

        # 날짜 형식 검증 (YYYY-MM-DD)
        import re

        date_pattern = r"^\d{4}-\d{2}-\d{2}$"
        if not re.match(date_pattern, self.date):
            return False, "Date must be in YYYY-MM-DD format."

        return True, None


@dataclass
class CalendarUpdateRequestDTO(BaseDTO):
    """캘린더 수정 요청 DTO"""

    id: int
    date: Optional[str] = None  # YYYY-MM-DD 형식
    rollCallType: Optional[str] = None
    paymentType: Optional[str] = None

    def validate(self) -> tuple[bool, Optional[str]]:
        """요청 데이터 검증"""
        if not isinstance(self.id, int) or self.id <= 0:
            return False, "ID must be a positive integer."

        # 날짜 형식 검증 (제공된 경우에만)
        if self.date is not None:
            import re

            date_pattern = r"^\d{4}-\d{2}-\d{2}$"
            if not re.match(date_pattern, self.date):
                return False, "Date must be in YYYY-MM-DD format."

        return True, None
