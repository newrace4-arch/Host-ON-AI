/**
 * 사이드바 (2026-09-08)
 *
 * 라우트 12개를 **평면 배치**한다. 모드·그룹 계층을 만들지 않는다
 * (ui_design.md 1-2절 원칙 3 — 12개는 한 화면에 들어가고, 묶으면 클릭이
 * 늘고 위치를 외워야 한다). 애니메이션·접기도 없다.
 */

import { NavLink } from "react-router-dom";

const NAV = [
  { to: "/dashboard", label: "대시보드" },
  { to: "/calendar", label: "캘린더" },
  { to: "/inquiries", label: "AI 인박스" },
  { to: "/actions", label: "액션센터" },
  { to: "/cleaning", label: "청소" },
  { to: "/settlements", label: "정산" },
  { to: "/compliance", label: "컴플라이언스" },
  { to: "/knowledge", label: "지식베이스" },
  { to: "/settings", label: "설정" },
];

export default function Sidebar() {
  return (
    <nav className="w-48 shrink-0 border-r border-gray-300 p-3">
      <ul className="space-y-1">
        {NAV.map((item) => (
          <li key={item.to}>
            <NavLink
              to={item.to}
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
