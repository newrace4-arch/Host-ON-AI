/**
 * 통합 캘린더 (2026-09-14, r48)
 *
 * ## 행 구성 — ui_design 1-4절
 *
 *   PROPERTY  한 줄(숙소 전체)
 *   ROOM      숙소 전체 행 + 객실 행
 *   BED       숙소 전체 행 + 객실 행(접기/펼치기) + 침대 행
 *
 * **숙소 전체 행을 `PROPERTY` 숙소에만 두지 않는다.** `room_id`가 `null`인
 * 예약은 판매단위와 무관하게 존재할 수 있고(독채 통대여 이력, iCal 숙소
 * 전체 피드), 그 행이 없으면 **예약이 화면에서 사라진다.**
 *
 * ## 공통 컴포넌트를 만들지 않는다
 *
 * 로딩·에러·빈 상태를 **인라인 JSX**로 그린다. `Loading`·`EmptyState`
 * 컴포넌트는 **r58(9/15)에서** 만든다 — 지금 화면이 둘뿐이라
 * (`Dashboard`·여기) 표본이 모자라고, CLAUDE.md 화면 규칙의 근거가
 * *"화면을 **3~4개** 먼저 만들면"*이다. 그리고 공통 컴포넌트는
 * **여러 화면의 응답 형태를 새로 정하는 것**이라 등급 2다 — 여기서
 * 만들면 등급 3 작업에 등급 2가 딸려 온다.
 *
 * ## 이름은 여기서 조립한다
 *
 * 예약 응답에 `room_name`·`bed_label`이 없다(api_contract 4.4절).
 * `room_id`·`bed_id`만 오고, 이름은 진입 시 받아 둔 `rows`에서 찾는다 —
 * 출처를 하나로 두기 위한 결정이라 화면이 조립하는 것이 정상이다.
 */

import { useMemo, useState } from "react";

import PropertyScopeGate from "@/components/PropertyScopeGate";
import EmptyState from "@/components/state/EmptyState";
import Loading from "@/components/state/Loading";
import { useAppOutletContext } from "@/hooks/useAppOutletContext";
import { useCalendarData, type RoomRow } from "@/hooks/useCalendarData";
import { useSelectedProperty } from "@/hooks/useSelectedProperty";
import type { Property, Reservation } from "@/types/ui";

/** 예약이 어느 행에 속하는가. 행 키는 `p` / `r:{id}` / `b:{id}` */
function rowKeyOf(r: Reservation): string {
  if (r.bed_id !== null) return `b:${r.bed_id}`;
  if (r.room_id !== null) return `r:${r.room_id}`;
  return "p";
}

/** 상태 3종을 한 줄 뱃지로. `is_conflict`는 별도로 가장 강하게 표시한다. */
function StatusBadges({ r }: { r: Reservation }) {
  return (
    <span className="ml-2 space-x-1 text-[11px] text-gray-600">
      <span className="rounded bg-gray-100 px-1">{r.reservation_status}</span>
      {r.refund_status !== "NONE" && (
        <span className="rounded bg-gray-100 px-1">{r.refund_status}</span>
      )}
      <span className="rounded bg-gray-100 px-1">{r.financial_status}</span>
    </span>
  );
}

function ReservationBlock({ r }: { r: Reservation }) {
  // 🔴 is_conflict는 **가장 강한 경고색**이다(ui_design 1-4절) —
  //   호스트에게 최악의 사고이며 대시보드 conflict_count와 함께 즉시
  //   인지되어야 한다.
  const cls = r.is_conflict
    ? "border-red-600 bg-red-50 text-red-900"
    : "border-gray-300 bg-white text-gray-800";

  return (
    <li className={`rounded border px-2 py-1 text-xs ${cls}`}>
      {r.is_conflict && <strong className="mr-1">⚠ 충돌</strong>}
      <span className="font-medium">
        {r.check_in} ~ {r.check_out}
      </span>
      <span className="ml-2">{r.guest_name ?? "(게스트명 없음)"}</span>
      <StatusBadges r={r} />
      <span className="ml-2 text-gray-500">
        {/* net_amount가 null인 것은 "요금 미설정"이지 0원이 아니다
            (api_contract 2.3절 base_price 주석). */}
        {r.net_amount === null ? "요금 미설정" : `${r.net_amount.toLocaleString()}원`}
      </span>
    </li>
  );
}

function Row({
  label,
  sub,
  items,
  depth = 0,
}: {
  label: string;
  sub?: string;
  items: Reservation[];
  depth?: number;
}) {
  return (
    <div
      className="border-b border-gray-200 py-2"
      style={{ paddingLeft: depth * 16 }}
    >
      <div className="flex items-baseline gap-2">
        <span className="text-sm font-medium">{label}</span>
        {sub && <span className="text-xs text-gray-500">{sub}</span>}
        <span className="text-xs text-gray-400">({items.length}건)</span>
      </div>
      {items.length > 0 && (
        <ul className="mt-1 space-y-1">
          {items.map((r) => (
            <ReservationBlock key={r.reservation_id} r={r} />
          ))}
        </ul>
      )}
    </div>
  );
}

function RoomGroup({
  row,
  byRow,
}: {
  row: RoomRow;
  byRow: Map<string, Reservation[]>;
}) {
  const [open, setOpen] = useState(true);
  const hasBeds = row.beds.length > 0;

  return (
    <div>
      <div className="flex items-center gap-2 border-b border-gray-200 py-2 pl-4">
        {hasBeds && (
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="rounded border border-gray-300 px-1 text-xs"
            aria-expanded={open}
          >
            {open ? "▾" : "▸"}
          </button>
        )}
        <span className="text-sm font-medium">{row.room.room_name}</span>
        <span className="text-xs text-gray-500">
          {row.room.capacity === null ? "정원 미입력" : `정원 ${row.room.capacity}`}
        </span>
        <span className="text-xs text-gray-400">
          ({(byRow.get(`r:${row.room.room_id}`) ?? []).length}건)
        </span>
      </div>

      {(byRow.get(`r:${row.room.room_id}`) ?? []).length > 0 && (
        <ul className="space-y-1 py-1 pl-8">
          {(byRow.get(`r:${row.room.room_id}`) ?? []).map((r) => (
            <ReservationBlock key={r.reservation_id} r={r} />
          ))}
        </ul>
      )}

      {hasBeds &&
        open &&
        row.beds.map((b) => (
          <Row
            key={b.bed_id}
            label={`침대 ${b.bed_label}`}
            items={byRow.get(`b:${b.bed_id}`) ?? []}
            depth={2}
          />
        ))}
    </div>
  );
}

function CalendarBody({ property }: { property: Property }) {
  const [month, setMonth] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });

  const data = useCalendarData(property, month);

  /** 예약을 행 키로 묶는다. 렌더마다 다시 만들지 않게 메모한다. */
  const byRow = useMemo(() => {
    const m = new Map<string, Reservation[]>();
    for (const r of data.reservations) {
      const k = rowKeyOf(r);
      const arr = m.get(k);
      if (arr) arr.push(r);
      else m.set(k, [r]);
    }
    return m;
  }, [data.reservations]);

  const conflictCount = data.reservations.filter((r) => r.is_conflict).length;
  const label = `${month.getFullYear()}년 ${month.getMonth() + 1}월`;

  const shift = (delta: number) =>
    setMonth((m) => new Date(m.getFullYear(), m.getMonth() + delta, 1));

  return (
    <div className="mt-3">
      {/* 월 이동 — rooms는 다시 부르지 않는다(useCalendarData) */}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => shift(-1)}
          className="rounded border border-gray-400 px-2 py-1 text-sm"
        >
          ← 이전 달
        </button>
        <span className="text-sm font-medium">{label}</span>
        <button
          type="button"
          onClick={() => shift(1)}
          className="rounded border border-gray-400 px-2 py-1 text-sm"
        >
          다음 달 →
        </button>
        <span className="ml-2 text-xs text-gray-500">
          {property.name} · {property.bookable_unit_type}
        </span>
      </div>

      {/* 🔴 `listStatus === "success"`로 막는다. 이것이 없으면 월을 넘기는
          동안 **지난달 충돌 건수가 새 달 제목 아래 남는다** — 브라우저
          확인에서 실제로 관측됐다(9/14). `reservations`를 로딩 시작 때
          비우지 않기 때문인데, 비우면 그리드가 깜빡이므로 **표시 쪽을
          막는 것이 맞다**(ui.ts의 `refetching`이 같은 이유로 data를
          유지한다). */}
      {data.listStatus === "success" && conflictCount > 0 && (
        <div className="mt-3 rounded border border-red-600 bg-red-50 p-2 text-sm text-red-900">
          <strong>충돌 {conflictCount}건</strong> — 같은 숙소에서 판매단위를
          넘나드는 기간 겹침입니다. OTA 한쪽을 취소해야 해소됩니다.
        </div>
      )}

      {/* ── 행 구성 ─────────────────────────────────────────────── */}
      {data.layoutStatus === "loading" && (
        <div className="mt-4">
          <Loading label="객실 구성" />
        </div>
      )}

      {data.layoutStatus === "error" && (
        <div className="mt-4">
          <EmptyState
            tone="error"
            title="객실 구성을 불러오지 못했습니다"
            description="객실 목록이 없으면 어느 줄에 예약을 놓을지 정할 수 없습니다."
            action={{ kind: "retry", onRetry: data.reloadLayout }}
          />
        </div>
      )}

      {/* ── 예약 ────────────────────────────────────────────────── */}
      {data.layoutStatus === "success" && (
        <>
          {data.listStatus === "loading" && (
            <div className="mt-4">
              <Loading label={`${label} 예약`} />
            </div>
          )}

          {data.listStatus === "error" && (
            <div className="mt-4">
              <EmptyState
                tone="error"
                title={`${label} 예약을 불러오지 못했습니다`}
                description="객실 구성은 정상입니다. 예약만 다시 받으면 됩니다."
                action={{ kind: "retry", onRetry: data.reloadList }}
              />
            </div>
          )}

          {data.listStatus === "success" && data.reservations.length === 0 && (
            // [r58] 3요소를 `EmptyState`가 강제한다 — ui_design 5-9절.
            //   문구는 4-5절이 정한 것을 쓴다.
            //   ⚠️ `<a href>`가 `<Link to>`로 바뀐다. 기존 `<a>`는 전체
            //     리로드라 앱 상태가 통째로 날아갔다(SPA에서 의도치 않은
            //     동작). 이동은 라우팅이 맞다.
            <div className="mt-4">
              <EmptyState
                tone="empty"
                title="이 기간에 예약이 없습니다"
                description="빈 날짜를 클릭해 예약을 추가하세요. 아직 채널을 연동하지 않았다면 먼저 연동하는 편이 빠릅니다."
                action={{
                  kind: "link",
                  to: `/settings?property=${property.property_id}`,
                  label: "채널 연동하러 가기 →",
                }}
              />
            </div>
          )}

          {data.listStatus === "success" && data.reservations.length > 0 && (
            <div className="mt-4 rounded border border-gray-200">
              {/* 숙소 전체 행 — 판매단위와 무관하게 항상 둔다(위 도크스트링) */}
              <Row
                label="숙소 전체"
                sub={property.name}
                items={byRow.get("p") ?? []}
              />
              {data.rows.map((row) => (
                <RoomGroup key={row.room.room_id} row={row} byRow={byRow} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default function Calendar() {
  const { propertyList } = useAppOutletContext();
  const selected = useSelectedProperty(propertyList);

  return (
    <div className="p-6">
      {/* 제목은 항상 보여준다 — 조회에 실패해도 어느 화면인지 알아야 한다
          (Placeholder와 같은 규약). 문구는 ui_design 2절 공식 화면명이다. */}
      <h1 className="text-lg font-semibold">캘린더</h1>
      <PropertyScopeGate>
        {selected.property ? (
          <CalendarBody property={selected.property} />
        ) : (
          <p className="mt-2 text-sm text-gray-600">숙소를 선택해 주세요.</p>
        )}
      </PropertyScopeGate>
    </div>
  );
}
