/**
 * 숙소 목록 훅 (2026-09-08)
 *
 * `GET /properties`를 **한 번만** 부르고 상태를 4가지로 정리한다.
 * AppLayout이 이 훅을 소유하고, Header(PropertySwitcher)와 하위 화면에
 * 내려준다.
 *
 * ⚠️ **왜 Header가 아니라 AppLayout인가**: 폴백 정책은 `property` 스코프
 *    화면 7개 전부에서 동작해야 한다. 데이터를 상단 크롬(Header)이
 *    소유하면 레이아웃 밖에서 재사용할 수 없고, 화면이 목록을 쓰려면
 *    같은 요청을 또 보내야 한다. 레이아웃이 소유하고 `Outlet context`로
 *    내려주면 호출은 한 번이다.
 *
 * ## 9/11 — 중복 호출 해소 완료
 *
 * **앱 전체에서 `GET /properties`를 부르는 곳은 이 훅 하나다.**
 * 9/8~9/10에는 `/dashboard`에서 `useDashboardSummary`가 같은 요청을 따로
 * 보내 총 2회가 나갔다(9/9 devlog 이월). 그 훅이 `useAppOutletContext()`로
 * 목록을 받게 바꿔 해소했다 — 위 주석이 말하는 "레이아웃이 소유하고
 * Outlet context로 내려주면 호출은 한 번"이 이제 실제로 성립한다.
 *
 * > 9/8 TODO는 **Context를 만들어 해소하는 안**을 전제했고, *"9/11 인증
 * > Context와 겹쳐 앱 최상위 상태가 두 겹이 된다"*는 이유로 미뤄두었다.
 * > 실제로는 **인증 Context를 만들지 않았고**(토큰은 `localStorage`,
 * > 호스트 정보는 아직 쓰는 곳이 없다) 겹침 자체가 발생하지 않았다.
 * > 새 전역 상태를 만들지 않고 이미 있던 Outlet context를 쓰는 쪽을
 * > 택했다 — 목록이 `AppLayout`(= `ProtectedRoute` 안쪽) 밖으로 나가지
 * > 않아야 로그아웃 시 이전 계정 데이터가 남지 않는다.
 * >
 * > 9/9에 *"인증이 붙으면 자연히 해소된다"*고 본 것은 틀렸다.
 * > **인증은 요청자가 누구인지를 정할 뿐 호출 횟수와 무관하다.**
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { fetchProperties } from "@/api/properties";
import type { PropertyListResult, PropertyListState } from "@/types/ui";

export function usePropertyList(): PropertyListResult {
  const [state, setState] = useState<PropertyListState>({
    status: "loading",
    properties: [],
  });

  /**
   * 재조회 토큰. `reload()`가 1 올리면 아래 effect가 다시 돈다.
   *
   * ⚠️ 규칙 14번: `setToken((t) => t + 1)`의 업데이터는 **순수하다.**
   * StrictMode가 두 번 호출해도 같은 `t`에서 같은 값이 나오므로 안전하다.
   * 28번에서 문제가 된 것은 업데이터가 **외부 변수를 건드린** 경우였다.
   */
  const [token, setToken] = useState(0);

  /**
   * StrictMode 이중 마운트에서 두 번 부르지 않게 한다.
   *
   * ⚠️ CLAUDE.md 규칙 14번: **ref 가드만 쓴다.** cleanup에 `cancelled`
   * 플래그를 더하면 첫 실행의 응답이 통째로 버려진다(troubleshooting 26번).
   */
  const startedRef = useRef(-1);

  useEffect(() => {
    if (startedRef.current === token) return;
    startedRef.current = token;

    void fetchProperties()
      .then((list) =>
        setState({
          // 숙소 0개는 에러가 아니라 온보딩 전 정상 상태다.
          status: list.length === 0 ? "empty" : "success",
          properties: list,
        }),
      )
      .catch((error) => setState({ status: "error", properties: [], error }));
  }, [token]);

  /** 목록 조회 실패 시 화면의 [다시 시도] 버튼이 부른다. */
  const reload = useCallback(() => {
    setState({ status: "loading", properties: [] });
    setToken((t) => t + 1);
  }, []);

  return { ...state, reload };
}
