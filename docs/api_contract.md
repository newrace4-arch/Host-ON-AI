# Host ON (AI) — API Contract v2.0 (9/7 action-items 응답 스펙 확정)

> `docs/3rd_host_ai_db_spec_v1.md`(**v1.3**) 16개 테이블을 기준으로 작성.
> **v1.9→v2.0 변경 (9/8 대시보드 구현 선행 작업)**:
> 1. **목록 응답 `meta` 규약 신설**(0절). `?page`/`size` 파라미터는 있었으나
>    응답에 총건수·페이지 정보를 담는 방법이 없었다. `GET /properties`는
>    구조적으로 페이지네이션 대상이 아니므로 예외로 명시.
> 2. `GET /properties/{property_id}/action-items` **응답 스펙 신규 확정**(9절).
>    9필드 전부 `ACTION_ITEMS` 실재 컬럼이며 파생 필드 없음. 정렬·쿼리
>    파라미터·`category` 값 현황·생성 경로도 함께 기록.
> 3. `PATCH /action-items/{id}/resolve` **요청·응답 스펙 확정**(9절).
>    `status`는 항상 `RESOLVED`로 전이하며, **가격 계열 액션에는 400으로
>    거부하는 서버 가드**를 둔다.
> 4. 가격 추천 카드 승인 시 호출 경로 명시(13절) — `resolve`가 아니라 `apply`.
> **v1.8→v1.9 변경 (9/7 크로스체크에서 발견)**:
> 1. `conflict_count`를 **키 고정·값 nullable** 계약으로 정정(4.1절).
>    v1.8은 "계산 실패 시 필드를 생략"이라고 적었으나 같은 절이 "응답
>    11필드"를 명시하고 있어 모순이었다.
> 2. `today_turnover_count` 집계 시 **`IS NOT DISTINCT FROM`** 사용을
>    명시(4.1절). PROPERTY 단위 예약은 `room_id`/`bed_id`가 NULL이라
>    일반 등호 비교로는 집계되지 않는다.
> **v1.7→v1.8 변경 (9/7 UI/UX 설계 중 확정)**:
> 1. `GET /properties/{property_id}/dashboard/summary` **응답 스펙 신규 확정**(4절).
>    9/7 확인 결과 이 엔드포인트는 표 한 행만 있고 응답 스펙이 문서 어디에도
>    없었다. 이 문서가 응답 스펙의 원본(SSOT)이 된다. 필드 11개 전부 기존
>    컬럼 집계이며 **DB 스키마 변경 없음**.
> 2. `GET /properties` **응답 스펙 신규 확정**(2절). 마찬가지로 응답 예시가
>    없던 엔드포인트다.
> 3. **통합 대시보드 조회 방식 명시**(4절) — 교차 숙소 집계 엔드포인트를
>    추가하지 않고 프론트가 N병렬 호출 후 합산한다.
> **v1.6→v1.7 변경 (9/5 예약 서비스 레이어 구현 중 확정)**:
> 1. 교차 판매단위 기간 충돌 에러를 `409 RESERVATION_OVERLAP`으로 명시(4절).
>    DB EXCLUDE가 같은 단위끼리만 막는다는 사실은 명세서에 있었으나,
>    그때 무엇을 반환할지가 API Contract에 없어 구현 시 새로 확정했다.
> **v1.5→v1.6 변경 (9/4 1단계 검증에서 발견된 불일치 정정)**:
> 1. `GET /reservations/{id}` 응답의 `net_payout` → **`net_amount`**로 정정.
>    (`net_payout`은 MONTHLY_SETTLEMENTS의 컬럼명이라 잘못 쓰인 것)
> 2. `POST /inquiries`의 `reservation_id` Optional 서술이 DB(NOT NULL)와
>    충돌했던 문제 해소 — DB 명세서 v1.3에서 실제로 nullable로 변경됨.
> 3. `GET /channels/{id}/sync-errors` 응답 스펙 명시(`last_error_message`
>    컬럼 v1.3 신규).
> 4. `POST /cleaning-tasks/{id}/photo`를 `photo_urls` 배열 **append**로 명시.
> 5. 동적 가격조정(명세서 6절) 대응 엔드포인트를 13절에 명시.
> 6. `POST /settlements/{month}/confirm` 정식 경로 확정.
>
> **v1.4→v1.5 변경**: 강사님 제안(Render 슬립방지) 검토 과정에서
> 발견된 `/health` 헬스체크 엔드포인트(11절) 신규 추가.
>
> 모든 목록/조회 API는 **Property 데이터 격리 원칙**에 따라 `property_id`
> 스코프가 강제된다(명세서 4절 -1번 참고). 인증은 JWT, 모든 요청은
> `Authorization: Bearer <token>` 헤더 필요(로그인/회원가입 제외).
> Property 소유권 검증(IDOR 방지)은 FastAPI `Depends()` 기반 재사용
> 가능한 의존성으로 구현한다(전역 미들웨어보다 경로파라미터 처리에
> 유연함).
>
> DB 구조 변경 시 이 문서도 함께 갱신할 것
> (명세서 → ERD → **API Contract** → 체크리스트 순서, CLAUDE.md 원칙).

---

## 0. 공통 규칙

- 응답 포맷: `{ "data": ..., "error": null }` 또는 실패시 `{ "data": null, "error": { "code": "...", "message": "..." } }`
- 페이지네이션: `?page=1&size=20` (목록 API 공통)
- **목록 응답 메타 규약 (v2.0 신설)**: **페이지네이션 파라미터(`page`,
  `size`)를 지원하는 컬렉션 엔드포인트**는 `meta` 객체를 포함한다.
  ```json
  { "data": [ ... ],
    "meta": { "total": 47, "page": 1, "size": 20 },
    "error": null }
  ```
  근거: 부분만 받아온 응답에서 `data` 길이로는 전체 건수를 알 수 없다.

  > **예외**: 목록이 아니라 **전체 컬렉션을 반환하는 것이 API의 목적**인
  > 엔드포인트는 `meta`를 생략하고 기존 형식을 유지한다.
  >
  > 해당 예 — **`GET /properties`**: `PropertySwitcher` 드롭다운과 대시보드
  > 병렬 호출의 **입력**으로서 항상 전체를 반환해야 하므로 페이지네이션이
  > 구조적으로 적용될 수 없다. 일부만 받으면 전환 목록에 숙소가 누락되고
  > 대시보드 합산에서도 빠진다.
  >
  > 이 예외는 **건수가 적어서가 아니라 용도 때문**이다. 향후 숙소 수가 크게
  > 늘어 목록 자체를 페이지네이션해야 할 상황이 오면 이 문장을 근거로
  > 재검토한다.
- 날짜: `YYYY-MM-DD`, 일시: ISO8601(`YYYY-MM-DDTHH:mm:ssZ`)
- 소유권 검증: 모든 `property_id` 경로/쿼리는 **요청자(JWT)의 host_id가 해당 Property를 실제 소유하는지** 서비스 레이어에서 검증(IDOR 방지, 명세서 확정 원칙)
- **`property_id`가 URL에 없는 하위 리소스 엔드포인트**(`GET /reservations/{id}`,
  `GET /inquiries/{id}` 등)는 **조회 쿼리 자체에 소유권 조건을 묶어서**
  처리한다(파이썬 if문으로 나중에 검사하지 않음):
  ```sql
  SELECT r.* FROM reservations r
  JOIN properties p ON r.property_id = p.property_id
  WHERE r.reservation_id = :id AND p.host_id = :current_host_id
  ```
  결과가 없으면(존재하지 않는 id든, 타인 소유 id든 구분하지 않고)
  **항상 동일하게 `404 Not Found`, `code: "RESOURCE_NOT_FOUND"`**를
  반환한다. **403을 쓰지 않는 이유**: id를 1씩 증가시키며 403/404를
  구분해서 반환하면 "어떤 id가 실제 존재하는지"를 외부에서 추론할 수
  있는 정보노출 취약점이 되기 때문(4차 크로스체크로 발견, 보안표준
  일치 확인).

---

## 1. 인증 (HOSTS)

| Method | Endpoint | 설명 |
|---|---|---|
| POST | `/auth/signup` | 회원가입 |
| POST | `/auth/login` | 로그인, JWT 발급 |
| GET | `/auth/me` | 현재 로그인한 호스트 정보 |

**POST /auth/login 요청/응답 예시**
```json
// Request
{ "email": "host@example.com", "password": "..." }
// Response
{ "data": { "access_token": "eyJ...", "host_id": 1, "name": "신경주" }, "error": null }
```

---

## 2. 숙소 관리 (PROPERTIES / ROOMS / BEDS)

| Method | Endpoint | 설명 |
|---|---|---|
| GET | `/properties` | 내 숙소 목록 |
| POST | `/properties` | 숙소 등록 (accommodation_type, bookable_unit_type 포함) |
| GET | `/properties/{property_id}` | 숙소 상세 |
| PATCH | `/properties/{property_id}` | 숙소 정보 수정(checkin_time, weekday_adjustment_enabled 등) |
| GET | `/properties/{property_id}/rooms` | 객실 목록 |
| POST | `/properties/{property_id}/rooms` | 객실 등록 |
| GET | `/rooms/{room_id}/beds` | 침대 목록 |
| POST | `/rooms/{room_id}/beds` | 침대 등록 |

**POST /properties 요청 예시**

> `accommodation_type` 허용값 6개(관광진흥법 시행령 제2조 제1항 제3호
> 바목 기준): `URBAN_HOMESTAY`, `RURAL_HOMESTAY`, `HANOK`, `HOSTEL`,
> `LODGING_FACILITY`, `GENERAL_LODGING` — 이 외 값은 400 에러.

```json
{
  "name": "강남 3룸 독채",
  "accommodation_type": "URBAN_HOMESTAY",
  "bookable_unit_type": "PROPERTY",
  "address": "서울시 강남구...",
  "base_price": 150000,
  "checkin_time": "15:00",
  "checkout_time": "11:00",
  "weekday_adjustment_enabled": true,
  "holiday_adjustment_enabled": true
}
```
> GET/PATCH 응답에도 위 두 필드(공백일 자동조정 on/off) 반드시 포함할 것
> (2차 크로스체크로 발견된 누락, DB v1.2 필드와 정확히 일치시켜야 함).

**GET /properties 응답 예시 (v1.8 신규 확정)**

```json
{
  "data": [
    { "property_id": 1, "name": "강남 3룸 독채",
      "accommodation_type": "URBAN_HOMESTAY", "bookable_unit_type": "PROPERTY" },
    { "property_id": 2, "name": "홍대 호스텔",
      "accommodation_type": "HOSTEL", "bookable_unit_type": "BED" }
  ],
  "error": null
}
```

| 필드 | 출처 | 용도 |
|---|---|---|
| `property_id` | `PROPERTIES.property_id` | 라우팅 키, 대시보드 병렬 호출 대상 식별 |
| `name` | `PROPERTIES.name` | PropertySwitcher 드롭다운 표시 텍스트 |
| `accommodation_type` | `PROPERTIES.accommodation_type` | 동명 숙소 구분 + 유형 뱃지 표시 |
| `bookable_unit_type` | `PROPERTIES.bookable_unit_type` | **예약 생성 모달이 room_id/bed_id 필수 여부를 이 값으로 분기**한다 |

> `bookable_unit_type`을 목록에 포함하는 이유: 4절의 400 에러 3종
> (`INVALID_UNIT_HIERARCHY`/`ROOM_ID_REQUIRED`/`BED_ID_REQUIRED`)이 전부 이 값을
> 기준으로 판정되므로, 목록에 없으면 예약 모달을 열 때마다 숙소 상세를
> 재호출해야 한다.
>
> `address`·`base_price`·`lower_bound_price`·`checkin_time`·`checkout_time`·
> `*_adjustment_enabled`는 **포함하지 않는다** — `/settings` 화면 소관이며,
> 드롭다운에는 쓰이지 않는다.
>
> **요약 지표(오픈 액션 수·오늘 체크인 건수 등)를 이 응답에 넣지 않는다.**
> 4절 `dashboard/summary`가 "캐싱 없이 매요청 실시간 집계 — 개별 API와 항상
> 일치 보장"을 명시하고 있어, 같은 지표를 목록 API에도 두면 두 API가 서로
> 다른 시점의 값을 반환해 그 보장이 깨진다.

---

## 3. 채널 연동 (CHANNEL_CONNECTIONS)

| Method | Endpoint | 설명 |
|---|---|---|
| GET | `/properties/{property_id}/channels` | 연동 채널 목록(동기화 상태 포함) |
| POST | `/properties/{property_id}/channels` | iCal URL 등록(Airbnb/Booking.com/네이버) |
| DELETE | `/channels/{connection_id}` | 채널 연동 해제 |
| POST | `/channels/{connection_id}/sync` | 수동 동기화 트리거 |
| GET | `/channels/{connection_id}/sync-errors` | 동기화 실패 사유 조회 (sync_status=FAILED일 때) |

> **중복 등록 시**: 이미 연동된 채널(동일 property_id+channel)로 다시 등록
> 시도하면 `409 Conflict`, `code: "CHANNEL_ALREADY_CONNECTED"` 반환
> (DB의 `UNIQUE(property_id, channel)` 제약과 일치).

> **[v1.6] `GET /channels/{connection_id}/sync-errors` 응답 스펙**:
> `CHANNEL_CONNECTIONS.last_error_message`(v1.3 신규 컬럼) 1건만 반환한다.
> 실패 이력을 누적하는 별도 테이블은 만들지 않는다(범위확장 방지).
> ```json
> { "data": { "connection_id": 7, "sync_status": "FAILED",
>             "last_synced_at": "2026-09-04T03:00:00Z",
>             "last_error_message": "iCal URL 응답 없음(timeout 5s)" },
>   "error": null }
> ```
> `sync_status`가 `FAILED`가 아니면 `last_error_message`는 항상 `null`이다
> (동기화 성공 시 서버가 NULL로 초기화 — 지난 에러가 화면에 남지 않게).
> 스택트레이스나 내부 URL은 이 필드에 넣지 않는다(정보노출 방지).

---

## 4. 예약 (RESERVATIONS) ⭐ 핵심

| Method | Endpoint | 설명 |
|---|---|---|
| GET | `/properties/{property_id}/reservations` | 예약 목록(캘린더용, 기간 필터, `is_conflict` 플래그 포함) |
| GET | `/reservations/{reservation_id}` | 예약 상세 |
| POST | `/reservations` | 예약 생성(iCal 동기화 또는 수동, bookable_unit_type 검증 포함) |
| PATCH | `/reservations/{reservation_id}/status` | 예약상태/환불상태/정산상태 개별 수정 |
| GET | `/properties/{property_id}/dashboard/summary` | 대시보드 통합 요약(캘린더요약+오픈액션수+오늘turnover건수, **캐싱 없이 매요청 실시간 집계** — 개별 API와 항상 일치 보장) |

### 4.1 GET /properties/{property_id}/dashboard/summary 응답 스펙 (v1.8 신규 확정)

> 9/7 확인 결과 이 엔드포인트는 위 표 한 행만 있고 응답 스펙이 문서 어디에도
> 없었다. **이 절이 응답 스펙의 원본(SSOT)이다.** 아래 11개 필드는 전부 기존
> 16개 테이블의 실재 컬럼에서 집계하며 **DB 스키마 변경을 요구하지 않는다.**

```json
{
  "data": {
    "property_id": 1,
    "property_name": "강남 3룸 독채",

    "today_checkin_count": 2,
    "today_checkout_count": 1,
    "today_turnover_count": 1,

    "open_action_count": 5,
    "red_now_count": 1,
    "yellow_today_count": 2,
    "green_auto_count": 2,

    "cleaning_pending_count": 2,
    "cleaning_issue_count": 0,

    "conflict_count": 1        // 계산 실패 시 null
  },
  "error": null
}
```

| 필드 | 집계 근거 |
|---|---|
| `property_id` / `property_name` | `PROPERTIES.property_id` / `PROPERTIES.name`. 프론트가 3~5개 숙소분을 병렬 호출해 합산하므로 **어느 숙소의 응답인지 식별이 필요**하다 |
| `today_checkin_count` | `RESERVATIONS` `WHERE check_in = CURRENT_DATE AND reservation_status IN ('CONFIRMED','MODIFIED')`. 인덱스 `idx_reservations_dates(property_id, check_in, check_out)` |
| `today_checkout_count` | `RESERVATIONS` `WHERE check_out = CURRENT_DATE` (같은 인덱스) |
| `today_turnover_count` | **같은 `(property_id, room_id, bed_id)` 조합**에서 당일 체크아웃 예약과 당일 체크인 예약이 **둘 다 존재하는 단위의 수**. 아래 정의 참고 |
| `open_action_count` | `ACTION_ITEMS` `WHERE status = 'OPEN'` (`action_status_enum`, 명세서 2.15절) |
| `red_now_count` / `yellow_today_count` / `green_auto_count` | `ACTION_ITEMS` `WHERE status='OPEN' GROUP BY risk_level` (`action_risk_level_enum`: `RED_NOW`/`YELLOW_TODAY`/`GREEN_AUTO`, 명세서 111행). 인덱스 `idx_action_items_property_status(property_id, status, risk_level)`가 **정확히 이 쿼리 형태와 일치** |
| `cleaning_pending_count` | `CLEANING_TASKS` `WHERE task_status IN ('PENDING','ASSIGNED','IN_PROGRESS')`. 인덱스 `idx_cleaning_tasks_property_status` |
| `cleaning_issue_count` | `CLEANING_TASKS` `WHERE task_status = 'ISSUE'` |
| `conflict_count` | `is_conflict = true`인 예약 수. `is_conflict`는 **DB 컬럼이 아니라 서버가 매 조회 시 계산하는 파생 필드**다(본 절 `GET /reservations/{id}` 주석 참고) |

**`today_turnover_count` 정의 (실제 운영 규칙 기반)**

체크아웃 **11:00** / 체크인 **16:00** 운영이므로, 같은 판매단위에서 당일
퇴실과 당일 입실이 겹치면 **청소 가용 시간이 5시간뿐**이고 당일 청소 완료가
필수가 된다. 그래서 이 건수는 단순 `today_checkout_count`와 **다른 개념**이며,
호스트가 오늘 반드시 처리해야 할 작업량을 나타낸다.

> **15:00 비밀번호 안내 메시지는 이 집계와 무관하다.** 그것은 turnover 여부와
> 관계없이 도는 별도 알림 스케줄이므로 `today_turnover_count`에 포함하지 않는다.

> ※ **PROPERTY 단위 판매 예약은 `room_id`·`bed_id`가 NULL이다.** SQL에서
> `NULL = NULL`은 참이 아니므로 일반 등호 비교로는 PROPERTY 단위 숙소의
> turnover가 집계되지 않는다. 조합 비교에는 **`IS NOT DISTINCT FROM`**을
> 사용한다. `COALESCE(room_id, 0)` 같은 트릭은 사용하지 않는다(CLAUDE.md
> 핵심 데이터 모델 원칙에서 이미 폐기 결정됨).

**`conflict_count` 포함 이유와 실패 처리**

iCal을 여러 OTA에서 받는 구조상 더블부킹이 실제로 발생 가능하며, 호스트가
대시보드에서 **가장 먼저 알아야 할 정보**다(숙소별 캘린더를 일일이 열어보게
해서는 안 된다). 다만 파생 필드이므로 계산에 실패할 수 있다.

**키는 항상 포함한다. 계산 실패 시 값을 `null`로 반환한다.** 나머지 10개
필드는 정상 값으로 반환한다(Graceful Degradation) — CLAUDE.md의 iCal
외부연동 방어 원칙과 같은 계열로, 일부 실패가 화면 전체를 못 쓰게 만들지
않는다.

> **필드를 생략하지 않는 이유**: 프론트에서 키가 없으면 `undefined`가 되어
> 조건부 렌더링 방어 코드가 늘어난다. `null`이면 **"계산 못 함"과 "0건"이
> 구분**되고, 위에 명시한 **11필드 고정 계약도 유지**된다.
> (v1.8은 "이 필드만 생략"이라고 적어 11필드 고정과 모순이었다 — v1.9 정정)

**포함하지 않는 필드**

`staying_count`(현재 투숙 중)는 넣지 않는다. 나머지 지표가 전부 "오늘 무엇을
해야 하는가"인 반면 투숙 중 인원은 호스트의 행동을 유발하지 않으며, 3~5개
숙소분을 합산해 표시하는 화면에서 필드 수를 늘리면 KPI 영역이 과밀해진다.

**UI 표기 규칙**

`risk_level`을 화면에 표시할 때 문구는 **"위험도"가 아니라 "우선순위"**를 쓴다
(CLAUDE.md: "ActionItems.risk_level은 AI의 법적/안전 판단이 아니라 규칙기반 운영
우선순위다").

> `RED_NOW` 판정의 "체크인 임박" 기준 시각은 **`PROPERTIES.checkin_time`에서
> 읽는다**. 숙소마다 체크인 시각이 다를 수 있으므로 하드코딩하지 않는다.
> (실제 판정 로직 구현은 10/6 액션센터 태스크 소관이며, 여기서는 원칙만 남긴다)

**체크인/체크아웃 시각과 turnover의 관계**

`PROPERTIES.checkin_time` / `checkout_time`은 숙소별 설정값이며, 스키마
기본값(`'15:00'`)과 실제 운영값은 다를 수 있다. 아래는 개발자가 실제 운영
중인 숙소(마포, PROPERTY 단위 판매)의 규칙으로, turnover 지표가 필요한
배경이다.

> ⚠️ **아래 규칙은 두 층으로 나뉜다. 이 구분을 반드시 지킬 것.**

**(1) 게스트 고지 사항 — 공식 규정**

- 체크아웃 11:00
- 체크인 16:00
- 비밀번호 안내 발송 15:00
- 조기 체크인 / 연장 체크아웃을 원하는 경우 **2일 전 사전협의 필수**
- **연장·조기 이용 시 1시간당 2만원의 추가요금이 발생할 수 있음**
  (숙소 안내·예약 확인 메시지에 비고로 항상 표시한다)

**(2) 호스트 내부 재량 — 게스트에게 고지하지 않음**

아래는 호스트가 그날 상황을 보고 개별 판단하는 사항이며, 사전에 안내하거나
시스템이 자동으로 노출하지 않는다.

- 12:00까지의 체크아웃 연장 가능 여부
  (청소 직원 일정이 사전 배치되어 12:00이 실질 한계. 게스트가 먼저
  문의하지 않으면 안내하지 않는다)
- 15:00 조기 체크인 수용 여부
- 당일 체크아웃이 없는 단위의 12:00 이후 체크인 수용 여부
- 실무상 1~2시간 정도 배려하는 관행
- 추가요금의 실제 부과 여부

**🔴 AI 게스트 응대에서의 취급**

**(2)의 내용은 `KNOWLEDGE_CHUNKS`에 등록하지 않는다.** RAG 검색 결과에
포함되면 AI가 호스트를 대신해 재량 사항을 약속하게 되며, 이는 호스트가 그날
상황(청소 일정, 다음 예약)을 보고 판단해야 할 문제다. 지식베이스에는 (1)의
공식 규정만 등록한다.

조기 체크인·연장 체크아웃 문의가 들어오면 AI는 "2일 전 사전협의가 필요하며
추가요금이 발생할 수 있다"는 공식 안내까지만 하고, 수용 여부는 호스트 승인
대기로 넘긴다.

**turnover가 제약하는 것**

청소 일정이 사전 배치되므로 체크아웃 측 한계(12:00)는 turnover 유무와
무관하게 동일하다. turnover가 실제로 제약하는 것은 **체크인 측**이다.
turnover가 없는 단위는 12:00부터 체크인을 받을 수 있으나, turnover가 발생한
단위는 청소가 끝나야 하므로 16:00을 지켜야 한다.

즉 `today_turnover_count`는 단순 집계가 아니라, **호스트가 그날 해당 단위의
체크인 시각을 앞당길 수 있는지를 판정하는 내부 지표**다. 게스트에게 노출되는
값이 아니다.

**구현 시 주의**

- 시각을 하드코딩하지 않는다. `PROPERTIES.checkin_time` / `checkout_time`에서
  읽는다.
- 추가요금(1시간당 2만원)은 호스트 재량이므로 **자동 부과·자동 계산 로직을
  만들지 않는다.** 현재 스키마에 저장할 컬럼이 없으며 이번 범위에서 추가하지
  않는다.
- 2일 전 사전협의 요청은 현재 시스템이 관리하지 않는다. 호스트가 채널
  메시지로 직접 처리하는 운영 업무다.
- 15:00 비밀번호 발송은 turnover 집계에 포함하지 않는다. 다만 체크인 1시간
  전이므로 향후 액션센터 `RED_NOW` 판정(체크인 임박 + 청소 미완료)의 기준점
  후보다. 실제 판정은 10/6 액션센터 태스크 소관이며 여기서는 배경으로만
  기록한다.

### 4.2 통합 대시보드 조회 방식 (v1.8 신규 명시)

대시보드는 **전체 숙소 통합 뷰**다. 백엔드에 교차 숙소 집계 엔드포인트를
**새로 만들지 않는다.** 프론트가 `GET /properties`로 목록을 받은 뒤 각 숙소의
`dashboard/summary`를 **병렬 호출해 합산**한다. 숙소 하나의 호출이 실패해도
나머지는 정상 렌더링한다.

근거:
1. 기검증된 백엔드(16테이블, `reservation_service.py`, 회귀테스트 20개 통과)를
   전혀 건드리지 않는다 — 안정성 우선.
2. 각 호출이 단일 숙소 쿼리이므로 **명세서 611행의 성능 보증 범위 안**에 있다
   ("조인 1회로 충분하며, 위 인덱스로 성능 문제 없이 동작합니다").
3. P1에서 숙소 수가 크게 늘면 통합 엔드포인트를 추가할 수 있고, 그때 필요한
   인덱스는 **이미 전부 존재한다**(`idx_properties_host`,
   `idx_reservations_property`, `idx_reservations_dates`,
   `idx_cleaning_tasks_property_status`, `idx_action_items_property_status`).
   즉 지금 결정이 나중을 막지 않는다.

> **PropertySwitcher는 대시보드의 필터가 아니다.** 개별 화면(캘린더/청소/정산
> 등)에 들어갈 때의 **컨텍스트 전환 도구**다.

---

**GET /reservations/{id} 응답 예시**
```json
{
  "data": {
    "reservation_id": 501,
    "property_id": 1,
    "room_id": null,
    "bed_id": null,
    "channel_connection_id": 7,
    "guest_name": "Reserved",
    "check_in": "2026-09-10",
    "check_out": "2026-09-12",
    "reservation_status": "CONFIRMED",
    "refund_status": "NONE",
    "financial_status": "ESTIMATED",
    "gross_amount": 300000,
    "fee_amount": 46500,
    "net_amount": 253500,
    "is_conflict": false
  },
  "error": null
}
```
> **필드명 주의(v1.6 정정)**: 예약의 정산 후 실수령액은 `net_amount`다.
> `net_payout`은 `MONTHLY_SETTLEMENTS`(월 단위 집계)의 컬럼명이므로
> 예약 응답에 쓰지 않는다. `is_conflict`는 DB 컬럼이 아니라 **서버가
> 매 조회 시 계산해 내려주는 파생 필드**(같은 property 내 다른 판매단위와
> 기간이 겹치는지 여부)이므로 스키마에 없는 것이 정상이다.
> ⚠️ 이 API는 `bookable_unit_type=PROPERTY`인데 `room_id`가 채워진 요청이
> 들어오면 400 에러로 거부해야 함(명세서 4절 0번 — DB CHECK가 못 잡는
> 부분을 여기서 애플리케이션이 검증). 구체적 에러 스펙:
>
> | bookable_unit_type | 위반 조건 | HTTP | code |
> |---|---|---|---|
> | PROPERTY | room_id 또는 bed_id가 NOT NULL | 400 | `INVALID_UNIT_HIERARCHY` |
> | ROOM | room_id가 NULL 이거나 bed_id가 NOT NULL | 400 | `ROOM_ID_REQUIRED` |
> | BED | room_id 또는 bed_id가 NULL | 400 | `BED_ID_REQUIRED` |

> **[v1.7 추가] 교차 판매단위 기간 충돌은 `409 Conflict`, code
> `RESERVATION_OVERLAP`**. DB의 EXCLUDE 제약 3종은 **같은 판매단위끼리만**
> 겹침을 막으므로(PROPERTY↔PROPERTY, ROOM↔ROOM, BED↔BED), 독채 예약과 그
> 하위 객실/침대 예약 사이의 충돌은 `POST /reservations` 서비스 레이어가
> 직접 조회해 차단한다(명세서 2.6.1절 경고, troubleshooting.md 1번).
> 응답 message에는 충돌한 예약번호를 함께 담는다.
>
> | 상황 | HTTP | code |
> |---|---|---|
> | 같은 숙소에서 기간이 겹치는 다른 단위 예약 존재 | 409 | `RESERVATION_OVERLAP` |
> | 동시성으로 DB EXCLUDE에 걸린 경우(마지막 방어선) | 409 | `RESERVATION_OVERLAP` |
>
> 겹침 판정은 반개구간이다 — **체크아웃일과 다음 예약의 체크인일이 같은 날인
> 연박 이어짐은 충돌이 아니다**(EXCLUDE의 `tsrange` 판정과 동일).

> `PATCH /reservations/{id}/status`는 3개 필드(reservation_status/
> refund_status/financial_status) 전부 Optional로 받는 단일 엔드포인트로
> 유지한다(엔드포인트 3개로 쪼개면 환불+취소 동시처리 시 트랜잭션이
> 2번 발생해 오히려 비효율). 단, 서비스 레이어에서 무의미한 조합(예:
> `reservation_status=CANCELLED`인데 `refund_status=NONE`인 경우)은
> validator로 차단한다.

---

## 5. 정산 (FINANCIAL_CONFIGS / MONTHLY_SETTLEMENTS)

| Method | Endpoint | 설명 |
|---|---|---|
| GET | `/properties/{property_id}/financial-config` | 수수료 설정 조회 |
| PATCH | `/properties/{property_id}/financial-config` | 수수료율 등 설정 변경(과거 정산에 영향 없음) |
| GET | `/properties/{property_id}/settlements` | 월별 정산 목록 |
| POST | `/properties/{property_id}/settlements/{month}/confirm` | 일괄확인(자동추정→확정) |

> **[v1.6] 정식 경로 확정**: 정산 확정 엔드포인트의 정식 경로는 위의
> `/properties/{property_id}/settlements/{month}/confirm`이다. CLAUDE.md
> 코딩규칙 3번에 축약형(`POST /settlements/{month}/confirm`)으로 적혀
> 있으나 그것은 서술 편의상의 축약이며, 실제 라우터는 property 스코프를
> 경로에 포함한다(데이터 격리 원칙상 property_id가 URL에 있어야 함).

> **정산 확정시 트랜잭션 범위**: `{month}`에 속하는 예약은
> **`check_out`(체크아웃일) 기준**으로 판별한다(예: 8/28 체크인~9/2
> 체크아웃 예약은 9월 정산에 포함 — 정산은 실제 퇴실 완료 시점 기준이
> 실무상 자연스러움). `MONTHLY_SETTLEMENTS.target_month` 갱신과, 해당
> 예약들의 `RESERVATIONS.financial_status`를 `ESTIMATED`→`CONFIRMED`로
> 일괄 변경하는 작업을 **하나의 DB 트랜잭션**으로 묶어 처리한다(둘 중
> 하나만 반영되는 부분실패 방지).

---

## 6. 청소 (CLEANING_TASKS)

| Method | Endpoint | 설명 |
|---|---|---|
| GET | `/properties/{property_id}/cleaning-tasks` | 청소작업 목록 |
| PATCH | `/cleaning-tasks/{task_id}/status` | 상태 전이(PENDING→...→VERIFIED) |
| POST | `/cleaning-tasks/{task_id}/photo` | 완료사진 업로드 |

> 청소작업은 `reservation_id`당 자동 1건 생성(예약이 CONFIRMED로
> 전이되는 즉시 서버가 자동 트리거, `scheduled_at`=해당 예약의
> `check_out`과 숙소 `checkout_time`을 결합한 실제 체크아웃 시각으로 미리
> 세팅, 별도 생성 API 없음 — UNIQUE 제약과 일치, 9/3 정정).
> ※ 이 컬럼은 v1.3에서 `scheduled_date` → `scheduled_at`으로 개명됐다
> (타입은 `TIMESTAMPTZ` 그대로). 응답 JSON 키도 `scheduled_at`을 쓴다.

> **[v1.6] `POST /cleaning-tasks/{task_id}/photo` 동작 규칙**: 업로드된
> 사진 URL을 `CLEANING_TASKS.photo_urls`(JSONB 배열, v1.3 신규) **끝에
> append**한다. 기존 배열을 교체하지 않는다 — 청소 구역을 나눠 여러 장
> 올리는 실제 운영 패턴을 지원하기 위함. 응답은 갱신된 전체 배열을
> 돌려준다.
> ```json
> { "data": { "task_id": 88,
>             "photo_urls": ["https://.../living.jpg", "https://.../bath.jpg"] },
>   "error": null }
> ```
> 사진 삭제가 필요하면 `PATCH /cleaning-tasks/{id}`로 배열 전체를
> 덮어쓰는 방식으로 처리한다(개별 삭제 엔드포인트는 만들지 않음).
> `VERIFIED` 전이는 호스트의 확인 행위로 결정되며 사진 0장이어도 가능하되,
> UI에서 "사진 없음" 경고를 표시한다.

---

## 7. AI 문의응대 (INQUIRIES 계열) ⭐ 핵심

| Method | Endpoint | 설명 |
|---|---|---|
| GET | `/properties/{property_id}/inquiries` | 문의 목록 |
| POST | `/inquiries` | 게스트 문의 접수(웹훅/폼) → RAG+Claude 1회 호출 트리거 |
| GET | `/inquiries/{inquiry_id}` | 문의 상세(분류+최신응답 포함) |
| POST | `/inquiries/{inquiry_id}/regenerate` | 재생성 요청(재시도 최대2회 제한 적용) |
| POST | `/inquiry-approvals/{approval_id}/approve` | 승인 후 발송 |
| POST | `/inquiry-approvals/{approval_id}/reject` | 거절(재생성으로 연결) |

> **POST /inquiries 요청 필드 nullable 규칙**: `property_id`는 **항상 필수**
> (Property 데이터격리 원칙 — 어느 숙소 RAG를 검색할지 결정하는 값이라
> 절대 생략 불가). `reservation_id`는 **Optional**(예약 전 문의, 예:
> "반려동물 동반 가능한가요?" 같은 사전 문의를 지원하기 위함).
>
> **[v1.6 정정 이력]** v1.5까지 이 문단은 "DB도 nullable로 설계되어 있음"
> 이라고 적혀 있었으나, 실제 명세서 2.10절은 `NOT NULL`이었다(9/4 1단계
> 검증에서 발견된 문서 간 정면 충돌). 개발자 결정에 따라 **DB 쪽을
> nullable로 변경**해 사전문의 기능을 유지하기로 했고, 명세서 v1.3에
> 반영 완료. 이때 `reservation_id`가 NULL이면 복합FK 검사가 통째로
> 스킵되므로(`MATCH SIMPLE`), `property_id`에 **단독 FK가 함께 추가**된
> 점을 구현 시 반드시 확인할 것(명세서 2.10절 참고).

> **is_latest 갱신 순서(반드시 이 순서로 구현)**:
> ```
> ① UPDATE inquiry_responses SET is_latest=false
>    WHERE inquiry_id=:id AND is_latest=true
> ② INSERT INTO inquiry_responses (..., is_latest=true)
> ```
> 순서를 반대로 하면(INSERT 먼저) 그 순간 is_latest=true인 행이 2개가
> 되어 부분 UNIQUE 인덱스(`uniq_inquiry_latest_response`) 위반으로 즉시
> 에러가 난다. ①②를 반드시 하나의 트랜잭션으로 묶을 것.

**POST /inquiries 응답 예시 (AI 처리 완료 후)**
```json
{
  "data": {
    "inquiry_id": 3001,
    "classification": { "category": "wifi", "risk_level": "LOW", "auto_respondable": true },
    "response": {
      "response_text": "The Wi-Fi password is...",
      "detected_language": "en",
      "is_latest": true,
      "sources": ["chunk_17"]
    },
    "auto_sent": true
  },
  "error": null
}
```
> `response_text`는 이미 게스트 언어(`detected_language`)로 번역된
> 최종 답변이다(Claude 1회 호출에서 다국어 응답까지 동시 생성하므로
> 별도 번역 API 불필요, DB명세서 AI아키텍처 원칙과 일치).

> **재시도 횟수 검증(정확한 계산식)**: `regenerate` 호출 시, 새 레코드를
> 만들기 **전에** 해당 `inquiry_id`의 기존 `INQUIRY_RESPONSES` 레코드
> 개수(`current_count`)를 먼저 조회한다. `current_count - 1 >= 2`이면
> (즉 이미 2회 재시도를 다 쓴 상태) 새 레코드를 만들지 않고 즉시
> `429 Too Many Requests`, `code: "MAX_RETRY_EXCEEDED"`,
> `message: "최대 재시도 횟수(2회)를 초과했습니다. 호스트 직접 작성
> 모달을 이용해주세요."`를 반환한다.
> (예: 최초생성 1건 후 재시도 2번 성공하면 총 3건 → 다음 시도에서
> `3-1=2`가 상한과 같으므로 차단)
>
> **동시요청 방어(중요)**: 같은 `inquiry_id`에 대해 두 개의 `regenerate`
> 요청이 거의 동시에 들어오면, count 조회 자체가 레이스 컨디션에
> 노출된다(둘 다 "2회 미만"으로 읽고 동시에 통과할 위험). 카운트 조회
> 시 `SELECT ... WHERE inquiry_id=:id FOR UPDATE`로 해당 inquiry의
> 응답 이력에 행 잠금을 걸어, 두 번째 요청이 첫 번째 트랜잭션 커밋을
> 기다리게 한다(순차 처리 강제). 이 잠금 없이는 재시도 상한이 실제로는
> 3회를 넘길 수 있다.

---

## 8. RAG 지식베이스 (KNOWLEDGE_CHUNKS)

| Method | Endpoint | 설명 |
|---|---|---|
| GET | `/properties/{property_id}/knowledge-chunks` | 지식 목록 |
| POST | `/properties/{property_id}/knowledge-chunks` | 하우스룰/FAQ 등록(로컬 임베딩 모델로 **동기 생성** — 응답 즉시 embedding 완료 상태로 반환, 별도 상태 폴링 불필요) |
| DELETE | `/knowledge-chunks/{chunk_id}` | 삭제 |

---

## 9. 알림·액션센터 (ACTION_ITEMS)

| Method | Endpoint | 설명 |
|---|---|---|
| GET | `/properties/{property_id}/action-items?status=OPEN` | 🔴🟡🟢 알림 목록 |
| PATCH | `/action-items/{action_id}/resolve` | 처리 완료 표시 |

> **생성 엔드포인트(`POST`)가 없다.** `ACTION_ITEMS`는 **시스템 배치·트리거로만
> 생성**되며(청소 지연 감지, 서류 만료 임박, 가격 조정 추천 등) 호스트가 직접
> 추가하지 않는다. 화면에도 "액션 추가" 기능을 두지 않는다.

### 9.1 GET /properties/{property_id}/action-items 응답 스펙 (v2.0 신규 확정)

**응답 9필드는 전부 `ACTION_ITEMS` 실재 컬럼이며 파생 필드가 없다.**

```json
{
  "data": [
    {
      "action_id": 91,
      "property_id": 1,
      "reservation_id": 501,
      "risk_level": "RED_NOW",
      "category": "CLEANING_DELAY",
      "title": "체크인 2시간 전인데 청소 미완료",
      "content": "강남 3룸 독채 · 오늘 16:00 체크인",
      "status": "OPEN",
      "created_at": "2026-09-08T09:12:00Z"
    }
  ],
  "meta": { "total": 47, "page": 1, "size": 20 },
  "error": null
}
```

| 필드 | 출처 컬럼(명세서 2.15절) | 타입 |
|---|---|---|
| `action_id` | `action_id` | BIGSERIAL |
| `property_id` | `property_id` | BIGINT NOT NULL |
| `reservation_id` | `reservation_id` | BIGINT **nullable**(서류만료 등 예약과 무관한 건) |
| `risk_level` | `risk_level` | `action_risk_level_enum` NOT NULL |
| `category` | `category` | VARCHAR(50) NOT NULL |
| `title` | `title` | TEXT NOT NULL |
| `content` | `content` | TEXT nullable |
| `status` | `status` | `action_status_enum` NOT NULL DEFAULT `'OPEN'` |
| `created_at` | `created_at` | TIMESTAMPTZ NOT NULL DEFAULT `now()` |

**쿼리 파라미터**

| 파라미터 | 근거 |
|---|---|
| `status` | 기존(위 표에 이미 있음) |
| `risk_level` | **v2.0 신규** — 아래 근거 참고 |
| `page` / `size` | 0절 공통 규약 |

> `risk_level` 필터는 인덱스
> `idx_action_items_property_status(property_id, status, risk_level)`의
> **세 번째 키**다. **`status`와 함께 사용할 때 인덱스로 커버되며**, `status`
> 없이 `risk_level`만 필터하면 앞 키를 건너뛰어 인덱스 효율이 떨어진다.
> **두 필터를 함께 쓰는 것을 전제한다.**
>
> **`category` 필터는 1차에 넣지 않는다.** 인덱스에 없어 필터링 시 인덱스를
> 못 쓰며, `/actions` 화면의 카테고리 탭은 프론트에서 처리한다.
>
> **`limit` 파라미터를 신설하지 않는다.** 0절의 `size`가 같은 역할을 하며
> 의미가 겹친다.

**정렬**

```sql
ORDER BY risk_level ASC, created_at DESC
```

`action_risk_level_enum`이 `RED_NOW` → `YELLOW_TODAY` → `GREEN_AUTO` 순으로
선언돼 있어 **PostgreSQL의 ENUM 비교가 선언 순서를 따른다.** 별도 `CASE` 문이
불필요하다.

> ※ `created_at`은 인덱스에 없어 **`risk_level`이 같은 항목 간 정렬은 별도로
> 수행된다.** `property_id` + `status`로 좁힌 뒤라 대상 건수가 적어 실사용에서
> 문제되지 않는다.

**두 화면이 같은 엔드포인트를 사용한다**

| 화면 | 호출 | 용도 |
|---|---|---|
| `/dashboard` 액션 프리뷰 | `?status=OPEN&size=5` | 조회·이동만(인라인 처리 버튼 없음) |
| `/actions` 전체 큐 | `?status=OPEN&size=20` | 전체 큐와 처리 |

> ※ 대시보드 프리뷰의 **"전체 N건 처리하러 가기"** 표시에는 이 응답의
> `meta.total`이 아니라 **`dashboard/summary`의 `open_action_count`를
> 사용한다.** 대시보드는 이미 `summary`를 호출하므로 같은 숫자를 두 경로로
> 얻을 이유가 없고, **두 값의 조회 시점이 어긋날 수 있다.**
> (`GET /properties`에 요약 지표를 넣지 않기로 한 것과 같은 근거 — 2절 참고)

**`category` 값 현황 (확정하지 않음)**

명세서 2.15절이 `category`를 `VARCHAR(50)`으로 두고 *"category 정의가 아직
세밀하지 않아 DB 제약으로 못박기엔 이름"*이라고 밝히고 있으므로 **허용값을
확정하지 않는다.** 현재 문서에 등장하는 값만 참고로 기록한다.

| 값 | 출처 |
|---|---|
| `CLEANING_DELAY` | 명세서 2.15절 검증 예시 |
| `COMPLIANCE_EXPIRY` | 명세서 2.15절 검증 예시 |
| `PRICE_ADJUSTMENT` | 본 문서 13절 |
| `PRICE_NEGLECT` | 본 문서 13절 |

- **각 기능 구현 시 값이 추가될 수 있다.**
- **신규 `category`를 추가할 때는 이 목록과 프론트 카드 컴포넌트 분기를 함께
  갱신한다.** `VARCHAR`라 **DB가 오타를 막지 못하며**, 오타가 들어가면 "동일
  `reservation_id` + `category` + `status='OPEN'` 조합 재사용" idempotency
  로직이 깨져 **같은 알림이 중복 생성된다**(명세서 2.15절).

### 9.2 PATCH /action-items/{action_id}/resolve 스펙 (v2.0 신규 확정)

**요청 본문 없음** — 경로 파라미터만 받는다.

**응답**: 갱신된 레코드 9필드를 그대로 반환한다(9.1과 동일 구조, 단건).

```json
{ "data": { "action_id": 91, "status": "RESOLVED", "...": "나머지 7필드 동일" },
  "error": null }
```

**`status`는 항상 `RESOLVED`로 전이한다.**

**서버 가드 — 가격 계열 액션 거부**

| 상황 | HTTP | code |
|---|---|---|
| `category`가 `PRICE_ADJUSTMENT` 또는 `PRICE_NEGLECT`인 액션에 호출 | 400 | `PRICE_ACTION_REQUIRES_APPLY` |

가격 카드는 `POST /properties/{property_id}/price-recommendations/apply`를
거쳐야 **Mock 반영이 함께** 이뤄진다. `resolve`만 허용하면 가격 반영 없이
카드만 닫히므로 서버에서 막는다(13절 참고).

**IDOR 방어**: 0절 공통 원칙대로, **소유권 불일치와 부존재를 구분하지 않고
`404 RESOURCE_NOT_FOUND`로 통일**한다. 이 엔드포인트는 경로에 `property_id`가
없으므로 조회 쿼리 자체에 소유권 조건을 묶는다.

> **이 엔드포인트는 `AUTO_RESOLVED`를 세팅하지 않는다.** 시스템이 자동으로
> 닫는 경로로 추정되나 **문서에 로직 정의가 없다**(9/7 확인). ENUM 정의와 ERD
> 표기에만 등장하며 언제 누가 세팅하는지 설명이 없고, `risk_level='GREEN_AUTO'`
> 와의 관계도 미정이다.
>
> **10/6 액션센터 구현 전까지 `GREEN_AUTO` 항목의 실질적 자동 해결은 동작하지
> 않는다.** 트리거 규칙과 함께 그 시점에 확정한다.

---

## 10. 컴플라이언스 (CHECKLIST_ITEMS)

| Method | Endpoint | 설명 |
|---|---|---|
| GET | `/properties/{property_id}/checklist-items` | 체크리스트 목록(만료 임박순 정렬) |
| PATCH | `/checklist-items/{item_id}` | 완료/갱신 처리 |

---

## 11. 헬스체크 엔드포인트 (인프라 공통, 신규)

> Render 무료 플랜의 15분 슬립 방지용 외부 핑(UptimeRobot/GitHub
> Actions 등) 대상. 비즈니스 로직 API로 핑을 보내면 매번 DB 조회가
> 발생해 불필요하게 무거우므로, 전용 경량 엔드포인트를 별도로 둔다.

| Method | Endpoint | 설명 |
|---|---|---|
| GET | `/health` | 인증 불필요, DB 조회 없이 즉시 `{"status": "ok"}` 반환 |

## 12. Claude API 장애 대응 (전체 도메인 공통, 신규)

> 지금까지 설계에 빠져있던 부분 — Claude API가 타임아웃되거나
> 응답불가일 때 시스템이 멈추지 않도록 명시.

- **타임아웃 기준**: 최초 호출은 **10초**, 시스템 자동재시도(1회)는
  **5초**로 단축(최악의 경우 총 대기 15.1초 — 게스트가 화면 앞에서
  기다리는 시간을 고려한 조정, 4차 크로스체크 반영)
- **처리 방식**: 타임아웃 또는 5xx 에러 발생 시,
  1. `INQUIRY_RESPONSES`에 실패 기록을 남기지 않는다(재시도 카운트에
     영향 주지 않음 — 시스템 장애를 게스트/호스트 책임으로 돌리지 않음)
  2. 즉시 `ACTION_ITEMS`에 🔴 알림 생성(`category: "AI_TIMEOUT"`)
  3. 게스트에게는 "확인 후 곧 답변드리겠습니다"류의 정적 대기 메시지
     자동 발송(별도 LLM 호출 없이 템플릿 문자열) — 응답 대기가 길어질
     수 있으므로 화면에도 즉시 "AI가 답변을 확인 중입니다" 안내 표시
  4. 호스트는 Action Center에서 이 건을 확인하고 직접 작성 모달로
     처리 가능
- **재시도 여부**: 타임아웃은 사용자의 `regenerate` 요청이 아니므로
  재시도 횟수(최대2회)와 **별개**로 시스템이 자동으로 1회만 조용히
  재시도하고, 그래도 실패하면 위 폴백으로 전환한다.
- **`regenerate`(재시도 잠금)와의 상호작용**: `POST /regenerate` 호출로
  이미 `FOR UPDATE` 잠금을 쥔 상태에서 시스템 자동재시도가 발생해도,
  **같은 트랜잭션(같은 세션) 안에서 재호출**하는 것이므로 자기 자신과
  락 경쟁이 생기지 않는다(별도 우회 경로 불필요, 4차 크로스체크로 확인).

---

## 13. 동적 가격 조정 (명세서 6절 대응, v1.6 신규)

> 9/4 1단계 검증에서 **"명세서 6절에 기능은 확정돼 있는데 대응 API가
> 하나도 없다"**는 누락이 발견되어 추가. 10/7 작업(추천가 카드·승인
> 클릭·하한가 경고)의 구현 대상이다.

**설계 원칙: 새 테이블을 만들지 않는다.** 가격 추천 결과는 별도
`price_recommendations` 테이블이 아니라 **`ACTION_ITEMS` 카드로만**
표현한다(명세서 6.1절 흐름과 일치, 범위확장 방지).

| Method | Endpoint | 설명 |
|---|---|---|
| GET | `/properties/{property_id}/price-recommendations` | 오늘자 배치가 만든 가격조정 추천 목록(향후 14일). 내부적으로 `ACTION_ITEMS` 중 `category='PRICE_ADJUSTMENT'`인 OPEN 건을 조회 |
| POST | `/properties/{property_id}/price-recommendations/apply` | 선택한 추천 일괄 승인 → **Mock 반영**(OTA 가격수정 API는 범위 밖) + 해당 ACTION_ITEMS를 `RESOLVED`로 전이 |

**응답/요청 예시**
```json
// GET 응답
{ "data": [
    { "action_id": 91, "date": "2026-09-16", "day_type": "WEEKDAY",
      "current_price": 150000, "recommended_price": 147000,
      "delta": -3000, "reason": "평일·체크인 3일 이내·미예약",
      "risk_level": "GREEN_AUTO", "below_lower_bound": false }
  ], "error": null }

// POST 요청
{ "action_ids": [91, 92] }
```

> **하한가 경고**: `recommended_price < PROPERTIES.lower_bound_price`이면
> `below_lower_bound: true`로 내려주고, apply 요청에 해당 건이 포함되면
> `400`, `code: "BELOW_LOWER_BOUND"`로 거부한다(호스트가 하한가를 먼저
> 낮춰야 적용 가능).
>
> **연휴 방치감지는 apply 대상이 아니다.** 명세서 6.3절 원칙대로 자동
> 조정 없이 🟡 알림 카드만 발행되므로, 이 건은 `recommended_price`가
> `null`이고 `category='PRICE_NEGLECT'`로 구분된다. 승인 UI에서 조정
> 추천과 섞이지 않게 별도 섹션으로 표시할 것.
>
> **가격조정은 AI가 아니라 규칙기반이다.** 응답의 `reason`은 LLM 생성
> 문장이 아니라 6.2절 조정폭 표에서 그대로 가져온 고정 문자열이다
> (명세서 4절 원칙과 동일 — "AI가 최적가를 계산한다"고 설명하지 않음).

**`action-items`와의 관계 및 호출 경로 (v2.0 명시)**

두 엔드포인트는 **같은 레코드를 가리킨다.** 가격 추천은 전용 테이블 없이
`ACTION_ITEMS` 카드로만 표현되므로(위 설계 원칙), 같은 행이
`GET /properties/{id}/action-items`에도 `category='PRICE_ADJUSTMENT'` 또는
`'PRICE_NEGLECT'`로 나타난다.

- `/actions` 화면에서 **가격 카드를 승인할 때는**
  `POST /properties/{property_id}/price-recommendations/apply`를 호출한다.
- **`PATCH /action-items/{action_id}/resolve`를 쓰면 안 된다.** `apply`가 Mock
  반영과 `RESOLVED` 전이를 **함께** 수행하므로, `resolve`만 호출하면 **가격
  반영 없이 카드만 닫힌다.**
- **9.2절의 서버 가드가 이 실수를 막는다**(`400 PRICE_ACTION_REQUIRES_APPLY`).
- **프론트에서도 카드 컴포넌트를 카테고리별로 분리해 각자 자기 엔드포인트를
  호출하게 한다.** 공통 카드에 `onResolve` 하나만 두면 분기를 놓치기 쉽다.

---

## 부록. 도메인별 → 테이블 매핑 요약

| 도메인 | DB 테이블 |
|---|---|
| 인증 | HOSTS |
| 숙소관리 | PROPERTIES, ROOMS, BEDS |
| 채널연동 | CHANNEL_CONNECTIONS |
| 예약 | RESERVATIONS |
| 정산 | FINANCIAL_CONFIGS, MONTHLY_SETTLEMENTS |
| 청소 | CLEANING_TASKS |
| AI응대 | INQUIRIES, INQUIRY_CLASSIFICATIONS, INQUIRY_RESPONSES, INQUIRY_APPROVALS |
| RAG | KNOWLEDGE_CHUNKS |
| 알림 | ACTION_ITEMS |
| 동적 가격조정 | ACTION_ITEMS(`category='PRICE_ADJUSTMENT'`/`'PRICE_NEGLECT'`) + PROPERTIES(`lower_bound_price`, `*_adjustment_enabled`) — **전용 테이블 없음** |
| 컴플라이언스 | CHECKLIST_ITEMS |

**16개 테이블 전부 매핑 완료.**
