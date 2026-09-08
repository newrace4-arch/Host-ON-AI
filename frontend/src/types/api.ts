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
