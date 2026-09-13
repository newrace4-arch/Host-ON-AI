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

from pydantic import BaseModel, ConfigDict, field_serializer

from app.models.enums import AccommodationType, BookableUnitType


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
