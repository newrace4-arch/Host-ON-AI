/**
 * 라우팅 (2026-09-08)
 *
 * 라우트 12개. `/dashboard`만 실제 구현하고 나머지 11개는 Placeholder
 * 하나를 이름만 바꿔 재사용한다.
 *
 * AppLayout은 **pathless layout route**다(path 없이 element만 지정).
 * /login·/signup·/onboarding은 이 바깥에 두어 사이드바가 나오지 않는다.
 *
 * `WakeUpGate`가 **라우터 전체를 감싼다**(9/9). 서버가 깨어나기 전에
 * 라우터가 렌더링되면 대시보드가 슬립 중인 서버로 숙소 3~5개분 요청을
 * 한꺼번에 보내 웨이크업 전략이 무력화된다.
 */

import { Navigate, Route, Routes } from "react-router-dom";

import WakeUpGate from "@/components/WakeUpGate";
import AppLayout from "@/components/layout/AppLayout";
import Dashboard from "@/pages/Dashboard";
import Placeholder from "@/pages/Placeholder";

export default function App() {
  return (
    <WakeUpGate>
      <Routes>
        {/* 레이아웃 밖 — 로그인 전이거나 초기 설정 중 */}
        {/* TODO(9/9): Placeholder → 실제 컴포넌트로 교체 */}
        <Route path="/login" element={<Placeholder name="로그인" />} />
        <Route path="/signup" element={<Placeholder name="회원가입" />} />
        <Route path="/onboarding" element={<Placeholder name="온보딩" />} />

        {/* 레이아웃 안 — 운영 화면 9개 */}
        <Route element={<AppLayout />}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          {/* TODO(9/9~): Placeholder → 실제 컴포넌트로 교체 */}
          <Route path="/calendar" element={<Placeholder name="캘린더" />} />
          <Route path="/inquiries" element={<Placeholder name="AI 인박스" />} />
          <Route path="/actions" element={<Placeholder name="액션센터" />} />
          <Route path="/cleaning" element={<Placeholder name="청소 관리" />} />
          <Route path="/settlements" element={<Placeholder name="정산 리포트" />} />
          <Route path="/compliance" element={<Placeholder name="인허가 체크리스트" />} />
          <Route path="/knowledge" element={<Placeholder name="지식베이스" />} />
          <Route path="/settings" element={<Placeholder name="설정" />} />
        </Route>
      </Routes>
    </WakeUpGate>
  );
}
