"""
외박 신청 관련 DTO 클래스들을 정의합니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .base_dto import BaseDTO


@dataclass
class OvernightStayCreateRequestDTO(BaseDTO):
    """외박 신청 생성 요청 DTO"""

    startDate: str
    endDate: str
    reason: str
    semester: str
    studentIdNum: Optional[str] = None

    def validate(self) -> tuple[bool, Optional[str]]:
        """요청 데이터 검증"""
        if not self.startDate or not self.startDate.strip():
            return False, "startDate is required."
        if not self.endDate or not self.endDate.strip():
            return False, "endDate is required."
        if not self.reason or not self.reason.strip():
            return False, "reason is required."
        if not self.semester or not self.semester.strip():
            return False, "semester is required."
        return True, None


@dataclass
class OvernightStayStatusUpdateRequestDTO(BaseDTO):
    """외박 신청 상태 변경 요청 DTO"""

    id: int
    status: str

    def validate(self) -> tuple[bool, Optional[str]]:
        """요청 데이터 검증"""
        if not isinstance(self.id, int) or self.id <= 0:
            return False, "id must be a positive integer."
        if self.status not in {"approved", "rejected"}:
            return False, "status must be either 'approved' or 'rejected'."
        return True, None


@dataclass
class OvernightStayDTO(BaseDTO):
    """외박 신청 응답 DTO"""

    id: int
    studentIdNum: str
    startDate: str
    endDate: str
    reason: str
    status: str
    semester: str
    createdAt: str
    studentName: Optional[str] = None
    roomNumber: Optional[int] = None

    @classmethod
    def from_supabase_data(cls, data: dict) -> "OvernightStayDTO":
        """Supabase 데이터에서 OvernightStayDTO 생성"""
        return cls(
            id=data["id"],
            studentIdNum=data["student_no"],
            startDate=data["start_date"],
            endDate=data["end_date"],
            reason=data["reason"],
            status=data["status"],
            semester=data["semester"],
            createdAt=data["created_at"],
            studentName=data.get("student_name"),
            roomNumber=data.get("room_number"),
        )


@dataclass
class OvernightStaySummaryDTO(BaseDTO):
    """외박 신청 요약 정보 DTO"""

    currentSemester: str
    approvedCount: int
    remainingCount: int


@dataclass
class OvernightStayStudentListDTO(BaseDTO):
    """학생용 외박 신청 목록 DTO"""

    data: list[OvernightStayDTO]
    summary: OvernightStaySummaryDTO

    def to_dict(self) -> dict:
        return {
            "data": [item.to_dict() for item in self.data],
            "summary": self.summary.to_dict(),
        }

    @classmethod
    def from_supabase_data(
        cls,
        data_list: list[dict],
        summary: OvernightStaySummaryDTO,
    ) -> "OvernightStayStudentListDTO":
        """Supabase 데이터와 요약 정보에서 DTO 생성"""
        stays = [OvernightStayDTO.from_supabase_data(data) for data in data_list]
        return cls(data=stays, summary=summary)


@dataclass
class OvernightStayPageInfoDTO(BaseDTO):
    """외박 신청 페이지 정보 DTO"""

    page: int
    pageSize: int
    totalItems: int
    totalPages: int


@dataclass
class OvernightStayAdminListDTO(BaseDTO):
    """사감용 외박 신청 목록 DTO"""

    data: list[OvernightStayDTO]
    pageInfo: OvernightStayPageInfoDTO
    total: int

    def to_dict(self) -> dict:
        return {
            "data": [item.to_dict() for item in self.data],
            "pageInfo": self.pageInfo.to_dict(),
            "total": self.total,
        }

    @classmethod
    def from_supabase_data(
        cls,
        data_list: list[dict],
        total_items: int,
        page: int,
        page_size: int,
    ) -> "OvernightStayAdminListDTO":
        """Supabase 데이터와 페이지 정보에서 DTO 생성"""
        stays = [OvernightStayDTO.from_supabase_data(data) for data in data_list]
        total_pages = (total_items + page_size - 1) // page_size if page_size else 1
        page_info = OvernightStayPageInfoDTO(
            page=page,
            pageSize=page_size,
            totalItems=total_items,
            totalPages=total_pages,
        )
        return cls(data=stays, pageInfo=page_info, total=total_items)
