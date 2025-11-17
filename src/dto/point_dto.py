"""
상벌점 관련 DTO 클래스들을 정의합니다.
"""

from typing import Optional
from dataclasses import dataclass
from .base_dto import BaseDTO


@dataclass
class PointDTO(BaseDTO):
    """상벌점 응답 DTO"""

    id: int
    studentId: str  # student_no → studentId 변환
    type: str  # 'MERIT' 또는 'DEMERIT'
    score: int
    reason: str
    date: str  # YYYY-MM-DD 형식

    @classmethod
    def from_supabase_data(cls, data: dict) -> "PointDTO":
        """Supabase 데이터에서 PointDTO 생성"""
        return cls(
            id=data["id"],
            studentId=data["student_no"],  # student_no → studentId 변환
            type=data["type"],
            score=data["score"],
            reason=data["reason"],
            date=data["date"],
        )


@dataclass
class PointCreateRequestDTO(BaseDTO):
    """상벌점 부여 요청 DTO"""

    studentId: str
    type: str  # 'MERIT' 또는 'DEMERIT'
    score: int
    reason: str
    date: str  # YYYY-MM-DD 형식


@dataclass
class PointBulkCreateRequestDTO(BaseDTO):
    """상벌점 대량 부여 요청 DTO"""

    studentIds: list[str]
    type: str  # 'MERIT' 또는 'DEMERIT'
    score: int
    reason: str
    date: str  # YYYY-MM-DD 형식


@dataclass
class PointListDTO(BaseDTO):
    """상벌점 목록 응답 DTO"""

    points: list[PointDTO]

    def to_dict(self) -> dict:
        """상벌점 목록을 딕셔너리 리스트로 변환"""
        return [point.to_dict() for point in self.points]

    @classmethod
    def from_supabase_data(cls, data_list: list[dict]) -> "PointListDTO":
        """Supabase 데이터 리스트에서 PointListDTO 생성"""
        points = [PointDTO.from_supabase_data(data) for data in data_list]
        return cls(points=points)
