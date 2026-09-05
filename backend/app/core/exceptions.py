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


class ReservationOverlapError(AppError):
    """같은 숙소 안에서 판매단위를 넘나드는 기간 충돌(409).

    예: 독채(PROPERTY) 예약이 잡힌 기간에 그 하위 객실(ROOM) 예약을 넣는 경우.
    DB의 EXCLUDE 제약 3종은 **같은 단위끼리만** 막으므로 이 검사가 필요하다
    (명세서 2.6.1절 경고, troubleshooting.md 1번).
    """

    status_code = 409
    code = "RESERVATION_OVERLAP"

    def __init__(self, message: str, *, conflicting_reservation_ids: list[int] | None = None):
        super().__init__(message)
        self.conflicting_reservation_ids = conflicting_reservation_ids or []
