/**
 * Mock 시나리오 제어 (2026-09-08)
 *
 * 대시보드의 5가지 상태를 **컴포넌트를 건드리지 않고** 검증하기 위한
 * URL 쿼리 플래그다. Mock 모드에서만 동작한다.
 *
 *   ?mock_properties_error=1  → GET /properties 자체가 실패 (ERROR)
 *   ?mock_empty=1             → 숙소 목록이 빈 배열      (EMPTY)
 *   ?mock_error=2             → 2번 숙소의 summary가 **계속** 실패 (PARTIAL)
 *   ?mock_error_once=2        → 2번 숙소가 **첫 호출만** 실패, 재시도는 성공
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

/**
 * 지정한 숙소의 summary를 실패시킨다.
 *
 * - `mock_error=N`      → N번 숙소가 **매번** 실패한다(PARTIAL 고정)
 * - `mock_error_once=N` → N번 숙소가 **첫 호출만** 실패하고 재시도는
 *   성공한다. 재시도 버튼이 PARTIAL → SUCCESS로 전환시키는 경로를
 *   검증하기 위한 것이다. `mock_error`만으로는 재시도가 계속 실패해
 *   성공 전환을 확인할 수 없다.
 */
const failedOnce = new Set<number>();

export function shouldFailSummary(propertyId: number): boolean {
  const f = flags();

  if (f.get("mock_error") === String(propertyId)) return true;

  if (f.get("mock_error_once") === String(propertyId)) {
    if (failedOnce.has(propertyId)) return false; // 두 번째부터는 성공
    failedOnce.add(propertyId);
    return true;
  }

  return false;
}

/** 네트워크 지연 흉내 — LOADING 상태를 눈으로 확인하기 위함 */
export function mockDelay(ms = 400): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
