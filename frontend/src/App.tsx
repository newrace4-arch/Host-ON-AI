/**
 * 라우팅 (2026-09-08)
 *
 * 라우트 12개. `/dashboard`만 실제 구현하고 나머지 11개는 Placeholder
 * 하나를 이름만 바꿔 재사용한다.
 *
 * AppLayout은 **pathless layout route**다(path 없이 element만 지정).
 * /login·/signup·/onboarding은 이 바깥에 두어 사이드바가 나오지 않는다.
 *
 * `WakeUpGate`가 **라우터 전체를 감싼다**(9/8). 서버가 깨어나기 전에
 * 라우터가 렌더링되면 대시보드가 슬립 중인 서버로 숙소 3~5개분 요청을
 * 한꺼번에 보내 웨이크업 전략이 무력화된다.
 */

import { Navigate, Route, Routes } from "react-router-dom";

import ProtectedRoute from "@/components/ProtectedRoute";
import WakeUpGate from "@/components/WakeUpGate";
import AppLayout from "@/components/layout/AppLayout";
import Dashboard from "@/pages/Dashboard";
import Login from "@/pages/Login";
import Placeholder from "@/pages/Placeholder";
import Signup from "@/pages/Signup";

export default function App() {
  return (
    <WakeUpGate>
      <Routes>
        {/* 레이아웃 밖 — 로그인 전이거나 초기 설정 중 */}
        {/* /login·/signup은 9/11 r47에서 실제 구현됐다.
            /onboarding은 아직 Placeholder다 — 가입 성공 시 여기로
            보내지만(ui_design 4-2절) 화면 자체는 미구현이다. */}
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />

        {/* 여기부터 로그인 필요 — 나머지 11개 전부.
            위 두 경로 외에 비로그인 접근이 허용되는 경로는 없다
            (ui_design 1-6절, 2절 라우트 표 전수 확인).
            /onboarding도 보호한다 — POST /properties를 부르므로 토큰이
            없으면 어차피 아무것도 못 한다. */}
        <Route element={<ProtectedRoute />}>
          {/* 레이아웃 밖 — 숙소 개념 이전 단계라 사이드바가 없다. */}
          <Route path="/onboarding" element={<Placeholder name="온보딩" />} />

          {/* 레이아웃 안 — 운영 화면 9개.
              `scoped`는 ?property= 컨텍스트가 필요한 화면 7개를 뜻한다.
              **라우트는 숙소 유무와 무관하게 항상 등록한다** — 조건부로
              등록하면 URL 직접 입력·새로고침에서 404가 뜨고 원인을 알 수
              없다. 목록이 없을 때의 안내는 PropertyScopeGate가 맡는다. */}
          <Route element={<AppLayout />}>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            {/* TODO(9/11~): Placeholder → 실제 컴포넌트로 교체 */}
            <Route path="/calendar" element={<Placeholder name="캘린더" scoped />} />
            <Route path="/inquiries" element={<Placeholder name="AI 인박스" scoped />} />
            <Route path="/actions" element={<Placeholder name="액션센터" scoped />} />
            <Route path="/cleaning" element={<Placeholder name="청소 관리" scoped />} />
            <Route path="/settlements" element={<Placeholder name="정산 리포트" scoped />} />
            {/* TODO: ui_design 2절은 /compliance를 /settings 4번째 탭으로
                흡수했다(9/8). 라우트 제거는 설정 화면 구현 시 함께 한다. */}
            <Route path="/compliance" element={<Placeholder name="인허가 체크리스트" />} />
            <Route path="/knowledge" element={<Placeholder name="지식베이스" scoped />} />
            <Route path="/settings" element={<Placeholder name="설정" scoped />} />
          </Route>
        </Route>
      </Routes>
    </WakeUpGate>
  );
}
