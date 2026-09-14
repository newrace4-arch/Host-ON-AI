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
    # ⚠️ [v1.4] net_amount는 **요청에서 받지 않는다.** DB 생성 컬럼
    #    (GENERATED ALWAYS AS (gross_amount - fee_amount) STORED)이라
    #    INSERT에 실리는 순간 PostgreSQL이 거부한다. 이 클래스는
    #    reservation_service에서 Reservation(**payload.model_dump())로
    #    통째로 펼쳐지므로, 기본값 None이라도 필드가 남아 있으면
    #    model_dump()에 포함돼 예약 생성 경로 전체가 깨진다.
    #    응답(ReservationResponse)에는 그대로 남는다 — 읽기는 정상이다.
    #    gross/fee는 유지한다: 4절 정책 6이 서비스가 계산해 저장한다고 정했다.

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
    # 🔴 **기본값을 두지 않는다.** `= False`로 두면 계산을 빠뜨린 경로가
    #   조용히 `false`를 내보낸다. 4.4절이 *"서버가 매 조회 시 계산"*
    #   이라고 정했으므로, 필수로 두어 **채우지 않은 경로가 그 자리에서
    #   드러나게** 한다(봉투 `data`를 required로 둔 것과 같은 이유).
    is_conflict: bool

    @classmethod
    def from_model(cls, r, *, is_conflict: bool) -> "ReservationResponse":
        """ORM 객체 + 파생 필드 → 응답 DTO.

        `model_validate(r)`을 쓸 수 없다 — `is_conflict`는 **DB 컬럼이
        아니라** 서버가 계산하는 값이라 ORM 객체에 없다. 응답 생성
        경로를 이 하나로 묶어 두면 계산을 빠뜨릴 자리가 없다
        (`ChannelConnectionResponse.from_model`과 같은 이유).
        """
        return cls(
            reservation_id=r.reservation_id,
            property_id=r.property_id,
            room_id=r.room_id,
            bed_id=r.bed_id,
            channel_connection_id=r.channel_connection_id,
            guest_name=r.guest_name,
            check_in=r.check_in,
            check_out=r.check_out,
            reservation_status=r.reservation_status,
            refund_status=r.refund_status,
            financial_status=r.financial_status,
            gross_amount=r.gross_amount,
            fee_amount=r.fee_amount,
            net_amount=r.net_amount,
            is_conflict=is_conflict,
        )


class ReservationStatusUpdateRequest(BaseModel):
    """`PATCH /reservations/{id}/status` 요청 (api_contract 4.6절).

    **3필드 전부 Optional이다.** 보낸 필드만 바뀌고 보내지 않은 필드는
    그대로 둔다 — "보냈는지"는 `model_fields_set`으로 본다
    (`PropertyUpdateRequest`와 같은 패턴).

    엔드포인트를 3개로 쪼개지 않은 이유는 4.6절에 있다 — **환불+취소
    동시처리 시 트랜잭션이 2번 발생해 오히려 비효율**이다.

    **빈 본문(`{}`)은 에러가 아니다.** 바꿀 것이 없다는 뜻이므로 현재
    상태를 그대로 200으로 돌려준다(2.5절과 같은 규약).

    ⚠️ 세 상태는 **서로 독립 전이**다(state_events 1절 주석). 여기서
    함께 받는 것은 한 트랜잭션으로 묶기 위함이지 셋이 연동된다는
    뜻이 아니다.
    """

    reservation_status: ReservationStatus | None = None
    refund_status: RefundStatus | None = None
    financial_status: FinancialStatus | None = None
