/**
 * 숙소 스코프 화면의 공통 전처리 (2026-09-08)
 *
 * **라우트를 조건부로 등록하지 않는다.** 라우트 존재 여부와 데이터 유무는
 * 다른 문제다. 숙소가 없다고 `/calendar`를 등록하지 않으면 사용자가 URL을
 * 직접 입력하거나 새로고침했을 때 **404가 뜨고 원인을 알 수 없다.**
 * 화면 목록이 늘 때마다 조건부 목록을 갱신해야 하는 유지보수 부담도 생긴다.
 * 라우트는 항상 등록하고, **화면 안에서** 안내한다.
 *
 * 숙소 스코프 화면 7개(/calendar·/inquiries·/actions·/cleaning·
 * /settlements·/knowledge·/settings)가 전부 같은 전처리를 필요로 하므로
 * 여기에 모은다. 실제 화면을 구현할 때 본문을 이 컴포넌트로 감싸면 된다.
 *
 *   <PropertyScopeGate>
 *     <CalendarBody propertyId={...} />
 *   </PropertyScopeGate>
 */

import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { useAppOutletContext } from "@/hooks/useAppOutletContext";

export default function PropertyScopeGate({
  children,
}: {
  children: ReactNode;
}) {
  const { propertyList } = useAppOutletContext();

  if (propertyList.status === "loading") {
    return <p className="mt-2 text-sm text-gray-500">숙소 목록 불러오는 중…</p>;
  }

  if (propertyList.status === "error") {
    return (
      <div className="mt-2">
        <p className="text-sm text-gray-700">숙소 목록을 불러오지 못했습니다</p>
        <p className="mt-1 text-sm text-gray-600">
          목록을 받지 못하면 어느 숙소의 자료를 보여줄지 정할 수 없습니다.
        </p>
        <button
          type="button"
          onClick={propertyList.reload}
          className="mt-3 rounded border border-gray-400 px-3 py-1 text-sm"
        >
          다시 시도
        </button>
      </div>
    );
  }

  if (propertyList.status === "empty") {
    // EmptyState 3요소(원인 / 다음 행동 / 그 행동으로 가는 링크)
    // — docs/ui_design.md 5-9절.
    return (
      <div className="mt-2">
        <p className="text-sm text-gray-700">등록된 숙소가 없습니다</p>
        <p className="mt-1 text-sm text-gray-600">
          숙소를 등록하면 이 화면에 자료가 쌓입니다.
        </p>
        <Link
          to="/onboarding"
          className="mt-3 inline-block rounded border border-gray-400 px-3 py-1 text-sm"
        >
          숙소 등록하러 가기 →
        </Link>
      </div>
    );
  }

  return <>{children}</>;
}
