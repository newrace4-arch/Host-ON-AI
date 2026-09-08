/**
 * Mock 데이터 (2026-09-08)
 *
 * 백엔드에 구현된 엔드포인트가 /health뿐이라 대시보드를 검증할 방법이
 * 없다. API 계층에서만 분기하며 **컴포넌트와 훅은 이 파일의 존재를
 * 모른다.**
 *
 * 숙소를 3개 둔 이유: 1~2개면 PARTIAL의 "N개 중 M개 기준" 표시가
 * 의미 있게 검증되지 않는다.
 */

import type { ActionItem, DashboardSummary, Property } from "@/types/ui";

export const mockProperties: Property[] = [
  {
    property_id: 1,
    name: "마포 3룸 독채",
    accommodation_type: "URBAN_HOMESTAY",
    bookable_unit_type: "PROPERTY",
  },
  {
    property_id: 2,
    name: "홍대 호스텔",
    accommodation_type: "HOSTEL",
    bookable_unit_type: "BED",
  },
  {
    property_id: 3,
    name: "연남 게스트하우스",
    accommodation_type: "HOSTEL",
    bookable_unit_type: "ROOM",
  },
];

/**
 * conflict_count를 세 숙소가 각각 다른 값으로 갖는다.
 *   1번 → 2    (충돌 있음)
 *   2번 → 0    (충돌 없음)
 *   3번 → null (계산 실패 = 확인 불가)
 * 화면에서 셋이 다르게 보이는지가 오늘의 검증 항목이다.
 */
export const mockSummaries: Record<number, DashboardSummary> = {
  1: {
    property_id: 1,
    property_name: "마포 3룸 독채",
    today_checkin_count: 2,
    today_checkout_count: 1,
    today_turnover_count: 1,
    open_action_count: 5,
    red_now_count: 1,
    yellow_today_count: 2,
    green_auto_count: 2,
    cleaning_pending_count: 2,
    cleaning_issue_count: 0,
    conflict_count: 2,
  },
  2: {
    property_id: 2,
    property_name: "홍대 호스텔",
    today_checkin_count: 4,
    today_checkout_count: 3,
    today_turnover_count: 2,
    open_action_count: 3,
    red_now_count: 0,
    yellow_today_count: 1,
    green_auto_count: 2,
    cleaning_pending_count: 3,
    cleaning_issue_count: 1,
    conflict_count: 0,
  },
  3: {
    property_id: 3,
    property_name: "연남 게스트하우스",
    today_checkin_count: 1,
    today_checkout_count: 0,
    today_turnover_count: 0,
    open_action_count: 2,
    red_now_count: 0,
    yellow_today_count: 0,
    green_auto_count: 2,
    cleaning_pending_count: 0,
    cleaning_issue_count: 0,
    conflict_count: null,
  },
};

export const mockActionItems: ActionItem[] = [
  {
    action_id: 91,
    property_id: 1,
    reservation_id: 501,
    risk_level: "RED_NOW",
    category: "CLEANING_DELAY",
    title: "체크인 2시간 전인데 청소 미완료",
    content: "마포 3룸 독채 · 오늘 16:00 체크인",
    status: "OPEN",
    created_at: "2026-09-08T09:12:00Z",
  },
  {
    action_id: 92,
    property_id: 1,
    reservation_id: null,
    risk_level: "YELLOW_TODAY",
    category: "COMPLIANCE_EXPIRY",
    title: "영업신고증 만료 D-3",
    content: null,
    status: "OPEN",
    created_at: "2026-09-08T08:40:00Z",
  },
  {
    action_id: 93,
    property_id: 2,
    reservation_id: null,
    risk_level: "YELLOW_TODAY",
    category: "PRICE_ADJUSTMENT",
    title: "9/16 평일 공백 — 147,000원 추천",
    content: "평일·체크인 3일 이내·미예약",
    status: "OPEN",
    created_at: "2026-09-08T00:05:00Z",
  },
  {
    action_id: 94,
    property_id: 2,
    reservation_id: 612,
    risk_level: "GREEN_AUTO",
    category: "CLEANING_DELAY",
    title: "청소 완료 확인 대기",
    content: null,
    status: "OPEN",
    created_at: "2026-09-07T23:10:00Z",
  },
  {
    action_id: 95,
    property_id: 3,
    reservation_id: null,
    risk_level: "GREEN_AUTO",
    category: "PRICE_NEGLECT",
    title: "추석 연휴 기본가 방치 감지",
    content: "자동 조정 대상 아님 — 호스트 확인 필요",
    status: "OPEN",
    created_at: "2026-09-07T00:05:00Z",
  },
];
