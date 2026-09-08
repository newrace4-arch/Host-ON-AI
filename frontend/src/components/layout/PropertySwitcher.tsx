/**
 * 숙소 전환기 (2026-09-08)
 *
 * **대시보드의 필터가 아니다.** 대시보드는 전체 숙소 통합 뷰이고, 이
 * 컴포넌트는 개별 화면(캘린더·청소·정산 등)에 들어갈 때의 컨텍스트 전환
 * 도구다(docs/ui_design.md 5-3절).
 *
 * 목록은 직접 부르지 않고 AppLayout이 내려준다 — `usePropertyList` 주석 참고.
 */

import { useNavigate } from "react-router-dom";

import { useSelectedProperty } from "@/hooks/useSelectedProperty";
import type { PropertyListState } from "@/types/ui";

/** 드롭다운 하단 `+ 새 숙소 등록`의 sentinel 값 */
const NEW_PROPERTY = "__new";

export default function PropertySwitcher({
  list,
}: {
  list: PropertyListState;
}) {
  const navigate = useNavigate();
  const { propertyId, notice, dismissNotice, select } = useSelectedProperty(list);

  if (list.status === "loading") {
    return <span className="text-sm text-gray-500">숙소 불러오는 중…</span>;
  }

  if (list.status === "error") {
    return (
      <span className="text-sm text-gray-700">숙소 목록을 불러오지 못했습니다</span>
    );
  }

  if (list.status === "empty") {
    // 숙소 0개 — 자동 선택·폴백을 하지 않고 등록으로 유도한다.
    return (
      <button
        type="button"
        onClick={() => navigate("/onboarding")}
        className="rounded border border-gray-400 px-3 py-1 text-sm"
      >
        + 첫 숙소 등록
      </button>
    );
  }

  return (
    <div className="flex items-center gap-2">
      {notice !== null && (
        <span className="flex items-center gap-1 text-xs text-gray-600">
          {notice}
          <button
            type="button"
            onClick={dismissNotice}
            aria-label="안내 닫기"
            className="px-1"
          >
            ✕
          </button>
        </span>
      )}

      <select
        value={propertyId ?? ""}
        aria-label="숙소 선택"
        onChange={(e) => {
          const value = e.target.value;
          // `+ 새 숙소 등록` — 온보딩은 가입 직후 1회 경로라, 두 번째 숙소를
          // 추가할 진입점이 여기밖에 없다(ui_design.md 6-2절).
          if (value === NEW_PROPERTY) {
            navigate("/onboarding");
            return;
          }
          select(Number(value));
        }}
        className="rounded border border-gray-300 px-2 py-1 text-sm"
      >
        {/* 폴백 effect가 URL을 채우기 전 한 프레임 동안만 쓰인다. */}
        {propertyId === null && <option value="">숙소 선택</option>}

        {list.properties.map((p) => (
          <option key={p.property_id} value={p.property_id}>
            {p.name}
          </option>
        ))}

        <option value={NEW_PROPERTY}>+ 새 숙소 등록</option>
      </select>
    </div>
  );
}
