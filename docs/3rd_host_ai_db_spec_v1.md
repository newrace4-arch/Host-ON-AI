# 3rd Host AI — DB 최종 명세서 (v1.2)

> 브랜드명: **Host ON (AI)** (내부 코드/폴더명은 3rd_host_ai 유지)
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

---

## 1. ENUM 타입 정의

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
  channel                channel_enum NOT NULL,
  ical_url               TEXT,
  external_property_id   VARCHAR(100),
  sync_status            sync_status_enum NOT NULL DEFAULT 'SYNCING',
  last_synced_at         TIMESTAMPTZ,
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (connection_id, property_id),  -- Reservation 복합 FK용
  UNIQUE (property_id, channel)         -- MVP: 채널당 연결 1개로 제한
);

CREATE INDEX idx_channel_connections_property ON channel_connections(property_id);
```

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
  gross_amount                INTEGER,
  fee_amount                  INTEGER,
  net_amount                  INTEGER,
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
  fee_type            fee_type_enum NOT NULL DEFAULT 'SINGLE_FEE',
  commission_rate     NUMERIC(5,4) NOT NULL DEFAULT 0.1550,  -- 2026.5.25 한국 단일수수료 기준
  fee_source          VARCHAR(50) NOT NULL DEFAULT 'system_default_2026',
  base_nightly_rate   INTEGER,
  vat_included        BOOLEAN NOT NULL DEFAULT true,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

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

### 2.9 CLEANING_TASKS

```sql
CREATE TABLE cleaning_tasks (
  task_id            BIGSERIAL PRIMARY KEY,
  reservation_id     BIGINT NOT NULL UNIQUE,   -- 체크아웃 1건당 정확히 1개 (1:1)
  property_id        BIGINT NOT NULL,
  task_status        task_status_enum NOT NULL DEFAULT 'PENDING',
  cleaner_name       VARCHAR(100),
  amenity_shortage   BOOLEAN NOT NULL DEFAULT false,
  scheduled_date     TIMESTAMPTZ,
  verified_at        TIMESTAMPTZ,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  FOREIGN KEY (reservation_id, property_id)
    REFERENCES reservations(reservation_id, property_id) ON DELETE CASCADE
);

CREATE INDEX idx_cleaning_tasks_property_status ON cleaning_tasks(property_id, task_status);
```

### 2.10 INQUIRIES

```sql
CREATE TABLE inquiries (
  inquiry_id       BIGSERIAL PRIMARY KEY,
  reservation_id   BIGINT NOT NULL,
  property_id      BIGINT NOT NULL,
  channel          VARCHAR(30),
  message          TEXT NOT NULL,
  language         VARCHAR(10),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  FOREIGN KEY (reservation_id, property_id)
    REFERENCES reservations(reservation_id, property_id) ON DELETE CASCADE
);

CREATE INDEX idx_inquiries_property ON inquiries(property_id);
CREATE INDEX idx_inquiries_reservation ON inquiries(reservation_id);
```

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
  inquiry_id       BIGINT NOT NULL REFERENCES inquiries(inquiry_id) ON DELETE CASCADE,
  response_text    TEXT NOT NULL,
  sources          JSONB,
  language         VARCHAR(10),
  is_latest        BOOLEAN NOT NULL DEFAULT true,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 문의 하나당 "최신 응답"은 정확히 하나만 존재하도록 부분 유니크 인덱스로 강제
CREATE UNIQUE INDEX uniq_inquiry_latest_response
  ON inquiry_responses(inquiry_id) WHERE is_latest = true;

CREATE INDEX idx_inquiry_responses_inquiry ON inquiry_responses(inquiry_id);
```

> **애플리케이션 규칙**: 재시도/재답변으로 새 응답을 만들 때는 기존 `is_latest=true` 행을
> `false`로 먼저 UPDATE한 뒤 새 행을 INSERT합니다(같은 트랜잭션 내에서 처리).

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
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
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
  reservation_id    BIGINT REFERENCES reservations(reservation_id) ON DELETE SET NULL,
  risk_level        action_risk_level_enum NOT NULL,  -- 규칙기반 우선순위. AI/법적 판단 아님 (섹션 8 참고)
  category          VARCHAR(50) NOT NULL,
  title             TEXT NOT NULL,
  content           TEXT,
  status            action_status_enum NOT NULL DEFAULT 'OPEN',
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_action_items_property_status ON action_items(property_id, status, risk_level);
```

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
   | CHANNEL_CONNECTIONS | 직접 FK |
   | FINANCIAL_CONFIGS / MONTHLY_SETTLEMENTS | 직접 FK |
   | CLEANING_TASKS | 복합FK로 RESERVATIONS 경유 확보(2.9절) |
   | INQUIRIES | 직접 FK(+ reservation_id로 이중 확인) |
   | KNOWLEDGE_CHUNKS | 직접 FK — **RAG 검색 시 이 필터가 없으면
     "숙소A 문의에 숙소B 하우스룰이 섞여 답변되는" 교차오답이라는
     치명적 버그로 이어짐(가장 위험한 누락 지점)** |
   | ACTION_ITEMS / CHECKLIST_ITEMS | 직접 FK |
   | ROOMS / BEDS | 계층 FK로 PROPERTIES까지 역추적 가능 |

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
3. **`MONTHLY_SETTLEMENTS`는 스냅샷**입니다. `FINANCIAL_CONFIGS`의 수수료율이 이후 바뀌어도
   과거 정산 결과(`applied_commission_rate`)는 변하지 않습니다.
4. **PROPERTY↔ROOM/BED 교차 예약 충돌은 DB가 아니라 애플리케이션 트랜잭션에서 방어**합니다
   (섹션 2.6.1 참고).

---

## 5. 구현 순서 (9/1부터)

> **ERD(논리적/물리적/RESERVATIONS 확대본 3종)는 `docs/erd.md` 참고.**
> DB 구조를 변경할 때는 이 문서(명세서)를 먼저 고치고, 그 다음 `docs/erd.md`를
> 반드시 같은 날 동기화할 것 (9/2에 이 동기화를 누락했던 사고 재발 방지).

```
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
변경 시 이 문서를 기준으로 diff 관리합니다. (v1.2: 6절 가격조정 로직 추가)*
