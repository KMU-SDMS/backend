"""
점호 관련 DTO 클래스들을 정의합니다.
"""

from typing import Optional
from dataclasses import dataclass, fields
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

    @classmethod
    def from_dict(cls, data: dict) -> "RollcallCreateRequestDTO":
        """딕셔너리에서 DTO 생성 및 검증"""
        # 허용된 필드만 있는지 검증 (클래스 필드에서 동적으로 가져옴)
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
        if not self.studentId or not self.studentId.strip():
            raise ValueError("studentId is required.")

        if not self.date or not self.date.strip():
            raise ValueError("date is required.")

        # 날짜 형식 검증 (YYYY-MM-DD)
        date_pattern = r"^\d{4}-\d{2}-\d{2}$"
        if not re.match(date_pattern, self.date):
            raise ValueError("Date must be in YYYY-MM-DD format.")

        # present 필드 검증 (bool 타입이어야 함)
        if not isinstance(self.present, bool):
            raise ValueError("present must be a boolean value.")


@dataclass
class RollcallUpdateRequestDTO(BaseDTO):
    """점호 부분 수정 요청 DTO"""

    id: int
    present: Optional[bool] = None
    note: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "RollcallUpdateRequestDTO":
        """딕셔너리에서 DTO 생성 및 검증"""
        # 허용된 필드만 있는지 검증 (클래스 필드에서 동적으로 가져옴)
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
        # ID 검증
        if not isinstance(self.id, int) or self.id <= 0:
            raise ValueError("ID must be a positive integer.")


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
