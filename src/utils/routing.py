from typing import Any, Dict, Tuple


# 규칙 기반 라우팅 매핑
# 1) 모듈 매핑: 첫 세그먼트 → 핸들러 모듈
MODULE_MAP: Dict[str, str] = {
    "rooms": "rooms_handler",
    "notices": "notices_handler",
    "notice": "notices_handler",
    "students": "students_handler",
    "student": "students_handler",
    "calendar": "calendar_handler",
    "bill": "bill_handler",
    "subscriptions": "subscriptions_handler",
    "notifications": "notifications_handler",
    "overnight-stay": "overnight_stays_handler",
    "overnight-stays": "overnight_stays_handler",
}

# 2) 예외 라우팅: (METHOD, path_after_api)
ROUTE_OVERRIDES: Dict[Tuple[str, str], Tuple[str, str]] = {
    ("GET", "student"): ("students_handler", "get_by_student_no"),
    ("POST", "bill/presign"): ("bill_handler", "presign"),
    ("GET", "bill/image"): ("bill_handler", "get_image"),
    ("GET", "bill/paid/image"): ("bill_handler", "get_paid_bill_image"),
    ("POST", "subscriptions"): ("subscriptions_handler", "create_subscription_handler"),
    ("GET", "subscriptions/status"): (
        "subscriptions_handler",
        "get_subscription_status_handler",
    ),
    ("PATCH", "subscriptions"): (
        "subscriptions_handler",
        "patch_subscription_handler",
    ),
    ("POST", "notifications"): (
        "notifications_handler",
        "send_notification_handler",
    ),
    ("POST", "notifications/individual"): (
        "notifications_handler",
        "send_individual_notification_handler",
    ),
    ("GET", "notices/filter"): ("notices_handler", "filter"),
}

# 3) 기본 함수 규칙: (METHOD, resource) → function name
DEFAULT_FUNC_RULES: Dict[Tuple[str, str], str] = {
    # collections
    ("GET", "rooms"): "get_all",
    ("GET", "notices"): "get_paginated",
    ("GET", "students"): "get_students",
    ("GET", "calendar"): "get_all",
    ("POST", "calendar"): "create",
    ("PUT", "calendar"): "update",
    ("DELETE", "calendar"): "delete",
    # singular resources
    ("GET", "notice"): "get_one",
    ("POST", "notice"): "create",
    ("PUT", "notice"): "update",
    ("DELETE", "notice"): "delete",
    ("POST", "student"): "create",
    ("PUT", "student"): "update",
    ("DELETE", "student"): "delete",
    ("POST", "overnight-stay"): "create",
    ("GET", "overnight-stay"): "get_student_requests",
    ("GET", "overnight-stays"): "get_admin_requests",
    ("PATCH", "overnight-stays"): "update_status",
}


def resolve_handler(
    path: str, method: str
) -> Tuple[Tuple[str, str] | None, Dict[str, Any]]:
    # 정규화
    method_u = (method or "").upper()
    normalized = (path or "").rstrip("/")
    if normalized.startswith("/api"):
        normalized = normalized[len("/api") :]
    normalized = normalized.lstrip("/")

    # 빈 경로면 미매핑
    if not normalized:
        return None, {}

    # 예외 우선
    key = (method_u, normalized)
    override = ROUTE_OVERRIDES.get(key)
    if override:
        module_name, func_name = override
        return (module_name, func_name), {}

    # 세그먼트 기반 기본 규칙
    segments = [seg for seg in normalized.split("/") if seg]
    if not segments:
        return None, {}

    # 세그먼트가 2개 이상이면 기본 규칙으로는 처리하지 않음(오버라이드 필요)
    if len(segments) >= 2:
        return None, {}

    resource = segments[0]
    module_name = MODULE_MAP.get(resource)
    if not module_name:
        return None, {}

    func_name = DEFAULT_FUNC_RULES.get((method_u, resource))
    if not func_name:
        return None, {}

    return (module_name, func_name), {}
