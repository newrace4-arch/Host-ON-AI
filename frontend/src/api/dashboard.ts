/**
 * 대시보드 요약 API (2026-09-08)
 *
 * 교차 숙소 집계 엔드포인트는 만들지 않는다(api_contract v2.0 4.2절).
 * 이 함수는 **숙소 1개**의 요약만 가져오며, 병렬 호출과 합산은 훅이 한다.
 */

import { api } from "@/api/client";
import { mockSummaries } from "@/api/mock/data";
import { mockDelay, shouldFailSummary } from "@/api/mock/scenarios";
import type { DashboardSummary } from "@/types/ui";

const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";

/** GET /properties/{property_id}/dashboard/summary */
export async function fetchDashboardSummary(
  propertyId: number,
): Promise<DashboardSummary> {
  // 🔴 **실패 주입은 `USE_MOCK` 밖에 둔다 (r58, 9/14).**
  //   안에 두면 실서버 모드(`VITE_USE_MOCK=false`)에서 **에러 상태를 재현할
  //   수단이 사라진다.** 백엔드를 내리면 `GET /properties`까지 함께 죽어
  //   **화면 전체 ERROR가 되어 카드별 실패(PARTIAL)와 구분되지 않는다.**
  //   `shouldFailSummary`가 `import.meta.env.DEV`로 자기를 막으므로
  //   프로덕션 번들에서는 이 줄이 통째로 사라진다 —
  //   `api/reservations.ts`의 `shouldFailReservations`와 **같은 형태**다.
  //   두 파일이 서로 다른 방식을 쓰던 것이 그 자체로 문제였다.
  if (shouldFailSummary(propertyId)) {
    throw new Error(`mock: ${propertyId}번 숙소 summary 실패`);
  }

  if (USE_MOCK) {
    await mockDelay(600);
    const summary = mockSummaries[propertyId];
    if (!summary) throw new Error(`mock: ${propertyId}번 숙소 데이터 없음`);
    return summary;
  }

  const res = await api.get<DashboardSummary>(
    `/properties/${propertyId}/dashboard/summary`,
  );
  if (!res.data) throw new Error(res.error?.message ?? "summary 조회 실패");
  return res.data;
}
