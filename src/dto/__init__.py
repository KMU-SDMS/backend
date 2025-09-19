# DTO 패키지 초기화 파일
from .base_dto import BaseDTO, ErrorDTO, SuccessDTO
from .room_dto import RoomDTO, RoomListDTO
from .notice_dto import (
    NoticeDTO,
    NoticeListDTO,
    NoticeCreateRequestDTO,
    NoticeDeleteRequestDTO,
    NoticeUpdateRequestDTO,
    NoticeListWithPageInfoDTO,
)
from .student_dto import StudentDTO, StudentListDTO
from .calendar_dto import (
    CalendarDTO,
    CalendarListDTO,
    CalendarCreateRequestDTO,
    CalendarUpdateRequestDTO,
)

__all__ = [
    "BaseDTO",
    "ErrorDTO",
    "SuccessDTO",
    "RoomDTO",
    "RoomListDTO",
    "NoticeDTO",
    "NoticeListDTO",
    "NoticeCreateRequestDTO",
    "NoticeDeleteRequestDTO",
    "NoticeUpdateRequestDTO",
    "NoticeListWithPageInfoDTO",
    "StudentDTO",
    "StudentListDTO",
    "CalendarDTO",
    "CalendarListDTO",
    "CalendarCreateRequestDTO",
    "CalendarUpdateRequestDTO",
]
