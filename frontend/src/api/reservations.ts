/**
 * 예약 API (2026-09-14)
 *
 * api_contract 4.3절. 캘린더 그리드가 **그 기간의 예약 블록 전부**를
 * 그릴 때 쓴다.
 *
 * ## 기간은 "겹치는 것 전부"다
 *
 * 서버가 `check_in <= :end AND check_out > :start`로 본다. 그 달 안에서
 * 시작하거나 끝나는 것뿐 아니라 **달을 가로지르는 예약도 포함**되며,
 * 빠뜨리면 그리드에서 막대가 끊긴다.
 *
 * ## `meta`가 없다
 *
 * 0절 메타 규약의 예외다 — 캘린더는 그 기간 전부를 받아야 하므로
 * 페이지네이션이 구조적으로 적용될 수 없다. 일부만 받으면 존재하는
 * 예약이 그리드에서 사라진다(`GET /properties`가 예외인 것과 같은 이유).
 *
 * ## `room_name`·`bed_label`이 응답에 없다
 *
 * `room_id`·`bed_id`만 온다(4.4절). 이름은 `GET /properties/{id}/rooms`·
 * `GET /rooms/{id}/beds`에서 오며, **출처를 하나로 두기 위한 결정**이다 —
 * 예약 응답에 이름을 박아두면 객실명을 바꿨을 때 캘린더와 예약 목록이
 * 서로 다른 이름을 보여준다. 화면이 진입 시 받아 둔 목록에서 찾아 쓴다.
 */

import { api } from "@/api/client";
import { shouldFailReservations } from "@/api/mock/scenarios";
import type { Reservation } from "@/types/ui";

/** `Date` → `YYYY-MM-DD`. `toISOString()`은 UTC로 밀려 날짜가 하루 어긋난다. */
export function toDateParam(d: Date): string {
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

/**
 * GET /properties/{property_id}/reservations?start=&end=
 *
 * ⚠️ 파라미터 이름이 `from`이 아니라 `start`다 — `from`은 파이썬 예약어라
 * 서버가 `from_`·`from_date` 같은 회피 이름을 쓰게 되고, 그러면 쿼리
 * 파라미터명과 코드 변수명이 갈린다(api_contract 4.3절).
 */
export async function fetchReservations(
  propertyId: number,
  start: string,
  end: string,
): Promise<Reservation[]> {
  // Mock 분기는 **이 계층에서만** 한다(api/properties.ts와 같은 규약).
  //   에러 상태를 눈으로 확인하려면 실패를 만들 수 있어야 하는데,
  //   서버를 고장 낼 수는 없다.
  if (shouldFailReservations(propertyId)) {
    throw new Error(`mock: ${propertyId}번 숙소 예약 조회 실패`);
  }

  const res = await api.get<Reservation[]>(
    `/properties/${propertyId}/reservations?start=${start}&end=${end}`,
  );
  return res.data ?? [];
}
