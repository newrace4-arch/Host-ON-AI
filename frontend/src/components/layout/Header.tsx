/**
 * 헤더 (2026-09-08)
 *
 * `PropertySwitcher`는 **Header에 위치하는 전역 컴포넌트다**
 * (docs/ui_design.md 5-3절). 목록은 직접 부르지 않고 AppLayout이 내려준다.
 */

import PropertySwitcher from "@/components/layout/PropertySwitcher";
import type { PropertyListState } from "@/types/ui";

export default function Header({
  propertyList,
}: {
  propertyList: PropertyListState;
}) {
  return (
    <header className="flex h-14 items-center justify-between border-b border-gray-300 px-4">
      <span className="font-semibold">Host ON</span>

      <div className="flex items-center gap-4">
        <PropertySwitcher list={propertyList} />
        {/* TODO(9/11): 로그인 구현 시 계정 메뉴(로그아웃·호스트 정보) 연결 */}
        <span className="text-sm text-gray-500">계정</span>
      </div>
    </header>
  );
}
