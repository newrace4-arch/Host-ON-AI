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
  if (USE_MOCK) {
    await mockDelay(600);
    if (shouldFailSummary(propertyId)) {
      throw new Error(`mock: ${propertyId}번 숙소 summary 실패`);
    }
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
