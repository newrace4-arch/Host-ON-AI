# Host ON (AI) — API Contract v1.2 (3차 크로스체크 반영)

> `docs/3rd_host_ai_db_spec_v1.md`(v1.2) 16개 테이블을 기준으로 작성.
> **v1.1→v1.2 변경**: reservation_id nullable 규칙, is_latest 갱신
> 트랜잭션 순서(이유 포함), 월정산 확정 기준일(check_out)+트랜잭션
> 범위 명시 — 9/5 구현 직전 코드레벨 맹점 3개 반영.
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
    "net_payout": 253500,
    "is_conflict": false
  },
  "error": null
}
```
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

> 청소작업은 `reservation_id`당 자동 1건 생성(예약 생성/체크아웃 이벤트에서
> 서버가 자동 트리거, 별도 생성 API 없음 — UNIQUE 제약과 일치).

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
> "반려동물 동반 가능한가요?" 같은 사전 문의를 지원하기 위함). DB의
> `INQUIRIES.reservation_id`도 nullable로 설계되어 있음(명세서 2.10절).

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
| 컴플라이언스 | CHECKLIST_ITEMS |

**16개 테이블 전부 매핑 완료.**
