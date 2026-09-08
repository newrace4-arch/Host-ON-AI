/**
 * 액션센터 API (2026-09-08)
 *
 * 대시보드 프리뷰와 /actions 전체 큐가 **같은 엔드포인트**를 쓴다.
 * 차이는 size뿐이다(api_contract v2.0 9.1절).
 *   프리뷰   ?status=OPEN&size=5
 *   전체 큐  ?status=OPEN&size=20
 */

import { api } from "@/api/client";
import { mockActionItems } from "@/api/mock/data";
import { mockDelay } from "@/api/mock/scenarios";
import type { ActionItem, Meta } from "@/types/ui";

const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";

/** 우선순위 정렬 — ENUM 선언 순서를 그대로 따른다(v2.0 9.1절). */
const RISK_ORDER = { RED_NOW: 0, YELLOW_TODAY: 1, GREEN_AUTO: 2 } as const;

export interface ActionItemsResult {
  items: ActionItem[];
  meta?: Meta;
}

/**
 * GET /properties/{property_id}/action-items
 *
 * 서버 정렬은 `ORDER BY risk_level ASC, created_at DESC`다.
 * Mock에서도 같은 순서를 재현해 화면에서 우선순위 순서를 확인할 수 있게 한다.
 */
export async function fetchActionItems(
  propertyId: number,
  params: { status?: string; size?: number } = {},
): Promise<ActionItemsResult> {
  const { status = "OPEN", size = 5 } = params;

  if (USE_MOCK) {
    await mockDelay(300);
    const filtered = mockActionItems
      .filter((a) => a.property_id === propertyId && a.status === status)
      .sort(
        (a, b) =>
          RISK_ORDER[a.risk_level] - RISK_ORDER[b.risk_level] ||
          b.created_at.localeCompare(a.created_at),
      );
    return {
      items: filtered.slice(0, size),
      meta: { total: filtered.length, page: 1, size },
    };
  }

  const res = await api.get<ActionItem[]>(
    `/properties/${propertyId}/action-items`,
    { params: { status, size } },
  );
  return { items: res.data ?? [], meta: res.meta };
}
