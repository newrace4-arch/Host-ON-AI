/**
 * 통합 대시보드 데이터 훅 (2026-09-08)
 *
 * 근거: docs/api_contract.md v2.0 4.2절, docs/ui_design.md 4-4절
 *
 * 조회 방식:
 *   AppLayout이 받아둔 숙소 목록  →  각 숙소 dashboard/summary를 **병렬 호출**
 *   →  프론트가 합산
 *
 * 백엔드에 교차 숙소 집계 엔드포인트를 만들지 않는다. 기검증된 백엔드를
 * 건드리지 않는 것이 우선이고, 각 호출이 단일 숙소 쿼리라 명세서의 성능
 * 보증 범위 안에 있다.
 *
 * ## GET /properties를 이 훅이 부르지 않는다 (9/11 변경)
 *
 * **목록은 `AppLayout`의 `usePropertyList`가 한 번만 부르고**, 화면이
 * `useAppOutletContext()`로 받아 이 훅에 넘긴다. 앱 전체에서 그 한 곳만
 * `GET /properties`를 호출한다.
 *
 * > 9/8에는 이 자리에 *"GET /properties는 앱 전체에서 이 훅에서만
 * > 호출한다(9/8 결정)"*고 적혀 있었다. **같은 날 `usePropertyList`가
 * > 만들어지면서 그 문장은 곧바로 거짓이 됐고**, `/dashboard`에서 같은
 * > 요청이 2회 나가고 있었다(9/9 devlog 이월 항목).
 * >
 * > 9/9에는 *"인증이 붙으면 자연히 해소된다"*고 봤으나 그렇지 않다 —
 * > **인증은 요청자가 누구인지를 정할 뿐 호출 횟수와 무관하다.**
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { fetchDashboardSummary } from "@/api/dashboard";
import type {
  DashboardStatus,
  DashboardTotals,
  DashboardViewModel,
  PropertyFetchMap,
  PropertyFetchState,
  PropertyListState,
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

export function useDashboardSummary(
  list: PropertyListState,
): DashboardViewModel {
  const [fetchMap, setFetchMap] = useState<PropertyFetchMap>({});

  /**
   * 숙소 ID를 **정렬해 이어 붙인 문자열**. effect 의존성이자 가드 키다.
   *
   * ⚠️ `list.properties`를 의존성에 그대로 넣으면 리렌더마다 새 배열
   * 참조라 effect가 매번 돌고, 그 안에서 상태를 바꾸므로 무한 호출이
   * 된다(`useSelectedProperty`가 같은 이유로 같은 형태를 쓴다).
   *
   * **정렬하는 이유**: 서버가 같은 집합을 다른 순서로 돌려주면 문자열이
   * 달라져 불필요한 재조회가 난다. 집합이 같으면 키도 같아야 한다.
   *
   * `useMemo`를 쓰지 않는다 — `join`은 원시값을 만들고 원시값은 렌더마다
   * 새로 계산돼도 `===`로 같다. `useMemo`는 의존성에 배열이 필요해 오히려
   * 같은 함정으로 돌아간다.
   */
  const idsKey = list.properties
    .map((p) => p.property_id)
    .sort((a, b) => a - b)
    .join(",");

  /**
   * 최신 fetchMap을 담는 거울.
   *
   * 재시도 가드(진행 중이면 재요청하지 않음)를 **setFetchMap 업데이터
   * 바깥에서** 판정하기 위해 둔다. 업데이터 안에서 외부 변수를 바꾸면
   * StrictMode가 업데이터를 두 번 호출할 때 두 번째 호출이 이미 갱신된
   * 상태를 보고 플래그를 뒤집어, 실제 요청이 나가지 않는다(9/8에 실제로
   * 겪음). **상태 갱신 함수는 순수하게 유지한다.**
   */
  const fetchMapRef = useRef<PropertyFetchMap>({});
  fetchMapRef.current = fetchMap;

  /**
   * **이 목록으로 이미 시작했나.** "한 번이라도 시작했나"가 아니다.
   *
   * 9/11 이전에는 `boolean` 가드였다. 목록을 밖에서 받게 되면서 그대로
   * 두면 **목록이 바뀌어도 summary가 재조회되지 않는다** — 평생 한 번만
   * 시작하는 가드이기 때문이다.
   *
   * StrictMode 이중 실행에서 한 번만 나가는 이유: `useRef`는 이중
   * 마운트에서도 같은 객체가 유지되므로, 두 번째 실행이 첫 번째가 쓴 키를
   * 보고 조기 return한다. 기존 `boolean` 가드가 동작하던 원리와 같고
   * 비교 대상만 넓어졌다.
   */
  const startedKeyRef = useRef<string | null>(null);

  /**
   * 시작 번호 — **늦게 도착한 이전 목록의 응답을 버리기 위한 것.**
   *
   * ⚠️ **키가 아니라 번호로 판정한다.** 키로 하면 `A → B → A`(숙소 추가
   * 직후 삭제)에서 **첫 A의 늦은 응답이 같은 키로 통과해** 새 값을
   * 덮어쓴다. 번호는 시작할 때마다 오르므로 그 경우를 가른다.
   *
   * **시작할 때만 올린다.** cleanup에서 건드리지 않는다. StrictMode
   * 두 번째 실행은 위 가드에 막혀 번호를 올리지 않으므로, 첫 실행의
   * 응답이 반드시 살아남는다.
   */
  const runIdRef = useRef(0);

  /**
   * 숙소 하나의 summary를 불러 상태를 갱신한다.
   *
   * `runId`는 **이 호출이 속한 시작 회차**다. 응답이 온 시점에 회차가
   * 이미 바뀌었으면 반영하지 않는다.
   *
   * ─────────────────────────────────────────────────────────────────
   * ⚠️ **읽는 사람에게: 여기에 `cancelled` 플래그와 cleanup을 추가하지 마라.**
   *
   * 아래 회차 비교는 CLAUDE.md 규칙 14의 *"중복 실행 방지와 취소 처리를
   * 한 effect에 같이 넣지 않는다"*와 문언상 겹쳐 보인다. 그러나
   * **troubleshooting 26번의 실패 구조가 성립하지 않는다**(9/11 판단).
   *
   *   26번:  mount → effect#1(가드 set, fetch 시작)
   *          → cleanup 실행 → cancelled = true      ← 여기가 원인
   *          → effect#2는 가드에 막혀 아무것도 안 함
   *          → #1의 응답 도착 → cancelled라 버려짐
   *          결과: 유일한 응답이 죽어 화면이 로딩에서 멈춘다
   *
   * 여기가 다른 점 셋:
   *   1. **cleanup이 없다.** 회차를 무효화하는 주체가 "cleanup"이 아니라
   *      "다른 키로 시작한 나중 effect 실행"뿐이다.
   *   2. StrictMode 두 번째 실행은 **같은 키**라 가드에 막혀 회차를
   *      올리지 않는다. 첫 실행의 응답은 반드시 통과한다.
   *   3. 응답을 버리는 경우는 **항상 그것을 대신할 새 요청이 이미 출발한
   *      뒤**다. 버려도 화면이 비지 않는다.
   *
   * **cleanup을 추가하면 1번이 무너지고 26번이 그대로 재현된다.**
   * ─────────────────────────────────────────────────────────────────
   */
  const loadSummary = useCallback(async (propertyId: number, runId: number) => {
    try {
      const data = await fetchDashboardSummary(propertyId);
      // 회차 비교는 **업데이터 바깥에서** 한다(규칙 14 — 상태 갱신 함수는
      //   순수해야 한다). 업데이터는 prev만 읽는다.
      if (runIdRef.current !== runId) return;
      // 성공했으므로 lastError도 함께 버린다.
      setFetchMap((prev) => ({
        ...prev,
        [propertyId]: { status: "success", data },
      }));
    } catch (error) {
      if (runIdRef.current !== runId) return;
      setFetchMap((prev) => ({
        ...prev,
        // 실패 시 직전 data는 버린다 — 낡은 값을 성공처럼 보여주지 않는다.
        // lastError는 유지한다: 재시도가 또 실패했을 때 직전 에러와
        // 새 에러를 비교할 수 있어야 한다.
        [propertyId]: {
          status: "error",
          error,
          lastError: prev[propertyId]?.lastError,
        },
      }));
    }
  }, []);

  useEffect(() => {
    // 목록이 확정되기 전에는 **ref를 건드리지 않는다.** loading·error에서
    //   키를 기록해버리면, 같은 집합으로 복구됐을 때 재조회되지 않는다.
    if (list.status === "loading" || list.status === "error") return;

    // 이 목록으로 이미 시작했다.
    if (startedKeyRef.current === idsKey) return;
    startedKeyRef.current = idsKey;
    const myRun = ++runIdRef.current;

    // **빈 목록도 키("")로 기록한다.** 기록하지 않으면
    //   "1,2" → 빈 목록 → "1,2"에서 ref가 "1,2"로 남아 재조회되지 않는다.
    //   부를 대상이 없으므로 fetch는 하지 않고 맵만 비운다.
    if (list.status === "empty") {
      setFetchMap({});
      return;
    }

    // 모든 숙소를 loading으로 먼저 표시한다.
    //
    // oxlint `react/set-state-in-effect` 경고가 나지만 불가피하다
    // (`useSelectedProperty`가 같은 경고를 같은 이유로 안고 있다):
    // "목록이 바뀌었다"는 사실은 렌더 중에 파생시킬 수 없고, 이전 목록의
    // 카드를 즉시 치우지 않으면 **사라진 숙소의 값이 한 프레임 남는다.**
    //
    // 9/11 이전에는 같은 호출이 effect 안 async IIFE 안에 있어 경고가
    // 나지 않았을 뿐, 동기 여부만 달랐고 성격은 같다.
    const ids = idsKey.split(",").map(Number);
    setFetchMap(
      Object.fromEntries(ids.map((id) => [id, { status: "loading" as const }])),
    );

    // Promise.allSettled를 쓴다. Promise.all은 하나만 실패해도 전체가
    // reject되어 PARTIAL 자체가 성립하지 않는다.
    void Promise.allSettled(ids.map((id) => loadSummary(id, myRun)));
  }, [list.status, idsKey, loadSummary]);

  /**
   * 해당 숙소만 재조회한다. 성공한 나머지는 재요청하지 않는다.
   *
   * success였으면 refetching(기존 data 유지 — 화면이 깜빡이지 않는다),
   * error였으면 보여줄 data가 없으므로 loading으로 간다.
   *
   * error에서 재시도할 때는 그 에러를 **`lastError`로 옮겨 보관**한다
   * (9/8 처리). `status`가 loading이 되며 `error`가 지워지는데, 재시도가
   * 또 실패했을 때 직전 에러와 비교할 근거가 없으면 같은 원인인지 알 수
   * 없기 때문이다. 화면에는 노출하지 않는다.
   *
   * 이미 진행 중이면(loading·refetching) 아무것도 하지 않는다 —
   * 버튼 중복 클릭으로 같은 요청이 겹치지 않게 한다.
   */
  const refetchProperty = useCallback(
    (propertyId: number) => {
      const current = fetchMapRef.current[propertyId];

      // 이미 진행 중이면 아무것도 하지 않는다(버튼 중복 클릭 방지).
      if (current?.status === "loading" || current?.status === "refetching") {
        return;
      }

      const next: PropertyFetchState =
        current?.status === "success" && current.data
          ? { status: "refetching", data: current.data }
          : { status: "loading", lastError: current?.error };

      setFetchMap((prev) => ({ ...prev, [propertyId]: next }));
      // **그 시점의 현재 회차**로 부른다. 응답이 올 때 회차가 그대로면
      //   통과하고, 그 사이 목록이 바뀌어 회차가 올랐다면 이미 새 요청이
      //   출발한 뒤이므로 버리는 것이 맞다.
      void loadSummary(propertyId, runIdRef.current);
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

  /**
   * **판정 분기와 순서는 9/8 그대로다. 소스만 바뀌었다**(9/11).
   *
   *   listLoading            → list.status === "loading"
   *   listError !== undefined → list.status === "error"
   *   properties.length === 0 → list.status === "empty"
   *
   * 셋째가 동등한 이유: `usePropertyList`가 `list.length === 0 ? "empty"
   * : "success"`로 판정하고 예전 코드는 `properties.length === 0`으로
   * 판정했다. **같은 배열에 대한 같은 조건**이라 결과가 갈릴 수 없다.
   */
  let status: DashboardStatus;
  if (list.status === "loading") {
    status = "loading";
  } else if (list.status === "error") {
    status = "error";
  } else if (list.status === "empty") {
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
    properties: list.properties,
    fetchMap,
    totals: sumTotals(fetchMap),
    succeededCount,
    totalCount: list.properties.length,
    error: list.error,
    refetchProperty,
  };
}
