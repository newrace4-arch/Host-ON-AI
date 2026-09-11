/**
 * 계정 메뉴 — 로그아웃 (2026-09-11)
 *
 * 근거: docs/ui_design.md 1-5·5절
 *   "로그아웃은 프론트에서 처리한다 — localStorage의 토큰을 지우고
 *    /login으로 이동한다. 진입점은 Header의 계정 메뉴다"
 *   (api_contract 1.5절: POST /auth/logout 같은 엔드포인트는 두지 않는다.
 *    JWT는 무상태라 서버가 이미 발급한 토큰을 무효화할 수 없다.)
 *
 * ## navigate가 아니라 window.location이다
 *
 * 401 인터셉터와 **같은 이유**다. 로그아웃은 세션이 끝났다는 뜻이고,
 * navigate로 전환하면 이전 세션의 숙소 목록·대시보드 데이터가 React 상태에
 * 남는다. 다른 계정으로 로그인하면 **남의 자료가 잠깐 비칠 여지**가 생긴다.
 * 전체 리로드는 그것을 구조적으로 막는다.
 *
 * ## 호스트 이름을 표시하지 않는다
 *
 * `GET /auth/me`로 받아올 수 있지만 **지금은 부르는 곳이 없다.** 이름을
 * 보여주려고 여기서 호출하면 화면마다 왕복이 하나 붙는다. 사용자 정보를
 * 어디서 한 번 받아 어떻게 나눠 쓸지는 별도 설계가 필요하고(ui_design은
 * 아직 정하지 않았다), 로그아웃 버튼은 그것 없이도 동작한다.
 *
 * ⚠️ 드롭다운을 만들지 않았다. 항목이 로그아웃 하나뿐이라 여는 동작이
 *    한 단계 늘기만 한다. 항목이 늘면 그때 메뉴로 바꾼다.
 */

import { clearAccessToken } from "@/api/client";

export default function AccountMenu() {
  function handleLogout() {
    clearAccessToken();

    // `redirect`를 붙이지 않는다 — 스스로 나간 사용자를 원래 화면으로
    //   되돌릴 이유가 없고, **다른 계정으로 로그인할 수도 있다.** 그때
    //   이전 사용자가 보던 경로로 보내면 엉뚱한 화면이 뜬다.
    //
    // `reason=logout`은 붙인다. ui_design 1-6절이 "왜 로그인 화면으로
    //   왔는지 반드시 알린다"고 정했고, 버튼을 눌렀는데 화면만 바뀌면
    //   "로그아웃이 된 건가" 싶어진다. 다만 "만료"도 "필요"도 아니므로
    //   세 번째 사유로 나눈다 — 스스로 나간 사람에게 "만료되었습니다"라고
    //   하면 거짓말이 된다(ProtectedRoute의 reason 주석과 같은 이유).
    window.location.replace("/login?reason=logout");
  }

  return (
    <button
      type="button"
      onClick={handleLogout}
      className="rounded border border-gray-300 px-3 py-1 text-sm text-gray-700 hover:bg-gray-50"
    >
      로그아웃
    </button>
  );
}
