/**
 * 숙소 API (2026-09-08)
 *
 * Mock 분기는 **이 계층에서만** 한다. 훅과 컴포넌트는 Mock의 존재를 모른다.
 */

import { client } from "@/api/client";
import { mockProperties } from "@/api/mock/data";
import {
  mockDelay,
  shouldFailProperties,
  shouldReturnEmptyProperties,
} from "@/api/mock/scenarios";
import type { Envelope } from "@/types/api";
import type { Property } from "@/types/ui";

const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";

/**
 * GET /properties — 내 숙소 목록
 *
 * api_contract v2.0 0절의 meta 규약에서 **예외**인 엔드포인트다.
 * PropertySwitcher와 대시보드 병렬 호출의 입력이라 항상 전체를 반환해야
 * 하므로 페이지네이션이 적용되지 않고 meta도 없다.
 */
export async function fetchProperties(): Promise<Property[]> {
  if (USE_MOCK) {
    await mockDelay();
    if (shouldFailProperties()) {
      throw new Error("mock: GET /properties 실패");
    }
    if (shouldReturnEmptyProperties()) {
      return [];
    }
    return mockProperties;
  }

  const res = await client.get<unknown, Envelope<Property[]>>("/properties");
  return res.data ?? [];
}
