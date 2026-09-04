# Host ON (AI) — API Contract v1.6 (9/4 1단계 검증 반영)

> `docs/3rd_host_ai_db_spec_v1.md`(**v1.3**) 16개 테이블을 기준으로 작성.
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
> 전이되는 즉시 서버가 자동 트리거, scheduled_date=체크아웃일로 미리
> 세팅, 별도 생성 API 없음 — UNIQUE 제약과 일치, 9/3 정정).

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
