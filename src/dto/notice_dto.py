"""
공지사항 관련 DTO 클래스들을 정의합니다.
"""

from typing import Optional
from dataclasses import dataclass
from .base_dto import BaseDTO


@dataclass
class NoticeCreateRequestDTO(BaseDTO):
    """공지사항 생성 요청 DTO"""

    title: str
    content: str
    is_important: bool = False

    def validate(self) -> tuple[bool, Optional[str]]:
        """요청 데이터 검증"""
        if not self.title or not self.title.strip():
            return False, "Title is required."
        if not self.content or not self.content.strip():
            return False, "Content is required."
        return True, None


@dataclass
class NoticeDTO(BaseDTO):
    """공지사항 응답 DTO"""

    id: int
    title: str
    content: str
    date: str  # created_at → date 변환
    is_important: bool

    @classmethod
    def from_supabase_data(cls, data: dict) -> "NoticeDTO":
        """Supabase 데이터에서 NoticeDTO 생성"""
        return cls(
            id=data["id"],
            title=data["title"],
            content=data["content"],
            date=data["created_at"],  # created_at → date 변환
            is_important=data["is_important"],
        )


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

    def validate(self) -> tuple[bool, Optional[str]]:
        """요청 데이터 검증"""
        if not isinstance(self.id, int) or self.id <= 0:
            return False, "ID must be a positive integer."
        if not self.title or not self.title.strip():
            return False, "Title is required."
        if not self.content or not self.content.strip():
            return False, "Content is required."
        return True, None
