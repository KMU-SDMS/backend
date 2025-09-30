"""
알림 관련 DTO 정의
"""

from typing import Optional
from dataclasses import dataclass
from .base_dto import BaseDTO


@dataclass
class SubscriptionDTO(BaseDTO):
    """FCM 구독 정보 DTO"""

    id: int
    fcm_token: str
    student_no: str
    is_active: bool
    platform: str
    created_at: str
    updated_at: str

    @classmethod
    def from_supabase_data(cls, data: dict) -> "SubscriptionDTO":
        """Supabase 응답 데이터를 DTO로 변환"""
        return cls(
            id=data.get("id"),
            fcm_token=data.get("fcm_token"),
            student_no=data.get("student_no"),
            is_active=data.get("is_active", False),
            platform=data.get("platform", "web"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


@dataclass
class SubscriptionCreateRequestDTO(BaseDTO):
    """FCM 구독 생성 요청 DTO"""

    fcm_token: str
    student_no: str
    platform: str = "web"

    def validate(self) -> tuple[bool, Optional[str]]:
        """요청 데이터 검증"""
        if not self.fcm_token or not self.fcm_token.strip():
            return False, "fcm_token is required"

        if not self.student_no or not self.student_no.strip():
            return False, "student_no is required"

        if self.platform not in ["web", "android", "ios"]:
            return False, "platform must be one of: web, android, ios"

        return True, None


@dataclass
class NotificationLogDTO(BaseDTO):
    """알림 발송 결과 로그 DTO"""

    id: int
    notice_id: int
    subscription_id: int
    status: str
    error_message: Optional[str]
    sent_at: str

    @classmethod
    def from_supabase_data(cls, data: dict) -> "NotificationLogDTO":
        """Supabase 응답 데이터를 DTO로 변환"""
        return cls(
            id=data.get("id"),
            notice_id=data.get("notice_id"),
            subscription_id=data.get("subscription_id"),
            status=data.get("status"),
            error_message=data.get("error_message"),
            sent_at=data.get("sent_at"),
        )
