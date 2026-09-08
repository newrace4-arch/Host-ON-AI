/**
 * Mock 시나리오 제어 (2026-09-08)
 *
 * 대시보드의 5가지 상태를 **컴포넌트를 건드리지 않고** 검증하기 위한
 * URL 쿼리 플래그다. Mock 모드에서만 동작한다.
 *
 *   ?mock_properties_error=1  → GET /properties 자체가 실패 (ERROR)
 *   ?mock_empty=1             → 숙소 목록이 빈 배열      (EMPTY)
 *   ?mock_error=2             → 2번 숙소의 summary만 실패 (PARTIAL)
 *
 * 아무 플래그도 없으면 정상 동작(LOADING → SUCCESS).
 */

function flags(): URLSearchParams {
  return new URLSearchParams(window.location.search);
}

/** GET /properties 자체를 실패시킨다 → 화면 전체 ERROR */
export function shouldFailProperties(): boolean {
  return flags().get("mock_properties_error") === "1";
}

/** 숙소 목록을 빈 배열로 만든다 → EMPTY(온보딩 유도) */
export function shouldReturnEmptyProperties(): boolean {
  return flags().get("mock_empty") === "1";
}

/** 지정한 숙소의 summary만 실패시킨다 → PARTIAL */
export function shouldFailSummary(propertyId: number): boolean {
  return flags().get("mock_error") === String(propertyId);
}

/** 네트워크 지연 흉내 — LOADING 상태를 눈으로 확인하기 위함 */
export function mockDelay(ms = 400): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
