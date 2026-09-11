/**
 * 라우트 가드 — 비로그인 접근 차단 (2026-09-11)
 *
 * 근거: docs/ui_design.md 1-6절
 *   "비로그인 상태로 보호된 경로 직접 진입 → 라우트 가드가 같은 형태로
 *    `/login`에 보낸다"
 *
 * ## 왜 필요한가
 *
 * 가드가 없으면 비로그인 상태로 주소창에 `/dashboard`를 쳐도 화면이 뜬다.
 * API가 401을 뱉으면 인터셉터가 `/login`으로 보내주기는 하지만, **그
 * 전까지 빈 화면이 잠깐 보이고 서버 왕복을 한 번 헛되이 쓴다.** 대시보드는
 * 숙소 수만큼 병렬 호출하므로 헛된 왕복이 1회가 아니라 N회다.
 *
 * ## 토큰 유효성을 검증하지 않는다
 *
 * **토큰이 있는지만 본다.** 만료·서명 무효는 여기서 알 수 없고
 * (서버만 판정할 수 있다 — api_contract 1.4절), 확인하려면 화면 전환마다
 * `GET /auth/me` 왕복이 하나씩 붙는다.
 *
 * 만료된 토큰은 **첫 API 호출의 401에서 걸러지고** `client.ts`의 401
 * 인터셉터가 같은 형태로 `/login?redirect=`에 보낸다. 가드와 인터셉터가
 * 같은 목적지·같은 형태를 만들므로 사용자 입장에서는 구분되지 않는다.
 *
 * > 이 가드가 막는 것은 "토큰이 아예 없는 접근"이고, 인터셉터가 막는 것은
 * > "토큰이 있으나 더 이상 유효하지 않은 접근"이다. **둘은 대체 관계가
 * > 아니라 앞뒤 관계다.**
 *
 * ## 게이트 순서 — WakeUpGate 다음, PropertyScopeGate 앞
 *
 * `WakeUpGate`(라우터 바깥)가 먼저다. 비로그인 사용자에게도 웨이크업을
 * 먼저 시키는 이유는 **그 사용자가 다음에 할 일이 로그인이기 때문**이다.
 * 로그인은 `POST`라 재시도 대상이 아니어서(코딩규칙 9), 슬립 중인 서버를
 * 깨우지 않고 `/login`을 열면 **첫 로그인 시도가 타임아웃으로 반드시
 * 실패한다.** 비밀번호가 맞는데도 "서버와 연결할 수 없습니다"를 본다.
 * api_contract 1.4절도 같은 순서를 명시한다.
 */

import { Navigate, Outlet, useLocation } from "react-router-dom";

import { getAccessToken } from "@/api/client";

/**
 * 로그인 화면에 **왜** 왔는지. `/login`이 안내 문구를 가른다.
 *
 *   required — 로그인한 적이 없는데 보호된 경로로 들어왔다(이 가드)
 *   expired  — 쓰던 중 토큰이 만료됐다(client.ts의 401 인터셉터)
 *   (없음)   — `/login`에 직접 왔다. 안내하지 않는다
 *
 * ⚠️ **둘을 구분하지 않으면 거짓말이 된다.** `?redirect`만 보고 판정하면
 * 로그인한 적 없는 사용자에게 "로그인이 만료되었습니다"라고 말하게 되고,
 * 사용자는 자기가 뭘 잘못했는지 찾게 된다. ui_design 4-1절이 "세션 만료로
 * 밀려온 경우와 처음 방문한 경우를 구분하지 않으면 사용자는 앱이 고장난
 * 것으로 받아들인다"고 못박은 지점이다.
 */
export type LoginReason = "required" | "expired";

/**
 * 돌아갈 경로를 만든다 — **쿼리까지 포함**한다.
 *
 * `/cleaning?property=2&task_id=42`처럼 어느 숙소의 어느 작업을 보고
 * 있었는지가 쿼리에 있다. 경로만 복원하면 목록 첫 화면으로 돌아가
 * 사용자가 다시 찾아 들어가야 한다(ui_design 1-6절: "쿼리를 포함한 전체 경로").
 *
 * `hash`는 넣지 않는다 — 이 앱은 해시 라우팅도 앵커 이동도 쓰지 않는다.
 */
export function buildLoginPath(
  pathname: string,
  search: string,
  reason: LoginReason,
): string {
  const back = encodeURIComponent(pathname + search);
  return `/login?redirect=${back}&reason=${reason}`;
}

export default function ProtectedRoute() {
  const location = useLocation();

  if (!getAccessToken()) {
    // replace를 쓴다. push면 로그인 후 뒤로가기에서 보호된 경로로 돌아가
    //   다시 튕기는 왕복이 히스토리에 쌓인다.
    return (
      <Navigate
        to={buildLoginPath(location.pathname, location.search, "required")}
        replace
      />
    );
  }

  return <Outlet />;
}
