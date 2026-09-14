/**
 * 서버 API 계약 전용 타입 — 임시 수기 정의 (2026-09-08)
 *
 * ⚠️ 이 파일은 백엔드 엔드포인트 구현 후 `npm run generate-api`가
 *    **통째로 덮어쓴다.** 수기로 다른 내용을 넣지 말 것.
 *    (CLAUDE.md 코딩규칙 8번, 9/8 완화)
 *
 * 근거: docs/api_contract.md v2.0
 *
 * 【형식을 흉내 낸 이유】
 * 9/8에 openapi-typescript 7.13.0을 한 번 실행해 출력 형식을 확인했다.
 * 자동생성물은 `export interface components { schemas: ... }` 구조를 쓰고
 * **root-level 별칭(`export type Property = ...`)은 만들지 않는다.**
 * 그래서 별칭은 이 파일이 아니라 `ui.ts`에 둔다 — 여기에 두면 자동생성이
 * 덮어쓸 때 별칭이 사라져 컴포넌트 전체가 컴파일 에러가 난다.
 *
 * 【스키마 이름】
 * 아래 이름(Property / DashboardSummary / ActionItem / Meta / Envelope)은
 * **우리가 지금 임의로 정한 것**이다. 실제 구현 시 FastAPI가 Pydantic
 * 클래스명을 그대로 쓰므로(예: DashboardSummaryResponse) 자동생성 후
 * 이름이 달라지면 그때 ui.ts의 별칭만 고치면 된다.
 *
 * `paths`·`operations`는 수기로 만들지 않는다(자동생성 소관).
 */

export interface components {
  schemas: {
    /** GET /properties — api_contract v2.0 2절 */
    Property: {
      property_id: number;
      name: string;
      accommodation_type: string;
      bookable_unit_type: string;
    };

    /**
     * GET /properties/{property_id}/rooms — api_contract v2.6 2.1절
     *
     * `capacity`의 `null`은 **미입력**이며 `0`이 아니다. 화면에서 둘을
     * 구분해 표시한다(2.1절).
     * `property_id`·`created_at`은 응답에 없다 — 경로에 이미 있고,
     * 등록 시각을 쓰는 화면이 없다.
     */
    Room: {
      room_id: number;
      room_name: string;
      capacity: number | null;
    };

    /** GET /rooms/{room_id}/beds — v2.6 2.2절. `room_id`·`created_at` 없음 */
    Bed: {
      bed_id: number;
      bed_label: string;
    };

    /**
     * 예약 1건 — v2.6 4.3·4.4절. **15필드**이며 목록과 상세가 같다.
     *
     * `is_conflict`는 **DB 컬럼이 아니라 서버가 매 조회 시 계산하는 파생
     * 필드**다(4.4절). 범위는 **판매단위를 넘나드는 겹침만**이며
     * `PENDING`끼리의 겹침은 포함하지 않는다.
     *
     * `room_name`·`bed_label`이 **없다.** 이름은 `Room`·`Bed` 목록에서
     * 찾아 쓴다 — 출처를 하나로 두기 위한 결정이다(4.4절).
     *
     * `net_amount`는 DB 생성 컬럼(`gross - fee`)이라 `gross`/`fee` 중
     * 하나가 `null`이면 `null`이다. `base_price`가 `0`(미설정)인 숙소의
     * 예약이 그 상태다 — **0원이 아니라 "요금 미설정"으로 표시한다.**
     */
    Reservation: {
      reservation_id: number;
      property_id: number;
      room_id: number | null;
      bed_id: number | null;
      channel_connection_id: number;
      guest_name: string | null;
      /** YYYY-MM-DD */
      check_in: string;
      /** YYYY-MM-DD */
      check_out: string;
      reservation_status:
        | "PENDING"
        | "CONFIRMED"
        | "MODIFIED"
        | "CANCELLED"
        | "COMPLETED";
      refund_status: "NONE" | "PARTIAL" | "FULL";
      financial_status: "ESTIMATED" | "CONFIRMED" | "MANUALLY_ADJUSTED";
      gross_amount: number | null;
      fee_amount: number | null;
      net_amount: number | null;
      is_conflict: boolean;
    };

    /**
     * GET /properties/{property_id}/dashboard/summary — v2.0 4.1절
     *
     * 12개 키 전부 항상 존재한다(옵셔널 아님).
     * `conflict_count`만 값이 null일 수 있다 — 문서 원문:
     *   "키는 항상 포함한다. 계산 실패 시 값을 null로 반환한다."
     * 따라서 `number | null`이며 `| undefined`가 아니다.
     * 0(충돌 없음)과 null(계산 실패)은 화면에서 구분해 표시한다.
     */
    DashboardSummary: {
      property_id: number;
      property_name: string;

      today_checkin_count: number;
      today_checkout_count: number;
      today_turnover_count: number;

      open_action_count: number;
      red_now_count: number;
      yellow_today_count: number;
      green_auto_count: number;

      cleaning_pending_count: number;
      cleaning_issue_count: number;

      conflict_count: number | null;
    };

    /**
     * GET /properties/{property_id}/action-items — v2.0 9.1절
     * 9필드 전부 ACTION_ITEMS 실재 컬럼. 파생 필드 없음.
     * `reservation_id`와 `content`만 nullable(DB에서 nullable).
     */
    ActionItem: {
      action_id: number;
      property_id: number;
      reservation_id: number | null;
      risk_level: "RED_NOW" | "YELLOW_TODAY" | "GREEN_AUTO";
      /** VARCHAR(50) — 허용값을 확정하지 않음(v2.0 9.1절). 문자열로 둔다. */
      category: string;
      title: string;
      content: string | null;
      status: "OPEN" | "RESOLVED" | "AUTO_RESOLVED";
      /** ISO8601 */
      created_at: string;
    };

    /**
     * 목록 응답 메타 — v2.0 0절
     * 페이지네이션 파라미터(page, size)를 지원하는 컬렉션 엔드포인트만
     * 포함한다. `GET /properties`는 예외라 meta가 없다.
     */
    Meta: {
      total: number;
      page: number;
      size: number;
    };

    /**
     * `host` 객체 — v2.3 1.1절
     *
     * 3필드뿐이다. **`password_hash`는 절대 포함되지 않으며**
     * `created_at`도 내리지 않는다(화면에서 쓰는 곳이 없다).
     * `GET /auth/me`는 이 객체를 그대로 반환한다(1.4절).
     */
    Host: {
      host_id: number;
      email: string;
      name: string;
    };

    /**
     * 로그인·회원가입 공통 응답 — v2.3 1.2·1.3절
     *
     * 가입(201)과 로그인(200)이 **같은 구조**를 쓴다. 가입 성공 시 토큰을
     * 함께 주므로 `/login`을 거치지 않고 다음 화면으로 간다.
     *
     * `token_type`은 항상 `"bearer"`지만 **프론트는 이 값을 쓰지 않는다** —
     * `client.ts`가 `Bearer`를 하드코딩한다(1.1절).
     */
    TokenResponse: {
      access_token: string;
      token_type: string;
      host: components["schemas"]["Host"];
    };

    /** 에러 봉투 — v2.0 0절 */
    ApiError: {
      code: string;
      message: string;
    };
  };
}

/**
 * 공통 응답 봉투 — v2.0 0절
 *   성공: { data, meta?, error: null }
 *   실패: { data: null, error: { code, message } }
 *
 * axios 인터셉터가 axios 껍데기만 벗기므로 호출부가 이 형태를 그대로 받는다.
 */
export interface Envelope<T> {
  data: T | null;
  meta?: components["schemas"]["Meta"];
  error: components["schemas"]["ApiError"] | null;
}
