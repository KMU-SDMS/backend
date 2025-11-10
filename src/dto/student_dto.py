"""
학생 관련 DTO 클래스들을 정의합니다.
"""

from typing import Optional
from dataclasses import dataclass
from .base_dto import BaseDTO


@dataclass
class StudentDTO(BaseDTO):
    """학생 응답 DTO"""

    name: str = ""
    studentIdNum: str = ""  # studentNo → studentIdNum 변환
    roomNumber: Optional[int] = None  # room_number → roomNumber 변환
    checkInDate: Optional[str] = None  # check_in_date → checkInDate 변환
    checkOutDate: Optional[str] = None  # check_out_date → checkOutDate 변환

    @classmethod
    def from_supabase_data(cls, data: dict) -> "StudentDTO":
        """Supabase 데이터에서 StudentDTO 생성"""
        return cls(
            name=data["name"],
            studentIdNum=data["studentNo"],  # studentNo → studentIdNum 변환
            roomNumber=data.get("room_number"),  # room_number → roomNumber 변환
            checkInDate=data.get("check_in_date"),  # check_in_date → checkInDate 변환
            checkOutDate=data.get(
                "check_out_date"
            ),  # check_out_date → checkOutDate 변환
        )


@dataclass
class StudentCreateRequestDTO(BaseDTO):
    """학생 생성 요청 DTO"""

    name: str
    studentIdNum: str
    roomNumber: Optional[int] = None
    checkInDate: Optional[str] = None
    checkOutDate: Optional[str] = None


@dataclass
class StudentUpdateRequestDTO(BaseDTO):
    """학생 수정 요청 DTO"""

    studentIdNum: str
    name: Optional[str] = None
    roomNumber: Optional[int] = None
    checkInDate: Optional[str] = None
    checkOutDate: Optional[str] = None


@dataclass
class StudentListDTO(BaseDTO):
    """학생 목록 응답 DTO"""

    students: list[StudentDTO]

    def to_dict(self) -> dict:
        """학생 목록을 딕셔너리 리스트로 변환"""
        return [student.to_dict() for student in self.students]

    @classmethod
    def from_supabase_data(cls, data_list: list[dict]) -> "StudentListDTO":
        """Supabase 데이터 리스트에서 StudentListDTO 생성"""
        students = [StudentDTO.from_supabase_data(data) for data in data_list]
        return cls(students=students)
