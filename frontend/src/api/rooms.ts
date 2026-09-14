/**
 * 객실·침대 API (2026-09-14)
 *
 * 🔴 **캘린더 그리드의 행 구성에 쓴다.** api_contract 2.1절 「용도」가
 * 두 가지를 적는데 그 첫 번째다 — `ROOM`/`BED` 단위 숙소는 하위 단위를
 * 별도 행으로 그리므로(ui_design 1-4절) **화면 진입 시점에** 목록이
 * 필요하다. 예약 생성 모달이 선택지를 채울 때가 두 번째다.
 *
 * ⚠️ **모달을 열 때마다 부르지 않는다.** 진입 시 한 번 받아 화면이
 * 소유한다 — 9/11에 `GET /properties`가 화면당 2회 나가던 것을
 * `Outlet context`로 해소한 것과 같은 자리다(`usePropertyList` 도크스트링).
 *
 * ## 침대는 객실 수만큼 부른다
 *
 * `BEDS`에 `property_id` 컬럼이 없어 **숙소 단위 조회 경로가 존재하지
 * 않는다**(api_contract 2.2절). `BED` 단위 숙소에서만 필요하고, 실측상
 * 운영 숙소의 객실이 0~1개라 지금은 최대 1회다.
 *
 * > **다시 볼 조건**(4.4절): 한 숙소의 객실이 **10개를 넘으면**
 * > `GET /properties/{id}/beds` 신설을 검토한다. 예약 응답에 이름을
 * > 담는 쪽이 아니다 — 이름의 출처는 하나로 둔다.
 */

import { api } from "@/api/client";
import type { Bed, Room } from "@/types/ui";

/** GET /properties/{property_id}/rooms */
export async function fetchRooms(propertyId: number): Promise<Room[]> {
  const res = await api.get<Room[]>(`/properties/${propertyId}/rooms`);
  // 🔴 빈 배열은 **정상**이다(2.1절). `PROPERTY` 단위 숙소는 객실 개념이
  //   없으므로 0건이 맞고, 에러나 EMPTY로 처리하면 안 된다.
  return res.data ?? [];
}

/** GET /rooms/{room_id}/beds */
export async function fetchBeds(roomId: number): Promise<Bed[]> {
  const res = await api.get<Bed[]>(`/rooms/${roomId}/beds`);
  // `ROOM` 단위 숙소의 객실은 침대를 나누어 팔지 않아 빈 배열이 정상이다(2.2절).
  return res.data ?? [];
}

/**
 * 객실 목록 + 각 객실의 침대를 한 번에 받는다.
 *
 * `BED` 단위 숙소가 아니면 침대를 부르지 않는다 — 어차피 빈 배열이고,
 * 객실 수만큼 왕복이 낭비된다.
 */
export async function fetchRoomsWithBeds(
  propertyId: number,
  needBeds: boolean,
): Promise<{ room: Room; beds: Bed[] }[]> {
  const rooms = await fetchRooms(propertyId);
  if (!needBeds || rooms.length === 0) {
    return rooms.map((room) => ({ room, beds: [] }));
  }

  // 객실 수만큼 병렬로 부른다. 순차로 하면 객실 수에 비례해 느려진다.
  const bedLists = await Promise.all(rooms.map((r) => fetchBeds(r.room_id)));
  return rooms.map((room, i) => ({ room, beds: bedLists[i] ?? [] }));
}
