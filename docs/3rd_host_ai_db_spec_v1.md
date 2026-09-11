# 3rd Host AI — DB 최종 명세서 (v1.4)

> 브랜드명: **Host ON (AI)** (내부 코드/폴더명은 3rd_host_ai 유지)
>
> **v1.3 → v1.4 변경사항 (9/11 강사님 4차 미팅 반영)**:
>
> 테이블이 **16개 → 19개**가 된다. 신설 3개(2.17·2.18·2.19)는 전부 기존
> 절 번호를 건드리지 않고 뒤에 붙였다.
>
> 1. **`INQUIRY_RESPONSES.sources`(JSONB) 제거 → `RESPONSE_SOURCES` 신설**
>    (2.12·2.17절). 강사님 요지: *JSONB 배열에 담긴 `["chunk_17"]`은 다른
>    테이블을 가리키는 참조인데 FK가 걸리지 않아 DB가 무결성을 보장하지
>    못한다. N:N은 중간 테이블로 푼다.*
>    사유: 청크가 삭제돼도 `"chunk_17"`이 그대로 남아 끊어진 참조가 됐다.
> 2. **`CLEANING_TASKS.photo_urls`(JSONB) 제거 → `CLEANING_TASK_PHOTOS`
>    신설**(2.9·2.18절). 강사님 요지: *1번과 같은 형태이므로 같은 방식으로
>    푼다.* 사유: 사진 1장이 행 1개가 되어 개별 삭제·정렬이 가능해진다.
> 3. **`CHANNEL_CONNECTIONS.room_id` 추가**(2.5절). 사유: iCal 피드가
>    객실을 알려주지 않아 호스텔은 **객실마다 별도 리스팅·별도 피드**를
>    받는데, 기존 `UNIQUE(property_id, channel)`로는 숙소당 채널 1개만
>    연결할 수 있었다. 이 앱의 차별점(여러 숙박업 유형 동시 운영)을 정면
>    으로 막는 제약이었다.
> 4. **`RESERVATIONS.net_amount`를 생성 컬럼으로 교체**(2.6절). 강사님
>    요지: *`gross - fee`로 항상 계산되는 값을 따로 저장하면 셋이 어긋날
>    수 있다. 계산으로 유도되는 값은 DB가 계산하게 한다.*
>    **컬럼 이름은 `net_amount` 그대로 유지**한다(api_contract v1.6이
>    `net_payout`과 구분해 이미 확정한 이름이다).
> 5. **채널별 수수료 전용 테이블 `CHANNEL_FEE_RATES` 신설**(2.7·2.19절).
>    `FINANCIAL_CONFIGS`의 `fee_type`·`commission_rate`·`fee_source`를
>    그리로 옮긴다. 사유: `FINANCIAL_CONFIGS.property_id`가 `UNIQUE`라
>    **숙소당 요율이 1개**인데 채널은 3개까지 허용된다. 채널마다 수수료가
>    다른 현실을 표현할 자리가 없었다.
> 6. **`FINANCIAL_CONFIGS.base_nightly_rate` 제거**(2.7절). 사유: 단가의
>    원본은 `PROPERTIES.base_price`다(`POST /properties` 요청 필드에도
>    그쪽만 있다). 같은 뜻의 컬럼이 두 테이블에 있으면 어느 쪽이 진짜인지
>    정해야 하는데, 정한 문서가 없었고 쓰는 코드도 없었다.
> 7. **복합 FK 대상 UNIQUE 3건 신규**: `INQUIRIES(inquiry_id,
>    property_id)`(2.10절), `INQUIRY_RESPONSES(response_id,
>    property_id)`(2.12절), `KNOWLEDGE_CHUNKS(chunk_id,
>    property_id)`(2.14절). 사유: 위 1번의 중간 테이블이 "응답과 청크가
>    같은 숙소인가"를 복합 FK로 검증하려면 후보키가 필요하다.
>    `ROOMS`·`BEDS`가 같은 목적으로 이미 갖고 있는 것과 같은 형태다.
> 8. **4절에 정책 3건 추가**: 요율 행 생성 시점 / 금액 계산 규칙 /
>    이 설계가 표현하지 못하는 한계 4가지.
>
> **v1.2 → v1.3 변경사항 (9/4 1단계 검증에서 발견된 4건 반영)**:
> 1. `INQUIRIES.reservation_id`를 **NOT NULL → nullable**로 변경(예약 전
>    사전문의 지원, API Contract 7절과 정합). 이로 인해 복합FK 검사가
>    통째로 스킵되는 구멍이 생기므로 `INQUIRIES.property_id`에 **단독 FK를
>    신규 추가**(2.10절).
> 2. `CHANNEL_CONNECTIONS.last_error_message` 신규 추가 — API Contract에
>    이미 있던 `GET /channels/{id}/sync-errors`가 저장할 컬럼이 없었음(2.5절).
> 3. `CLEANING_TASKS.photo_urls`(JSONB 배열) 신규 추가 — 청소 완료사진
>    업로드 API가 저장할 컬럼이 없었음. 교체가 아니라 **append 누적**(2.9절).
> 4. `ACTION_ITEMS`의 `reservation_id`를 단독 FK → **복합 FK**로 변경.
>    다른 숙소의 예약을 참조하는 액션아이템이 만들어질 수 있던 구멍을
>    DB 레벨에서 차단(2.15절, 4절 -1번 원칙과 일치).
> 5. `CLEANING_TASKS.scheduled_date` → **`scheduled_at`으로 개명**(타입은
>    `TIMESTAMPTZ` 그대로). `_date`라는 이름이 DATE 타입으로 오해를 부르고,
>    다른 TIMESTAMPTZ 컬럼(`last_synced_at`, `verified_at`, `approved_at`)의
>    `_at` 네이밍 컨벤션과도 어긋났음. 저장값 의미도 "체크아웃일 00:00"이
>    아니라 **`check_out` + `checkout_time`을 결합한 실제 체크아웃 시각**으로
>    명확히 함(2.9절).
>
> **v1.1 → v1.2 변경사항**: "공백일 자동 미세조정 + 성수기 방치감지"
> 기능(6절) 신규 추가. `PROPERTIES`에 필드 2개 추가(새 테이블 없음).
> Property 단위 데이터 격리 원칙(4절 -1번) 신규 추가.
>
> **v1.0 → v1.1 변경사항**: 아래 3개 정합성 문제 수정 후 Schema Freeze 대상으로
> 재확정
> 1. `bookable_unit_type` CHECK 관련 서술을 기술적으로 정확하게 수정
>    (DB CHECK는 room/bed 내부 형태만 검증, Property와의 교차일치는 앱 책임)
> 2. Action Center "체크인 N시간 전" 규칙 실현을 위해 PROPERTIES에
>    `checkin_time`/`checkout_time` 필드 추가
> 3. 청소 완료 판정에 VERIFIED 상태 포함하도록 Action Center 쿼리 수정
>
> [문서 변경관리 규칙]
> 1. 본 문서를 DB Schema의 Single Source of Truth로 한다.
> 2. DB 구조 변경은 본 문서를 먼저 수정한다.
> 3. ERD/SQLAlchemy/Alembic/API Contract/Excel 체크리스트는 본 문서 변경
>    후 동기화한다. Excel을 먼저 고치고 본 문서를 나중에 맞추는 순서는 금지.
> 4. 구현 코드와 본 문서가 다르면 본 문서를 기준으로 차이를 해결한다.
> 5. Schema Freeze 이후 변경은 반드시 버전(v1.1→v1.2 등)과 변경 사유를 기록한다.
> 6. 단순 구현 버그 수정은 문서 변경 대상이 아니며, 스키마·제약조건·필드·
>    관계가 바뀔 때만 문서를 갱신한다.
>
> 9/1 착수 전 확정할 최종 리스트 및 아래 12개 항목은 이미 이 문서에
> 전부 반영되어 있습니다. 실행 체크리스트(엑셀)와의 정합성 기준 문서는
> **이 파일**입니다 (Single Source of Truth).

> 9/1 스키마 구현 착수용. ERD 6차 크로스체크(doc19·doc20 대조 포함) 결과를 반영한 최종 확정본입니다.
> DB: PostgreSQL (로컬 Docker Postgres / 배포 Supabase 동일 버전 사용)

---

## 0. 이번 명세에서 확정한 핵심 결정 요약

| # | 결정 사항 | 채택 근거 |
|---|---|---|
| 1 | `bookable_unit_type` ↔ `room_id`/`bed_id`의 **내부 형태**(shape) 일치는 Reservation CHECK로 DB가 강제. 단, `bookable_unit_type`은 PROPERTIES에 있고 room_id/bed_id는 RESERVATIONS에 있어 **PostgreSQL 일반 CHECK로는 테이블을 넘나드는 검증이 불가능** — 이 교차일치는 애플리케이션 트랜잭션 책임 | 공통, v1.1에서 정정 |
| 2 | Room/Bed가 실제로 해당 Property/Room 소속인지 **계층적 복합 FK**로 보장 | doc19 (doc20엔 없던 항목) |
| 3 | 예약 겹침 방지는 PROPERTY/ROOM/BED **단위별로 EXCLUDE 3개 분리** | doc19 채택, doc20의 `COALESCE(room_id,0)` 방식은 **폐기** — 0을 "값 없음"과 "진짜 0번 ID"로 구분 못 해 데이터 오염 위험 |
| 4 | PROPERTY↔ROOM/BED 간 **교차 충돌은 애플리케이션 트랜잭션 검증**으로 방어 | doc19 |
| 5 | `CLEANING_TASKS.reservation_id` UNIQUE (1:1) | 공통 |
| 6 | `INQUIRY_RESPONSES`는 1:N + `is_latest` 플래그 | doc20 채택 (doc19의 "1:N, UI에서 최신것만" 보다 구체적) |
| 7 | `FINANCIAL_CONFIGS → MONTHLY_SETTLEMENTS` 직접 관계 제거, 정산은 스냅샷으로 독립 | doc19 |
| 8 | `ACTION_ITEMS` 중복 생성 방지는 DB UNIQUE가 아닌 **애플리케이션 idempotency**로 처리 | doc19 |
| 9 | `risk_level`은 AI 판단이 아니라 **규칙기반 우선순위**임을 명시적으로 문서화 | doc19 |
| 10 | `CHECKLIST_ITEMS.accommodation_type`은 "파생 템플릿 유형"을 의미(Property 현재 유형의 실시간 복사본 아님) | doc19 |
| 11 | **[v1.4]** 다중값 JSONB 컬럼 2개(`INQUIRY_RESPONSES.sources`, `CLEANING_TASKS.photo_urls`)를 **전용 테이블로 분리**(2.17·2.18절) | 9/11 강사님 4차 미팅 — FK가 걸리지 않는 참조는 DB가 무결성을 보장하지 못한다 |
| 12 | **[v1.4]** `CHANNEL_CONNECTIONS`에 `room_id` 추가 + UNIQUE를 **`NULLS NOT DISTINCT (property_id, channel, room_id)`**로 확장 | iCal 피드가 객실을 주지 않아 호스텔은 객실별 리스팅·객실별 피드가 된다 |
| 13 | **[v1.4]** `RESERVATIONS.net_amount`를 **생성 컬럼**(`gross_amount - fee_amount`)으로 교체. 이름은 유지 | 계산으로 유도되는 값을 따로 저장하면 셋이 어긋난다 |
| 14 | **[v1.4]** 수수료를 **채널 단위**로 분리(`CHANNEL_FEE_RATES`, 2.19절). `FINANCIAL_CONFIGS`에는 `vat_included`만 남는다 | `FINANCIAL_CONFIGS.property_id`가 UNIQUE라 숙소당 요율 1개인데 채널은 3개까지 허용된다 |

---

## 1. ENUM 타입 정의

> `accommodation_type`은 단일 값만 허용(복수 등록 불가). 근거: **관광진흥법
> 시행령 제2조 제1항 제3호 바목** — 외국인관광 도시민박업 등 숙박업
> 유형은 관광객 이용시설업으로 분류되며, 동일 공간에 대해 복수
> 유형을 동시 등록할 수 없음(9/3 재조사로 정확한 조항까지 확인, 최초엔
> "관광진흥법상"으로만 알고 있었으나 정확히는 "시행령"임).

```sql
CREATE TYPE accommodation_type_enum AS ENUM (
  'URBAN_HOMESTAY', 'RURAL_HOMESTAY', 'HANOK', 'HOSTEL',
  'LODGING_FACILITY', 'GENERAL_LODGING'
);

CREATE TYPE bookable_unit_type_enum AS ENUM ('PROPERTY', 'ROOM', 'BED');

CREATE TYPE channel_enum AS ENUM ('AIRBNB', 'BOOKING_COM', 'NAVER');

CREATE TYPE sync_status_enum AS ENUM ('SYNCING', 'SYNCED', 'FAILED', 'STALE');

CREATE TYPE reservation_status_enum AS ENUM (
  'PENDING', 'CONFIRMED', 'MODIFIED', 'CANCELLED', 'COMPLETED'
);

CREATE TYPE refund_status_enum AS ENUM ('NONE', 'PARTIAL', 'FULL');

CREATE TYPE financial_status_enum AS ENUM (
  'ESTIMATED', 'CONFIRMED', 'MANUALLY_ADJUSTED'
);

CREATE TYPE fee_type_enum AS ENUM ('SPLIT_FEE', 'SINGLE_FEE');

CREATE TYPE task_status_enum AS ENUM (
  'PENDING', 'ASSIGNED', 'IN_PROGRESS', 'COMPLETED', 'VERIFIED', 'ISSUE'
);

CREATE TYPE inquiry_risk_level_enum AS ENUM ('LOW', 'MEDIUM', 'HIGH');

-- ACTION_ITEMS 전용: 법적/안전 위험도가 아니라 "운영상 처리 우선순위" (섹션 8 참고)
CREATE TYPE action_risk_level_enum AS ENUM ('RED_NOW', 'YELLOW_TODAY', 'GREEN_AUTO');

CREATE TYPE action_status_enum AS ENUM ('OPEN', 'RESOLVED', 'AUTO_RESOLVED');

CREATE TYPE approval_status_enum AS ENUM ('PENDING', 'APPROVED', 'REJECTED');

CREATE TYPE document_type_enum AS ENUM ('HOUSE_RULE', 'POLICY', 'FAQ');

CREATE TYPE renewal_trigger_type_enum AS ENUM (
  'NONE', 'EXPIRATION_BASED', 'EVENT_BASED'
);
```

---

## 2. 테이블 DDL

### 2.1 HOSTS

```sql
CREATE TABLE hosts (
  host_id        BIGSERIAL PRIMARY KEY,
  email          VARCHAR(255) NOT NULL UNIQUE,
  password_hash  VARCHAR(255) NOT NULL,
  name           VARCHAR(100) NOT NULL,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

> **phone 필드 미포함 결정(확정)**: 현재 설계상 호스트 본인에게 전화/문자를
> 보내는 기능이 없어 실사용처가 없음. "일단 있으면 좋을 것 같아서" 넣는
> 필드는 범위확장의 시작점이 되므로 배제. 2차에서 실제 필요(예: 문자알림을
> 호스트 본인에게도 발송)가 생기면 `ALTER TABLE hosts ADD COLUMN phone`으로
> 언제든 추가 가능 — 지금 안 넣는다고 나중에 못 넣는 게 아님.

### 2.2 PROPERTIES

```sql
CREATE TABLE properties (
  property_id        BIGSERIAL PRIMARY KEY,
  host_id            BIGINT NOT NULL REFERENCES hosts(host_id) ON DELETE CASCADE,
  name               VARCHAR(150) NOT NULL,
  accommodation_type accommodation_type_enum NOT NULL,
  bookable_unit_type bookable_unit_type_enum NOT NULL,
  address            VARCHAR(255),
  base_price         INTEGER NOT NULL DEFAULT 0,
  lower_bound_price  INTEGER,
  checkin_time       TIME NOT NULL DEFAULT '15:00',   -- v1.1 추가: Action Center 시간규칙용
  checkout_time      TIME NOT NULL DEFAULT '11:00',   -- v1.1 추가: Action Center 시간규칙용
  weekday_adjustment_enabled BOOLEAN NOT NULL DEFAULT true,  -- v1.2 추가: 공백일 미세조정 on/off
  holiday_adjustment_enabled BOOLEAN NOT NULL DEFAULT true,  -- v1.2 추가: 성수기 방치감지 on/off
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_properties_host ON properties(host_id);
```

> **v1.1 추가 이유**: `RESERVATIONS.check_in`은 DATE 타입이라 "몇 시"인지
> 알 수 없다. Action Center의 "체크인 2시간 전" 같은 규칙은 실제로는
> `check_in + checkin_time`(날짜+숙소별 체크인 시각)을 합쳐야 계산 가능하다.
> 체크인 시각을 예약마다 따로 저장하지 않고 **숙소(Property) 단위 정책**으로
> 둔 이유는 실제 운영에서 체크인 시각은 예약별이 아니라 숙소 운영정책으로
> 고정되는 경우가 대부분이기 때문이다(예: 오후 3시 체크인).

### 2.3 ROOMS

```sql
CREATE TABLE rooms (
  room_id      BIGSERIAL PRIMARY KEY,
  property_id  BIGINT NOT NULL REFERENCES properties(property_id) ON DELETE CASCADE,
  room_name    VARCHAR(100) NOT NULL,
  capacity     INTEGER,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- (property_id, room_id): room_id가 이미 PK라 이 자체로 "중복방지" 효과는 없음.
  --   목적은 따로 있음 — Reservation이 (room_id, property_id) 복합FK로 이 조합을
  --   참조할 때 "이 room이 정말 이 property 소속인가"를 DB가 검증하기 위한
  --   후보키(candidate key)로만 사용. 반드시 유지할 것.
  UNIQUE (room_id, property_id),
  -- 실제 게스트가 보는 객실명("101호" 등)이 같은 숙소 안에서 중복되지 않도록
  -- 하는 운영 무결성용 제약. 위 UNIQUE와 목적이 다르므로 둘 다 필요함.
  UNIQUE (property_id, room_name)
);

CREATE INDEX idx_rooms_property ON rooms(property_id);
```

> **한 문장 요약**: `UNIQUE(room_id, property_id)`는 "미래 Reservation 참조용",
> `UNIQUE(property_id, room_name)`는 "지금 당장 같은 숙소 안 객실명 중복 방지용"
> — 목적이 다른 두 제약이니 하나로 합치거나 둘 중 하나를 빼지 말 것.

### 2.4 BEDS

```sql
CREATE TABLE beds (
  bed_id      BIGSERIAL PRIMARY KEY,
  room_id     BIGINT NOT NULL REFERENCES rooms(room_id) ON DELETE CASCADE,
  bed_label   VARCHAR(50) NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- ROOMS와 동일한 이유: 미래 Reservation 복합FK 참조용 후보키
  UNIQUE (bed_id, room_id),
  -- 같은 객실 안에서 침대 라벨("A","B" 등) 중복 방지용 운영 무결성 제약
  UNIQUE (room_id, bed_label)
);

CREATE INDEX idx_beds_room ON beds(room_id);
```

### 2.5 CHANNEL_CONNECTIONS

```sql
CREATE TABLE channel_connections (
  connection_id          BIGSERIAL PRIMARY KEY,
  property_id            BIGINT NOT NULL REFERENCES properties(property_id) ON DELETE CASCADE,
  room_id                BIGINT,   -- v1.4 추가: 객실별 리스팅용. NULL이면 숙소 전체 피드
  channel                channel_enum NOT NULL,
  ical_url               TEXT,
  external_property_id   VARCHAR(100),
  sync_status            sync_status_enum NOT NULL DEFAULT 'SYNCING',
  last_synced_at         TIMESTAMPTZ,
  last_error_message     TEXT,   -- v1.3 추가: 마지막 동기화 실패 사유(1건만 보관)
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),

  -- v1.4: 다른 숙소의 객실을 가리키는 연결을 DB가 막는다.
  --   room_id가 NULL이면 MATCH SIMPLE 규칙에 따라 검사가 스킵되고,
  --   property_id는 위 단독 FK가 보장한다(2.10절 INQUIRIES와 같은 구조).
  FOREIGN KEY (room_id, property_id)
    REFERENCES rooms(room_id, property_id),

  UNIQUE (connection_id, property_id),  -- Reservation 복합 FK용
  -- v1.4: (property_id, channel) → (property_id, channel, room_id)로 확장.
  UNIQUE NULLS NOT DISTINCT (property_id, channel, room_id)
);

CREATE INDEX idx_channel_connections_property ON channel_connections(property_id);
```

> **[v1.4] 왜 `room_id`가 필요한가**
>
> iCal 피드는 **객실을 알려주지 않는다.** 실제로는 호스텔 객실마다 별도
> 리스팅이 만들어지고 **객실마다 별도 iCal URL**이 나온다. 그런데 기존
> `UNIQUE(property_id, channel)`은 숙소당 채널 1개만 허용해, 객실이 3개인
> 호스텔의 에어비앤비 피드 3개를 등록할 방법이 없었다. `room_id`가
> 있어야 동기화된 예약을 어느 객실에 넣을지도 정할 수 있다.
>
> `room_id`는 **nullable**이다. `bookable_unit_type=PROPERTY`인 독채는
> 객실 개념이 없으므로 NULL로 둔다.
>
> **⚠️ `NULLS NOT DISTINCT`를 반드시 붙인다.** PostgreSQL의 기본 UNIQUE는
> **NULL을 서로 다른 값으로 취급**하므로, 그냥 `UNIQUE(property_id,
> channel, room_id)`로 쓰면 `room_id`가 NULL인 행을 **몇 개든 넣을 수
> 있다.** 독채 숙소에 에어비앤비 연결이 2개, 3개 생겨 *"채널당 연결 1개"*
> 보장이 조용히 깨진다. `NULLS NOT DISTINCT`는 **PostgreSQL 15+ 문법**이며
> 이 프로젝트는 로컬·Supabase 모두 17이라 사용 가능하다.
>
> **⚠️ 제약 이름은 `uq_property_channel`을 그대로 유지한다.** 컬럼이
> 바뀌었으니 이름도 바꾸고 싶어지지만, `backend/app/services/
> channel_service.py`의 `create_channel`이 **이 이름으로 `IntegrityError`를
> `409 CHANNEL_ALREADY_CONNECTED`로 번역**한다
> (`violates_constraint(exc, "uq_property_channel")`). 이름을 바꾸면 판정이
> 조용히 실패해 409가 500으로 새어 나간다 — troubleshooting 32번이 같은
> 종류의 사고였다. 이름을 바꾸려면 서비스 코드를 같은 커밋에서 고쳐야 한다.

> **[v1.3] `last_error_message` 운용 규칙**: iCal 파싱/네트워크 실패 시
> `sync_status='FAILED'`와 함께 사람이 읽을 수 있는 사유 1줄을 저장한다
> (예: `"iCal URL 응답 없음(timeout 5s)"`, `"ICS 파싱 실패: 잘못된 DTSTART"`).
> 성공 시(`SYNCED`)에는 반드시 `NULL`로 초기화한다 — 지난 에러가 화면에
> 계속 남아 호스트를 혼란시키는 것을 막기 위함. 이력 누적은 하지 않고
> **마지막 1건만** 보관한다(테이블 추가 없이 처리하기 위한 의도적 제한).
> 원문 스택트레이스는 여기 넣지 않고 서버 로그로만 남긴다(정보노출 방지).

### 2.6 RESERVATIONS ⭐ 핵심 테이블

```sql
CREATE TABLE reservations (
  reservation_id             BIGSERIAL PRIMARY KEY,
  property_id                BIGINT NOT NULL REFERENCES properties(property_id) ON DELETE CASCADE,
  room_id                    BIGINT,
  bed_id                     BIGINT,
  channel_connection_id      BIGINT NOT NULL,
  external_uid               VARCHAR(150),
  guest_name                 VARCHAR(100),
  guest_language             VARCHAR(10),
  check_in                   DATE NOT NULL,
  check_out                  DATE NOT NULL,
  booked_at                  TIMESTAMPTZ,
  reservation_status         reservation_status_enum NOT NULL DEFAULT 'CONFIRMED',
  refund_status               refund_status_enum NOT NULL DEFAULT 'NONE',
  financial_status           financial_status_enum NOT NULL DEFAULT 'ESTIMATED',
  -- v1.4: 금액 3종의 출처와 계산 시점을 명시한다(4절 "금액 계산" 참고).
  --   gross_amount = properties.base_price × 박수. 예약 생성·동기화 시점에 저장.
  --                  base_price가 0이면 "미설정"으로 보고 NULL로 둔다.
  gross_amount                INTEGER,
  --   fee_amount = gross_amount × 해당 채널 요율(channel_fee_rates).
  --                **계산 시점의 요율 스냅샷**이며 이후 요율이 바뀌어도 소급하지 않는다.
  fee_amount                  INTEGER,
  --   net_amount = 생성 컬럼. gross/fee 중 하나라도 NULL이면 NULL이 된다.
  --                v1.4에서 일반 컬럼 → 생성 컬럼으로 교체(이름은 유지).
  net_amount                  INTEGER GENERATED ALWAYS AS (gross_amount - fee_amount) STORED,
  expected_settlement_at     DATE,
  actual_settlement_at       DATE,
  host_confirmation_required BOOLEAN NOT NULL DEFAULT false,
  created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),

  -- (A) 계층적 무결성: room/bed가 실제로 해당 property/room 소속인지 DB가 보장
  --     room_id/bed_id가 NULL이면 FK 검사 자체가 스킵되어 PROPERTY 단위 예약과 자연히 호환됨
  FOREIGN KEY (room_id, property_id)
    REFERENCES rooms(room_id, property_id),
  FOREIGN KEY (bed_id, room_id)
    REFERENCES beds(bed_id, room_id),
  FOREIGN KEY (channel_connection_id, property_id)
    REFERENCES channel_connections(connection_id, property_id),

  -- (B) room_id/bed_id 조합의 "내부 형태(shape)"가 유효한 3가지 패턴 중
  --     하나인지만 검증. 주의: 이 CHECK는 PROPERTIES.bookable_unit_type
  --     값과 실제로 일치하는지는 검증하지 못한다(PostgreSQL 일반 CHECK는
  --     다른 테이블을 참조할 수 없음). 예: bookable_unit_type=PROPERTY인데
  --     room_id가 채워진 예약도 이 CHECK만으로는 걸러지지 않는다.
  --     → Property.bookable_unit_type과의 교차일치는 반드시 애플리케이션
  --       트랜잭션(예약 생성 서비스 레이어)에서 별도 검증할 것.
  CHECK (
    (room_id IS NULL AND bed_id IS NULL) OR         -- PROPERTY 단위
    (room_id IS NOT NULL AND bed_id IS NULL) OR      -- ROOM 단위
    (room_id IS NOT NULL AND bed_id IS NOT NULL)     -- BED 단위
  ),
  CHECK (check_out > check_in),

  UNIQUE (channel_connection_id, external_uid),  -- 플랫폼별 UID 충돌 방지
  UNIQUE (reservation_id, property_id)           -- CLEANING_TASKS/INQUIRIES 복합 FK용
);

CREATE INDEX idx_reservations_property ON reservations(property_id);
CREATE INDEX idx_reservations_room ON reservations(room_id);
CREATE INDEX idx_reservations_bed ON reservations(bed_id);
CREATE INDEX idx_reservations_channel ON reservations(channel_connection_id);
CREATE INDEX idx_reservations_dates ON reservations(property_id, check_in, check_out);
```

> **[v1.4] `net_amount`를 생성 컬럼으로 바꾼 이유**
>
> `net_amount`는 언제나 `gross_amount - fee_amount`다. 일반 컬럼으로 두면
> 세 값을 각각 저장하게 되고, 어느 하나를 고치면서 나머지를 안 고치면
> **셋이 서로 어긋난 채 저장된다.** 생성 컬럼은 DB가 매번 계산하므로 그
> 상태가 원리상 생기지 않는다.
>
> - `STORED`를 쓴다. PostgreSQL은 `VIRTUAL` 생성 컬럼을 지원하지 않는다.
> - **애플리케이션이 `net_amount`에 값을 쓸 수 없다.** INSERT/UPDATE에
>   포함하면 에러가 난다. `ReservationCreateRequest`에서도 이 필드를 빼야
>   한다(스키마 구현 시 함께 처리).
> - `gross_amount`나 `fee_amount`가 NULL이면 `net_amount`도 NULL이다
>   (NULL 연산 규칙). "금액 미설정" 상태가 셋 다 NULL로 일관되게 표현된다.
> - **컬럼 이름을 바꾸지 않는다.** api_contract v1.6이 `MONTHLY_SETTLEMENTS.
>   net_payout`과 구분하려고 이미 확정한 이름이며, 바꾸면 응답 스펙·
>   와이어프레임·프론트 타입이 함께 움직인다.

#### 2.6.1 예약 겹침 방지 — EXCLUDE 3분리 (doc20의 COALESCE 방식 폐기)

```sql
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- ① PROPERTY 단위 예약끼리 겹침 방지 (독채 통대여, room/bed 둘다 NULL인 경우만)
ALTER TABLE reservations ADD CONSTRAINT excl_property_overlap
EXCLUDE USING gist (
  property_id WITH =,
  tsrange(check_in::timestamp, check_out::timestamp) WITH &&
) WHERE (room_id IS NULL AND bed_id IS NULL
         AND reservation_status IN ('CONFIRMED', 'MODIFIED'));

-- ② ROOM 단위 예약끼리 겹침 방지
ALTER TABLE reservations ADD CONSTRAINT excl_room_overlap
EXCLUDE USING gist (
  room_id WITH =,
  tsrange(check_in::timestamp, check_out::timestamp) WITH &&
) WHERE (room_id IS NOT NULL AND bed_id IS NULL
         AND reservation_status IN ('CONFIRMED', 'MODIFIED'));

-- ③ BED 단위 예약끼리 겹침 방지
ALTER TABLE reservations ADD CONSTRAINT excl_bed_overlap
EXCLUDE USING gist (
  bed_id WITH =,
  tsrange(check_in::timestamp, check_out::timestamp) WITH &&
) WHERE (bed_id IS NOT NULL
         AND reservation_status IN ('CONFIRMED', 'MODIFIED'));
```

> ⚠️ **DB가 막지 못하는 것**: PROPERTY 예약(독채 통대여)과 그 하위 ROOM/BED 예약 간의 교차 충돌은
> 위 3개 EXCLUDE로 잡히지 않습니다. 이건 **서비스 레이어에서 예약 생성 트랜잭션 시작 시
> "같은 property_id 내 다른 단위의 겹치는 예약이 있는지" 쿼리로 확인 후 커밋**하는 방식으로
> 방어합니다. (doc20의 `COALESCE(room_id,0)` 트릭은 0을 실제 ID와 구분 못 해 폐기)

### 2.7 FINANCIAL_CONFIGS

```sql
CREATE TABLE financial_configs (
  config_id          BIGSERIAL PRIMARY KEY,
  property_id        BIGINT NOT NULL UNIQUE REFERENCES properties(property_id) ON DELETE CASCADE,
  -- v1.4: "properties.base_price가 VAT 포함 금액인가"를 뜻한다.
  --   **표시 전용이며 어떤 계산에도 쓰지 않는다.** 정산에 세금계산서·
  --   부가세·회계 기능을 넣지 않는다는 원칙(CLAUDE.md)에 따라, 이 값은
  --   화면에서 "VAT 포함가"라고 알려주는 데까지만 쓴다.
  vat_included        BOOLEAN NOT NULL DEFAULT true,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

> **[v1.4] 이 테이블에서 빠진 것 4개**
>
> | 컬럼 | 어디로 | 사유 |
> |---|---|---|
> | `fee_type` | **2.19 `CHANNEL_FEE_RATES`** | 아래 |
> | `commission_rate` | **2.19 `CHANNEL_FEE_RATES`** | 아래 |
> | `fee_source` | **2.19 `CHANNEL_FEE_RATES`** | 아래 |
> | `base_nightly_rate` | **제거**(이동 아님) | `PROPERTIES.base_price`가 단가의 원본이다 |
>
> **수수료 3개를 옮긴 이유**: `property_id`가 `UNIQUE`라 이 테이블은
> **숙소당 정확히 한 행**이다. 그런데 `channel_enum`은 3값이고
> `CHANNEL_CONNECTIONS`는 숙소당 채널 3개까지 허용한다. 즉 **채널마다
> 수수료가 다른 현실을 담을 자리가 구조적으로 없었다.** 요율은 "숙소의
> 속성"이 아니라 "숙소×채널의 속성"이다.
>
> **`base_nightly_rate`를 제거한 이유**: `PROPERTIES.base_price`와 뜻이
> 같은데 어느 쪽이 진짜인지 정한 문서가 없었고, 값을 채우거나 읽는 코드도
> 없었다(9/11 전수 확인 — 모델·마이그레이션 선언 외 사용처 0건).
> `POST /properties` 요청 필드에도 `base_price`만 있다. 단가의 원본을
> `PROPERTIES.base_price` 하나로 고정한다(4절 "금액 계산" 참고).
>
> **남은 것은 `vat_included` 하나**다. 테이블을 없애지 않는 이유는
> `GET·PATCH /properties/{id}/financial-config`가 api_contract 5절에 이미
> 있고, 앞으로 숙소 단위 정산 설정이 더 생길 자리이기 때문이다.

### 2.8 MONTHLY_SETTLEMENTS (FINANCIAL_CONFIGS와 직접 관계 없음 — 스냅샷)

```sql
CREATE TABLE monthly_settlements (
  settlement_id             BIGSERIAL PRIMARY KEY,
  property_id               BIGINT NOT NULL REFERENCES properties(property_id) ON DELETE CASCADE,
  target_month              CHAR(7) NOT NULL,   -- 'YYYY-MM'
  total_reservations        INTEGER NOT NULL DEFAULT 0,
  occupied_nights           INTEGER NOT NULL DEFAULT 0,
  occupancy_rate            NUMERIC(5,2),
  gross_revenue             INTEGER NOT NULL DEFAULT 0,
  channel_fee               INTEGER NOT NULL DEFAULT 0,
  net_payout                INTEGER NOT NULL DEFAULT 0,
  applied_commission_rate   NUMERIC(5,4),  -- 계산 당시 수수료율 스냅샷 (설정 변경돼도 과거값 불변)
  created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (property_id, target_month)
);
```

> **[v1.4] `applied_commission_rate`가 뜻하는 것 — 채널이 여럿일 때**
>
> v1.3까지는 요율이 숙소당 하나뿐이라(`FINANCIAL_CONFIGS.commission_rate`)
> 이 컬럼에 무엇을 넣을지 고민할 일이 없었다. v1.4에서 요율이 **채널
> 단위**가 되면서 "그 달에 여러 채널 예약이 섞이면 무엇을 적는가"가
> 생겼다. **컬럼은 바꾸지 않고 뜻만 정한다.**
>
> | 그 달 예약의 채널 | `applied_commission_rate` |
> |---|---|
> | 한 채널뿐 | **그 채널의 요율** |
> | 둘 이상 섞임 | **NULL** |
>
> **섞이면 NULL인 이유**: 대표값을 하나 고르면(가중평균이든 최빈값이든)
> 그 숫자로 역산한 금액이 실제 `channel_fee`와 맞지 않는다. **틀린 숫자를
> 보여주느니 "단일 요율로 말할 수 없음"을 NULL로 표현한다.** 컬럼이
> nullable인 것이 이 표현을 이미 허용한다.
>
> **채널별 내역이 필요하면** 이 컬럼이 아니라
> **`RESERVATIONS.fee_amount` 스냅샷을 채널별로 묶어** 계산한다. 예약마다
> 계산 시점의 요율로 이미 저장돼 있으므로(4절 6번) 집계만 하면 된다.
> `MONTHLY_SETTLEMENTS`는 숙소×월 단위 요약이지 채널별 내역표가 아니다.
>
> ⚠️ **확정 계산식은 10월 정산 구현(체크리스트 5단계, r89~r94)에서 정한다.**
> 위는 이 컬럼이 담을 수 있는 것과 없는 것을 정한 것이고, `gross_revenue`·
> `channel_fee`·`net_payout`을 어떤 쿼리로 채울지는 그때 확정한다.

### 2.9 CLEANING_TASKS

```sql
CREATE TABLE cleaning_tasks (
  task_id            BIGSERIAL PRIMARY KEY,
  reservation_id     BIGINT NOT NULL UNIQUE,   -- 예약당 정확히 1개(1:1).
                                                -- v1.2 재정정(9/3): 체크아웃 시점이
                                                -- 아니라 예약 CONFIRMED 즉시 선제생성
                                                -- (scheduled_at=체크아웃 시각). 전날/당일
                                                -- 자동알림 기능 성립을 위해 필요(state_events.md 참고)
  property_id        BIGINT NOT NULL,
  task_status        task_status_enum NOT NULL DEFAULT 'PENDING',
  cleaner_name       VARCHAR(100),
  amenity_shortage   BOOLEAN NOT NULL DEFAULT false,
  scheduled_at       TIMESTAMPTZ,   -- v1.3: scheduled_date에서 개명. 타입은 그대로.
                                     -- 저장값 = reservations.check_out(DATE)와
                                     --   properties.checkout_time(TIME)을 결합한
                                     --   "실제 체크아웃 시각"(예: 2026-09-12 11:00+09).
                                     --   00:00이 아니며, 청소 착수 가능 시각의 기준점이다.
                                     -- 전날/당일 알림 스케줄러가 이 값에서 역산하므로
                                     --   날짜만으로는 부족하고 시각까지 필요하다.
  -- v1.4: photo_urls(JSONB) 제거 → 2.18 CLEANING_TASK_PHOTOS로 분리
  verified_at        TIMESTAMPTZ,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  FOREIGN KEY (reservation_id, property_id)
    REFERENCES reservations(reservation_id, property_id) ON DELETE CASCADE
);

CREATE INDEX idx_cleaning_tasks_property_status ON cleaning_tasks(property_id, task_status);
```

> **[v1.3] `photo_urls` 운용 규칙**: `POST /cleaning-tasks/{id}/photo`는
> 기존 값을 **교체하지 않고 배열 끝에 append**한다(청소 여러 구역을 나눠
> 찍어 올리는 실제 운영 패턴 반영). 저장 형태는 URL 문자열 배열
> (`["https://.../a.jpg", "https://.../b.jpg"]`). `VERIFIED` 전이 조건은
> "호스트가 사진을 확인하고 승인" — 사진이 0장이어도 호스트가 직접
> 확인했다면 전이 가능하게 두되, UI에서 사진 없음 경고를 표시한다.

> **[v1.4] 위 규칙 중 저장 형태만 바뀐다.** `photo_urls` 컬럼이 사라지고
> **2.18 `CLEANING_TASK_PHOTOS`의 행**으로 옮겨간다. *"교체하지 않고
> append"*라는 **운용 규칙은 그대로**이며, 배열 끝에 원소를 더하는 대신
> **행을 하나 추가**하는 것으로 실현된다(api_contract v1.6 동작 규칙과
> 결과가 같다). `VERIFIED` 전이 조건도 바뀌지 않는다 — "사진 0장"은
> 이제 "이 `task_id`를 가진 행이 0건"이다.

### 2.10 INQUIRIES

```sql
CREATE TABLE inquiries (
  inquiry_id       BIGSERIAL PRIMARY KEY,
  reservation_id   BIGINT,            -- v1.3: NOT NULL 해제. 예약 전 사전문의 지원
  property_id      BIGINT NOT NULL
                     REFERENCES properties(property_id) ON DELETE CASCADE,
                     -- ↑ v1.3 신규: 단독 FK. 아래 복합FK가 스킵될 때의 유일한 방어선
  channel          VARCHAR(30),
  message          TEXT NOT NULL,
  language         VARCHAR(10),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  FOREIGN KEY (reservation_id, property_id)
    REFERENCES reservations(reservation_id, property_id) ON DELETE CASCADE,
  -- v1.4 신규: INQUIRY_RESPONSES가 (inquiry_id, property_id) 복합 FK로
  --   이 조합을 참조하기 위한 후보키. ROOMS/BEDS의 UNIQUE와 같은 목적이며
  --   inquiry_id가 이미 PK라 중복방지 효과는 없다.
  UNIQUE (inquiry_id, property_id)
);

CREATE INDEX idx_inquiries_property ON inquiries(property_id);
CREATE INDEX idx_inquiries_reservation ON inquiries(reservation_id);
```

> **[v1.3] `reservation_id` nullable 전환 — 왜 `property_id` 단독 FK가
> 반드시 함께 필요한가**
>
> PostgreSQL 복합 FK의 기본 매칭 방식은 `MATCH SIMPLE`이다. 이 방식은
> **구성 컬럼 중 하나라도 NULL이면 FK 검사를 통째로 건너뛴다.** 따라서
> `reservation_id`가 NULL인 사전문의 행에서는 위 복합FK가 아예 동작하지
> 않고, 그 결과 `property_id`가 **존재하지도 않는 숙소 ID여도 INSERT가
> 통과**한다. 이는 4절 -1번 "Property 단위 데이터 격리" 원칙에 정면으로
> 반하는 구멍이므로, `property_id`에 단독 FK를 별도로 걸어 어떤 경우에도
> 실재하는 숙소를 가리키도록 보장한다.
>
> - **두 FK는 역할이 다르므로 둘 다 유지한다.** 단독 FK = "이 숙소가
>   실재하는가", 복합 FK = "이 예약이 정말 이 숙소의 예약인가".
> - **애플리케이션 책임**: `reservation_id`가 NULL이 아닌 경우에도
>   `property_id`는 여전히 필수 입력이다(어느 숙소의 RAG를 검색할지
>   결정하는 값이라 생략 불가 — API Contract 7절과 동일 규칙).
> - **`ON DELETE CASCADE` 중복 지정은 정상이다.** 예약이 삭제되면 복합FK
>   경로로, 숙소가 삭제되면 단독FK 경로로 각각 정리된다.

### 2.11 INQUIRY_CLASSIFICATIONS (1:1 — "1문의=Claude 1회 통합호출" 아키텍처와 일치)

```sql
CREATE TABLE inquiry_classifications (
  classification_id   BIGSERIAL PRIMARY KEY,
  inquiry_id           BIGINT NOT NULL UNIQUE REFERENCES inquiries(inquiry_id) ON DELETE CASCADE,
  category             VARCHAR(50),
  risk_level           inquiry_risk_level_enum NOT NULL,
  auto_respondable     BOOLEAN NOT NULL DEFAULT false
);
```

### 2.12 INQUIRY_RESPONSES (1:N + is_latest — doc20 채택)

```sql
CREATE TABLE inquiry_responses (
  response_id      BIGSERIAL PRIMARY KEY,
  inquiry_id       BIGINT NOT NULL,
  -- v1.4 신규: RESPONSE_SOURCES가 "응답과 청크가 같은 숙소인가"를 복합 FK로
  --   검증하려면 응답 쪽에도 property_id가 있어야 한다.
  --   **서버가 INQUIRIES.property_id를 복사해 채운다**(요청에서 받지 않는다).
  property_id      BIGINT NOT NULL,
  response_text    TEXT NOT NULL,
  -- v1.4: sources(JSONB) 제거 → 2.17 RESPONSE_SOURCES로 분리
  language         VARCHAR(10),
  is_latest        BOOLEAN NOT NULL DEFAULT true,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

  -- v1.4: inquiry_id 단독 FK → 복합 FK로 교체.
  --   "이 응답이 정말 이 숙소의 문의에 달린 응답인가"를 DB가 보장한다.
  --   두 컬럼 모두 NOT NULL이라 MATCH SIMPLE 스킵이 일어나지 않는다
  --   (2.10 INQUIRIES와 달리 단독 FK를 따로 둘 필요가 없는 이유).
  FOREIGN KEY (inquiry_id, property_id)
    REFERENCES inquiries(inquiry_id, property_id) ON DELETE CASCADE,

  -- v1.4 신규: RESPONSE_SOURCES 복합 FK 대상 후보키
  UNIQUE (response_id, property_id)
);

-- 문의 하나당 "최신 응답"은 정확히 하나만 존재하도록 부분 유니크 인덱스로 강제
CREATE UNIQUE INDEX uniq_inquiry_latest_response
  ON inquiry_responses(inquiry_id) WHERE is_latest = true;

CREATE INDEX idx_inquiry_responses_inquiry ON inquiry_responses(inquiry_id);
```

> **애플리케이션 규칙**: 재시도/재답변으로 새 응답을 만들 때는 기존 `is_latest=true` 행을
> `false`로 먼저 UPDATE한 뒤 새 행을 INSERT합니다(같은 트랜잭션 내에서 처리).

> **[v1.4] `property_id`는 누가 채우는가**
>
> **서버가 `INQUIRIES.property_id`를 복사해 넣는다.** 요청 본문에서 받지
> 않는다 — 받으면 호출부가 다른 숙소 id를 넣을 수 있고, 그러면 위 복합
> FK가 그 INSERT를 거부해 500으로 새어 나간다. 응답을 만드는 코드는
> AI 처리 경로 한 곳뿐이며 그 시점에 문의 행을 이미 들고 있다.
>
> **정규화 관점에서 중복처럼 보이지만 중복이 아니다.** `property_id`는
> `inquiry_id`에 함수 종속이지만, 이 컬럼은 **"값을 보관하려고"가 아니라
> "복합 FK의 구성 컬럼으로" 존재한다.** `RESERVATIONS`가
> `CLEANING_TASKS`·`INQUIRIES`·`ACTION_ITEMS`에게 같은 방식으로
> `property_id`를 요구하는 것과 같은 형태이며, 이 프로젝트가 v1.3부터
> 일관되게 쓰는 계층 무결성 패턴이다(4절 -1번).

### 2.13 INQUIRY_APPROVALS

```sql
CREATE TABLE inquiry_approvals (
  approval_id    BIGSERIAL PRIMARY KEY,
  response_id    BIGINT NOT NULL REFERENCES inquiry_responses(response_id) ON DELETE CASCADE,
  status         approval_status_enum NOT NULL DEFAULT 'PENDING',
  approved_by    BIGINT REFERENCES hosts(host_id),
  approved_at    TIMESTAMPTZ
);

CREATE INDEX idx_inquiry_approvals_response ON inquiry_approvals(response_id);
```

### 2.14 KNOWLEDGE_CHUNKS (RAG, 정적 지식 콘텐츠 — INQUIRIES 계열과 역할 분리)

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE knowledge_chunks (
  chunk_id          BIGSERIAL PRIMARY KEY,
  property_id       BIGINT NOT NULL REFERENCES properties(property_id) ON DELETE CASCADE,
  document_type     document_type_enum NOT NULL,
  category          VARCHAR(50),
  content           TEXT NOT NULL,
  embedding         VECTOR(384),  -- 사용할 로컬 임베딩 모델 차원수에 맞춰 확정 후 변경
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- v1.4 신규: RESPONSE_SOURCES가 (chunk_id, property_id) 복합 FK로 이 조합을
  --   참조하기 위한 후보키. chunk_id가 이미 PK라 중복방지 효과는 없다.
  UNIQUE (chunk_id, property_id)
);

CREATE INDEX idx_knowledge_chunks_property ON knowledge_chunks(property_id);
-- 초기 구현: 인덱스 없이 정확검색으로 시작
--   SELECT ... WHERE property_id = :pid ORDER BY embedding <=> :query LIMIT 5;
-- 데이터量 증가시 추가:
--   CREATE INDEX ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);
```

### 2.15 ACTION_ITEMS

```sql
CREATE TABLE action_items (
  action_id         BIGSERIAL PRIMARY KEY,
  property_id       BIGINT NOT NULL REFERENCES properties(property_id) ON DELETE CASCADE,
  reservation_id    BIGINT,   -- v1.3: 단독 FK 제거, 아래 복합FK로 대체
  risk_level        action_risk_level_enum NOT NULL,  -- 규칙기반 우선순위. AI/법적 판단 아님 (섹션 8 참고)
  category          VARCHAR(50) NOT NULL,
  title             TEXT NOT NULL,
  content           TEXT,
  status            action_status_enum NOT NULL DEFAULT 'OPEN',
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),

  -- v1.3 신규: CLEANING_TASKS/INQUIRIES와 동일한 계층 무결성 방어.
  --   reservation_id가 NULL이면(예: 서류만료 알림처럼 예약과 무관한 건)
  --   MATCH SIMPLE 규칙에 따라 검사가 스킵되고, property_id는 위 단독 FK가 보장한다.
  FOREIGN KEY (reservation_id, property_id)
    REFERENCES reservations(reservation_id, property_id)
    ON DELETE SET NULL (reservation_id)
);

CREATE INDEX idx_action_items_property_status ON action_items(property_id, status, risk_level);
```

> **[v1.3] 왜 복합 FK로 바꿨는가**: 기존 설계는 `property_id`와
> `reservation_id`가 서로 무관한 단독 FK였다. 그래서 **"강남 숙소의
> 액션아이템인데 참조하는 예약은 홍대 호스텔 예약"** 같은 행이 DB
> 레벨에서 아무 저항 없이 만들어질 수 있었다. 이는 4절 -1번 데이터 격리
> 원칙에 어긋나고, Action Center 화면이 다른 숙소 예약을 잘못 띄우는
> 버그로 직결된다. `RESERVATIONS`에 이미 `UNIQUE(reservation_id,
> property_id)`가 있으므로 추가 제약 없이 복합FK 참조가 가능하다.
>
> ⚠️ **`ON DELETE SET NULL (reservation_id)`는 PostgreSQL 15+ 문법이다**
> (컬럼 목록을 지정하는 SET NULL). 컬럼 목록 없이 그냥 `SET NULL`을 쓰면
> `property_id`까지 NULL로 만들려다 NOT NULL 위반으로 **삭제 자체가
> 실패**한다. 로컬 Docker Postgres 이미지를 반드시 15 이상으로 고정할 것
> (dev/prod parity 원칙 — Supabase는 15+). 만약 14 이하를 쓰게 되면
> 대안은 `ON DELETE CASCADE`이며, 이 경우 예약이 삭제될 때 해당
> 액션아이템 이력도 함께 사라진다는 점을 감수해야 한다.

> **중복 생성 방지**: DB UNIQUE 제약 대신 애플리케이션에서 "동일 `reservation_id` +
> `category` + `status='OPEN'` 조합이 이미 있으면 새로 만들지 않고 기존 항목을 재사용"하는
> idempotency 로직으로 처리합니다 (category 정의가 아직 세밀하지 않아 DB 제약으로 못박기엔 이름).

### 2.16 CHECKLIST_ITEMS

```sql
CREATE TABLE checklist_items (
  checklist_item_id     BIGSERIAL PRIMARY KEY,
  property_id           BIGINT NOT NULL REFERENCES properties(property_id) ON DELETE CASCADE,
  accommodation_type    accommodation_type_enum NOT NULL,  -- "파생 템플릿 유형" (섹션 8 참고)
  item_name             VARCHAR(150) NOT NULL,
  status                VARCHAR(20) NOT NULL DEFAULT 'INCOMPLETE',
  renewal_trigger_type  renewal_trigger_type_enum NOT NULL DEFAULT 'NONE',
  expiry_date           DATE,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (
    (renewal_trigger_type = 'NONE' AND expiry_date IS NULL) OR
    (renewal_trigger_type = 'EXPIRATION_BASED' AND expiry_date IS NOT NULL) OR
    (renewal_trigger_type = 'EVENT_BASED')
  )
);

CREATE INDEX idx_checklist_items_property ON checklist_items(property_id);
```

### 2.17 RESPONSE_SOURCES [v1.4 신규] — AI 응답 ↔ 인용 청크 (N:N)

```sql
CREATE TABLE response_sources (
  response_id   BIGINT NOT NULL,
  chunk_id      BIGINT NOT NULL,
  property_id   BIGINT NOT NULL,
  rank          SMALLINT NOT NULL,   -- RAG 검색 결과 순위(1이 가장 유사)
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),

  -- 이 테이블만 대리키를 쓰지 않는다. 아래 설명 참고.
  PRIMARY KEY (response_id, chunk_id),

  FOREIGN KEY (response_id, property_id)
    REFERENCES inquiry_responses(response_id, property_id) ON DELETE CASCADE,
  FOREIGN KEY (chunk_id, property_id)
    REFERENCES knowledge_chunks(chunk_id, property_id) ON DELETE CASCADE
);

CREATE INDEX idx_response_sources_chunk ON response_sources(chunk_id);
```

> **무엇을 대체하는가**: v1.3까지 `INQUIRY_RESPONSES.sources`(JSONB)에
> `["chunk_17"]` 형태로 담던 것이다. 그 방식은 **FK가 걸리지 않아** 청크가
> 삭제돼도 `"chunk_17"`이 그대로 남아 끊어진 참조가 됐고, DB가 아무것도
> 검증하지 못했다.

> **이 테이블만 대리키(`BIGSERIAL`)를 쓰지 않는 이유**
>
> 나머지 18개 테이블은 전부 단일 대리키를 PK로 쓴다. 여기만 다른 이유는
> 둘이다.
>
> 1. **다른 테이블이 이 행을 참조하지 않는다.** 대리키가 필요한 가장 큰
>    이유는 "남이 이 행을 가리킬 짧은 키"인데, 이 테이블을 FK로 참조하는
>    테이블이 하나도 없고 앞으로도 없다(순수 연결 테이블).
> 2. **`(응답, 청크)` 쌍 자체가 식별자다.** 같은 응답이 같은 청크를 두 번
>    인용하는 일은 있을 수 없으므로, 복합 PK가 그 규칙을 **추가 제약 없이**
>    강제한다. 대리키를 두면 `UNIQUE(response_id, chunk_id)`를 따로 걸어야
>    하고 컬럼만 하나 늘어난다.
>
> `rank`를 PK에 넣지 않는다 — 순위는 속성이지 식별자가 아니다. 같은 쌍이
> 순위만 다르게 두 번 들어가면 안 된다.

> **두 FK가 모두 `ON DELETE CASCADE`인 이유**
>
> `response_id` 쪽은 자명하다 — 응답이 지워지면 그 응답의 인용 목록도
> 지워져야 한다.
>
> `chunk_id` 쪽이 판단이 필요한 자리였다. **`RESTRICT`를 쓸 수 없다.**
> api_contract 8절에 지식 청크 **수정 API가 없고** `POST`/`DELETE`만 있어,
> 호스트가 하우스룰을 고치는 유일한 방법이 **"지우고 다시 등록"**이다.
> `RESTRICT`면 그 청크를 인용한 응답이 하나라도 있는 순간 **호스트가
> 하우스룰을 영원히 고칠 수 없게 된다.**
>
> **CASCADE의 대가를 명시한다**: 청크를 지우면 그 청크를 가리키던 인용
> 기록이 함께 사라진다. 다만 **`INQUIRY_RESPONSES.response_text`는 그대로
> 남는다** — 게스트에게 실제로 나간 답변 원문은 보존되고, "무엇을 근거로
> 그렇게 답했는지"만 사라진다. 화면에서는 근거 0건으로 보인다.

> **응답과 청크가 같은 숙소임을 두 복합 FK가 함께 보장한다.** 한 행의
> `property_id`는 하나뿐이고, 그 값이 응답 쪽 FK와 청크 쪽 FK를 **동시에**
> 만족해야 한다. 따라서 "강남 숙소 문의에 대한 답변이 홍대 호스텔의
> 지식청크를 인용"하는 행은 DB가 거부한다. 이것이 v1.3에서 `ACTION_ITEMS`를
> 복합 FK로 바꾼 것과 같은 방어다(4절 -1번).

> **행을 쓰는 곳은 한 곳뿐이다** — RAG 검색 결과를 받아 응답을 저장하는
> 서버 코드(`backend/app/services/ai/`)다. 호스트가 직접 추가·수정하는
> 화면이 없고 그럴 이유도 없다. `rank`는 검색이 돌려준 순서를 그대로 넣는다.

### 2.18 CLEANING_TASK_PHOTOS [v1.4 신규] — 청소 완료사진

```sql
CREATE TABLE cleaning_task_photos (
  photo_id      BIGSERIAL PRIMARY KEY,
  task_id       BIGINT NOT NULL REFERENCES cleaning_tasks(task_id) ON DELETE CASCADE,
  photo_url     TEXT NOT NULL,
  sort_order    INTEGER NOT NULL DEFAULT 0,   -- 화면 표시 순서
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_cleaning_task_photos_task ON cleaning_task_photos(task_id, sort_order);
```

> **무엇을 대체하는가**: v1.3의 `CLEANING_TASKS.photo_urls`(JSONB 배열)다.
> 2.17과 같은 이유로 전용 테이블로 푼다.

> **기존 append 운용 규칙은 그대로다.** api_contract v1.6은
> `POST /cleaning-tasks/{task_id}/photo`가 *"기존 배열을 교체하지 않고 끝에
> append"*한다고 정했다. 이제 **행을 하나 INSERT**하는 것으로 같은 결과가
> 된다. 응답은 그 task의 전체 목록을 `sort_order` 순으로 돌려준다.
>
> 덤으로 얻는 것: **사진 한 장만 지우는 것이 `DELETE ... WHERE photo_id=`
> 한 줄이 된다.** JSONB 시절에는 "배열 전체를 덮어쓰기"로만 가능했다
> (api_contract v1.6이 그렇게 적고 있다).

> **⚠️ 파일 자체를 어디에 저장할지는 아직 정하지 않았다.** 이 테이블은
> **URL 문자열만** 보관한다. 9/11 전수 확인 결과 db_spec·api_contract·
> ui_design 어디에도 저장처를 정한 문장이 없다.
>
> **Render 무료 플랜의 디스크는 후보가 아니다** — 인스턴스가 재시작·슬립
> 복귀할 때마다 초기화되므로 업로드한 사진이 사라진다. 15분 무요청 슬립이
> 잦은 환경이라 실제로 발생한다.
>
> 결정 시점: 청소 화면 구현(체크리스트 4단계) 전. 그때까지 이 컬럼은
> 시드 데이터의 정적 URL을 담는다.

### 2.19 CHANNEL_FEE_RATES [v1.4 신규] — 채널별 수수료율

```sql
CREATE TABLE channel_fee_rates (
  channel_fee_rate_id  BIGSERIAL PRIMARY KEY,
  property_id          BIGINT NOT NULL REFERENCES properties(property_id) ON DELETE CASCADE,
  channel              channel_enum NOT NULL,
  fee_type             fee_type_enum NOT NULL DEFAULT 'SINGLE_FEE',
  commission_rate      NUMERIC(5,4) NOT NULL DEFAULT 0.1550,  -- 2026.5.25 한국 단일수수료 기준
  fee_source           VARCHAR(50) NOT NULL DEFAULT 'system_default_2026',
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),

  UNIQUE (property_id, channel),
  -- 요율은 비율이다. 15.5%를 15.5로 잘못 넣으면 수수료가 매출의 15.5배가 된다.
  CHECK (commission_rate >= 0 AND commission_rate <= 1)
);

CREATE INDEX idx_channel_fee_rates_property ON channel_fee_rates(property_id);
```

> **무엇을 대체하는가**: `FINANCIAL_CONFIGS`의 `fee_type`·
> `commission_rate`·`fee_source` 3개다. 그 테이블은 `property_id`가
> `UNIQUE`라 **숙소당 요율 1개**였는데 채널은 3개까지 허용된다.

> **이름이 `channel_fee`가 아닌 이유**
>
> `MONTHLY_SETTLEMENTS.channel_fee`가 **이미 있고 그것은 금액(INTEGER)**
> 이다. 같은 이름이 한쪽은 비율, 한쪽은 금액을 뜻하면 쿼리를 읽을 때마다
> 어느 쪽인지 확인해야 한다. `_rates`를 붙여 **비율임을 이름에 박는다.**
> `net_amount`(예약)와 `net_payout`(월정산)을 구분한 것과 같은 취지다.

> **`CHANNEL_CONNECTIONS`를 FK로 참조하지 않는 이유**
>
> 연결(`CHANNEL_CONNECTIONS`)은 **지웠다 다시 만드는 자원**이다.
> api_contract 3절에 `PATCH`가 없어 iCal URL을 바꾸려면 `DELETE` 후 다시
> `POST`해야 한다. 요율을 연결에 매달면 **URL을 한 번 바꿀 때마다 호스트가
> 입력한 수수료율이 함께 사라진다.**
>
> 요율은 "이 숙소가 이 채널과 맺은 조건"이지 "지금 연결이 살아 있는가"와
> 무관하다. 그래서 `(property_id, channel)`에 직접 건다. 연결이 없는
> 채널의 요율 행이 남아 있는 것은 **정상**이며, 다시 연결하면 그 값이
> 그대로 쓰인다.

> **`fee_source`의 뜻**: 이 요율을 어디서 얻었는가. 기본값
> `'system_default_2026'`은 **"호스트가 확인하지 않은 시스템 기본값"**을
> 뜻한다. 호스트가 화면에서 요율을 고치면 다른 값으로 바뀌며, 그때부터
> "호스트가 확인한 값"이 된다. 화면은 이 둘을 구분해 표시한다 — 추정치를
> 확정치처럼 보여주지 않기 위해서다.

---

## 3. Action Center 쿼리 예시 (실현 가능성 확인 완료)

```sql
-- 예: "체크인 2시간 전인데 청소가 완료되지 않은 긴급 건" 조회
-- v1.1: check_in(DATE)만으로는 "몇 시"를 알 수 없어 property의 checkin_time과
--   합산. 청소 "완료"는 COMPLETED 또는 VERIFIED 둘 다 정상 종료로 취급
--   (VERIFIED는 COMPLETED보다 더 진행된 상태이므로 COMPLETED만 완료로
--   보면 VERIFIED가 잘못 긴급건으로 잡히는 버그가 생김)
SELECT r.reservation_id, r.property_id, r.guest_name, r.check_in, c.task_status
FROM reservations r
JOIN properties p ON p.property_id = r.property_id
JOIN cleaning_tasks c ON r.reservation_id = c.reservation_id
WHERE r.property_id = :target_property_id
  AND r.reservation_status = 'CONFIRMED'
  AND (r.check_in + p.checkin_time) BETWEEN NOW() AND NOW() + INTERVAL '2 hours'
  AND c.task_status NOT IN ('COMPLETED', 'VERIFIED');
```

조인 1회로 충분하며, 위 인덱스(`idx_reservations_dates`, `idx_cleaning_tasks_property_status`)로
성능 문제 없이 동작합니다.

---

## 4. 문서화가 필요한 정책 (코드 주석/README에 반드시 남길 것)

-1. **[v1.2 추가] Property 단위 데이터 격리 원칙 (전체 테이블 공통 최상위 원칙)**:
   이 프로젝트의 핵심 전제는 **"한 호스트가 서로 다른 유형의 숙소를 여러 개
   운영"**하는 것이므로, 숙소(Property)를 넘나드는 데이터 오염이 곧 서비스
   신뢰성 붕괴로 직결된다. 따라서 게스트에게 노출되거나 운영 판단에 쓰이는
   모든 테이블은 **직접 또는 간접적으로 반드시 `property_id`를 갖고, 모든
   조회 쿼리는 `WHERE property_id = :current_property_id`를 빠짐없이
   포함**해야 한다.

   | 테이블 | property_id 확보 방식 |
   |---|---|
   | RESERVATIONS | 직접 FK |
   | CHANNEL_CONNECTIONS | 직접 FK + **복합FK(v1.4 신규)** — `(room_id,
     property_id)`로 다른 숙소의 객실을 가리키는 연결을 DB가 차단(2.5절 참고).
     `room_id`가 NULL(독채)이면 복합FK는 스킵되고 직접 FK가 보장한다 |
   | FINANCIAL_CONFIGS / MONTHLY_SETTLEMENTS | 직접 FK |
   | CHANNEL_FEE_RATES **[v1.4 신규]** | 직접 FK(2.19절) |
   | CLEANING_TASKS | 복합FK로 RESERVATIONS 경유 확보(2.9절) |
   | CLEANING_TASK_PHOTOS **[v1.4 신규]** | `task_id`로 **CLEANING_TASKS 경유**
     확보(2.18절) — 자체 `property_id` 컬럼이 없다. 조회 시
     `JOIN cleaning_tasks`가 필요하다 |
   | INQUIRIES | **직접 FK(v1.3 신규) + 복합FK 이중 방어** — `reservation_id`가
     nullable이라 복합FK만으로는 사전문의 행에서 검사가 스킵됨(2.10절 참고) |
   | INQUIRY_RESPONSES **[v1.4 변경]** | **직접 컬럼 + 복합FK** —
     `(inquiry_id, property_id)`로 INQUIRIES를 참조한다(2.12절). 두 컬럼 모두
     NOT NULL이라 MATCH SIMPLE 스킵이 없어 단독 FK를 따로 두지 않는다.
     값은 서버가 INQUIRIES에서 복사해 채운다 |
   | KNOWLEDGE_CHUNKS | 직접 FK — **RAG 검색 시 이 필터가 없으면
     "숙소A 문의에 숙소B 하우스룰이 섞여 답변되는" 교차오답이라는
     치명적 버그로 이어짐(가장 위험한 누락 지점)** |
   | RESPONSE_SOURCES **[v1.4 신규]** | **직접 컬럼 + 복합FK 2개** — 한 행의
     `property_id`가 응답 쪽(`inquiry_responses`)과 청크 쪽
     (`knowledge_chunks`) FK를 **동시에** 만족해야 하므로, 응답과 청크가
     같은 숙소임을 DB가 보장한다(2.17절) |
   | ACTION_ITEMS | 직접 FK + **복합FK(v1.3 신규)** — 다른 숙소의 예약을
     참조하는 액션아이템을 DB가 차단(2.15절 참고) |
   | CHECKLIST_ITEMS | 직접 FK |
   | ROOMS / BEDS | 계층 FK로 PROPERTIES까지 역추적 가능 |

   > **[v1.4] 이 표에 없는 테이블 2개**: `INQUIRY_CLASSIFICATIONS`(1:1,
   > `inquiry_id`만)와 `INQUIRY_APPROVALS`(`response_id`만)는 `property_id`를
   > 갖지 않고 상위 테이블을 JOIN으로 역추적한다. v1.4에서 바뀐 것이 없어
   > 이번에 추가하지 않았다.

   **애플리케이션 구현 시 반드시 지킬 것**: 서비스 레이어의 모든 조회
   함수는 `property_id` 파라미터를 필수 인자로 받고, 이를 누락한 쿼리가
   실수로 만들어지지 않도록 리뷰 시 이 항목을 체크리스트로 확인한다.
   (스마트락 관련 데이터도 이 원칙을 그대로 따르되, 현재 스마트락은
   100% Mock이라 실제 하드웨어 데이터는 없음 — 향후 실연동 시에도
   동일 원칙 적용)

0. **[v1.1 추가] DB가 보장하는 것과 애플리케이션이 보장하는 것을 명확히 구분**:
   - DB 보장: room이 실제 해당 property 소속인가 / bed가 실제 해당 room
     소속인가 / channel이 실제 해당 property 소속인가 / room·bed 조합
     자체의 내부 형태가 유효한가 / 예약기간 중복 여부(EXCLUDE)
   - 애플리케이션 보장: **Property.bookable_unit_type과 실제 예약의
     room/bed 사용형태가 일치하는가**(PostgreSQL CHECK는 테이블을 넘나들며
     검증할 수 없어 DB가 대신할 수 없음) — 예약 생성 서비스 레이어에서
     반드시 검증 로직 구현
1. **`ACTION_ITEMS.risk_level`은 법적·안전 위험 판단이 아니라 운영 처리 우선순위**입니다.
   `RED_NOW`=체크인 임박+청소 미완료 등 시간·상태 기준 규칙일 뿐, AI가 게스트 위험도를
   판단하는 것이 아닙니다.
2. **`CHECKLIST_ITEMS.accommodation_type`**은 "이 항목이 파생된 템플릿 유형"을 의미하며,
   `PROPERTIES.accommodation_type`이 나중에 바뀌어도 기존 체크리스트 항목은 자동 갱신되지
   않습니다(의도된 동작).
3. **`MONTHLY_SETTLEMENTS`는 스냅샷**입니다. **[v1.4 정정]**
   `CHANNEL_FEE_RATES`의 수수료율이 이후 바뀌어도 과거 정산 결과
   (`applied_commission_rate`)는 변하지 않습니다.
   (v1.3까지는 요율이 `FINANCIAL_CONFIGS.commission_rate`에 있었고 이
   문장도 그 이름을 가리켰습니다. 2.19절로 옮겨지면서 참조만 갱신했으며
   **스냅샷 원칙 자체는 그대로**입니다.)
4. **PROPERTY↔ROOM/BED 교차 예약 충돌은 DB가 아니라 애플리케이션 트랜잭션에서 방어**합니다
   (섹션 2.6.1 참고).

5. **[v1.4] 수수료율 행은 채널을 연결할 때 만든다.**
   채널 연결을 생성하는 **같은 트랜잭션**에서 `(property_id, channel)`
   요율 행이 없으면 만들고 있으면 그대로 둔다.

   ```sql
   INSERT INTO channel_fee_rates (property_id, channel)
   VALUES (:property_id, :channel)
   ON CONFLICT (property_id, channel) DO NOTHING;
   ```

   - **`DO NOTHING`이 핵심이다.** 호스트가 이미 요율을 고쳐 뒀는데
     연결을 지웠다 다시 만들었다고 해서 **기본값으로 되돌려서는 안 된다.**
   - **연결을 삭제해도 요율 행은 남긴다.** 2.19절 참고 — 요율은 연결의
     수명과 무관하다.
   - `fee_source='system_default_2026'`은 **"호스트 미확인"**을 뜻한다.
     호스트가 수정하면 다른 값으로 바뀌며, 화면은 둘을 구분해 표시한다.

6. **[v1.4] 예약 금액 계산 — 계산은 서비스 함수 한 곳에서만 한다.**
   라우터·배치·동기화가 각자 계산하면 규칙이 갈라진다. 아래 셋을 한
   함수가 계산해 저장한다.

   | 값 | 계산 | 시점 |
   |---|---|---|
   | `gross_amount` | `PROPERTIES.base_price × 박수` | 예약 생성·iCal 동기화 시점 |
   | `fee_amount` | `gross_amount × CHANNEL_FEE_RATES.commission_rate` | 〃 (**스냅샷**) |
   | `net_amount` | 생성 컬럼 — DB가 계산 | 자동 |

   - **`base_price`는 "판매단위 1개의 1박 요금"이다.**
     `bookable_unit_type`이 `PROPERTY`면 독채 1박, `ROOM`이면 객실 1개
     1박, `BED`면 침대 1개 1박을 뜻한다. 박수는 `check_out - check_in`이다.
   - **`base_price`가 0이면 "미설정"으로 본다.** `gross_amount`와
     `fee_amount`를 **둘 다 NULL**로 두고, 생성 컬럼인 `net_amount`도
     자동으로 NULL이 된다. 0원 예약과 미설정을 구분하기 위함이다
     (`base_price`의 DB 기본값이 0이라 숙소 등록 직후가 이 상태다).
   - **`fee_amount`는 스냅샷이다.** 계산 시점의 요율로 한 번 저장하고,
     이후 `CHANNEL_FEE_RATES.commission_rate`가 바뀌어도 **소급하지
     않는다.** `MONTHLY_SETTLEMENTS.applied_commission_rate`가 월 단위로
     같은 일을 하는 것과 같은 원칙이다(위 3번).
   - **VAT는 계산에 넣지 않는다.** `FINANCIAL_CONFIGS.vat_included`는
     표시 전용이다. CLAUDE.md가 *"정산 기능에 세금계산서/부가세/회계
     기능을 추가하지 않는다"*고 정한 범위를 지킨다.
   - 계산 결과의 `financial_status`는 **`'ESTIMATED'`**다(컬럼 기본값).
     호스트가 일괄확인하면 `'CONFIRMED'`, 개별 보정하면
     `'MANUALLY_ADJUSTED'`로 간다.

7. **[v1.4] 이 설계가 표현하지 못하는 것 (설명문서에 옮길 것)**

   제출 설명문서에 **한계로 명시**한다. 발표에서 "왜 안 되는가"를 묻는
   질문에 이 목록으로 답한다.

   1. **같은 숙소의 객실·침대 가격이 모두 같다고 가정한다.**
      단가가 `PROPERTIES.base_price` 하나뿐이라 "101호 5만원, 201호
      7만원"을 표현할 수 없다. `ROOMS`에 가격 컬럼이 없다.
   2. **공백일 가격 조정이 바꾼 가격은 추정에 반영되지 않는다.**
      6절 배치가 만드는 조정가는 `ACTION_ITEMS` 카드로만 표현되고
      `base_price`를 바꾸지 않는다(CLAUDE.md: 동적 가격조정에 전용
      테이블을 만들지 않는다). 따라서 추정 금액은 항상 조정 전 기준이다.
   3. **호스트가 월말에 수수료를 내는 정산 방향을 표현할 수 없다.**
      금액 컬럼이 전부 `INTEGER`이고 부호를 쓰지 않는 전제로 설계됐다.
      부킹닷컴처럼 후불 청구 방식이면 정산이 *"받을 돈"*이 아니라
      **"낼 돈"**이 되는데 그 방향을 담을 자리가 없다.
   4. **예약이 있는 채널은 삭제가 막히고, 수정 API가 없어 iCal URL을
      바꿀 수 없다.** `RESERVATIONS.channel_connection_id`가 NOT NULL이라
      DB가 삭제를 거부하고(`CHANNEL_HAS_RESERVATIONS`), api_contract 3절에
      `PATCH`가 없어 URL 교체는 `DELETE` 후 재등록뿐이다. 즉 **한 번
      예약이 들어온 채널은 URL을 바꿀 방법이 없다.**

---

## 5. 구현 순서 (9/1부터)

> **ERD(논리적/물리적/RESERVATIONS 확대본 3종)는 `docs/erd.md` 참고.**
> DB 구조를 변경할 때는 이 문서(명세서)를 먼저 고치고, 그 다음 `docs/erd.md`를
> 반드시 같은 날 동기화할 것 (9/2에 이 동기화를 누락했던 사고 재발 방지).

```
0. PostgreSQL 버전 확인 — 반드시 15 이상 (v1.3: ACTION_ITEMS의
   `ON DELETE SET NULL (컬럼목록)` 문법이 15+ 전용. 로컬 Docker 이미지와
   Supabase 버전을 같은 메이저로 맞출 것)
1. PostgreSQL extension 활성화 (btree_gist, vector)
2. ENUM 타입 생성 (섹션 1)
3. Alembic 초기 마이그레이션 작성 → 테이블 생성 순서:
   hosts → properties → rooms → beds → channel_connections
   → reservations (+ EXCLUDE 3종) → financial_configs → monthly_settlements
   → cleaning_tasks → inquiries → inquiry_classifications
   → inquiry_responses → inquiry_approvals → knowledge_chunks
   → action_items → checklist_items
4. SQLAlchemy 모델을 DDL과 1:1로 작성
5. Seed 데이터로 계층 FK/EXCLUDE 제약이 실제로 걸리는지 테스트
   (예: 같은 room에 겹치는 날짜 예약 INSERT 시도 → 에러 발생 확인)
6. Reservation 무결성 테스트(회귀 테스트 케이스로 등록)
```

> **⚠️ 위 목록은 9/1 초기 스키마 생성 순서다(v1.3, 16개 테이블).**
> 이미 `alembic upgrade head`로 적용돼 있으므로 **이력으로 그대로 둔다.**

#### [v1.4] 마이그레이션 순서 — 기존 스키마 위 revision 5개

v1.4는 초기 생성이 아니라 **이미 존재하는 16개 테이블 위에 얹는
revision**이다. 한 revision에 다 넣지 않고 **성격별로 5개**로 나눈다 —
하나가 실패했을 때 어디까지 적용됐는지가 분명해야 하고, downgrade도
덩어리 단위로 되돌릴 수 있어야 한다.

```
① response_sources 관련   (inquiries · inquiry_responses · knowledge_chunks 변경 포함)
② cleaning_task_photos
③ channel_connections.room_id
④ reservations.net_amount 생성 컬럼
⑤ channel_fee_rates + financial_configs 컬럼 제거
```

**revision ① 안의 순서 — 이것만 순서가 강제된다**

```
1) inquiries          UNIQUE (inquiry_id, property_id) 추가
2) knowledge_chunks   UNIQUE (chunk_id, property_id) 추가
3) inquiry_responses  property_id 컬럼 추가
                      → inquiry_id 단독 FK를 (inquiry_id, property_id) 복합 FK로 교체
                      → UNIQUE (response_id, property_id) 추가
4) response_sources   테이블 생성 (복합 FK 2개)
5) inquiry_responses  sources(JSONB) 컬럼 제거
```

> **복합 FK는 참조 대상에 그 컬럼 조합의 UNIQUE(또는 PK)가 먼저 있어야
> 걸린다.** 1)·2)가 3)·4)보다 앞서는 이유이며, 순서를 바꾸면
> `there is no unique constraint matching given keys` 에러로 마이그레이션이
> 멈춘다.
>
> 3)의 `property_id`는 `NOT NULL`인데 기존 행이 있으면 채울 값이 필요하다.
> 현재 `inquiry_responses`는 **0건**(9/11 실측)이라 `NOT NULL`로 바로
> 추가할 수 있다. 행이 있는 상태에서 적용하게 되면 nullable로 추가 →
> `UPDATE ... FROM inquiries` → `SET NOT NULL` 3단계로 나눠야 한다.
>
> 5)를 맨 뒤에 두는 이유: `sources`를 먼저 지우면 마이그레이션이 중간에
> 실패했을 때 **옮길 원본이 사라진 채로 남는다.** 새 테이블이 만들어진
> 뒤에 지운다(지금은 데이터가 0건이라 실제 이관은 없지만, 순서 자체를
> 안전한 쪽으로 고정해 둔다).

**②~⑤는 서로 의존하지 않는다.** 각각 다른 테이블을 건드리므로 순서를
바꿔도 되고, 하나가 실패해도 나머지가 영향받지 않는다. 다만 **⑤를 마지막에
둔다** — `financial_configs`에서 컬럼 4개를 제거하는 작업이라 **되돌리기가
가장 번거롭다.** downgrade에서 컬럼을 되살리려면 타입·기본값·NOT NULL을
전부 다시 적어야 하고, 그 사이 들어온 데이터는 복구되지 않는다. 앞의
네 개가 전부 성공한 것을 확인한 뒤에 실행한다.

### 5-1. P0 항목 검증 시나리오 (9/1 설계확인 과정에서 확정, 9/5 실행용)

> 8/31~9/1 설계 재확인 과정에서 나온 검증 쿼리를 여기 모아둔다. 9/5
> Docker Postgres 실행 후 그대로 복사해서 실행하면 된다.

**① Reservation CHECK 제약 검증 (간극항목1)**

```sql
-- 실패해야 정상 (제약이 제대로 걸렸다는 뜻) — bed만 있고 room은 NULL인 잘못된 조합
INSERT INTO reservations (property_id, room_id, bed_id, channel_connection_id, check_in, check_out)
VALUES (1, NULL, 5, 1, '2026-09-10', '2026-09-12');
-- 예상 결과: ERROR: new row violates check constraint

-- 성공해야 정상 (PROPERTY 단위, room/bed 둘다 NULL)
INSERT INTO reservations (property_id, room_id, bed_id, channel_connection_id, check_in, check_out)
VALUES (1, NULL, NULL, 1, '2026-09-10', '2026-09-12');
```

**② INQUIRY_RESPONSES is_latest 검증 (간극항목7)**

```sql
-- 1) 첫 응답 생성
INSERT INTO inquiry_responses (inquiry_id, response_text, is_latest)
VALUES (1, '첫번째 응답', true);

-- 2) 재시도/재생성: 반드시 UPDATE 먼저, 그 다음 INSERT (순서 중요)
UPDATE inquiry_responses SET is_latest=false WHERE inquiry_id=1 AND is_latest=true;
INSERT INTO inquiry_responses (inquiry_id, response_text, is_latest)
VALUES (1, '두번째 응답(재생성)', true);

-- 3) 확인: 최신응답이 정확히 1개인지
SELECT COUNT(*) FROM inquiry_responses WHERE inquiry_id = 1 AND is_latest = true;
-- 예상 결과: 1

-- 4) 이력이 삭제 안 되고 남아있는지 확인
SELECT COUNT(*) FROM inquiry_responses WHERE inquiry_id = 1;
-- 예상 결과: 2

-- 5) 실수 재현(UPDATE 생략하고 바로 INSERT) — 에러 나야 정상, 안전장치 확인용
INSERT INTO inquiry_responses (inquiry_id, response_text, is_latest)
VALUES (1, '실수로 넣은 응답', true);
-- 예상 결과: ERROR: duplicate key value violates unique constraint "uniq_inquiry_latest_response"
```

**③ MONTHLY_SETTLEMENTS 스냅샷 검증 (간극항목9)**

```sql
-- 1) 9월 정산 계산 (당시 수수료율 0.155로 스냅샷 저장)
INSERT INTO monthly_settlements (property_id, target_month, gross_revenue, applied_commission_rate)
VALUES (1, '2026-09', 1000000, 0.155);

-- 2) 이후 수수료율 변경(정책 변경 시뮬레이션)
UPDATE financial_configs SET commission_rate = 0.16 WHERE property_id = 1;

-- 3) 확인: 9월 정산기록이 여전히 0.155인지(변경 전 값 유지)
SELECT applied_commission_rate FROM monthly_settlements
WHERE property_id = 1 AND target_month = '2026-09';
-- 예상 결과: 0.155 (0.16이 나오면 스냅샷이 깨진 것 — 설계 오류)
```

> **⚠️ [v1.4] 위 SQL의 2)단계는 더 이상 실행되지 않는다.**
>
> `commission_rate`가 `FINANCIAL_CONFIGS`에서 `CHANNEL_FEE_RATES`로
> 옮겨졌다(2.7·2.19절). 위 원문은 **v1.3 시점의 기록으로 그대로 둔다.**
> v1.4 이후 같은 원칙을 검증할 때는 아래를 쓴다 — **검증하려는 것은
> 동일하다**: 요율이 바뀌어도 과거 정산 스냅샷이 변하지 않는가.
>
> ```sql
> -- 1) 9월 정산 계산 (당시 수수료율 0.155로 스냅샷 저장) — 원문과 같다
> INSERT INTO monthly_settlements (property_id, target_month, gross_revenue, applied_commission_rate)
> VALUES (1, '2026-09', 1000000, 0.155);
>
> -- 2) [v1.4] 이후 수수료율 변경 — 이제 (property_id, channel) 단위다
> UPDATE channel_fee_rates SET commission_rate = 0.16
> WHERE property_id = 1 AND channel = 'AIRBNB';
>
> -- 3) 확인: 9월 정산기록이 여전히 0.155인지(변경 전 값 유지)
> SELECT applied_commission_rate FROM monthly_settlements
> WHERE property_id = 1 AND target_month = '2026-09';
> -- 예상 결과: 0.155 (0.16이 나오면 스냅샷이 깨진 것 — 설계 오류)
> ```
>
> **2)단계가 `WHERE`에 `channel`을 요구하는 것이 v1.4의 전부**다. 요율이
> 숙소당 1개에서 숙소×채널당 1개가 됐기 때문이며, 1)·3)단계는 바뀌지 않는다.

**④ [v1.3 신규] INQUIRIES 사전문의 + property_id 단독FK 검증**

```sql
-- 성공해야 정상 (예약 전 사전문의 — reservation_id NULL)
INSERT INTO inquiries (reservation_id, property_id, message)
VALUES (NULL, 1, '반려동물 동반 가능한가요?');

-- 실패해야 정상 (존재하지 않는 숙소 ID — 단독FK가 잡아야 함)
INSERT INTO inquiries (reservation_id, property_id, message)
VALUES (NULL, 99999, '없는 숙소로 들어온 문의');
-- 예상 결과: ERROR: violates foreign key constraint (property_id)
--   ※ 이 INSERT가 통과하면 단독FK를 빠뜨린 것 — 복합FK는 reservation_id가
--     NULL이라 검사를 스킵하므로 절대 잡아주지 못한다.
```

**⑤ [v1.3 신규] ACTION_ITEMS 교차숙소 참조 차단 검증**

```sql
-- 전제: reservation 501은 property 1 소속
-- 실패해야 정상 (property 2의 액션아이템이 property 1의 예약을 참조)
INSERT INTO action_items (property_id, reservation_id, risk_level, category, title)
VALUES (2, 501, 'RED_NOW', 'CLEANING_DELAY', '교차 참조 테스트');
-- 예상 결과: ERROR: violates foreign key constraint (복합FK)

-- 성공해야 정상 (예약과 무관한 서류만료 알림 — reservation_id NULL)
INSERT INTO action_items (property_id, reservation_id, risk_level, category, title)
VALUES (2, NULL, 'YELLOW_TODAY', 'COMPLIANCE_EXPIRY', '영업신고증 만료 D-3');
```

---

## 6. 동적 가격 조정 로직 (공백일 미세조정 + 성수기 방치감지) [v1.2 신규]

> 9/2 크로스체크로 추가 확정. "3박 이상만 받다보니 화~금이 비어버리는"
> 실제 운영 페인포인트를 규칙화한 기능. 새 테이블 없이 `PROPERTIES`
> 필드 2개만으로 구현한다.

### 6.1 배치 처리 흐름

```
매일 00:00 배치 실행 (숙소별, 향후 14일 순회)
  ↓
STEP 1. 날짜 분류
  평일(화~금) → "할인 후보"
  주말(금·토) → "인상 후보"
  공휴일/연휴(공공데이터 API) → "인상 후보"로 강제 격상
  ↓
STEP 2. 연휴 구간(3일 이상 연속 공휴일) 방치 감지
  해당 구간 가격이 전부 base_price와 동일하게 M일 이상 방치됐으면
  → 자동조정 하지 않고 "방치 감지" 알림만 생성
  ↓
STEP 3. 미예약 상태 + 날짜분류에 따라 추천가 계산(아래 표)
  ↓
Action Center에 "가격 조정 추천 N건(▲인상 M건/▼할인 K건)" 카드 생성
  ↓
호스트 대시보드에서 일괄승인 / 개별조정 / 무시
```

### 6.2 조정폭 표 (양방향)

| 상황 | 조정 |
|---|---|
| 평일, 체크인 3일 이내, 미예약 | -3,000원(-1%) |
| 평일, 체크인 7일 이내, 미예약 | -1,500원 |
| 주말(금·토), 체크인 7일 이내, 미예약 | +3,000원(+1%) |
| 공휴일/연휴, 미예약 | +5,000원(+2%) |
| 공휴일/연휴인데 기본가와 동일하게 M일 이상 방치 | 조정 없이 알림만(호스트 승인 필요) |

### 6.3 설계 원칙

- **연휴·공휴일 가격은 시스템이 임의로 계속 올리지 않는다.** 방치 감지 →
  알림 → 호스트 최종 승인 흐름으로만 처리(성수기 가격은 임팩트가 커서
  100% 자동보다 안전장치 필요).
- 평일/주말 미세조정(±1500~3000원)은 `weekday_adjustment_enabled=true`인
  숙소에 한해 Action Center 🟢(자동처리 후보)로, 방치 감지는 🟡(오늘확인)로
  분류한다.
- 이 기능은 어디까지나 **규칙기반 추천**이며, "AI가 최적가격을 계산한다"는
  과장된 설명을 하지 않는다(섹션 4의 원칙과 동일).

---

*본 문서는 3rd Host AI 프로젝트의 6차 ERD 크로스체크 결과를 반영한 최종본이며, 이후
변경 시 이 문서를 기준으로 diff 관리합니다. (v1.2: 6절 가격조정 로직 추가 /
v1.3: 9/4 1단계 검증 결과 4건 반영 — INQUIRIES nullable+단독FK,
CHANNEL_CONNECTIONS.last_error_message, CLEANING_TASKS.photo_urls,
ACTION_ITEMS 복합FK)*
