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
 * ⚠️ **9/11 인증 작업에서 바뀔 수 있다.** 로그인이 붙으면 앱 최상위
 *    상태(토큰·현재 호스트)를 정리하게 되고, 그때 이 훅의 위치도 함께
 *    본다. 오늘은 상태관리 라이브러리를 추가하지 않는 선에서 가장 단순한
 *    형태로 둔다.
 *
 * TODO(9/11 인증 구현 시): **`GET /properties` 중복 호출을 해소한다.**
 *    `/dashboard`에서는 `useDashboardSummary`가 같은 요청을 따로 보내
 *    총 2회가 나간다. 그 훅은 목록 조회와 숙소별 병렬 호출이 한 effect에
 *    묶여 있어, 지금 손대면 검증 끝난 5상태 로직까지 다시 봐야 한다.
 *    **지금 Context를 만들지 않는 이유**: 9/11 인증 Context와 겹쳐 앱
 *    최상위 상태가 두 겹이 된다. 그때 최상위를 정리하면서 이 훅이 그
 *    상태를 쓰거나, `useDashboardSummary`가 아래 Outlet context를 쓰게
 *    바꾸면 중복은 사라진다.
 *    웨이크업 게이트가 먼저 서버를 깨우므로 콜드 스타트를 두 번 겪지는
 *    않는다.
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
