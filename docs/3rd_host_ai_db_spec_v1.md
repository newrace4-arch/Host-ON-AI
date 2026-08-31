# 3rd Host AI — DB 최종 명세서 (v1.0)

> 브랜드명: **Host ON (AI)** (내부 코드/폴더명은 3rd_host_ai 유지)
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
| 1 | `bookable_unit_type` ↔ `room_id`/`bed_id` 조합은 CHECK 제약으로 DB가 강제 | 공통 |
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
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_properties_host ON properties(host_id);
```

### 2.3 ROOMS

```sql
CREATE TABLE rooms (
  room_id      BIGSERIAL PRIMARY KEY,
  property_id  BIGINT NOT NULL REFERENCES properties(property_id) ON DELETE CASCADE,
  room_name    VARCHAR(100) NOT NULL,
  capacity     INTEGER,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (room_id, property_id)   -- Reservation의 계층적 복합 FK를 위한 필수 UNIQUE
);

CREATE INDEX idx_rooms_property ON rooms(property_id);
```

### 2.4 BEDS

```sql
CREATE TABLE beds (
  bed_id      BIGSERIAL PRIMARY KEY,
  room_id     BIGINT NOT NULL REFERENCES rooms(room_id) ON DELETE CASCADE,
  bed_label   VARCHAR(50) NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (bed_id, room_id)        -- Reservation의 계층적 복합 FK를 위한 필수 UNIQUE
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

  -- (B) bookable_unit_type과 실제 FK 조합 일치 검증
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
SELECT r.reservation_id, r.property_id, r.guest_name, r.check_in, c.task_status
FROM reservations r
JOIN cleaning_tasks c ON r.reservation_id = c.reservation_id
WHERE r.property_id = :target_property_id
  AND r.reservation_status = 'CONFIRMED'
  AND r.check_in BETWEEN NOW() AND NOW() + INTERVAL '2 hours'
  AND c.task_status <> 'COMPLETED';
```

조인 1회로 충분하며, 위 인덱스(`idx_reservations_dates`, `idx_cleaning_tasks_property_status`)로
성능 문제 없이 동작합니다.

---

## 4. 문서화가 필요한 정책 (코드 주석/README에 반드시 남길 것)

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

---

*본 문서는 3rd Host AI 프로젝트의 6차 ERD 크로스체크 결과를 반영한 최종본이며, 이후
변경 시 이 문서를 기준으로 diff 관리합니다.*
