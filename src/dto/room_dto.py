"""
호실 관련 DTO 클래스들을 정의합니다.
"""

from typing import Optional
from dataclasses import dataclass
from .base_dto import BaseDTO


@dataclass
class RoomDTO(BaseDTO):
    """호실 응답 DTO"""

    id: int
    name: str
    floor: int
    headcount: int

    @classmethod
    def from_supabase_data(cls, data: dict) -> "RoomDTO":
        """Supabase 데이터에서 RoomDTO 생성"""
        return cls(
            id=data["id"],
            name=data["room_number"],  # room_number → name 변환
            floor=data["floor"],
            headcount=data["capacity"],  # capacity → headcount 변환
        )


@dataclass
class RoomListDTO(BaseDTO):
    """호실 목록 응답 DTO"""

    rooms: list[RoomDTO]

    def to_dict(self) -> dict:
        """호실 목록을 딕셔너리 리스트로 변환"""
        return [room.to_dict() for room in self.rooms]

    @classmethod
    def from_supabase_data(cls, data_list: list[dict]) -> "RoomListDTO":
        """Supabase 데이터 리스트에서 RoomListDTO 생성"""
        rooms = [RoomDTO.from_supabase_data(data) for data in data_list]
        return cls(rooms=rooms)
