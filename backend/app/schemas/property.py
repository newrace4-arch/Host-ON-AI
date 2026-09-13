"""숙소/객실/침대 Request·Response DTO (Pydantic v2, api_contract.md 2절).

## 🔴 목록과 상세를 **다른 타입**으로 둔다

`GET /properties`는 **4필드**, `GET /properties/{id}`와 `POST /properties`는
**11필드**다. 2.3절이 이 차이를 의도된 것으로 못박고 있다 — 목록은
`PropertySwitcher` 드롭다운의 *입력*이라 그 이상이 필요 없고, 상세는
`/settings` 화면이 그리는 숙소 정보 전체다.

하나로 묶으면 **양방향으로 깨진다.** 목록 타입으로 등록 응답을 받으면
`base_price`·`checkin_time` 같은 7필드를 읽지 못하고, 상세 타입으로 목록을
받으면 없는 필드를 있다고 가정한다(2.3절).

**클래스 이름이 프론트 타입 이름을 결정한다.** FastAPI가 Pydantic 클래스명을
그대로 OpenAPI 스키마 이름으로 쓰고, `npm run generate-api`가 그것으로
`types/api.ts`를 만든다. api_contract 2.3절이 프론트에 요구한 이름이
`PropertySummary`/`PropertyDetail`이므로 **`Response` 접미사만 붙여** 둘이
그대로 이어지게 한다.

## 응답에 넣지 않는 것

`host_id` — JWT가 이미 소유자를 결정하므로 클라이언트가 쓸 일이 없고,
내보내면 다른 호스트의 id 공간을 추론할 단서가 된다(2.3절).
`created_at` — 등록 시각을 쓰는 화면이 없다(2.1·2.3절).
객실·침대 목록 — 별도 엔드포인트가 있으며, 중첩해 돌려주면 같은 데이터가
두 경로로 나가 한쪽만 갱신되는 상태가 생긴다(2.4절).
"""

from __future__ import annotations

from datetime import time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from app.models.enums import AccommodationType, BookableUnitType

# `PATCH`에서 **명시적 `null`을 허용하는** 필드. DB가 nullable인 둘뿐이며,
#   여기에 `null`을 보내는 것은 *"값을 지운다"*는 뜻이다(2.5절).
#   나머지는 `NOT NULL` 컬럼이라 `null`이 곧 형식 오류다.
_NULLABLE_ON_PATCH = frozenset({"address", "lower_bound_price"})


class PropertyCreateRequest(BaseModel):
    """`POST /properties` 요청 (api_contract 2절 요청 예시 + 2.3절).

    **`host_id`를 받지 않는다.** 소유자는 JWT가 결정한다 — 본문으로 받으면
    남의 id를 적어 보내는 순간 다른 호스트 앞으로 숙소가 생긴다.

    `name`·`accommodation_type`·`bookable_unit_type`은 DB에서 `NOT NULL`이라
    **요청에서도 필수**다. 누락하면 FastAPI의 본문 검증에 걸려
    `400 VALIDATION_ERROR`가 된다(2.3절 말미).

    나머지는 전부 생략 가능하며 **생략하면 DB 기본값**으로 채워진다 —
    `base_price` `0`, `checkin_time` `"15:00"`, `checkout_time` `"11:00"`,
    두 스위치 `true`, `address`·`lower_bound_price`는 `null`(2.3절).

    ⚠️ **`base_price`에 범위 제약을 걸지 않는다.** `0`이 "미설정"이라는
    것은 2.3절이 정했지만 **하한·상한은 어느 문서에도 없고 DB에도 CHECK가
    없다**(`properties`의 CHECK는 0건 — 9/14 실측). 스펙에 없는 규칙을
    구현이 만들지 않는다. `lower_bound_price`와의 대소 관계도 같은
    이유로 검사하지 않는다(devlog 9/13 이월 — 9/24 확정).
    """

    name: str = Field(min_length=1, max_length=150)
    accommodation_type: AccommodationType
    bookable_unit_type: BookableUnitType
    address: str | None = Field(default=None, max_length=255)
    base_price: int | None = None
    lower_bound_price: int | None = None
    checkin_time: time | None = None
    checkout_time: time | None = None
    weekday_adjustment_enabled: bool | None = None
    holiday_adjustment_enabled: bool | None = None


class PropertyUpdateRequest(BaseModel):
    """`PATCH /properties/{id}` 요청 (api_contract 2.5절).

    **부분 수정이라 모든 필드가 Optional이다.** 보낸 필드만 바뀌고 보내지
    않은 필드는 그대로 둔다 — "보냈는지"는 `model_fields_set`으로 본다.
    값이 `None`인 것과 아예 보내지 않은 것을 구분해야 하기 때문이다.

    🔴 **`accommodation_type`·`bookable_unit_type`을 스키마에서 빼지
    않는다.** 빼면 Pydantic이 **모르는 필드로 조용히 무시**해 2.5절이
    요구한 `400 IMMUTABLE_FIELD`가 나가지 않는다. 필드를 두고
    **서비스가 거부**하는 형태여야 한다.

    ⚠️ 그 둘의 타입이 `Any`인 것도 같은 이유다. `AccommodationType`으로
    두면 잘못된 값을 보냈을 때 Pydantic이 먼저 걸어 `VALIDATION_ERROR`가
    나간다 — **바꿀 수 없는 필드인데 "값이 틀렸다"고 답하는 셈**이라
    프론트가 입력을 비활성화하지 못한다. 어떤 값이 와도 같은
    `IMMUTABLE_FIELD`여야 한다.
    """

    model_config = ConfigDict(extra="ignore")

    name: str | None = Field(default=None, min_length=1, max_length=150)
    address: str | None = Field(default=None, max_length=255)
    base_price: int | None = None
    lower_bound_price: int | None = None
    checkin_time: time | None = None
    checkout_time: time | None = None
    weekday_adjustment_enabled: bool | None = None
    holiday_adjustment_enabled: bool | None = None

    # 수정 불가 2필드 — 값이 아니라 **존재 여부**만 본다(위 도크스트링).
    accommodation_type: Any = None
    bookable_unit_type: Any = None

    @model_validator(mode="after")
    def _reject_null_on_not_null_columns(self) -> "PropertyUpdateRequest":
        """`NOT NULL` 컬럼에 명시적 `null`을 보내는 것은 형식 오류다.

        2.5절이 `null`의 뜻을 **nullable 컬럼에 한해** *"값을 지운다"*로
        정했다(`address`·`lower_bound_price`). `name`에 `null`을 보내면
        지울 수도 없고 바꿀 수도 없어 **조용히 무시되는 것이 최악**이다 —
        호스트는 이름이 지워진 줄 안다.

        형식 문제이므로 여기(Pydantic)에서 잡는다 → `400 VALIDATION_ERROR`.
        업무 규칙인 `IMMUTABLE_FIELD`는 서비스가 잡는다.
        """
        nulled = [
            f
            for f in self.model_fields_set
            if getattr(self, f) is None
            and f not in _NULLABLE_ON_PATCH
            and f not in ("accommodation_type", "bookable_unit_type")
        ]
        if nulled:
            raise ValueError(
                f"다음 필드는 null로 지울 수 없습니다: {', '.join(sorted(nulled))}"
            )
        return self


class PropertySummaryResponse(BaseModel):
    """`GET /properties` 목록의 원소 — **4필드**(api_contract 2절).

    `address`·`base_price`·`lower_bound_price`·`checkin_time`·`checkout_time`·
    `*_adjustment_enabled`는 **일부러 뺀 것**이다. `/settings` 화면 소관이며
    드롭다운에는 쓰이지 않는다(2절).

    `bookable_unit_type`이 목록에 있는 이유는 따로 있다 — 예약 생성 모달이
    `room_id`/`bed_id` 필수 여부를 이 값으로 분기하므로, 없으면 모달을 열
    때마다 숙소 상세를 재호출해야 한다(2절).

    **요약 지표(오픈 액션 수·오늘 체크인 건수 등)를 넣지 않는다.** 4절
    `dashboard/summary`가 *"캐싱 없이 매요청 실시간 집계 — 개별 API와 항상
    일치 보장"*을 명시하고 있어, 같은 지표를 목록에도 두면 두 API가 서로
    다른 시점의 값을 반환해 그 보장이 깨진다(2절).
    """

    model_config = ConfigDict(from_attributes=True)

    property_id: int
    name: str
    accommodation_type: AccommodationType
    bookable_unit_type: BookableUnitType


class PropertyDetailResponse(BaseModel):
    """`GET /properties/{id}` 상세 — **11필드**(api_contract 2.4절).

    `POST /properties`(2.3절)와 `PATCH /properties/{id}`(2.5절) 응답도
    **같은 구성**이다. 2.3절이 *"필드 표는 아래 2.4절과 같다"*로 명시하고
    있어 세 곳이 한 타입을 공유한다.

    ⚠️ **`base_price`의 `0`은 "미설정"이지 "0원"이 아니다**(2.3절). DB
    기본값이 `0`이라 숙소 등록 직후가 바로 이 상태이며, 화면은 이것을
    "요금 미설정"으로 안내해야 한다. `capacity`의 `null`/`0` 구분과 같은
    취급이다(2.1절).
    """

    model_config = ConfigDict(from_attributes=True)

    property_id: int
    name: str
    accommodation_type: AccommodationType
    bookable_unit_type: BookableUnitType
    address: str | None
    base_price: int
    lower_bound_price: int | None
    checkin_time: time
    checkout_time: time
    weekday_adjustment_enabled: bool
    holiday_adjustment_enabled: bool

    @field_serializer("checkin_time", "checkout_time")
    def _hhmm(self, value: time) -> str:
        """`TIME`을 **`"HH:MM"`**으로 직렬화한다(2.4절).

        Pydantic 기본값은 `"15:00:00"`(초 포함)이라 2절 요청 예시
        (`"checkin_time": "15:00"`)와 어긋난다. 요청과 응답의 표기가 다르면
        화면이 받은 값을 그대로 폼에 되돌려 넣지 못한다.
        """
        return value.strftime("%H:%M")


class RoomResponse(BaseModel):
    """객실 1건 — `GET /properties/{id}/rooms`의 원소(api_contract 2.1절).

    `POST /properties/{id}/rooms`의 201 응답도 **같은 모양**이다(2.6절).
    등록 직후 화면이 목록에 그 항목을 덧붙이기만 하면 되도록 맞춘 것이다.

    ⚠️ **`capacity`의 `null`은 "미입력"이며 `0`이 아니다**(2.1절). 화면에서
    둘을 구분해 표시해야 한다 — `0`은 있을 수 없는 값이다.

    `property_id`는 넣지 않는다(경로에 이미 있다). `created_at`도 넣지
    않는다 — 선택지를 채우는 것이 이 API의 용도이며 등록 시각을 쓰는
    화면이 없다(2.1절).
    """

    model_config = ConfigDict(from_attributes=True)

    room_id: int
    room_name: str
    capacity: int | None


class BedResponse(BaseModel):
    """침대 1건 — `GET /rooms/{id}/beds`의 원소(api_contract 2.2절).

    `POST /rooms/{id}/beds`의 201 응답도 같은 모양이다(2.6절).
    `room_id`·`created_at`은 넣지 않는다(2.1절과 같은 이유).
    """

    model_config = ConfigDict(from_attributes=True)

    bed_id: int
    bed_label: str
