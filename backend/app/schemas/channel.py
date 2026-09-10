"""채널 연동 Request/Response DTO (Pydantic v2, api_contract.md 3절).

응답에 **`ical_url` 원문을 절대 내보내지 않는다**(3절). Airbnb·Booking.com의
iCal export URL은 URL 자체가 자격증명이라, 값을 아는 사람은 인증 없이 예약
일정 전체를 읽을 수 있다. 그래서 응답 필드명을 `ical_url_masked`로 두어
프론트가 실제 URL로 착각해 링크로 걸거나 되돌려 보내는 실수까지 막는다.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import Channel, SyncStatus

# 마스킹 시 양끝에 남길 글자 수. 호스트가 "어느 URL인지" 알아볼 정도만 남긴다.
_MASK_HEAD = 8
_MASK_TAIL = 4


def mask_ical_url(url: str | None) -> str | None:
    """iCal URL을 사람이 식별만 할 수 있을 정도로 가린다.

    스킴+호스트 앞부분과 끝 몇 글자만 남기고 가운데를 `****`로 덮는다.
    원문 복원이 불가능해야 하므로 마스킹 길이를 원문 길이에 비례시키지
    않는다(길이 정보도 흘리지 않기 위함).
    """
    if not url:
        return None
    if len(url) <= _MASK_HEAD + _MASK_TAIL:
        return "****"
    return f"{url[:_MASK_HEAD]}****{url[-_MASK_TAIL:]}"


class ChannelConnectionCreateRequest(BaseModel):
    """POST /properties/{property_id}/channels 요청 (api_contract 3.2절)."""

    channel: Channel
    # DB에서는 nullable이지만 **API에서는 필수**다(3.2절). 컬럼이 nullable인
    #   것은 향후 iCal이 아닌 연동 방식을 위한 여지이고, 지금 이 엔드포인트의
    #   용도는 iCal URL 등록 하나뿐이다. URL 없이 만든 연결은 동기화 대상이
    #   없어 SYNCING으로 영원히 남는다.
    ical_url: str = Field(min_length=1)
    external_property_id: str | None = Field(default=None, max_length=100)

    @field_validator("ical_url")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("ical_url은 비어 있을 수 없습니다.")
        return v


class ChannelConnectionResponse(BaseModel):
    """채널 연결 1건. 목록(3.1절)과 생성 응답(3.2절)이 같은 구성을 쓴다."""

    model_config = ConfigDict(from_attributes=True)

    connection_id: int
    channel: Channel
    ical_url_masked: str | None
    external_property_id: str | None
    sync_status: SyncStatus
    last_synced_at: datetime | None
    last_error_message: str | None
    created_at: datetime

    @classmethod
    def from_model(cls, conn) -> "ChannelConnectionResponse":
        """ORM 객체 → 응답 DTO. `ical_url`은 여기서 마스킹돼 원문이 빠진다.

        `model_validate(conn)`을 직접 쓰지 않는 이유: 그 경로로는 마스킹이
        적용되지 않아 원문이 샐 수 있다. 응답 생성 경로를 이 하나로 묶는다.
        """
        return cls(
            connection_id=conn.connection_id,
            channel=conn.channel,
            ical_url_masked=mask_ical_url(conn.ical_url),
            external_property_id=conn.external_property_id,
            sync_status=conn.sync_status,
            # v1.3 운용 규칙: FAILED가 아니면 항상 null로 내려보낸다.
            #   DB에 남아 있더라도 지난 에러가 화면에 남지 않게 한다.
            last_error_message=(
                conn.last_error_message
                if conn.sync_status == SyncStatus.FAILED
                else None
            ),
            last_synced_at=conn.last_synced_at,
            created_at=conn.created_at,
        )


class SyncErrorResponse(BaseModel):
    """GET /channels/{connection_id}/sync-errors 응답 (api_contract 3절 v1.6).

    실패 이력을 누적하는 별도 테이블은 만들지 않는다 — `last_error_message`
    1건만 반환한다(범위확장 방지).
    """

    connection_id: int
    sync_status: SyncStatus
    last_synced_at: datetime | None
    last_error_message: str | None


class SyncResultResponse(BaseModel):
    """POST /channels/{connection_id}/sync 응답 (api_contract 3.3절).

    **건수를 사유별로 나눠 돌려준다.** 하나로 묶으면 호스트가 숫자를 보고도
    조치가 필요한지 아닌지 판단할 수 없다 — "이미 반영돼서 넘어간 것"과
    "객실을 몰라서 못 넣은 것"은 성격이 완전히 다르다.
    """

    connection_id: int
    sync_status: SyncStatus
    last_synced_at: datetime | None
    last_error_message: str | None

    # --- 예약 반영 단계 ---
    created_count: int          # 새로 만든 예약
    updated_count: int          # 기간·게스트명이 바뀌어 갱신
    unchanged_count: int        # 이미 반영돼 있고 변경 없음 — 정상
    skipped_no_room_count: int  # 객실 미지정(ROOM/BED 단위 숙소) — 구조적
    skipped_overlap_count: int  # 기간 겹침 — 처리 방침 미정의(r49)
    failed_count: int           # 예상 못 한 오류 — 서버 로그 확인 필요

    # --- 피드 파싱 단계(다른 층) ---
    invalid_event_count: int    # 필수 필드 누락 등으로 버려진 이벤트
