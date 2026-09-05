"""DB명세서 v1.3 1절의 ENUM 타입 정의 (16개 테이블 공용).

- 파이썬 Enum의 **value**가 곧 PostgreSQL ENUM 라벨이다.
- SQLAlchemy Enum 인스턴스를 모듈 레벨에서 1개만 만들어 여러 모델이
  공유한다(같은 타입을 두 번 CREATE TYPE 하지 않기 위함).
- 명세서에 없는 값을 임의로 추가하지 않는다.
"""

import enum

from sqlalchemy import Enum as SAEnum


class AccommodationType(str, enum.Enum):
    URBAN_HOMESTAY = "URBAN_HOMESTAY"
    RURAL_HOMESTAY = "RURAL_HOMESTAY"
    HANOK = "HANOK"
    HOSTEL = "HOSTEL"
    LODGING_FACILITY = "LODGING_FACILITY"
    GENERAL_LODGING = "GENERAL_LODGING"


class BookableUnitType(str, enum.Enum):
    PROPERTY = "PROPERTY"
    ROOM = "ROOM"
    BED = "BED"


class Channel(str, enum.Enum):
    AIRBNB = "AIRBNB"
    BOOKING_COM = "BOOKING_COM"
    NAVER = "NAVER"


class SyncStatus(str, enum.Enum):
    SYNCING = "SYNCING"
    SYNCED = "SYNCED"
    FAILED = "FAILED"
    STALE = "STALE"


class ReservationStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    MODIFIED = "MODIFIED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class RefundStatus(str, enum.Enum):
    NONE = "NONE"
    PARTIAL = "PARTIAL"
    FULL = "FULL"


class FinancialStatus(str, enum.Enum):
    ESTIMATED = "ESTIMATED"
    CONFIRMED = "CONFIRMED"
    MANUALLY_ADJUSTED = "MANUALLY_ADJUSTED"


class FeeType(str, enum.Enum):
    SPLIT_FEE = "SPLIT_FEE"
    SINGLE_FEE = "SINGLE_FEE"


class TaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    VERIFIED = "VERIFIED"
    ISSUE = "ISSUE"


class InquiryRiskLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ActionRiskLevel(str, enum.Enum):
    """ACTION_ITEMS 전용 — 법적/안전 위험도가 아니라 **운영 처리 우선순위**.

    명세서 4절 1번: RED_NOW는 "체크인 임박 + 청소 미완료" 같은 시간·상태
    기반 규칙일 뿐이며, AI가 게스트 위험도를 판단하는 것이 아니다.
    """

    RED_NOW = "RED_NOW"
    YELLOW_TODAY = "YELLOW_TODAY"
    GREEN_AUTO = "GREEN_AUTO"


class ActionStatus(str, enum.Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    AUTO_RESOLVED = "AUTO_RESOLVED"


class ApprovalStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class DocumentType(str, enum.Enum):
    HOUSE_RULE = "HOUSE_RULE"
    POLICY = "POLICY"
    FAQ = "FAQ"


class RenewalTriggerType(str, enum.Enum):
    NONE = "NONE"
    EXPIRATION_BASED = "EXPIRATION_BASED"
    EVENT_BASED = "EVENT_BASED"


def _pg_enum(py_enum: type[enum.Enum], type_name: str) -> SAEnum:
    """파이썬 Enum → PostgreSQL ENUM 타입(라벨은 value 기준)."""
    return SAEnum(
        py_enum,
        name=type_name,
        values_callable=lambda e: [member.value for member in e],
        create_type=True,
    )


accommodation_type_enum = _pg_enum(AccommodationType, "accommodation_type_enum")
bookable_unit_type_enum = _pg_enum(BookableUnitType, "bookable_unit_type_enum")
channel_enum = _pg_enum(Channel, "channel_enum")
sync_status_enum = _pg_enum(SyncStatus, "sync_status_enum")
reservation_status_enum = _pg_enum(ReservationStatus, "reservation_status_enum")
refund_status_enum = _pg_enum(RefundStatus, "refund_status_enum")
financial_status_enum = _pg_enum(FinancialStatus, "financial_status_enum")
fee_type_enum = _pg_enum(FeeType, "fee_type_enum")
task_status_enum = _pg_enum(TaskStatus, "task_status_enum")
inquiry_risk_level_enum = _pg_enum(InquiryRiskLevel, "inquiry_risk_level_enum")
action_risk_level_enum = _pg_enum(ActionRiskLevel, "action_risk_level_enum")
action_status_enum = _pg_enum(ActionStatus, "action_status_enum")
approval_status_enum = _pg_enum(ApprovalStatus, "approval_status_enum")
document_type_enum = _pg_enum(DocumentType, "document_type_enum")
renewal_trigger_type_enum = _pg_enum(RenewalTriggerType, "renewal_trigger_type_enum")
