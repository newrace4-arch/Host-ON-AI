"""도메인에 속하지 않는 공통 응답 타입 (api_contract.md 0절).

## 왜 별도 파일인가

`Envelope`·`ApiError`는 **어느 도메인에도 속하지 않는다.** `reservation.py`에
두면 `channels`가 예약 스키마를 import하게 되고, `core/`에 두면 인프라
계층이 Pydantic **응답 모델**을 갖게 되어 지금 경계가 흐려진다
(`core/`는 설정·DB·보안·의존성·예외까지다).

`utils/db_errors.py`가 *"`channel_service`와 `reservation_service` 양쪽이
쓰므로 서비스 모듈이 아니라 여기에 둔다 — 둘 중 한쪽에 두면 순환 import가
된다"*로 같은 판단을 이미 내렸다. 그것을 `schemas/`에 적용한 것이다.

## 🔴 `data`에 기본값을 두지 않는다

`data: T | None = None`으로 두면 OpenAPI에서 `required`가 아니게 되고,
`openapi-typescript`가 **`data?:`(optional)**로 뽑는다. 프론트 수기 정의는
`data: T | null`(필수)이라 **타입이 조용히 어긋난다**(9/14 실측).

`error`도 같은 이유로 기본값이 없다. 0절이 *"성공: `{ data, error: null }`"*로
**성공 응답에도 `error` 키가 있다**고 정했으므로, 호출부가 `error=None`을
명시적으로 넘겨야 한다.

## 에러 응답은 이 타입을 거치지 않는다

실패 경로는 `main.py`의 예외 핸들러가 `JSONResponse`를 **직접** 돌려주므로
`response_model` 검증을 지나가지 않는다(9/14 실측). 그래서 `data: T`가
non-nullable이어도 404·409가 정상 동작한다 — 선언된 200/201 스키마만
이 모양이면 된다.

## `MetaEnvelope`를 만들지 않는다

0절의 `meta`는 **페이지네이션을 지원하는 컬렉션**에만 붙는데, 현재 구현된
엔드포인트 중 그런 것이 **0개**다(`GET /properties`·객실·침대·예약 목록이
전부 "전체를 반환하는 것이 목적"인 예외다). 쓰는 곳이 생기는 날 만든다 —
지금 만들면 아무도 쓰지 않는 스키마가 OpenAPI에 실린다.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiError(BaseModel):
    """실패 응답의 `error` 객체 (api_contract 0절).

    `core/exceptions.py`의 `AppError.to_error_body()`가 만드는 dict와 같은
    모양이다. 여기에 타입으로 선언해 두면 **OpenAPI에 실려** 프론트
    `types/api.ts`의 `ApiError`와 처음으로 기계 대조가 가능해진다.
    """

    code: str
    message: str


class Envelope(BaseModel, Generic[T]):
    """공통 응답 봉투 (api_contract 0절).

        { "data": ..., "error": null }

    라우터가 `response_model=Envelope[X]`로 선언하고 지금처럼
    `{"data": ..., "error": None}` dict를 반환하면 된다 — **본문을 고칠
    필요가 없다.**

    ⚠️ **두 필드 모두 기본값이 없다**(위 모듈 도크스트링). `error=None`을
    빠뜨리면 `ResponseValidationError`로 500이 나므로, 호출부가 봉투를
    반쪽만 만드는 일이 그 자리에서 드러난다.
    """

    data: T
    error: ApiError | None
