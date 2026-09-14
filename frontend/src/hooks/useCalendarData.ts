/**
 * 캘린더 데이터 훅 (2026-09-14, r48)
 *
 * 🔴 **두 축을 나눠서 받는다.** 합치면 월을 넘길 때마다 행 구성까지 다시
 * 받는다.
 *
 *   행 구성(rooms + beds)  숙소가 바뀔 때만    — 진입 시 1회
 *   예약(reservations)      숙소·월이 바뀔 때  — 진입 + 월 이동
 *
 * api_contract 2.1절 「용도」가 *"진입 시 한 번만 받아 화면이 소유한다"*로
 * 못박은 자리이며, 9/11에 `GET /properties`가 화면당 2회 나가던 것을
 * 해소한 것과 같은 판단이다.
 *
 * ## 🔴 상태를 effect가 아니라 **렌더 중에 판정한다**
 *
 * 처음에는 effect 안에서 `setListStatus("loading")`을 불렀는데, **브라우저
 * 확인에서 결함이 드러났다**(9/14) — 월을 넘기면 제목은 곧바로 *"10월"*이
 * 되는데 `reservations`는 아직 9월 것이고 `listStatus`도 아직
 * `"success"`라, **10월 제목 아래 9월 예약이 통째로 렌더되는 한 프레임**이
 * 있었다. `month`는 즉시 바뀌지만 상태 갱신은 effect가 돈 뒤이기 때문이다.
 *
 * 그래서 **"어느 키의 데이터를 들고 있는가"를 함께 저장하고**, 요청 키와
 * 다르면 렌더 시점에 `loading`으로 본다. 스스로 모순되는 화면이 원리상
 * 나올 수 없다.
 *
 * > 규칙 14번이 *"판정이 필요하면 업데이터 **바깥에서** 한다"*고 정한 것과
 * > 같은 방향이다 — **파생할 수 있는 값을 상태로 들지 않는다.**
 *
 * ## 상태를 둘로 나눈 이유
 *
 * *"행은 그렸는데 예약만 못 받았다"*가 실제로 가능하다. 하나로 합치면
 * 그 경우 **행까지 사라져** 사용자는 숙소 구조 자체가 망가진 줄 안다.
 * 대시보드의 `PARTIAL`과 성격이 다르다 — 저쪽은 **같은 종류의 호출 N개**
 * 중 일부 실패이고, 이쪽은 **다른 종류의 호출 둘**이다.
 *
 * ## StrictMode
 *
 * 규칙 14번대로 **ref 가드만** 쓴다. cleanup에 `cancelled` 플래그를 더하면
 * 첫 실행의 응답이 통째로 버려진다(troubleshooting 26번). 업데이터 안에서
 * 외부 변수를 읽거나 쓰지 않는다(28번).
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { fetchReservations, toDateParam } from "@/api/reservations";
import { fetchRoomsWithBeds } from "@/api/rooms";
import type { Bed, Property, Reservation, Room } from "@/types/ui";

export interface RoomRow {
  room: Room;
  beds: Bed[];
}

type Status = "loading" | "success" | "error";

export interface CalendarData {
  /** 행 구성 — 숙소가 바뀔 때만 다시 받는다 */
  layoutStatus: Status;
  rows: RoomRow[];
  /** 예약 — 월을 넘길 때마다 다시 받는다 */
  listStatus: Status;
  reservations: Reservation[];
  reloadLayout: () => void;
  reloadList: () => void;
}

/** 그 달의 1일과 말일. `new Date(y, m + 1, 0)`이 말일이다. */
export function monthRange(month: Date): { start: string; end: string } {
  const y = month.getFullYear();
  const m = month.getMonth();
  return {
    start: toDateParam(new Date(y, m, 1)),
    end: toDateParam(new Date(y, m + 1, 0)),
  };
}

/** 어느 키의 결과인지 함께 들고 있는 저장소. 키가 다르면 아직 안 온 것이다. */
interface Loaded<T> {
  key: string;
  ok: boolean;
  data: T;
}

const NOTHING = { key: "", ok: false, data: null } as const;

export function useCalendarData(
  property: Property | null,
  month: Date,
): CalendarData {
  const propertyId = property?.property_id ?? null;
  // `BED` 단위 숙소에서만 침대를 부른다 — 아니면 어차피 빈 배열이다(2.2절).
  const needBeds = property?.bookable_unit_type === "BED";
  const { start, end } = monthRange(month);

  const [layoutToken, setLayoutToken] = useState(0);
  const [listToken, setListToken] = useState(0);

  // 🔴 **요청 키**. 이 값이 바뀌는 순간(렌더 중) 아래 저장소의 키와
  //   달라지므로 상태가 즉시 `loading`이 된다 — effect를 기다리지 않는다.
  const layoutKey = `${propertyId}:${needBeds}:${layoutToken}`;
  const listKey = `${propertyId}:${start}:${end}:${listToken}`;

  const [layout, setLayout] = useState<Loaded<RoomRow[] | null>>(NOTHING);
  const [list, setList] = useState<Loaded<Reservation[] | null>>(NOTHING);

  const layoutRef = useRef("");
  const listRef = useRef("");

  // ── 행 구성 — 숙소가 바뀔 때만 ──────────────────────────────────
  useEffect(() => {
    if (propertyId === null) return;
    // 🔴 키에 **월이 들어가지 않는다.** 월 이동으로는 이 effect가 돌지
    //   않는다는 것이 이 훅의 요점이다(네트워크 로그로 확인 — 9/14).
    if (layoutRef.current === layoutKey) return;
    layoutRef.current = layoutKey;

    void fetchRoomsWithBeds(propertyId, needBeds)
      .then((rows) => setLayout({ key: layoutKey, ok: true, data: rows }))
      .catch(() => setLayout({ key: layoutKey, ok: false, data: null }));
  }, [propertyId, needBeds, layoutKey]);

  // ── 예약 — 숙소·월이 바뀔 때 ────────────────────────────────────
  useEffect(() => {
    if (propertyId === null) return;
    if (listRef.current === listKey) return;
    listRef.current = listKey;

    void fetchReservations(propertyId, start, end)
      .then((rows) => setList({ key: listKey, ok: true, data: rows }))
      .catch(() => setList({ key: listKey, ok: false, data: null }));
  }, [propertyId, start, end, listKey]);

  const reloadLayout = useCallback(() => setLayoutToken((t) => t + 1), []);
  const reloadList = useCallback(() => setListToken((t) => t + 1), []);

  // ── 렌더 중 판정 ────────────────────────────────────────────────
  //   키가 맞을 때만 데이터를 내보낸다. 지난달 것이 새 달 제목 아래
  //   남는 일이 **원리상** 생기지 않는다.
  const layoutFresh = layout.key === layoutKey;
  const listFresh = list.key === listKey;

  return {
    layoutStatus: !layoutFresh ? "loading" : layout.ok ? "success" : "error",
    rows: layoutFresh && layout.ok ? (layout.data ?? []) : [],
    listStatus: !listFresh ? "loading" : list.ok ? "success" : "error",
    reservations: listFresh && list.ok ? (list.data ?? []) : [],
    reloadLayout,
    reloadList,
  };
}
