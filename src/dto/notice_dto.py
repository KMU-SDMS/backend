"""
공지사항 관련 DTO 클래스들을 정의합니다.
"""

from typing import Optional, List
from dataclasses import dataclass
from .base_dto import BaseDTO


@dataclass
class NoticeCreateRequestDTO(BaseDTO):
    """공지사항 생성 요청 DTO"""

    title: str
    content: str
    is_important: bool = False
    status: str = "PUBLISHED"

    def validate(self) -> tuple[bool, Optional[str]]:
        """요청 데이터 검증"""
        if not self.title or not self.title.strip():
            return False, "Title is required."
        if not self.content or not self.content.strip():
            return False, "Content is required."
        if self.status not in ["DRAFT", "SCHEDULED", "PUBLISHED"]:
            return False, "Status must be one of: DRAFT, SCHEDULED, PUBLISHED"
        return True, None


@dataclass
class NoticeDTO(BaseDTO):
    """공지사항 응답 DTO"""

    id: int
    title: str
    content: str
    date: str  # created_at → date 변환
    is_important: bool
    status: str

    @classmethod
    def from_supabase_data(cls, data: dict) -> "NoticeDTO":
        """Supabase 데이터에서 NoticeDTO 생성"""
        return cls(
            id=data["id"],
            title=data["title"],
            content=data["content"],
            date=data["created_at"],  # created_at → date 변환
            is_important=data["is_important"],
            status=data.get("status", "PUBLISHED"),  # 기본값 처리
        )


@dataclass
class PageInfoDTO(BaseDTO):
    """페이지 정보 DTO"""

    total_page: int
    total_notice: int
    now_page: int


@dataclass
class NoticeListDTO(BaseDTO):
    """공지사항 목록 응답 DTO"""

    notices: list[NoticeDTO]

    def to_dict(self) -> dict:
        """공지사항 목록을 딕셔너리 리스트로 변환"""
        return [notice.to_dict() for notice in self.notices]

    @classmethod
    def from_supabase_data(cls, data_list: list[dict]) -> "NoticeListDTO":
        """Supabase 데이터 리스트에서 NoticeListDTO 생성"""
        notices = [NoticeDTO.from_supabase_data(data) for data in data_list]
        return cls(notices=notices)


@dataclass
class NoticeListWithPageInfoDTO(NoticeListDTO):
    """페이지 정보가 포함된 공지사항 목록 응답 DTO (NoticeListDTO 상속)"""

    page_info: PageInfoDTO

    def to_dict(self) -> dict:
        """페이지 정보가 포함된 공지사항 목록을 딕셔너리로 변환"""
        return {"notices": super().to_dict(), "page_info": self.page_info.to_dict()}

    @classmethod
    def from_supabase_data(
        cls, data_list: list[dict], total_count: int, current_page: int, page_size: int
    ) -> "NoticeListWithPageInfoDTO":
        """Supabase 데이터와 페이지 정보에서 NoticeListWithPageInfoDTO 생성"""
        notices = [NoticeDTO.from_supabase_data(data) for data in data_list]

        # 페이지 정보 계산
        total_pages = (total_count + page_size - 1) // page_size  # 올림 계산

        page_info = PageInfoDTO(
            total_page=total_pages,
            total_notice=total_count,
            now_page=current_page,
        )

        return cls(notices=notices, page_info=page_info)


@dataclass
class NoticeDeleteRequestDTO(BaseDTO):
    """공지사항 삭제 요청 DTO"""

    id: int

    def validate(self) -> tuple[bool, Optional[str]]:
        """요청 데이터 검증"""
        if not isinstance(self.id, int) or self.id <= 0:
            return False, "ID must be a positive integer."
        return True, None


@dataclass
class NoticeUpdateRequestDTO(BaseDTO):
    """공지사항 수정 요청 DTO"""

    id: int
    title: str
    content: str
    is_important: bool = False
    status: Optional[str] = None

    def validate(self) -> tuple[bool, Optional[str]]:
        """요청 데이터 검증"""
        if not isinstance(self.id, int) or self.id <= 0:
            return False, "ID must be a positive integer."
        if not self.title or not self.title.strip():
            return False, "Title is required."
        if not self.content or not self.content.strip():
            return False, "Content is required."
        if self.status is not None and self.status not in [
            "DRAFT",
            "SCHEDULED",
            "PUBLISHED",
        ]:
            return False, "Status must be one of: DRAFT, SCHEDULED, PUBLISHED"
        return True, None


@dataclass
class NoticeFilterRequestDTO(BaseDTO):
    """공지사항 필터링 요청 DTO"""

    status: Optional[List[str]] = None
    is_important: Optional[bool] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    year: Optional[int] = None
    month: Optional[int] = None
    day: Optional[int] = None
    sort: str = "latest"
    page: int = 1
    search: Optional[str] = None

    def validate(self) -> tuple[bool, Optional[str]]:
        """요청 데이터 검증"""
        # status 검증
        if self.status is not None:
            valid_statuses = {"DRAFT", "SCHEDULED", "PUBLISHED"}
            for s in self.status:
                if s not in valid_statuses:
                    return (
                        False,
                        f"Invalid status: {s}. Must be one of: DRAFT, SCHEDULED, PUBLISHED",
                    )

        # sort 검증
        if self.sort not in ["latest", "oldest"]:
            return False, "Sort must be 'latest' or 'oldest'"

        # page 검증
        if not isinstance(self.page, int) or self.page < 1:
            return False, "Page must be a positive integer"

        # 날짜 범위 검증
        if self.start_date and self.end_date:
            try:
                from datetime import datetime

                start = datetime.strptime(self.start_date, "%Y-%m-%d")
                end = datetime.strptime(self.end_date, "%Y-%m-%d")
                if start > end:
                    return False, "start_date must be less than or equal to end_date"
            except ValueError:
                return False, "Date format must be YYYY-MM-DD"

        # 단일 날짜 파라미터 검증
        date_params = [self.year, self.month, self.day]
        date_params_count = sum(1 for p in date_params if p is not None)
        if date_params_count > 0 and date_params_count < 3:
            return False, "year, month, and day must all be provided together"

        if self.year is not None:
            if not (1 <= self.month <= 12):
                return False, "month must be between 1 and 12"
            if not (1 <= self.day <= 31):
                return False, "day must be between 1 and 31"

        return True, None
