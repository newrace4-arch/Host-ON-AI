/**
 * 통합 대시보드 데이터 훅 (2026-09-08)
 *
 * 근거: docs/api_contract.md v2.0 4.2절, docs/ui_design.md 4-4절
 *
 * 조회 방식:
 *   GET /properties  →  각 숙소 dashboard/summary를 **병렬 호출**  →  프론트가 합산
 *
 * 백엔드에 교차 숙소 집계 엔드포인트를 만들지 않는다. 기검증된 백엔드를
 * 건드리지 않는 것이 우선이고, 각 호출이 단일 숙소 쿼리라 명세서의 성능
 * 보증 범위 안에 있다.
 *
 * ※ GET /properties는 앱 전체에서 **이 훅에서만** 호출한다(9/8 결정).
 *   Header의 PropertySwitcher는 오늘 API를 호출하지 않는다 — 상태관리
 *   라이브러리 없이 둘이 목록을 공유할 깔끔한 방법이 없어, 내일 로그인
 *   작업에서 앱 최상위 상태를 정리할 때 함께 결정한다.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { fetchDashboardSummary } from "@/api/dashboard";
import { fetchProperties } from "@/api/properties";
import type {
  DashboardStatus,
  DashboardTotals,
  DashboardViewModel,
  Property,
  PropertyFetchMap,
} from "@/types/ui";

const EMPTY_TOTALS: DashboardTotals = {
  today_checkin_count: 0,
  today_checkout_count: 0,
  today_turnover_count: 0,
  open_action_count: 0,
  red_now_count: 0,
  yellow_today_count: 0,
  green_auto_count: 0,
  cleaning_pending_count: 0,
  cleaning_issue_count: 0,
};

/**
 * 성공한 숙소만 합산한다.
 *
 * `conflict_count`는 합산 대상이 아니다 — null(계산 실패)과 0(충돌 없음)을
 * 구분해야 하는데 합산하면 그 구분이 사라진다. 카드에서 개별 표시한다.
 */
function sumTotals(fetchMap: PropertyFetchMap): DashboardTotals {
  const totals = { ...EMPTY_TOTALS };
  for (const state of Object.values(fetchMap)) {
    const d = state.data;
    if (!d) continue;
    totals.today_checkin_count += d.today_checkin_count;
    totals.today_checkout_count += d.today_checkout_count;
    totals.today_turnover_count += d.today_turnover_count;
    totals.open_action_count += d.open_action_count;
    totals.red_now_count += d.red_now_count;
    totals.yellow_today_count += d.yellow_today_count;
    totals.green_auto_count += d.green_auto_count;
    totals.cleaning_pending_count += d.cleaning_pending_count;
    totals.cleaning_issue_count += d.cleaning_issue_count;
  }
  return totals;
}

export function useDashboardSummary(): DashboardViewModel {
  const [properties, setProperties] = useState<Property[]>([]);
  const [fetchMap, setFetchMap] = useState<PropertyFetchMap>({});
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState<unknown>(undefined);

  /**
   * StrictMode의 이중 마운트에서 목록을 두 번 불러오지 않도록 한다.
   *
   * ⚠️ 이 가드와 `cancelled` 플래그를 함께 쓰면 안 된다(9/8에 실제로 겪음):
   * StrictMode는 마운트 직후 cleanup을 한 번 실행하므로, cleanup이
   * cancelled=true로 만들고 두 번째 effect는 이 가드에 막혀 아무것도 하지
   * 않는다. 결과적으로 첫 실행의 응답이 전부 버려져 화면이 로딩에서 멈춘다.
   * 중복 호출은 이 가드 하나로 충분하다.
   */
  const startedRef = useRef(false);

  /** 숙소 하나의 summary를 불러 상태를 갱신한다. */
  const loadSummary = useCallback(async (propertyId: number) => {
    try {
      const data = await fetchDashboardSummary(propertyId);
      setFetchMap((prev) => ({
        ...prev,
        [propertyId]: { status: "success", data },
      }));
    } catch (error) {
      setFetchMap((prev) => ({
        ...prev,
        // 실패 시 직전 data는 버린다 — 낡은 값을 성공처럼 보여주지 않는다.
        [propertyId]: { status: "error", error },
      }));
    }
  }, []);

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;

    void (async () => {
      try {
        const list = await fetchProperties();
        setProperties(list);
        setListLoading(false);

        // 모든 숙소를 loading으로 먼저 표시한다.
        setFetchMap(
          Object.fromEntries(
            list.map((p) => [p.property_id, { status: "loading" as const }]),
          ),
        );

        // Promise.allSettled를 쓴다. Promise.all은 하나만 실패해도 전체가
        // reject되어 PARTIAL 자체가 성립하지 않는다.
        await Promise.allSettled(
          list.map((p) => loadSummary(p.property_id)),
        );
      } catch (error) {
        // GET /properties 실패는 전체 중단이다. 목록이 없으면 병렬 호출을
        // 시작할 대상 자체가 없다.
        setListError(error);
        setListLoading(false);
      }
    })();
  }, [loadSummary]);

  /**
   * 해당 숙소만 재조회한다. 성공한 나머지는 재요청하지 않는다.
   *
   * success였으면 refetching(기존 data 유지 — 화면이 깜빡이지 않는다),
   * error였으면 보여줄 data가 없으므로 loading으로 간다.
   *
   * TODO(9/9 재시도 버튼 UI 작업 시): error 상태에서 재시도하면
   * loading으로 전이되며 기존 error 정보가 사라진다. 재시도가 또
   * 실패했을 때 직전 에러와 새 에러가 같은 원인인지 구분할 근거가
   * 없어진다. lastError 보존을 검토할 것.
   */
  const refetchProperty = useCallback(
    (propertyId: number) => {
      setFetchMap((prev) => {
        const current = prev[propertyId];
        const next =
          current?.status === "success" && current.data
            ? { status: "refetching" as const, data: current.data }
            : { status: "loading" as const };
        return { ...prev, [propertyId]: next };
      });
      void loadSummary(propertyId);
    },
    [loadSummary],
  );

  /* ── 화면 상태 판정 ─────────────────────────────────────────── */

  const states = Object.values(fetchMap);
  const succeededCount = states.filter((s) => s.data !== undefined).length;
  const failedCount = states.filter((s) => s.status === "error").length;
  const pendingCount = states.filter(
    (s) => s.status === "loading" || s.status === "refetching",
  ).length;

  let status: DashboardStatus;
  if (listLoading) {
    status = "loading";
  } else if (listError !== undefined) {
    status = "error";
  } else if (properties.length === 0) {
    status = "empty";
  } else if (pendingCount > 0 && succeededCount === 0 && failedCount === 0) {
    status = "loading";
  } else if (failedCount > 0) {
    // 하나라도 실패했으면 PARTIAL이다. 전부 실패해도 마찬가지 —
    // 숙소 목록 자체는 받았으므로 화면 전체를 에러로 덮지 않는다.
    status = "partial";
  } else {
    status = "success";
  }

  return {
    status,
    properties,
    fetchMap,
    totals: sumTotals(fetchMap),
    succeededCount,
    totalCount: properties.length,
    error: listError,
    refetchProperty,
  };
}
