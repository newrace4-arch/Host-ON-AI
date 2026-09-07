# Host ON (AI) — UI/UX 설계 (화면 목록 · 공통 컴포넌트)

## 0. 문서 성격

- **9/7 확정.** 화면 목록과 공통 컴포넌트의 SSOT다.
- 근거가 되는 API 스펙은 `docs/api_contract.md` **v1.8**.
- 이 문서는 체크리스트 9/7 태스크 **R33(전체 화면목록 확정)**과
  **R36(디자인시스템 공통 컴포넌트 정의)**의 산출물이다.
- **와이어프레임(R35)은 이 문서에 포함하지 않는다.** 화면 목록을
  크로스체크로 검증한 뒤 별도로 추가한다.

---

## 1. UI/UX 설계 원칙 (9/7)

### 1-1. 이 원칙의 근거

아래 원칙은 대부분 **우리 프로젝트의 API 구조와 실사용 판단**에서
나온 것이다. 9/7에 Hostaway·Guesty·Lodgify·ONDA를 조사했으나
공식 문서로 확인된 것은 아래 한 가지뿐이며 나머지는 해석이었다.
설계 근거를 "업계 표준"으로 서술하지 않는다.

**공식 문서로 확인된 것 (1건)**
- 예약 이벤트 기반 자동 청소 태스크 생성: Hostaway·Guesty·Lodgify
  3사 공식 문서에서 확인. 단 트리거 시점은 체크인/체크아웃 기준이며
  우리는 예약 확정 시점으로 더 이르다(의도된 차이)

**조사했으나 확인하지 못한 것 (2건)**
- 서로 다른 숙박업 유형을 한 계정에서 통합 관리하는 사례
- 숙박업 인허가·서류 만료를 관리하는 기능
  → 둘 다 "없다"가 아니라 "공개 자료로 확인 불가"다.
    발표·문서에서 이 표현을 지킨다

**조사 과정에서 사실이 아님이 확인된 것**
- "채널별 예약 블록 색상(에어비앤비 초록 / 부킹닷컴 파랑 등)"은
  사실이 아니다. Hostaway 공식 지원문서의 색상 체계는 채널이 아니라
  예약 상태 기준이다. 3회의 독립 검증에서 일치. 이 주장을 근거로
  쓰지 않는다.

**출처가 아니라 가설로 취급하는 것**
- "통합 뷰가 업계 기본값이다", "조회와 처리를 분리하는 것이 업계
  원칙이다", "경쟁 제품은 동선이 길어 피로하다" — 이 셋은 제품
  문서에서 확인된 사실이 아니라 화면을 보고 도출한 해석이다.
  우리 판단의 참고로만 쓰고, "경쟁사가 그렇게 한다"고 서술하지
  않는다.

**인용하지 않는 것**
- 경쟁 제품의 타깃 규모 숫자(5~100개, 2~20개 등)는 어느 것도 공식
  표기와 일치하지 않았다. 문서·발표에서 인용하지 않는다.
- ONDA는 비교 근거에서 제외한다. 유형 혼합 관리와 인허가 관리
  기능 두 항목이 우리 차별점과 정확히 겹치는데 둘 다 공개 자료로
  확인 불가이므로, 확인되지 않은 것을 "우리만 한다"의 근거로 쓸
  수 없다.

### 1-2. 설계 원칙 (우리 판단)

**1. 전체 통합이 기본, 개별 전환은 도구**
근거: property_id 스코프 엔드포인트가 13종. 숙소를 하나씩 골라야
조회되는 구조라 3~5개 운영 시 아침마다 5번 전환해야 한다.
대시보드는 전체 통합, PropertySwitcher는 개별 화면 전환용.

**2. 조회와 처리를 분리**
근거: 액션 카드는 운영이 쌓일수록 누적된다. 대시보드에 전부 담으면
스크롤 지옥, 상위 N건만 담으면 나머지를 볼 곳이 없다.
대시보드는 요약 + 상위 프리뷰, /actions는 전체 큐와 처리 이력.

**3. 사이드바에 계층을 만들지 않는다**
근거: 라우트 12개는 사이드바 한 화면에 들어간다. 모드·그룹으로
묶으면 클릭이 늘고 위치를 외워야 한다.
※ 이 원칙은 사이드바 네비게이션에 적용되며, 화면 내부의 탭
  구조(예: /settings 3탭)는 대상이 아니다.

**4. 위젯 구성은 고정**
근거: 커스터마이즈는 설정 화면과 저장 구조를 추가로 요구한다.
1인 개발 일정에서 우선순위가 아니다.

**5. 저해상도 와이어프레임**
근거: 이 단계의 목표는 "화면이 몇 개고 무엇이 들어가는가"다.
색·폰트·간격은 프론트 구현 시점에 정한다.
※ 이 원칙은 와이어프레임을 **어떻게 그릴지**에 대한 것이다.
  와이어프레임 자체(R35)를 이 문서에 포함할지 여부는 0절 참고.

### 1-3. 새 화면·기능 판단 기준

**"3~5개 숙소를 혼자 운영하는 호스트가 아침에 이걸 쓰는가?"**

아니면 넣지 않는다. 특히 아래는 이번 범위에서 제외한다.
- 고급 분석·커스텀 리포트
- 팀원 배정·권한 관리
- 오너 포털

### 1-4. 캘린더 표시 방식

PROPERTY 단위 숙소는 한 줄, ROOM/BED 단위 숙소는 접기/펼치기로
하위 단위를 별도 행에 표시한다.
근거: 하나의 예약 테이블로 세 판매 단위를 표현하는 우리 구조를
한 화면에 담는 방법. 유사 화면을 쓰는 제품이 있으나 공식 문서로
확인된 것은 "서브유닛 개별 행 표시"까지이며 접기/펼치기는 확인하지
못했다. 이 선택은 우리 판단이다.

**예약 블록 색상은 예약 상태 기준으로 구분한다.** 채널별 색상은
쓰지 않는다.
- 색상 대상 필드: reservation_status / refund_status /
  financial_status, 그리고 파생 필드 is_conflict
- **구체적인 색상 값은 여기서 정하지 않는다.** 원칙 5(저해상도)에
  따라 프론트 구현 시점에 정한다. 다만 is_conflict(더블부킹)는
  가장 강한 경고색을 쓴다 — 호스트에게 최악의 사고이며 대시보드
  conflict_count와 함께 즉시 인지되어야 한다.

---

## 2. 라우트 12개

| # | 라우트 | 화면명 | 주요 API | 비고 |
|---|---|---|---|---|
| 1 | `/login` | 로그인 | `POST /auth/login` | JWT 발급 |
| 2 | `/signup` | 회원가입 | `POST /auth/signup` | |
| 3 | `/onboarding` | 온보딩 위저드 | `POST /properties`, `POST /properties/{id}/rooms`, `POST /rooms/{room_id}/beds`, `POST /properties/{id}/channels` | 단일 URL, 2스텝 (아래 상세) |
| 4 | `/dashboard` | 통합 대시보드 | `GET /properties` + `GET /properties/{id}/dashboard/summary` × N | 전체 숙소 통합 |
| 5 | `/calendar` | 캘린더 | `GET /properties/{id}/reservations`, `GET /reservations/{id}`, `POST /reservations`, `PATCH /reservations/{id}/status` | 예약 생성/상세는 **모달** |
| 6 | `/inquiries` | AI 게스트 인박스 | `GET /properties/{id}/inquiries`, `GET /inquiries/{id}`, `POST /inquiries/{id}/regenerate`, `POST /inquiry-approvals/{id}/approve`, `POST /inquiry-approvals/{id}/reject` | 재시도 최대 2회(총 3회) |
| 7 | `/actions` | 액션센터 | `GET /properties/{id}/action-items?status=OPEN`, `PATCH /action-items/{id}/resolve`, `GET /properties/{id}/price-recommendations`, `POST /properties/{id}/price-recommendations/apply` | 가격 추천 승인 포함 |
| 8 | `/cleaning` | 청소 관리 | `GET /properties/{id}/cleaning-tasks`, `PATCH /cleaning-tasks/{id}/status`, `POST /cleaning-tasks/{id}/photo` | |
| 9 | `/settlements` | 정산 리포트 | `GET /properties/{id}/settlements`, `POST /properties/{id}/settlements/{month}/confirm`, `GET·PATCH /properties/{id}/financial-config` | 스냅샷 정산 |
| 10 | `/compliance` | 인허가 체크리스트 | `GET /properties/{id}/checklist-items`, `PATCH /checklist-items/{id}` | |
| 11 | `/knowledge` | RAG 지식베이스 | `GET·POST /properties/{id}/knowledge-chunks`, `DELETE /knowledge-chunks/{id}` | |
| 12 | `/settings` | 설정 (3탭) | `GET·PATCH /properties/{id}`, 채널 5종 | 아래 상세 |

### 2-3. `/onboarding` — 단일 URL, 2스텝 위저드

**라우트를 `/step1`, `/step2`로 쪼개지 않는다.**

| 스텝 | 내용 |
|---|---|
| **STEP 1** | 숙소 등록 + 판매단위 설정. `bookable_unit_type`이 `PROPERTIES` 컬럼이므로 **같은 폼에서 함께 받는다.** `ROOM`/`BED` 선택 시에만 객실 입력 폼이 조건부로 펼쳐진다 |
| **STEP 2** | iCal 채널 연동. **"나중에 하기" 허용** |

**지식베이스는 온보딩에 포함하지 않는다.** 대시보드 배너로 유도한다.
> 근거: 게스트 문의를 받아보고 채우는 정보이며, 온보딩에서 긴 텍스트
> 입력을 강제하면 이탈 지점이 된다.

### 2-12. `/settings` — 3탭

| 탭 | 내용 | API |
|---|---|---|
| 탭 1 | 숙소정보 | `GET·PATCH /properties/{id}` |
| 탭 2 | 가격정책 | `PATCH /properties/{id}` — `base_price`, `lower_bound_price`, `weekday_adjustment_enabled`, `holiday_adjustment_enabled` |
| 탭 3 | 채널연동 | `GET·POST /properties/{id}/channels`, `DELETE /channels/{id}`, `POST /channels/{id}/sync`, `GET /channels/{id}/sync-errors` |

**가격정책 탭이 필요한 근거**: api_contract 13절이 가격 추천 apply 시
하한가 위반을 `400 BELOW_LOWER_BOUND`로 거부하며 *"호스트가 하한가를
먼저 낮춰야 적용 가능"*이라고 명시한다. 즉 **하한가를 낮추는 화면이
반드시 필요하다.**

---

## 3. 제외한 화면과 근거

### `/checkin` (비대면 체크인) — **P1 확장 예정 화면**

- api_contract에 관련 엔드포인트 **0개**, DB명세서 16개 테이블에
  체크인 도메인 **없음**(9/7 확인).
- 체크리스트상 비대면 체크인은 **9/29~9/30 4단계 태스크**이므로,
  그 시점에 **데이터 설계부터** 진행한다.

### 가격 전용 화면 — 만들지 않는다

CLAUDE.md 원칙상 가격조정은 **전용 테이블 없이 `ACTION_ITEMS` 카드로만**
표현한다. 따라서 화면도 둘로 나눈다.

| 기능 | 화면 |
|---|---|
| 추천 승인 | `/actions` |
| 기준가·하한가 편집 | `/settings` 가격정책 탭 |

---

## 4. 화면별 주요 구성

> **4상태(LOADING / SUCCESS / EMPTY / ERROR)를 화면마다 정의한다.**
> 특히 **EMPTY가 핵심**이다 — 발표 시연에서 빈 화면이 나오면 안 되므로,
> 데이터 0건일 때의 안내 문구와 **다음 행동**을 반드시 적는다.

### 4-1. `/login`

- **목적**: 호스트 인증 후 JWT 발급
- **주요 API**: `POST /auth/login`
- **화면 요소**: 이메일 / 비밀번호 / 로그인 버튼 / 회원가입 링크

| 상태 | 표시 |
|---|---|
| LOADING | 버튼 스피너, 입력 비활성 |
| SUCCESS | `/dashboard`로 이동 |
| EMPTY | 해당 없음(입력 폼) |
| ERROR | 폼 하단 인라인 에러. 이메일/비밀번호 중 어느 쪽이 틀렸는지 구분하지 않음(계정 존재 여부 노출 방지) |

### 4-2. `/signup`

- **목적**: 신규 호스트 계정 생성
- **주요 API**: `POST /auth/signup`
- **화면 요소**: 이메일 / 비밀번호 / 비밀번호 확인 / 가입 버튼

| 상태 | 표시 |
|---|---|
| LOADING | 버튼 스피너 |
| SUCCESS | `/onboarding`으로 이동 |
| EMPTY | 해당 없음 |
| ERROR | 이메일 중복 등 필드별 인라인 에러 |

### 4-3. `/onboarding`

- **목적**: 첫 숙소와 채널을 등록해 나머지 화면이 동작할 최소 데이터를 만든다
- **주요 API**: `POST /properties`, `POST /properties/{id}/rooms`, `POST /rooms/{room_id}/beds`, `POST /properties/{id}/channels`
- **화면 요소**: 스텝 인디케이터(2단계) / 숙소 폼 / 조건부 객실·침대 폼 / iCal URL 입력 / "나중에 하기"

| 상태 | 표시 |
|---|---|
| LOADING | 스텝 전환 시 버튼 스피너 |
| SUCCESS | STEP 2 완료(또는 건너뛰기) 후 `/dashboard`로 이동 |
| EMPTY | 해당 없음(입력 전용 화면) |
| ERROR | `accommodation_type` 허용값 위반 등 필드 인라인 에러. iCal 등록 실패는 STEP 2에 머문 채 재시도 안내 |

### 4-4. `/dashboard` ⭐

- **목적**: 오늘 무엇을 해야 하는지를 전체 숙소 기준으로 한 화면에서 파악
- **주요 API**: `GET /properties` → 각 숙소 `GET /properties/{id}/dashboard/summary` **병렬 호출 후 합산**

**조회 방식** (api_contract v1.8 4.2절)
- 백엔드에 **교차 숙소 집계 엔드포인트를 만들지 않는다.**
- 프론트가 `GET /properties`로 목록을 받은 뒤 각 숙소의 summary를
  병렬 호출해 합산한다.
- **숙소 1개 호출이 실패해도 나머지는 정상 렌더링한다.**

**구성**

| 영역 | 내용 |
|---|---|
| 상단 | 합산 KPI (전체 숙소 합계) |
| 중단 | 숙소별 상태 카드 — 신호등 표시 |
| 하단 | 긴급 액션 상위 N건 프리뷰 + `전체 보기 →`(`/actions`로 이동) |

**신호등**: `ACTION_ITEMS.risk_level`(`RED_NOW` / `YELLOW_TODAY` /
`GREEN_AUTO`) 기준.
> **UI 문구는 "위험도"가 아니라 "우선순위"를 쓴다.**
> (CLAUDE.md: `ActionItems.risk_level`은 AI의 법적/안전 판단이 아니라
> 규칙기반 운영 우선순위다)

| 상태 | 표시 |
|---|---|
| LOADING | KPI·카드 영역 스켈레톤 |
| SUCCESS | 합산 KPI + 숙소별 카드 + 액션 프리뷰 |
| EMPTY | **숙소 0건** → "첫 숙소를 등록해 주세요" + `/onboarding` 이동 버튼<br>**액션 0건** → "지금 처리할 일이 없습니다" (빈 카드가 아니라 정상 상태임을 명시)<br>**`knowledge_chunks` 0건** → 지식베이스 등록 유도 배너 표시 |
| ERROR | 일부 숙소 호출 실패 시 **해당 카드에만** 오류 표시 + 재시도 버튼, 나머지는 정상 렌더링 |

### 4-5. `/calendar` + 예약 생성/상세 모달 ⭐

- **목적**: 기간별 예약 현황 확인과 예약 생성·수정
- **주요 API**: `GET /properties/{id}/reservations`, `GET /reservations/{id}`, `POST /reservations`, `PATCH /reservations/{id}/status`

**예약은 별도 라우트가 아니라 캘린더 내 모달로 처리한다.**

| 동작 | 결과 |
|---|---|
| 빈 칸 클릭 | 예약 **생성** 모달 |
| 예약 블록 클릭 | 예약 **상세** 모달 |

**모달 폼은 `bookable_unit_type`에 따라 분기한다**

| `bookable_unit_type` | 폼 |
|---|---|
| `PROPERTY` | `room_id`/`bed_id` 입력 **없음** |
| `ROOM` | `room_id` **필수** |
| `BED` | `room_id` + `bed_id` **필수** |

> `bookable_unit_type`은 `GET /properties` 응답에서 **미리 받아둔다**
> (숙소 상세 재호출 방지 — api_contract v1.8 2절).

**모달에 표시할 에러 4종**

| HTTP | code |
|---|---|
| 400 | `INVALID_UNIT_HIERARCHY` |
| 400 | `ROOM_ID_REQUIRED` |
| 400 | `BED_ID_REQUIRED` |
| 409 | `RESERVATION_OVERLAP` |

| 상태 | 표시 |
|---|---|
| LOADING | 캘린더 그리드 스켈레톤 / 모달 제출 시 버튼 스피너 |
| SUCCESS | 예약 블록 렌더링, `is_conflict=true`인 건은 충돌 강조 |
| EMPTY | "이 기간에 예약이 없습니다" + **"빈 날짜를 클릭해 예약을 추가하세요"** 안내. iCal 미연동 상태면 **"채널 연동하러 가기 →"**(`/settings` 채널연동 탭) 배너를 함께 표시 |
| ERROR | 목록 조회 실패는 그리드 자리에 재시도 버튼. 모달 에러는 위 4종을 폼 안에 인라인 표시(409는 충돌한 예약번호 함께) |

### 4-6. `/inquiries`

- **목적**: 게스트 문의에 대한 AI 초안을 검토·승인·발송
- **주요 API**: `GET /properties/{id}/inquiries`, `GET /inquiries/{id}`, `POST /inquiries/{id}/regenerate`, `POST /inquiry-approvals/{id}/approve`, `POST /inquiry-approvals/{id}/reject`
- **화면 요소**: 문의 목록 / 상세(분류 + 최신 응답) / 승인·거절 버튼 / 재생성 버튼(잔여 횟수 표시)

| 상태 | 표시 |
|---|---|
| LOADING | 목록 스켈레톤 / 재생성 중 응답 영역 스피너 |
| SUCCESS | 문의 + AI 초안 + 근거 표시 |
| EMPTY | "받은 문의가 없습니다" + 지식베이스가 비어 있으면 `/knowledge` 등록 유도 |
| ERROR | 재시도 상한 초과(429 `MAX_RETRY_EXCEEDED`) 시 재생성 버튼 비활성 + **호스트 수동 작성 모달**로 전환 |

### 4-7. `/actions`

- **목적**: 규칙기반 우선순위 큐를 처리하고 가격 추천을 승인
- **주요 API**: `GET /properties/{id}/action-items?status=OPEN`, `PATCH /action-items/{id}/resolve`, `GET /properties/{id}/price-recommendations`, `POST /properties/{id}/price-recommendations/apply`
- **화면 요소**: 우선순위별 그룹(🔴🟡🟢) / 처리 완료 버튼 / 가격 추천 섹션(일괄 선택 + 승인)

> 가격 추천 섹션은 **조정 추천과 방치 감지를 분리 표시**한다.
> `category='PRICE_NEGLECT'` 건은 `recommended_price`가 `null`이며
> apply 대상이 아니다(api_contract 13절).

| 상태 | 표시 |
|---|---|
| LOADING | 카드 리스트 스켈레톤 |
| SUCCESS | 우선순위별 카드 + 가격 추천 목록 |
| EMPTY | **"처리할 작업이 없습니다 — 모든 숙소가 정상 운영 중"** 완료 표시. 회색 빈 박스로 두지 않는다. **경고색 사용 금지** — 0건이 정상인 화면이다 |
| ERROR | apply 시 `400 BELOW_LOWER_BOUND`면 해당 건을 표시하고 `/settings` 가격정책 탭으로 이동 링크 제공 |

### 4-8. `/cleaning`

- **목적**: 청소 작업 상태 관리와 완료 사진 확인
- **주요 API**: `GET /properties/{id}/cleaning-tasks`, `PATCH /cleaning-tasks/{id}/status`, `POST /cleaning-tasks/{id}/photo`
- **화면 요소**: 상태별 목록(PENDING/ASSIGNED/IN_PROGRESS/COMPLETED/VERIFIED/ISSUE) / 사진 업로드 / 상태 전이 버튼

| 상태 | 표시 |
|---|---|
| LOADING | 목록 스켈레톤 |
| SUCCESS | 작업 카드 + `scheduled_at` 기준 정렬 |
| EMPTY | "예정된 청소가 없습니다" — 청소는 예약 확정 시 자동 생성되므로 **"예약이 없어서 비어 있다"는 맥락**을 함께 안내 |
| ERROR | 상태 전이 실패 시 토스트 + 원래 상태로 롤백 |

> `VERIFIED` 전이는 사진 0장이어도 가능하되 **"사진 없음" 경고를 표시**한다
> (api_contract 6절).

### 4-9. `/settlements`

- **목적**: 월별 정산 확인과 일괄 확정
- **주요 API**: `GET /properties/{id}/settlements`, `POST /properties/{id}/settlements/{month}/confirm`, `GET·PATCH /properties/{id}/financial-config`
- **화면 요소**: 월 선택 / 정산 목록 / 일괄확인 버튼 / 수수료 설정

| 상태 | 표시 |
|---|---|
| LOADING | 표 스켈레톤 |
| SUCCESS | 월별 정산 + `applied_commission_rate` 표시 |
| EMPTY | "정산할 예약이 없습니다" |
| ERROR | 확정 실패 시 토스트, 목록은 유지 |

> 금액이 추정치인지 확정인지 `financial_status`(ESTIMATED/CONFIRMED/
> MANUALLY_ADJUSTED)로 **반드시 구분 표시**한다.

### 4-10. `/compliance`

- **목적**: 인허가 서류 만료 관리
- **주요 API**: `GET /properties/{id}/checklist-items`, `PATCH /checklist-items/{id}`
- **화면 요소**: 만료 임박순 목록 / 완료·갱신 처리

| 상태 | 표시 |
|---|---|
| LOADING | 목록 스켈레톤 |
| SUCCESS | 만료 임박순 정렬 |
| EMPTY | **미정** — 아래 참고 |
| ERROR | 갱신 실패 시 토스트 |

> 화면에 **"참고용, 실제 인허가는 관할 지자체 확인 필요"** 문구를 유지한다
> (CLAUDE.md 원칙).

**EMPTY 상태: 미정 (2026-10-01~07 컴플라이언스 구현 시 확정)**

`CHECKLIST_ITEMS`의 생성 시점이 문서에 정의돼 있지 않아 빈 상태 설계를
확정할 수 없다(9/7 확인).

- `CHECKLIST_ITEMS.accommodation_type`이 `NOT NULL`로 존재하고, 명세서 8절이
  "이 항목이 파생된 템플릿 유형"이라고 설명하므로 **템플릿 파생 개념은
  존재한다**
- 그러나 그 파생이 **언제·무엇에 의해** 일어나는지(숙소 등록 시 자동 생성 /
  배치 / 호스트 수동 추가)는 어디에도 없다
- **생성 엔드포인트(POST)도 없다.** api_contract 10절에는 `GET`과 `PATCH`
  둘뿐이다

| 생성 방식 | EMPTY 설계 |
|---|---|
| 자동 생성 | 생성 실패·지연 안내 |
| 수동 생성 | `+ 항목 추가` CTA + 숙박업 유형별 필요 서류 안내 |

둘 중 어느 쪽인지는 **컴플라이언스 구현 시 API 설계와 함께 정한다.
UI가 먼저 정해질 사안이 아니다.**

### 4-11. `/knowledge` ⭐

- **목적**: 숙소별 하우스룰·FAQ를 등록해 AI 응대의 근거를 만든다
- **주요 API**: `GET·POST /properties/{id}/knowledge-chunks`, `DELETE /knowledge-chunks/{id}`
- **화면 요소**: 지식 목록 / 등록 폼 / 삭제

**입력 화면에 등록 기준 구분을 안내하는 요소가 필요하다** (CLAUDE.md 규칙 13)

| 구분 | 예시 |
|---|---|
| ✅ 등록한다 — 게스트 고지 사항 | 체크인·체크아웃 시각 / 추가요금 발생 가능성과 금액 / 사전협의 절차 / 와이파이·주차·시설 이용법 |
| ❌ 등록하지 않는다 — 호스트 내부 재량 | 예외 수용 여부 / 관행적 배려 범위 / 추가요금 실제 부과 여부 / 상황에 따라 달라지는 운영 판단 |

> 재량 사항이 RAG 검색 결과에 포함되면 **AI가 호스트를 대신해 약속하게
> 된다.** 등록 폼 옆에 이 기준을 상시 노출한다.

| 상태 | 표시 |
|---|---|
| LOADING | 목록 스켈레톤 / 등록 시 버튼 스피너(임베딩은 동기 생성이라 별도 폴링 없음) |
| SUCCESS | 등록 즉시 목록에 반영 |
| EMPTY | "등록된 지식이 없습니다. AI가 답변할 근거가 없으면 응대 품질이 떨어집니다" + **`+ 첫 항목 추가` CTA를 이 화면에 직접 배치한다.** 대시보드 배너에만 의존하지 않는다 — 배너를 닫은 뒤 재진입하는 경우를 대비 |
| ERROR | 등록 실패 시 입력값을 유지한 채 토스트 |

### 4-12. `/settings`

- **목적**: 숙소 정보·가격 정책·채널 연동을 한곳에서 관리
- **주요 API**: 위 **2-12** 표 참고
- **화면 요소**: 3탭 / 각 탭 폼 / 채널 동기화 상태·수동 동기화 버튼

| 상태 | 표시 |
|---|---|
| LOADING | 폼 스켈레톤 |
| SUCCESS | 저장 시 토스트 |
| EMPTY | 채널연동 탭에 연결된 채널 0건이면 "연동된 채널이 없습니다" + iCal URL 등록 유도 |
| ERROR | `sync_status=FAILED`인 채널은 `GET /channels/{id}/sync-errors`로 사유를 조회해 표시 |

---

## 5. 공통 컴포넌트 9개

| # | 컴포넌트 | 용도 / 사용처 |
|---|---|---|
| 1 | `Header` | 상단 고정. 로고, `PropertySwitcher`, 계정 메뉴 — 전 화면 |
| 2 | `Sidebar` | 좌측 네비게이션. 라우트 12개 이동 — 로그인·회원가입·온보딩 제외 전 화면 |
| 3 | `PropertySwitcher` | 숙소 컨텍스트 전환 (아래 상세) |
| 4 | `Card` | 지표·항목 묶음 표시 — 대시보드 숙소 카드, 액션 카드, 청소 작업 카드 |
| 5 | `Badge` | 상태·우선순위 표시 — 예약 상태 3종, 청소 상태 6종, 우선순위 3색, 숙소 유형 |
| 6 | `Modal` | 화면 전환 없이 입력·확인 — 예약 생성/상세, 문의 수동 작성, 삭제 확인 |
| 7 | `Toast` | 일시적 결과 알림 — 저장 성공, 상태 전이 실패, 승인 완료 |
| 8 | `Loading` | 조회 중 표시 — 스켈레톤(목록·표) / 스피너(버튼·부분 갱신) |
| 9 | `EmptyState` | 데이터 0건 안내 (아래 상세) |

### 5-3. `PropertySwitcher` (상세)

- **`Header`에 위치하는 전역 컴포넌트다.**
- **근거**: api_contract의 `property_id` 스코프 엔드포인트가 **13종**이라
  대부분의 조회가 숙소 지정을 전제로 한다(9/7 확인).
- **`GET /properties` 응답 4필드를 사용한다**

| 필드 | 용도 |
|---|---|
| `property_id` | 라우팅 키, 조회 대상 지정 |
| `name` | 드롭다운 표시 텍스트 |
| `accommodation_type` | 동명 숙소 구분 + 유형 뱃지 |
| `bookable_unit_type` | 예약 생성 모달의 폼 분기(재호출 방지) |

> **대시보드의 필터가 아니다.** 대시보드는 전체 숙소 통합 뷰이고,
> `PropertySwitcher`는 **개별 화면(캘린더/청소/정산 등)에 들어갈 때의
> 컨텍스트 전환 도구**다.

### 5-9. `EmptyState` (상세) — 4상태 정의와의 연결

4상태는 모든 조회 화면이 공통으로 가진다.

| 상태 | 정의 | 컴포넌트 |
|---|---|---|
| LOADING | 요청 진행 중 | `Loading` (스켈레톤 / 스피너) |
| SUCCESS | 데이터 1건 이상 | 화면별 본문 |
| EMPTY | 요청 성공 + 데이터 0건 | `EmptyState` |
| ERROR | 요청 실패 | `EmptyState`(전체 실패) 또는 `Toast`(부분 실패) |

**`EmptyState`는 반드시 세 가지를 담는다**

1. 왜 비어 있는지 (원인)
2. 지금 무엇을 하면 되는지 (다음 행동)
3. 그 행동으로 가는 버튼·링크

> **EMPTY와 ERROR를 시각적으로 구분한다.** "처리할 일이 없습니다"는
> 정상 상태이므로 경고색을 쓰지 않는다.

**화면별 EmptyState 연결**

| 화면 | 0건일 때 다음 행동 |
|---|---|
| `/dashboard` | 숙소 등록(`/onboarding`) / 지식베이스 등록 배너(`/knowledge`) |
| `/calendar` | 예약 추가(빈 칸 클릭) |
| `/inquiries` | 지식베이스 등록(`/knowledge`) |
| `/actions` | 없음 — 정상 상태 문구만 |
| `/cleaning` | 예약이 없어 청소가 생성되지 않았음을 안내 |
| `/settlements` | 없음 — 정산할 예약 없음 안내 |
| `/compliance` | 체크리스트 항목 등록 |
| `/knowledge` | 첫 지식 등록 |
| `/settings` | 채널 연동 등록 |

---

## 6. 화면 간 이동 경로

### 6-1. 이동 경로 원칙

1. **컨텍스트를 함께 전달한다.** 대시보드는 전체 통합이고 개별 화면은
   `property_id` 스코프다. 숙소를 지목한 지점에서 이동할 때 전환 없이
   보내면 사용자가 헤더에서 숙소를 **다시 골라야 한다** — 전체 통합
   대시보드를 만든 이유가 무너진다.
2. **빈 화면으로 진입시키지 않는다.** 숙소가 선택되지 않은 상태로
   `property_id` 스코프 화면에 들어오면, 조회 결과가 아니라 **숙소 선택을
   유도하는 화면을 먼저 보여준다.**

### 6-2. 이동 경로

| 출발 | 도착 | 조건/동작 |
|---|---|---|
| `/dashboard` 숙소별 신호등 카드 | 해당 개별 화면 | **`PropertySwitcher`가 그 숙소로 자동 전환된 상태로 열린다** |
| `/dashboard` 액션 프리뷰 `전체 보기 →` | `/actions` | — |
| `/actions` 청소 지연 카드 | `/cleaning` | 해당 작업에 **포커스** |
| `/actions` 서류 만료 카드 | `/compliance` | 해당 항목에 **포커스** |
| `/actions` 가격 추천 카드 | — | **카드 내에서 즉시 승인. 화면 이동 없음** |
| `/calendar` 예약 상세 모달 | `/cleaning` | 그 예약에 대응하는 청소 작업으로 이동 |
| `PropertySwitcher` 드롭다운 하단 | `/onboarding` | `+ 새 숙소 등록` |
| `property_id` 스코프 화면(`/calendar`·`/cleaning`·`/settlements` 등) | — | 숙소 미선택 상태로 진입 시 **숙소 선택 유도 화면을 먼저 표시**(빈 화면 금지) |

**근거**

- **숙소 자동 전환**: 위 6-1의 1번 원칙.
- **예약 → 청소**: 예약이 `CONFIRMED`되는 **즉시 `CLEANING_TASKS`가
  선제생성**되는 구조(CLAUDE.md 청소 생성 시점 원칙)이므로 **1:1 대응하는
  청소 건이 반드시 존재한다.** 목록에서 다시 찾게 하지 않는다.
- **`+ 새 숙소 등록`을 `PropertySwitcher`에 두는 이유**: 온보딩은 가입 직후
  1회 경로라, 이미 숙소가 있는 호스트가 **두 번째 숙소를 추가할 진입점이
  없다.** 숙소를 고르려고 연 드롭다운에 두는 것이 가장 자연스럽다.

> ※ **User Flow 다이어그램(화면 간 이동 구조 전체)은 9/9 별도 태스크다.**
> 이 절은 개별 이동 경로와 컨텍스트 전달 규칙만 다룬다.

---

## 7. 채택하지 않은 설계와 근거

| 검토한 안 | 결정 | 근거 |
|---|---|---|
| `/inquiries` 빈 상태에 **"샘플 문의 생성" 버튼** | **두지 않는다** | 실제 호스트가 쓰는 제품에 데모용 기능을 넣지 않는다. 시연 데이터는 **10/2 시드 스크립트**가 담당한다 |
| 수수료 설정(`financial-config`)을 `/settings`로 이동 | **`/settlements` 유지** | `FINANCIAL_CONFIGS`는 `PROPERTIES`와 **별도 테이블**이라 저장 경로가 다르고, `MONTHLY_SETTLEMENTS.applied_commission_rate` 스냅샷과 **현재 설정값을 같은 화면에서 대조**해야 한다 |
