# Host-Property-Room-Bed 계층 스키마 — 최종 실행 지시서 (9/5 실행용)

> ⚠️ **실행 시점 주의**: 이 지시서는 오늘(8/31~9/1) 실행하는 것이 아닙니다.
> 아래 전제조건이 모두 준비된 **9/5**에 실행하세요.
>
> **전제조건 체크(9/5 당일 먼저 확인)**
> - [ ] Docker Postgres 컨테이너 실행 중
> - [ ] `backend/.venv` 가상환경 생성 및 활성화
> - [ ] FastAPI/SQLAlchemy/Alembic 설치 완료
> - [ ] `alembic init alembic` 완료
> - [ ] `.env`에 `DATABASE_URL` 설정 완료
>
> 이 조건이 하나라도 안 갖춰졌다면 아래 2단계(`alembic upgrade head`)에서
> 바로 에러가 납니다.

---

## 1단계: Claude Code에게 모델 생성 지시 (아래 그대로 복사)

```
[지시서: Host-Property-Room-Bed 계층 스키마 생성]

3rd_host_ai_db_spec_v1.md 명세에 맞춰 backend/app/models/ 디렉토리에
계층형 공간 모델을 생성해주세요. 명세서에 없는 컬럼/테이블/ENUM 값은
임의로 추가하지 마세요.

1. 파일 위치: backend/app/models/space.py

2. 구현 요구사항:

   - Base = DeclarativeBase 사용 (SQLAlchemy 2.0 Mapped 스타일)

   - Host (hosts 테이블):
     host_id, email(UNIQUE, NOT NULL), password_hash(NOT NULL),
     name(NOT NULL), created_at
     ※ phone 필드는 넣지 않는다(명세서에 없음, 의도적 제외 결정)

   - AccommodationType ENUM (명세서 6개 값 정확히 사용, 추가/변경 금지):
     URBAN_HOMESTAY, RURAL_HOMESTAY, HANOK, HOSTEL,
     LODGING_FACILITY, GENERAL_LODGING

   - BookableUnitType ENUM: PROPERTY, ROOM, BED

   - Property (properties 테이블):
     property_id, host_id(FK→hosts, ON DELETE CASCADE),
     name(NOT NULL), accommodation_type(NOT NULL),
     bookable_unit_type(NOT NULL), address, base_price(DEFAULT 0),
     lower_bound_price, checkin_time(TIME, DEFAULT '15:00'),
     checkout_time(TIME, DEFAULT '11:00'), created_at
     ※ checkin_time/checkout_time은 v1.1에서 추가됨 — 나중 단계(5단계)
       Action Center의 "체크인 N시간 전" 규칙 계산에 반드시 필요하니
       지금 단계에서 빠뜨리지 말 것.
     ※ bookable_unit_type과 room_id/bed_id의 일치 여부를 강제하는
       CHECK 제약은 이 단계에서 만들지 않는다. 그건 Reservation
       테이블 생성 시점(명세서 2.6절)에 구현하되, **PostgreSQL 일반
       CHECK로는 테이블을 넘나드는 검증이 불가능**하므로 이 부분은
       애플리케이션 서비스 레이어에서 검증하도록 설계한다(DB CHECK로
       해결된다고 오해하지 말 것).

   - Room (rooms 테이블):
     room_id, property_id(FK→properties, ON DELETE CASCADE),
     room_name(NOT NULL), capacity, created_at
     * UniqueConstraint("room_id", "property_id",
       name="uq_room_property_ref")
       → 이 제약은 "중복 방지용"이 아니라 향후 Reservation이
         (room_id, property_id) 복합FK로 참조할 후보키(candidate key)
         용도임을 주석으로 명시할 것.
     * UniqueConstraint("property_id", "room_name",
       name="uq_property_room_name")
       → 같은 숙소 안에서 실제 객실명("101호" 등) 중복을 막는
         운영 무결성용 제약. 위 제약과 목적이 다르므로 둘 다 만든다.

   - Bed (beds 테이블):
     bed_id, room_id(FK→rooms, ON DELETE CASCADE),
     bed_label(NOT NULL), created_at
     * UniqueConstraint("bed_id", "room_id",
       name="uq_bed_room_ref")
       → Room과 동일한 이유로 향후 복합FK 참조용
     * UniqueConstraint("room_id", "bed_label",
       name="uq_room_bed_label")
       → 같은 객실 안에서 침대 라벨("A","B" 등) 중복 방지용

   - FK는 DB 레벨 ON DELETE CASCADE와 SQLAlchemy ORM
     cascade="all, delete-orphan"을 **둘 다** 명시한다. 이 둘은
     별개 메커니즘이므로 하나만 설정하면 안 된다
     (ORM 삭제와 직접 SQL 삭제 시 동작이 다를 수 있음).

   - 인덱스: idx_properties_host_id, idx_rooms_property_id,
     idx_beds_room_id

구현 후 `alembic revision --autogenerate`로 마이그레이션 파일을 생성하고,
**바로 upgrade하지 말고** 생성된 파일 내용을 먼저 보여주세요. PK/FK/
UNIQUE/CASCADE/인덱스가 의도대로 다 들어갔는지 확인한 뒤 제가 승인하면
그때 upgrade head를 실행합니다.
```

---

## 2단계: 마이그레이션 파일 검토 → DB 적용

**먼저 검토, 승인 후 적용** — autogenerate 결과를 바로 믿지 않습니다.

```powershell
cd "C:\3rd host AI\backend"
.venv\Scripts\activate

# 1. 마이그레이션 파일 생성 (아직 DB에 적용 안 됨)
alembic revision --autogenerate -m "create_space_hierarchy_tables"

# 2. 생성된 파일을 직접 열어서 확인
#    alembic/versions/ 폴더의 최신 파일을 열어 아래를 눈으로 확인:
#    - PK/FK가 다 있는가
#    - ON DELETE CASCADE가 반영됐는가
#    - UNIQUE 제약 4개(room_property_ref, room_name, bed_room_ref, bed_label) 다 있는가
#    - ENUM 값이 6개 정확히 맞는가(PENSION/OTHER/HANOK_STAY 같은 값 없어야 함)

# 3. 확인 후에만 실제 DB에 적용
alembic upgrade head
```

---

## 3단계: 제약조건 무결성 검증 (수정된 Smoke Test)

기존 안의 "room_id 중복 테스트"는 room_id가 이미 PK라 의미가 없어서
**room_name 중복 테스트로 교체**했습니다.

**Test A — 객실명 중복 방지 (UNIQUE(property_id, room_name) 검증)**
```
1. Property A에 Room "101호" 생성 → 성공
2. Property A에 또 Room "101호" 생성 → 실패해야 함(UNIQUE 위반)
3. Property B에 Room "101호" 생성 → 성공해야 함(다른 숙소는 이름 겹쳐도 됨)
```

**Test B — 베드 라벨 중복 방지 (UNIQUE(room_id, bed_label) 검증)**
```
1. Room A에 Bed "A" 생성 → 성공
2. Room A에 또 Bed "A" 생성 → 실패해야 함
3. Room B에 Bed "A" 생성 → 성공해야 함
```

**Test C — Cascade 삭제 검증**
```
1. Host 삭제 시 하위 Property→Room→Bed가 한 번에 정리되는지 확인
2. ORM으로 삭제(Python 코드)했을 때와, psql로 직접
   `DELETE FROM hosts WHERE host_id=...` 실행했을 때 둘 다
   동일하게 cascade가 걸리는지 각각 확인
   (DB 레벨 CASCADE가 없으면 후자에서 에러가 날 수 있음)
```

---

## 4단계: 체크리스트 업데이트 및 Git 커밋

```powershell
git add backend/
git commit -m "feat(db): establish Host-Property-Room-Bed schema with composite unique constraints (room_name/bed_label 포함)"
git tag -a v0.1 -m "1단계 공간계층 스키마 확정(Schema Freeze)"
```

---

## Schema Freeze 통과 기준 (전부 체크되면 다음 단계로)

- [ ] Host/Property/Room/Bed 컬럼이 명세서와 정확히 일치 (phone 없음)
- [ ] ENUM 6개 값 정확
- [ ] FK 4단계 전부 ON DELETE CASCADE + ORM cascade 둘 다 적용
- [ ] UNIQUE 4개(room_property_ref, room_name, bed_room_ref, bed_label) 전부 생성
- [ ] Test A, B, C 전부 통과
- [ ] 마이그레이션 파일 직접 검토 완료
- [ ] git commit + v0.1 태그 완료

**이 게이트를 통과해야 다음 단계(RESERVATIONS·CHANNEL_CONNECTIONS 구현,
여기서 bookable_unit_type CHECK 제약도 함께 구현)로 넘어갑니다.**
