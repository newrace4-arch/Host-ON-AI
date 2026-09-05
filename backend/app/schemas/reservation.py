"""예약 Request/Response DTO (Pydantic v2).

⚠️ 여기서 하는 검증은 **같은 요청 안에서 확인 가능한 형태(shape)까지**다.
`Property.bookable_unit_type`과의 교차 일치는 다른 테이블 값을 봐야 하므로
반드시 서비스 레이어(reservation_service)에서 한 번 더 검증한다
(troubleshooting.md 2번: DB CHECK도, Pydantic도 단독으로는 못 잡는 영역).
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import FinancialStatus, RefundStatus, ReservationStatus


class ReservationCreateRequest(BaseModel):
    """예약 생성 요청(iCal 동기화 / 수동 등록 공용)."""

    property_id: int
    room_id: int | None = None
    bed_id: int | None = None
    channel_connection_id: int
    external_uid: str | None = Field(default=None, max_length=150)
    guest_name: str | None = Field(default=None, max_length=100)
    guest_language: str | None = Field(default=None, max_length=10)
    check_in: date
    check_out: date
    booked_at: datetime | None = None
    reservation_status: ReservationStatus = ReservationStatus.CONFIRMED
    gross_amount: int | None = None
    fee_amount: int | None = None
    net_amount: int | None = None

    @model_validator(mode="after")
    def _validate_shape(self) -> "ReservationCreateRequest":
        # DB CHECK(ck_reservations_unit_shape)와 동일한 규칙을 입력단에서 먼저 거른다.
        #   유효 조합 3가지: (NULL,NULL) / (room,NULL) / (room,bed)
        if self.bed_id is not None and self.room_id is None:
            raise ValueError("bed_id를 지정하려면 room_id도 함께 지정해야 합니다.")
        if self.check_out <= self.check_in:
            raise ValueError("check_out은 check_in보다 뒤여야 합니다.")
        return self


class ReservationResponse(BaseModel):
    """예약 응답. `is_conflict`는 DB 컬럼이 아니라 조회 시 계산되는 파생 필드다."""

    model_config = ConfigDict(from_attributes=True)

    reservation_id: int
    property_id: int
    room_id: int | None
    bed_id: int | None
    channel_connection_id: int
    guest_name: str | None
    check_in: date
    check_out: date
    reservation_status: ReservationStatus
    refund_status: RefundStatus
    financial_status: FinancialStatus
    gross_amount: int | None
    fee_amount: int | None
    # ⚠️ 예약 건별 실수령액은 net_amount다. net_payout은 월정산 컬럼명이므로
    #    예약 응답에 쓰지 않는다(api_contract.md v1.6 정정).
    net_amount: int | None
    is_conflict: bool = False
