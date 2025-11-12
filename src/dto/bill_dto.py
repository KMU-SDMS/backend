"""
관리비(Bill) 관련 DTO 클래스들을 정의합니다.
"""

from typing import Optional, Any
from dataclasses import dataclass
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

    @classmethod
    def from_supabase_data(cls, data: dict) -> "BillDTO":
        """Supabase row(snake_case) -> DTO(camelCase) 매핑"""
        return cls(
            id=data.get("id"),
            studentNo=data.get("student_no", ""),
            type=data.get("type", ""),
            amount=data.get("amount"),
            endDate=(
                str(data.get("end_date")) if data.get("end_date") is not None else None
            ),
            bankInfo=data.get("bank_info"),
        )


@dataclass
class BillListDTO(BaseDTO):
    """관리비 목록 응답 DTO"""

    items: list[BillDTO]

    def to_dict(self) -> list[dict[str, Any]]:
        return [item.to_dict() for item in self.items]

    @classmethod
    def from_supabase_data(cls, rows: list[dict]) -> "BillListDTO":
        return cls(items=[BillDTO.from_supabase_data(row) for row in rows])
