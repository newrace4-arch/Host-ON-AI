/**
 * 선택된 숙소와 폴백 정책 (2026-09-08)
 *
 * 선택 상태를 Context가 아니라 **URL 쿼리(`?property=123`)로** 관리한다.
 * 새로고침·뒤로가기에 그대로 보존되고, 액션센터 카드에서
 * `/cleaning?property=2` 같은 딥링크를 만들 수 있다.
 *
 * 폴백 정책(docs/ui_design.md 6-1절 2번 — 빈 화면으로 진입시키지 않는다)
 *   - 쿼리 없음        → 첫 번째 숙소로 치환. **안내하지 않는다**(정상 경로)
 *   - 없는 ID·잘못된 형식 → 안내 후 첫 번째 숙소로 폴백
 *   - 숙소 0개         → 자동 선택·폴백을 **하지 않는다**
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useSearchParams } from "react-router-dom";

import type { Property, PropertyListState } from "@/types/ui";

/**
 * `?property=` 값을 숙소 id로 해석한다. 해석 불가면 `null`.
 *
 * ⚠️ **`Number()`를 그냥 쓰면 안 된다.** `Number("abc")`는 `NaN`이지만
 *    `Number("")`는 **0**, `Number(" 7 ")`은 **7**, `Number("1e3")`은
 *    **1000**이라 조용히 통과한다. 정규식으로 먼저 형식을 막는다.
 */
export function parsePropertyId(raw: string | null): number | null {
  if (raw === null || !/^\d+$/.test(raw)) return null;
  const id = Number(raw);
  return Number.isSafeInteger(id) && id > 0 ? id : null;
}

/**
 * 숙소명 뒤에 "로 / 으로"를 붙인다.
 *
 * 항상 "으로"를 쓰면 *"마포 3룸 독채으로"*가 된다. 한글 음절이면 종성
 * 유무로 고르고(ㄹ 받침도 "로"), 영문·숫자로 끝나면 판정할 수 없으므로
 * "(으)로"로 둔다.
 */
function withRoParticle(name: string): string {
  const code = name.charCodeAt(name.length - 1);
  if (code >= 0xac00 && code <= 0xd7a3) {
    const jongseong = (code - 0xac00) % 28;
    return jongseong === 0 || jongseong === 8 ? `${name}로` : `${name}으로`;
  }
  return `${name}(으)로`;
}

export interface SelectedProperty {
  /** 확정된 숙소 id. 목록 로딩 중이거나 숙소 0개면 null */
  propertyId: number | null;
  property: Property | null;
  /** 폴백 안내 문구. 없으면 null */
  notice: string | null;
  dismissNotice: () => void;
  select: (propertyId: number) => void;
}

export function useSelectedProperty(
  list: PropertyListState,
): SelectedProperty {
  const [searchParams, setSearchParams] = useSearchParams();

  /**
   * ⚠️ 아래 세 값은 전부 **문자열·불리언**이다. `searchParams`나
   * `list.properties` 같은 객체·배열을 의존성에 넣으면 리렌더마다 새
   * 참조라 effect가 매번 돌고, effect 안에서 URL을 바꾸므로 곧바로
   * 무한 루프가 된다.
   */
  const raw = searchParams.get("property");
  const currentQuery = searchParams.toString();
  const idsKey = list.properties.map((p) => p.property_id).join(",");

  const parsed = parsePropertyId(raw);
  const resolved =
    parsed === null
      ? null
      : (list.properties.find((p) => p.property_id === parsed) ?? null);
  const exists = resolved !== null;

  const [notice, setNotice] = useState<string | null>(null);

  /**
   * 화면을 이동하면 안내를 지운다.
   *
   * ⚠️ **아래 폴백 effect보다 먼저 선언한다.** effect는 선언 순서대로
   * 실행되므로, 이동한 화면에서 또 폴백이 일어나면 지운 **뒤에** 새
   * 안내가 붙는다. 순서가 뒤바뀌면 새 안내가 곧바로 지워진다.
   *
   * 폴백의 URL replace는 pathname을 바꾸지 않으므로 이 effect를 깨우지
   * 않는다. 같은 값을 반환하면 React가 리렌더를 건너뛴다.
   */
  const { pathname } = useLocation();
  useEffect(() => {
    setNotice((prev) => (prev === null ? prev : null));
  }, [pathname]);

  /**
   * 안내 문구에 쓸 숙소명을 꺼내기 위한 거울.
   *
   * ⚠️ `list.properties`를 폴백 effect의 의존성에 **넣을 수 없다.** 리렌더
   * 마다 새 배열이라 effect가 매번 돌고, 그 안에서 URL을 바꾸므로 즉시
   * 무한 루프가 된다. 아래 폴백 effect보다 **먼저 선언해** 같은 커밋에서
   * 최신 값이 먼저 채워지게 한다.
   */
  const propertiesRef = useRef(list.properties);
  useEffect(() => {
    propertiesRef.current = list.properties;
  });

  /**
   * 마지막으로 **유효했던** 선택을 기억한다.
   *
   * 없으면 `/dashboard`를 거칠 때마다 선택이 1번 숙소로 초기화된다(9/8
   * 검증에서 실제로 발견). `/dashboard`는 전체 통합 뷰라 사이드바 링크에
   * 숙소 쿼리를 붙이지 않는데, 그렇게 도착한 URL에는 `property`가 없으므로
   * 폴백이 "첫 번째"를 고른다. 홍대 호스텔을 보다가 대시보드를 들렀다
   * 돌아오면 마포 독채가 떠 있는 셈이다.
   *
   * `AppLayout`은 화면 전환 시 리렌더되지 않으므로(pathless layout route)
   * 이 ref는 로그인 화면 밖으로 나가기 전까지 살아 있다. 새로고침하면
   * 사라지고 첫 번째 숙소로 돌아가는데, URL에 쿼리가 있는 정상 경로에서는
   * 그쪽이 이기므로 문제되지 않는다.
   */
  const lastValidRef = useRef<number | null>(null);
  const resolvedId = resolved?.property_id ?? null;

  // 렌더 중에 ref를 쓰지 않는다(oxlint react/refs). 아래 폴백 effect와
  // 이 effect는 서로 배타적이다 — 유효할 때만 기록하고, 무효할 때만
  // 폴백하므로 실행 순서에 의존하지 않는다.
  useEffect(() => {
    if (resolvedId !== null) lastValidRef.current = resolvedId;
  }, [resolvedId]);

  useEffect(() => {
    // 목록이 확정되기 전에는 판단하지 않는다. loading 중에 폴백하면
    // 사용자가 딥링크로 연 숙소를 첫 번째로 덮어쓴다.
    if (list.status !== "success") return;
    // 숙소 0개 — 폴백할 대상이 없다. 온보딩 유도는 화면이 담당한다.
    if (idsKey === "") return;
    // 이미 유효하다. **여기서 안내를 지우지 않는다** — 방금 폴백해서
    // 유효해진 경우에도 이 분기로 들어오므로, 지우면 안내가 한 프레임
    // 만에 사라진다.
    if (exists) return;

    // 값이 있었는데 못 찾은 경우에만 안내한다. 쿼리 자체가 없는 것은
    // 첫 진입이라 정상이다.
    // 기억해둔 선택이 아직 목록에 있으면 그쪽으로, 없으면 첫 번째로.
    const ids = idsKey.split(",");
    const remembered = lastValidRef.current;
    const target =
      remembered !== null && ids.includes(String(remembered))
        ? String(remembered)
        : ids[0];

    /**
     * **요청한 값이 있었을 때만 안내한다.** 쿼리가 아예 없어서 채운 경우는
     * 사용자가 요청한 것이 없으므로 "전환"이 아니다 — 첫 진입의 정상 경로다.
     *
     * Toast를 만들지 않고 전환기 옆 인라인 텍스트로 처리한다(9/8 결정).
     *
     * oxlint react/set-state-in-effect 경고가 나지만 불가피하다: 잘못된
     * 값은 바로 아래에서 URL을 replace하며 사라지므로 렌더 중에 파생시킬
     * 수 없다. 안내를 남기려면 이 시점에 상태로 붙잡아야 한다.
     */
    if (raw !== null && raw !== "") {
      const targetName =
        propertiesRef.current.find((p) => String(p.property_id) === target)
          ?.name ?? target;
      setNotice(
        `요청하신 숙소를 찾을 수 없어 ${withRoParticle(targetName)} 전환했습니다`,
      );
    }

    const next = new URLSearchParams(currentQuery);
    next.set("property", target);

    /**
     * ⚠️ **`{ replace: true }`를 빠뜨리면 안 된다.** 폴백은 사용자가
     * 요청한 이동이 아니므로 히스토리에 쌓이면 뒤로가기가 먹통이 된다
     * (뒤로 갈 때마다 다시 폴백되어 같은 화면으로 돌아온다).
     */
    setSearchParams(next, { replace: true });
  }, [list.status, idsKey, exists, raw, currentQuery, setSearchParams]);

  const dismissNotice = useCallback(() => setNotice(null), []);

  const select = useCallback(
    (propertyId: number) => {
      setNotice(null);
      const next = new URLSearchParams(currentQuery);
      next.set("property", String(propertyId));
      // 폴백과 달리 **replace를 쓰지 않는다.** 사용자가 직접 고른 전환이라
      // 뒤로가기로 이전 숙소에 돌아갈 수 있어야 한다.
      setSearchParams(next);
    },
    [currentQuery, setSearchParams],
  );

  return {
    propertyId: resolvedId,
    property: resolved,
    notice,
    dismissNotice,
    select,
  };
}
