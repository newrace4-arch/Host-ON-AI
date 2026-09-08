/**
 * 숙소 컨텍스트를 보존하는 경로 생성 훅 (2026-09-08)
 *
 * **컴포넌트가 아니라 "경로 문자열을 만들어 반환하는 함수"다.**
 * `<Link to={...}>`와 `navigate(...)` 양쪽에서 같은 규칙을 쓰기 위함이다.
 * Link 래퍼로 만들면 프로그래매틱 이동(액션센터 카드 → 청소 상세 등)에서
 * 재사용할 수 없다.
 *
 * 각 화면이 쿼리 문자열을 직접 조립하면 7개 중 하나만 빠져도 딥링크가
 * 깨진다. 사이드바를 포함해 숙소 스코프 이동은 전부 이 함수를 쓴다.
 *
 * TODO(별도 처리): **이 훅의 사용을 강제할 방법이 없다.**
 *    `<Link to="/calendar">`를 직접 쓰면 `?property=`가 빠지는데 컴파일
 *    타임에 막을 수단이 없다. ESLint 커스텀 규칙이나 Link 래퍼 컴포넌트는
 *    D-32 일정에 넣을 범위가 아니라고 판단했다(래퍼는 navigate() 경로를
 *    못 막는 문제도 그대로다). 당분간 `docs/ui_design.md`에 규칙으로
 *    명시하는 것으로 대신한다.
 *
 * 근거: docs/ui_design.md 6-1절(컨텍스트를 함께 전달한다)
 */

import { useCallback } from "react";
import { useLocation, useSearchParams } from "react-router-dom";

export type PropertyLinkBuilder = (to: string) => string;

export function usePropertyLink(): PropertyLinkBuilder {
  const { pathname } = useLocation();
  const [searchParams] = useSearchParams();

  /**
   * ⚠️ `searchParams` **객체를 의존성에 넣지 않는다.** 리렌더마다 새
   * 객체라 useCallback이 매번 무효화되고, useEffect에 넣으면 무한 루프가
   * 된다. 직렬화한 **문자열만** 쓴다.
   */
  const currentQuery = searchParams.toString();

  return useCallback(
    (to: string) => {
      const [path, ownQuery = ""] = to.split("?");

      /**
       * 같은 화면이면 현재 쿼리를 **전부** 보존한다.
       * `/actions?status=OPEN&size=20`에서 property를 붙일 때
       * status·size가 날아가면 안 된다.
       *
       * 다른 화면이면 `property`만 넘긴다. status·size 같은 값은 화면마다
       * 의미가 달라서, 액션센터의 `status=OPEN`이 청소 화면으로 따라가면
       * 엉뚱한 필터가 걸린다.
       */
      const params =
        path === pathname
          ? new URLSearchParams(currentQuery)
          : new URLSearchParams();

      // 호출부가 `to`에 직접 붙인 쿼리가 가장 우선한다.
      for (const [key, value] of new URLSearchParams(ownQuery)) {
        params.set(key, value);
      }

      if (!params.has("property")) {
        const property = new URLSearchParams(currentQuery).get("property");
        if (property !== null && property !== "") {
          params.set("property", property);
        }
      }

      const query = params.toString();
      return query === "" ? path : `${path}?${query}`;
    },
    [pathname, currentQuery],
  );
}
