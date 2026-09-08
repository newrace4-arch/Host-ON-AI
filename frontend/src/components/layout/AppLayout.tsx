/**
 * 앱 레이아웃 (2026-09-08)
 *
 * **pathless layout route로 구성한다** — 조건부 렌더링이 아니다.
 * App.tsx에서 `<Route element={<AppLayout />}>`로 감싸면 화면 전환 시
 * 레이아웃이 리렌더되지 않는다.
 *
 * 적용 범위: 운영 화면 8개.
 * /login, /signup, /onboarding은 **제외**한다 — 로그인 전이거나 초기 설정
 * 중이라 사이드바·숙소 전환기가 의미 없다.
 *
 * **숙소 목록의 소유자다(9/8).** 여기서 한 번 부르고 Header(전환기)와
 * 하위 화면 양쪽에 내려준다. 이유와 9/11 재검토 예정은
 * `hooks/usePropertyList.ts` 주석 참고.
 */

import { Outlet } from "react-router-dom";

import Header from "@/components/layout/Header";
import Sidebar from "@/components/layout/Sidebar";
import { usePropertyList } from "@/hooks/usePropertyList";
import type { AppOutletContext } from "@/types/ui";

export default function AppLayout() {
  const propertyList = usePropertyList();
  const outletContext: AppOutletContext = { propertyList };

  return (
    <div className="flex min-h-screen flex-col">
      <Header propertyList={propertyList} />
      <div className="flex flex-1">
        <Sidebar />
        <main className="flex-1">
          {/* 하위 화면은 useOutletContext<AppOutletContext>()로 받는다.
              목록을 각자 부르면 화면마다 같은 요청이 반복된다. */}
          <Outlet context={outletContext} />
        </main>
      </div>
    </div>
  );
}
