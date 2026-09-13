"""도메인 예외 → API Contract 0절 에러 응답 포맷 매핑.

응답 포맷(api_contract.md 0절):
    { "data": null, "error": { "code": "...", "message": "..." } }

서비스 레이어는 HTTPException 대신 이 예외들을 던진다. 라우터/미들웨어가
`status_code`와 `code`를 그대로 꺼내 위 포맷으로 감싼다.
"""


class AppError(Exception):
    """모든 도메인 예외의 베이스."""

    status_code: int = 400
    code: str = "BAD_REQUEST"

    def __init__(self, message: str, *, code: str | None = None):
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code

    def to_error_body(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


class UnauthorizedError(AppError):
    """인증 자체가 실패했다(401) — 토큰 없음·만료·서명 무효(api_contract 0절).

    ⚠️ **`ResourceNotFoundError`와 섞지 않는다.** 이것은 *요청자가 누구인지
    확인할 수 없는* 경우이고, "인증은 유효하나 그 리소스가 없거나 내 것이
    아니다"는 404다. 권한 문제에 401을 반환하면 프론트가 **세션 만료로
    오인해 토큰을 지우고 로그아웃시킨다** — 남의 숙소 id를 한 번 잘못
    눌렀을 뿐인데 로그인이 풀린다(0절 "401과 404의 경계").

    만료와 서명 무효는 `core/security.py`의 `TokenExpiredError` /
    `TokenInvalidError`가 같은 코드로 낸다. 셋 다 `UNAUTHORIZED`다.
    """

    status_code = 401
    code = "UNAUTHORIZED"


class ResourceNotFoundError(AppError):
    """존재하지 않는 리소스 + 타인 소유 리소스를 **구분 없이** 404로 통일.

    403을 쓰지 않는 이유(api_contract.md 0절): id를 1씩 증가시키며 403/404를
    구분해 반환하면 어떤 id가 실재하는지 외부에서 추론할 수 있는 정보노출
    취약점이 된다.
    """

    status_code = 404
    code = "RESOURCE_NOT_FOUND"


class InvalidUnitHierarchyError(AppError):
    """bookable_unit_type ↔ room_id/bed_id 조합 위반(400).

    code는 위반 유형별로 다르다(api_contract.md 4절 표):
      PROPERTY 위반 → INVALID_UNIT_HIERARCHY
      ROOM 위반     → ROOM_ID_REQUIRED
      BED 위반      → BED_ID_REQUIRED
    """

    status_code = 400
    code = "INVALID_UNIT_HIERARCHY"


class ImmutableFieldError(AppError):
    """수정할 수 없는 필드를 바꾸려 했다(400, api_contract 2.5절).

    `PROPERTIES.accommodation_type`·`bookable_unit_type`이 대상이다.

    🔴 **요청에 담겨 오면 조용히 무시하지 않고 거부한다.** 받아서 버리면
    호스트는 바뀐 줄 알고 화면을 떠난다. 그래서 요청 스키마에서 필드를
    **빼지 않고** 두되, 서비스가 이 예외를 던지는 형태여야 한다 — 스키마에서
    빼면 Pydantic이 모르는 필드로 무시해 400이 나가지 않는다.

    ⚠️ **`VALIDATION_ERROR`와 뜻이 다르다.** 그쪽은 *"형식이 틀렸다"*라
    고쳐서 다시 보내면 되지만, 이것은 *"형식은 맞는데 바꿀 수 없다"*라
    프론트가 그 입력을 **비활성화**해야 한다(api_contract 0절 v2.5 이력).

    `message`에 해당 필드명을 담는다(2.5절 에러 표).
    """

    status_code = 400
    code = "IMMUTABLE_FIELD"


class RoomNameAlreadyExistsError(AppError):
    """같은 숙소에 같은 `room_name`(409, api_contract 2.6절).

    DB의 `uq_property_room_name`과 짝을 이루는 도메인 에러다.
    `CHANNEL_ALREADY_CONNECTED`와 같은 계열이며, **선조회로 미리 막지
    않는다** — 조회와 INSERT 사이에 다른 요청이 끼어들 수 있다(TOCTOU).
    제약 위반을 잡아 번역하는 것이 유일하게 정확한 방법이다.
    """

    status_code = 409
    code = "ROOM_NAME_ALREADY_EXISTS"


class BedLabelAlreadyExistsError(AppError):
    """같은 객실에 같은 `bed_label`(409, api_contract 2.6절).

    DB의 `uq_room_bed_label`과 짝을 이룬다. 위 `RoomNameAlreadyExistsError`와
    같은 이유로 선조회를 쓰지 않는다.
    """

    status_code = 409
    code = "BED_LABEL_ALREADY_EXISTS"


class ReservationOverlapError(AppError):
    """같은 숙소 안에서 판매단위를 넘나드는 기간 충돌(409).

    예: 독채(PROPERTY) 예약이 잡힌 기간에 그 하위 객실(ROOM) 예약을 넣는 경우.
    RESERVATIONS의 EXCLUDE 제약 3종(`excl_property_overlap` /
    `excl_room_overlap` / `excl_bed_overlap`)은 **같은 단위끼리만**
    막으므로 이 검사가 필요하다
    (명세서 2.6.1절 경고, troubleshooting.md 1번).
    """

    status_code = 409
    code = "RESERVATION_OVERLAP"

    def __init__(self, message: str, *, conflicting_reservation_ids: list[int] | None = None):
        super().__init__(message)
        self.conflicting_reservation_ids = conflicting_reservation_ids or []
