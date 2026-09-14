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

/**
 * 캘린더의 예약 조회를 실패시킨다 → 그리드 자리에 ERROR (9/14 추가)
 *
 *   ?mock_reservations_error=2  → 2번 숙소의 예약 조회가 계속 실패
 *
 * ⚠️ **Mock 모드가 아니어도 동작한다. 대신 개발 빌드에서만 산다.**
 * 위 세 플래그와 다른 점이다. 캘린더는 실서버(`VITE_USE_MOCK=false`)로
 * 붙어 동작을 확인하는데 **에러 상태만은 실서버로 재현할 수 없다** —
 * 서버를 고장 낼 수 없고, 네트워크를 끊으면 `rooms`까지 함께 죽어
 * 그리드 에러와 구분되지 않는다. 완료 조건이 *"브라우저에서 세 상태를
 * 눈으로 봤다"*이므로 재현 수단이 없으면 완료할 수 없다.
 *
 * 🔴 **`import.meta.env.DEV`로 막는다.** 프로덕션 번들에서는 상수 `false`가
 * 되어 본문이 통째로 제거된다 — **배포본에 화면을 고장 내는 쿼리
 * 파라미터를 남기지 않는다.**
 */
export function shouldFailReservations(propertyId: number): boolean {
  if (!import.meta.env.DEV) return false;
  return flags().get("mock_reservations_error") === String(propertyId);
}

/** 네트워크 지연 흉내 — LOADING 상태를 눈으로 확인하기 위함 */
export function mockDelay(ms = 400): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
