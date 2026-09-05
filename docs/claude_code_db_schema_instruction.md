# Claude Code 지시서 — DB 스키마 16개 테이블 구현 (9/5)

> 이 문서는 CLAUDE.md의 원칙(디렉토리구조/네이밍컨벤션/코딩규칙)을
> 전제로 한다. 시작 전 CLAUDE.md 전체를 먼저 읽을 것.

## 목표

`docs/3rd_host_ai_db_spec_v1.md`(v1.3, SSOT)에 정의된 16개 테이블을
SQLAlchemy 2.0 모델로 구현하고, Alembic 마이그레이션까지 생성한다.

## 작업 순서

### 1단계 — 명세서 전체 정독 (필수, 생략 금지)
`docs/3rd_host_ai_db_spec_v1.md`를 처음부터 끝까지 읽는다. 특히
1절(ENUM 정의)과 4절(-1번 데이터격리 원칙)을 놓치지 말 것.

### 2단계 — 모델 파일 작성 (CLAUDE.md 디렉토리구조 그대로)

이미 골격이 있는 폴더에 아래 매핑대로 작성:

| 파일 | 담당 테이블 |
|---|---|
| `app/models/host.py` | HOSTS |
| `app/models/property.py` | PROPERTIES, ROOMS, BEDS |
| `app/models/channel.py` | CHANNEL_CONNECTIONS |
| `app/models/reservation.py` | RESERVATIONS |
| `app/models/cleaning.py` | CLEANING_TASKS |
| `app/models/settlement.py` | FINANCIAL_CONFIGS, MONTHLY_SETTLEMENTS |
| `app/models/inquiry.py` | INQUIRIES, INQUIRY_CLASSIFICATIONS, INQUIRY_RESPONSES, INQUIRY_APPROVALS |
| `app/models/rag.py` | KNOWLEDGE_CHUNKS |
| `app/models/action_item.py` | ACTION_ITEMS |
| `app/models/compliance.py` | CHECKLIST_ITEMS |

모든 모델은 `app/core/database.py`의 `Base`를 상속한다.

## 🔴 반드시 정확히 반영해야 할 v1.3 세부사항 (오늘 크로스체크로 확정)

1. **ENUM 6개**: `accommodation_type_enum` = URBAN_HOMESTAY, RURAL_HOMESTAY,
   HANOK, HOSTEL, LODGING_FACILITY, GENERAL_LODGING (철자 정확히)
2. **CLEANING_TASKS.scheduled_at**(❌ scheduled_date 아님) — TIMESTAMPTZ,
   예약 CONFIRMED 즉시 선제생성. `photo_urls` JSONB
   NOT NULL DEFAULT '[]'::jsonb 컬럼도 포함
3. **CHANNEL_CONNECTIONS.last_error_message** TEXT — sync_status=FAILED
   시 사유 저장, 성공하면 NULL로 초기화
4. **INQUIRIES.reservation_id**는 **nullable**(예약 전 문의 지원),
   대신 `property_id`에 단독 FK를 반드시 추가해서 데이터격리 보장
5. **ACTION_ITEMS**는 `(reservation_id, property_id)` **복합FK**로
   교차숙소 오염을 DB단에서 차단(reservation_id가 NULL이어도
   PostgreSQL은 그 행의 FK 검증만 건너뜀 — 정상 동작)
6. **RESERVATIONS.net_amount**(예약건별) vs
   **MONTHLY_SETTLEMENTS.net_payout**(월정산) — 이름 절대 혼동 금지
7. **KNOWLEDGE_CHUNKS**는 pgvector 확장 사용
   (`CREATE EXTENSION IF NOT EXISTS vector`), ChromaDB 사용 금지
8. **MONTHLY_SETTLEMENTS**는 `FINANCIAL_CONFIGS`와 FK로 연결하지 않음
   — `applied_commission_rate`에 계산 당시 값을 스냅샷으로 저장
9. **EXCLUDE 제약 3종**(예약 겹침 방지)과 **복합 UNIQUE 3종**
   (channel_connection_id+external_uid / property_id+target_month /
   property_id+channel)을 명세서 그대로 반영

## 3단계 — Alembic 마이그레이션 생성

```bash
alembic revision --autogenerate -m "16개 테이블 초기 스키마"
```

**생성된 파일을 바로 upgrade하지 말고 먼저 열어서 검토**한다(CLAUDE.md
코딩규칙 10번). 특히 아래가 autogenerate로 누락되기 쉬우니 직접 확인:
- pgvector 컬럼(`Vector` 타입)이 제대로 잡혔는지
- EXCLUDE 제약 3종이 마이그레이션에 포함됐는지(SQLAlchemy가 자동 인식
  못 하는 경우 많음 — 수동으로 `op.execute()` 추가 필요할 수 있음)
- 복합 UNIQUE 3종이 포함됐는지

검토 후 문제없으면:
```bash
alembic upgrade head
```

## 4단계 — 검증

```bash
docker exec -it host_on_ai_db psql -U hoston -d host_on_ai -c "\dt"
```
16개 테이블이 전부 나오는지 확인. 안 나오는 테이블이 있으면 즉시 보고.

## 완료 조건 (Definition of Done)

- [ ] 16개 테이블 전부 `\dt`로 확인됨
- [ ] pgvector 확장 정상 설치 확인(`\dx`)
- [ ] `git status`로 변경된 파일 목록 확인 후 커밋 1개로 정리
- [ ] 새로 발견한 문제가 있으면 `docs/troubleshooting.md`에 즉시 기록
