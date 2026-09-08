/**
 * 사이드바 (2026-09-08)
 *
 * 운영 화면을 **평면 배치**한다. 모드·그룹 계층을 만들지 않는다
 * (ui_design.md 1-2절 원칙 3 — 한 화면에 들어가고, 묶으면 클릭이 늘고
 * 위치를 외워야 한다). 애니메이션·접기도 없다.
 *
 * **숙소 스코프 화면 링크에는 `usePropertyLink()`를 쓴다.** 각 컴포넌트가
 * 쿼리를 직접 조립하면 화면 하나만 빠져도 딥링크가 깨진다.
 */

import { NavLink } from "react-router-dom";

import { usePropertyLink } from "@/hooks/usePropertyLink";

/**
 * `scoped`: `?property=` 컨텍스트를 이어받는 화면인가.
 *
 * `/dashboard`는 **전체 숙소 통합 뷰**라 특정 숙소로 좁히면 존재 이유가
 * 없어진다(ui_design.md 4-4절). 쿼리를 붙이지 않는다.
 */
const NAV: { to: string; label: string; scoped: boolean }[] = [
  { to: "/dashboard", label: "대시보드", scoped: false },
  { to: "/calendar", label: "캘린더", scoped: true },
  { to: "/inquiries", label: "AI 인박스", scoped: true },
  { to: "/actions", label: "액션센터", scoped: true },
  { to: "/cleaning", label: "청소", scoped: true },
  { to: "/settlements", label: "정산", scoped: true },
  // TODO(설정 화면 구현 시): /compliance 라우트를 제거한다. 컴플라이언스는
  // /settings 인허가 탭으로 흡수됐고(ui_design.md 4-11절) 사이드바 메뉴는
  // 8개다. 지금은 Placeholder라 남겨두되 숙소 컨텍스트는 잇지 않는다.
  { to: "/compliance", label: "컴플라이언스", scoped: false },
  { to: "/knowledge", label: "지식베이스", scoped: true },
  { to: "/settings", label: "설정", scoped: true },
];

export default function Sidebar() {
  const propertyLink = usePropertyLink();

  return (
    <nav className="w-48 shrink-0 border-r border-gray-300 p-3">
      <ul className="space-y-1">
        {NAV.map((item) => (
          <li key={item.to}>
            <NavLink
              to={item.scoped ? propertyLink(item.to) : item.to}
              // 쿼리가 붙어도 활성 판정은 경로만 본다(NavLink 기본 동작).
              className={({ isActive }) =>
                `block rounded px-3 py-2 text-sm ${
                  isActive ? "bg-gray-200 font-semibold" : "hover:bg-gray-100"
                }`
              }
            >
              {item.label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
