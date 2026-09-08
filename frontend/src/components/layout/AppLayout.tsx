/**
 * 앱 레이아웃 (2026-09-08)
 *
 * **pathless layout route로 구성한다** — 조건부 렌더링이 아니다.
 * App.tsx에서 `<Route element={<AppLayout />}>`로 감싸면 화면 전환 시
 * 레이아웃이 리렌더되지 않는다.
 *
 * 적용 범위: 운영 화면 9개.
 * /login, /signup, /onboarding은 **제외**한다 — 로그인 전이거나 초기 설정
 * 중이라 사이드바·숙소 전환기가 의미 없다.
 */

import { Outlet } from "react-router-dom";

import Header from "@/components/layout/Header";
import Sidebar from "@/components/layout/Sidebar";

export default function AppLayout() {
  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <div className="flex flex-1">
        <Sidebar />
        <main className="flex-1">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
