/**
 * 화면 전용 타입 (2026-09-08)
 *
 * 【이 파일에 별칭이 있는 이유】
 * `api.ts`는 백엔드 구현 후 `npm run generate-api`가 **통째로 덮어쓴다.**
 * openapi-typescript는 root-level 별칭(`export type Property = ...`)을
 * 만들지 않으므로(9/8 출력 형식 확인), 별칭을 api.ts에 두면 덮어쓰는 순간
 * 사라져 컴포넌트 전체가 컴파일 에러가 난다.
 * 그래서 별칭을 이 파일에 모아 재export한다. 자동생성 후 스키마 이름이
 * 바뀌어도 **이 파일 한 곳만** 고치면 컴포넌트는 손대지 않는다.
 *
 * 【컴포넌트 규칙 — CLAUDE.md 코딩규칙 8번】
 * 컴포넌트는 타입을 **ui.ts에서만** import한다. api.ts를 직접 import하지
 * 않으며, API 응답·요청 타입을 새로 정의하지도 않는다.
 */

import type { components } from "@/types/api";

/* ── 서버 계약 별칭 (api.ts 재export) ───────────────────────────── */

export type Host = components["schemas"]["Host"];
export type TokenResponse = components["schemas"]["TokenResponse"];
export type Property = components["schemas"]["Property"];
export type DashboardSummary = components["schemas"]["DashboardSummary"];
export type ActionItem = components["schemas"]["ActionItem"];
export type Meta = components["schemas"]["Meta"];
export type ApiError = components["schemas"]["ApiError"];

/* ── 화면 전용 타입 (API 응답이 아님) ───────────────────────────── */

/**
 * 숙소 1개의 summary 조회 상태.
 *
 * `loading`과 `refetching`을 나누는 이유: 재조회 중에 data를 비우면 화면이
 * 깜빡인다. refetching은 **기존 data를 유지한 채** 재요청 중임을 뜻한다.
 *
 * 전이:
 *   최초 호출        → loading
 *   성공             → success
 *   실패             → error
 *   refetch(success) → refetching (data 유지)
 *   refetch(error)   → loading    (보여줄 data가 없음)
 */
export type PropertyFetchStatus =
  | "loading"
  | "success"
  | "error"
  | "refetching";

export interface PropertyFetchState {
  status: PropertyFetchStatus;
  /** refetching 중에도 직전 성공 데이터를 유지한다. */
  data?: DashboardSummary;
  error?: unknown;
  /**
   * 재시도 직전의 에러를 보관한다.
   *
   * `error` 상태에서 재시도하면 `status`가 `loading`으로 가며 `error`가
   * 지워지는데, 재시도가 **또 실패했을 때 직전 에러와 새 에러가 같은
   * 원인인지** 비교할 근거가 사라진다. 화면에 노출하지는 않고 상태로만
   * 보관한다.
   *
   * 카드가 "최초 로딩"과 "재시도 중"을 구분하는 데도 쓴다 —
   * `status === 'loading'`이면서 `lastError`가 있으면 재시도 중이다.
   */
  lastError?: unknown;
}

/** 숙소 id → 조회 상태 */
export type PropertyFetchMap = Record<number, PropertyFetchState>;

/**
 * 숙소 목록 조회 상태 — `GET /properties` 하나에 대한 것이다.
 *
 * 대시보드 5상태(`DashboardStatus`)와 **합치지 않는다.** 이쪽은 "전환기에
 * 띄울 목록이 있는가"이고, 저쪽은 "숙소별 summary 병렬 호출이 어디까지
 * 성공했는가"다. PARTIAL이 여기엔 존재할 수 없다 — 호출이 하나뿐이다.
 */
export type PropertyListStatus = "loading" | "success" | "empty" | "error";

export interface PropertyListState {
  status: PropertyListStatus;
  /** loading·error·empty에서는 빈 배열이다 */
  properties: Property[];
  error?: unknown;
}

/** 상태 + 재조회 액션. `usePropertyList()`의 반환 타입이다. */
export interface PropertyListResult extends PropertyListState {
  /** 실패 후 [다시 시도]용. 성공 상태에서 불러도 무해하다. */
  reload: () => void;
}

/**
 * AppLayout이 `Outlet context`로 하위 화면에 내려주는 것.
 *
 * 숙소 스코프 화면 7개(/calendar·/inquiries·/actions·/cleaning·
 * /settlements·/knowledge·/settings)가 목록을 다시 부르지 않고 쓰게 한다.
 */
export interface AppOutletContext {
  propertyList: PropertyListResult;
}

/**
 * 웨이크업 상태 — 대시보드 5상태와 **별개**다.
 *
 * `ERROR` 하나로 합치지 않는다: **서버가 안 깨어난 것**과 **대시보드
 * 데이터를 못 받은 것**은 원인도 복구 방법도 다르다. 전자는 서버를 다시
 * 깨우면 되고, 후자는 특정 숙소만 재시도하면 된다.
 */
export type WakeUpStatus = "connecting" | "connected" | "connection_failed";

/**
 * 대시보드 화면 상태 5가지 — docs/ui_design.md 4-4절.
 *
 * PARTIAL은 기존 4상태에 없는 다섯 번째 상태다. 전체 숙소 통합 대시보드가
 * 숙소별 병렬 호출이라 일부만 실패하는 경우가 생기며, 이때 **전체를 에러로
 * 처리하지 않는다.**
 */
export type DashboardStatus =
  | "loading"
  | "success"
  | "empty"
  | "error"
  | "partial";

/**
 * 성공한 숙소들의 summary를 합산한 결과.
 *
 * `conflict_count`는 합산하지 않는다 — null(계산 실패)과 0(충돌 없음)을
 * 구분해야 하는데 합산하면 그 구분이 사라진다. 카드별로 표시한다.
 */
export interface DashboardTotals {
  today_checkin_count: number;
  today_checkout_count: number;
  today_turnover_count: number;
  /** 액션 프리뷰의 "전체 N건"에 쓰는 값(meta.total 아님 — v2.0 9.1절) */
  open_action_count: number;
  red_now_count: number;
  yellow_today_count: number;
  green_auto_count: number;
  cleaning_pending_count: number;
  cleaning_issue_count: number;
}

/** useDashboardSummary가 화면에 넘기는 것 전부 */
export interface DashboardViewModel {
  status: DashboardStatus;
  properties: Property[];
  fetchMap: PropertyFetchMap;
  totals: DashboardTotals;
  /** 합산에 실제로 반영된 숙소 수 — PARTIAL의 "N개 중 M개 기준" 표시용 */
  succeededCount: number;
  totalCount: number;
  /** GET /properties 자체가 실패한 경우에만 채워진다 */
  error?: unknown;
  /** 해당 숙소만 재조회. 성공한 나머지는 건드리지 않는다. */
  refetchProperty: (propertyId: number) => void;
}
