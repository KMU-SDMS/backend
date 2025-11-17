"""
점호 관련 DTO 클래스들을 정의합니다.
"""

from typing import Optional
from dataclasses import dataclass
from .base_dto import BaseDTO


@dataclass
class RollcallDTO(BaseDTO):
    """점호 기록 응답 DTO"""

    id: int
    studentId: str  # student_no → studentId 변환
    date: str  # YYYY-MM-DD 형식
    present: bool
    note: Optional[str] = None

    @classmethod
    def from_supabase_data(cls, data: dict) -> "RollcallDTO":
        """Supabase 데이터에서 RollcallDTO 생성"""
        return cls(
            id=data["id"],
            studentId=data["student_no"],  # student_no → studentId 변환
            date=data["date"],
            present=data["present"],
            note=data.get("note"),
        )


@dataclass
class RollcallCreateRequestDTO(BaseDTO):
    """점호 생성/수정 요청 DTO"""

    studentId: str
    date: str  # YYYY-MM-DD 형식
    present: bool
    note: Optional[str] = None


@dataclass
class RollcallUpdateRequestDTO(BaseDTO):
    """점호 부분 수정 요청 DTO"""

    id: int
    present: Optional[bool] = None
    note: Optional[str] = None


@dataclass
class RollcallListDTO(BaseDTO):
    """점호 목록 응답 DTO"""

    rollcalls: list[RollcallDTO]

    def to_dict(self) -> dict:
        """점호 목록을 딕셔너리 리스트로 변환"""
        return [rollcall.to_dict() for rollcall in self.rollcalls]

    @classmethod
    def from_supabase_data(cls, data_list: list[dict]) -> "RollcallListDTO":
        """Supabase 데이터 리스트에서 RollcallListDTO 생성"""
        rollcalls = [RollcallDTO.from_supabase_data(data) for data in data_list]
        return cls(rollcalls=rollcalls)
