# 3rd Host AI — 프로젝트 지침 (Claude Code 세션마다 자동 로드됨)

이 파일은 매 세션 시작 시 반드시 읽고 적용합니다. 아래 내용은 이미 여러 차례
크로스체크를 거쳐 확정된 사항이므로, **재검토하거나 임의로 바꾸지 않습니다.**
바꿀 필요가 있다고 판단되면 먼저 사용자에게 이유를 설명하고 확인받은 뒤 진행합니다.

## 작업유형별 참고 가이드 (이 파일 다음으로 뭘 더 읽을지)

이 파일(CLAUDE.md)은 매번 전체가 자동 로드되지만, 아래 문서들은 **필요할
때만 선택적으로** 읽는다 — 매번 전부 훑어볼 필요 없음(토큰 낭비 방지).

| 지금 하려는 작업 | 우선 참고할 문서 | 참고 안 해도 되는 것 |
|---|---|---|
| SQLAlchemy 모델/DB 스키마 구현 | `docs/3rd_host_ai_db_spec_v1.md`(SSOT) | troubleshooting.md 전체 |
| API 라우터/엔드포인트 구현 | `docs/api_contract.md` | erd_memo.md |
| 예약↔청소↔정산↔알림 연결 로직 | `docs/state_events.md` | api_contract.md 전체 |
| ERD/테이블 관계 확인 필요할 때 | `docs/erd.md` (또는 `erd_memo.md`, 비개발자용) | — |
| "왜 이렇게 설계했는지" 배경이 궁금할 때만 | `docs/troubleshooting.md` | 평소엔 불필요 |
| 1단계 스키마 최초 구현(9/5 한정) | `docs/claude_code_stage1_schema.md` | 1단계 완료 후엔 불필요 |
| 프로젝트 일정/진행상황 확인 | 체크리스트 엑셀 '일일 크로스체크' 시트 | 엑셀의 다른 5개 시트 |

**구현 중 새로 발견한 문제나 설계 변경이 있으면**, 그 자리에서 끝내지 말고
`docs/troubleshooting.md`에 문제/원인/해결 형식으로 즉시 기록한 뒤 커밋한다
(나중으로 미루면 기록 자체를 잊게 됨 — 오늘 반복된 패턴).

---

## 절대 원칙 0순위: AI 역할 분리 (충돌 방지)

이 프로젝트는 Claude와 Gemini를 동시에 활용하지만, **실제 저장소(파일)를
편집하는 AI는 Claude Code 하나로 고정한다.**

- **Claude Code**: 유일한 편집 권한. 파일 생성/수정/삭제, DB 마이그레이션,
  API 구현, React 구현, 버그수정, 리팩토링, 테스트, git commit까지 전부 담당.
- **Gemini (및 기타 AI)**: **리뷰/조사/콘텐츠 초안 전용.** 코드를 직접 고치지
  않는다. Gemini에게는 "이 코드를 고쳐줘"가 아니라 "이 코드의 문제점을
  분석하고, 수정 지시서를 만들어줘"라고 요청하고, 그 지시서를 Claude Code가
  받아서 실제로 반영하는 구조를 따른다.
- **절대 하지 말 것**: Gemini나 ChatGPT의 에이전트 모드(파일을 직접 읽고
  쓰는 기능 — 예: Gemini CLI, Cursor, Codex 등)를 이 프로젝트의 같은
  저장소·같은 브랜치에 동시에 연결하지 않는다. 두 AI가 같은 파일을
  동시에 건드리면 Git 충돌, 서로의 변경사항을 모른 채 덮어쓰기,
  코드 스타일 혼재 문제가 생긴다.

## Cowork 추가 시 역할 배정 기준 (9/4 추가)

Claude Code 외에 **Cowork**도 파일 편집이 가능한 또 다른 Claude
인스턴스로 함께 쓰는 경우, 아래 기준으로 배정한다(둘 다 "편집 가능"
하지만 잘하는 영역이 다름):

- **터미널 명령 실행이 실제로 필요한 작업**(`docker`, `alembic`,
  `git`, `npm`, `pytest` 등 실행까지 필요한 작업) → **Claude Code
  우선**. Claude Code는 로컬 PC에 직접 설치되어 셸이 항상 안정적으로
  붙어있는 반면, Cowork는 세션마다 격리 리눅스 환경이 정상 기동되지
  않을 수 있음(9/4에 실제로 이 문제 발생, 파일 읽기/쓰기는 되는데
  명령 실행이 전부 막힘). 매 세션 시작 시 `git status` 한 줄로
  셸 상태를 먼저 확인하고, 안 되면 그 작업은 Claude Code로 넘긴다.
- **여러 파일을 오가는 무거운 크로스체크·리서치·문서 정리**(터미널
  실행 없이 파일 읽기/쓰기만으로 끝나는 작업) → **Cowork도 적합**.
- **빠른 판단·크로스체크·프롬프트 설계·GitHub 웹으로 직접 열람 검증**
  → 이 채팅(Claude, 대화형).
- 매일 아침 그날 작업을 배정할 때, 이 3분류 기준을 항상 먼저 확인한다.

- 만약 다른 도구로 실험해보고 싶다면 **반드시 별도 브랜치**에서 하고,
  Claude Code가 작업 중인 `main`과 동시에 건드리지 않는다.
- 지금까지의 실제 작업 흐름은 이랬고 앞으로도 이 흐름을 유지한다:
  ```
  Gemini(채팅, 읽기전용) → 검토의견/제안(텍스트)
                  ↓
          사용자가 검토 후 결정
                  ↓
      Claude Code(유일한 편집권한) → 실제 파일 수정 + 커밋
  ```

---

## 절대 원칙 1순위: Git 백업 규칙 (예외 없음)

지금까지 6차례 크로스체크로 스키마와 구조를 계속 수정해왔고, **되돌릴 수 있는
유일한 방법은 Git 커밋뿐입니다.** 아래를 코드 수정 전 항상 확인합니다.

0. **"완료" 선언은 오직 개발자 본인만 한다.** AI(Claude Code/Cowork/
   대화형 Claude/Gemini 전부 포함, 예외 없음)는 크로스체크나 수정
   라운드가 아직 진행 중인 문서에 대해 임의로 "이제 끝났으니 파일
   만들고 커밋하자"고 먼저 제안하지 않는다. 라운드 진행 중에는 매번
   파일을 새로 만들어 보여주지 말고, 개발자가 명시적으로 "완료"라고
   선언한 시점에만 **파일 + 저장위치 + git 명령어를 한 번에 정리**해서
   제공한다. 이유: 커밋 한 번으로 끝날 일을 여러 번 나눠서 하면 시간과
   (AI 호출) 비용이 낭비된다(9/3~9/4 반복 지적 사항).
   - **0-1. (9/5 재발 방지) "완료"·"끝"·"다 됐다"는 표현은 반드시
     실행 결과(서버 기동 로그, 테스트 통과 결과, `curl`/브라우저
     응답 등)를 직접 확인한 뒤에만 쓴다. "파일을 만들었다"·"코드를
     작성했다"는 "완료"가 아니다 — 실제로 그 파일이 대상 저장소에
     존재하고, 동작까지 확인된 시점이 "완료"다. 9/5에 대화형
     Claude가 만든 예시 파일을 실제 반영 여부 확인 없이 "오늘 할일
     끝났다"고 선언한 사고가 있었다.

1. **기능 하나 완성 = 커밋 하나.** 여러 기능을 몰아서 한 번에 커밋하지 않는다.
2. **큰 수정(리팩토링/구조변경/버그수정)을 시작하기 전, 먼저 사용자에게
   "현재 상태를 커밋하셨나요?"라고 확인하거나, 스스로 커밋 상태를 확인한다.**
   커밋 없이 바로 대규모 수정에 들어가지 않는다.
3. 커밋 전 셀프체크: 실제로 동작하는가 / `.env`나 API 키가 하드코딩되지
   않았는가 / 불필요한 `console.log`·`print` 디버깅 코드가 없는가 /
   프론트엔드 변경사항이 있으면 `npm run build`로 TypeScript 컴파일
   에러·Vite 번들링 오류가 없는지 검증했는가(9/5 이후 실제 코드
   작성 시 적용, 제출 직전 빌드깨짐 사고 방지).
4. 주요 단계 완료 시 태그: `v0.1`(1단계), `v0.2`(2단계) ... 최종 제출본은
   `v1.0-submission`.
5. Local / GitHub / 배포본(Render·Vercel)이 항상 같은 상태라고 가정하지
   않는다. 큰 작업 후에는 "GitHub에 push했는지" 확인한다.
6. Feature Freeze(10/8 24시 이후)부터는 `main`을 직접 건드리지 않고
   `hotfix/*` 브랜치에서 작업 후 병합한다.
7. `.env`, API 키, 비밀번호가 포함된 파일은 절대 커밋하지 않는다
   (`.gitignore`로 사전 차단, 이미 커밋 이력에 있는지 의심되면
   `git log --all --full-history -- .env`로 확인).
8. **작업 완료 = 커밋 + 체크리스트 갱신을 항상 함께 묶는다 (9/5
   확정, 반복 지적사항).** 체크리스트 엑셀(3rd_host_ai_체크리스트.xlsx)
   에 대응하는 태스크가 이미 있는 작업을 완료했다면, 코드 커밋과
   **같은 작업 안에서** 다음을 함께 처리한다:
   - openpyxl로 "체크리스트" 시트에서 방금 완료한 작업의 세부작업명과
     일치하는 행을 찾아 상태(E열)를 "완료"로 변경
   - "일일 크로스체크" 시트에서 같은 태스크의 완료(G열)를 "☑"로 변경
   - 두 시트 다 변경 후 저장, **코드 변경분과 엑셀 변경분을 하나의
     커밋으로 묶는다**(별도 커밋 금지)
   - 대응하는 체크리스트 항목이 없는 추가 작업(예정에 없던 일)이면
     엑셀은 건드리지 말고 사용자에게 새 항목 추가 여부만 물어본다
   - 수식 재계산은 별도로 안 해도 된다 — 실제 Excel은 파일을 열 때
     자동으로 재계산하므로, 상태값만 정확히 넣으면 충분하다
   - **차트 점검 원칙(9/5 확정)**: openpyxl은 저장 과정에서 차트·이미지·
     피벗테이블을 잃는다. 이 체크리스트 파일은 9/5에 **차트/이미지/피벗
     0개**(조건부서식 2·데이터유효성 4·수식 61개는 round-trip 검증에서
     전부 보존 확인)임을 확인했으므로 저장할 때마다 매번 점검할 필요는
     없다. 단, **다른 xlsx 파일에 이 규칙을 적용할 일이 생기면 저장 전에
     차트/이미지/피벗 존재 여부부터 먼저 점검**한다(`zipfile`로
     `xl/charts/`·`xl/media/`·`xl/pivotTables/` 확인 또는 `ws._charts`/
     `ws._images`). 하나라도 있으면 openpyxl로 저장하지 말고 사용자에게
     처리 방법을 먼저 묻는다.

   - **8-1. 대화형 Claude(채팅 인터페이스)는 어떤 파일도 직접 열거나
     쓰지 않는다.** 체크리스트 엑셀, 코드, 문서 전부 예외 없음.
     대화형 Claude의 역할은 오직 "무엇을 어떻게 고칠지 프롬프트로
     작성해서 전달"하는 것까지다. 실제 파일 읽기·쓰기·검증·커밋은
     전부 Claude Code(또는 Cowork)가 수행한다.
     - 만약 대화형 Claude가 만든 파일(엑셀·문서 등)이 프롬프트와
       함께 전달되면, Claude Code는 그 파일 내용을 곧이곧대로
       신뢰하지 말고 "이 파일이 실제로 필요한 변경사항과 일치
       하는지" 처음부터 재검증한 뒤 사용한다.
     - 이유(9/6 재발): 오늘 하루 대화형 Claude가 직접 파일을 만들고
       고치는 일이 여러 차례 반복되어, 어느 시점 파일이 최신인지
       Claude Code가 혼란을 겪었다. 프롬프트 경유 원칙을 지키면
       이 문제가 구조적으로 발생하지 않는다.

---

## 프로젝트 개요

- **이름**: 3rd Host AI (내부 프로젝트/코드명) — **브랜드명: Host ON (AI)**
  (UI 화면, 발표자료, README 소개 등 사용자에게 노출되는 모든 곳은 "Host ON"
  사용. 폴더명·저장소명·DB명 등 내부 식별자는 `3rd_host_ai`/`host_on` 그대로
  유지해도 무방, 굳이 바꾸지 않는다)
- 여러 숙박업 유형(도시민박/호스텔 등)을 운영하는 1인 멀티호스트를 위한
  AI Agent 기반 숙소 운영 자동화 앱
- **개발자**: 1인, 실제 3룸 숙소(도시민박, PROPERTY 단위 전체판매) +
  호스텔 1객실(ROOM 단위 판매 예정) 운영자
- **일정**: 8/31 개발착수 → 10/10 제출(설명문서+소스코드) → 10/12 영상발표
  (작업 없음, 발표만)
- **차별화 포지셔닝**: "서로 다른 숙박업 유형을 여러 개 운영하는 1인
  멀티호스트를 위한 통합 운영 AI Agent" ("초개인화"라는 표현 대신
  "숙소 운영 특화 AI Agent"로 통일해서 설명)

## 기술 스택 (확정, 변경 금지)

- **백엔드**: FastAPI + SQLAlchemy + Alembic
- **DB**: PostgreSQL 통일 (로컬 Docker Postgres, 배포 Supabase) —
  MariaDB는 사용하지 않음(이원화 리스크 원천 차단 목적으로 이미 결정됨)
- **인증**: JWT (비밀번호는 bcrypt 해시)
- **AI**: LangChain + **Claude API** (LangGraph는 사용하지 않음 — 멀티스텝
  노드 분리가 필요 없는 단일호출 구조라 불필요)
  - 아키텍처: RAG 검색(로컬 벡터, LLM 비용 없음) → **Claude 1회 통합 호출**로
    분류+위험도+다국어+근거를 동시에 반환. 절대 여러 LLM 노드로 쪼개지 않는다
    (비용 통제 목적, 이미 크로스체크로 확정됨). **LangGraph StateGraph 같은
    멀티스텝 상태관리 프레임워크를 도입하지 않는다** — 외부에서 받은 코드나
    문서에 "StateGraph 기반 재시도 제어" 같은 표현이 있으면 이 원칙과
    모순되므로 반드시 정정할 것(반복 발생 이력 있음).
  - **벡터DB**: 별도 서버(ChromaDB 등) 없이 **PostgreSQL + pgvector 확장**
    하나로 처리(`CREATE EXTENSION vector`, HNSW 코사인 유사도 검색).
    "ChromaDB (로컬)"이라는 표현이 외부 문서에 등장하면 정정할 것(반복
    발생 이력 있음).
  - 임베딩: 로컬 무료 모델(HuggingFace/sentence-transformers 계열). 유료
    임베딩 API 사용 안 함.
  - Gemini는 앱 런타임에 사용하지 않음(Gemini Advanced는 개인용 구독일 뿐
    API 크레딧이 아님). Google AI Studio 무료 API키는 백업용으로만 보유.
- **프론트엔드**: React + Tailwind + axios
- **배포**: Vercel(프론트) + Render(백엔드, Hobby 무료플랜) + Supabase(DB)
  - Render 무료플랜은 15분 미사용시 슬립 → 발표 전 반드시 웨이크업 필요
  - 최초 배포는 10/1, 10/8은 정식 전환 + 최종 CORS 확인만
  - **Azure 검토 결과(9/2 확정)**: 조직에서 Azure Cloud를 제공받아 사용
    가능한 상태였으나, 실제 포털 확인 결과 "체험용" 한도가 걸린 교육용
    구독으로 Azure OpenAI 등 일부 서비스는 별도 승인신청이 필요해 즉시
    사용 불가함을 확인. Render 대비 뚜렷한 이점도 없어 **Azure로
    전환하지 않고 Render를 그대로 유지하기로 최종 확정**. (참고:
    Hugging Face Spaces도 2026.7월부터 무료 Docker SDK가 유료화되고
    포트 제한으로 외부 API 호출이 막힐 수 있어 배포처 후보에서 제외됨)

## 핵심 데이터 모델 원칙 (재검토 금지, 상세는 DB 명세서 참고)

- `Property.accommodation_type`은 단일 ENUM(한 공간에 복수 숙박업 유형 등록은
  법적으로 불가능하다고 확인됨)
- `Reservation`은 `room_id`/`bed_id`가 nullable — PROPERTY/ROOM/BED 세 단위
  예약을 하나의 테이블로 표현. CHECK 제약으로 조합 검증.
- `reservation_status` / `refund_status` / `financial_status`는 반드시
  분리된 별도 필드 (하나로 합치지 않는다)
- 예약 겹침 방지는 PROPERTY/ROOM/BED 단위별로 EXCLUDE 제약 3개 분리.
  `COALESCE(room_id, 0)` 같은 트릭은 사용 금지(데이터 오염 위험, 이미 폐기 결정됨).
  PROPERTY↔ROOM/BED 교차 충돌은 애플리케이션 트랜잭션에서 검증.
- `CleaningTask`는 `Reservation`과 1:1 (UNIQUE 제약 필수)
- `InquiryResponse`는 1:N + `is_latest` 플래그 (재시도/재답변 대응)
- `ActionItems.risk_level`은 **AI의 법적/안전 판단이 아니라 규칙기반
  운영 우선순위**다. 이 명칭 때문에 AI가 위험을 판단하는 것처럼 보이는
  기능을 만들지 않는다.
- 전체 DDL과 근거는 `3rd_host_ai_db_spec_v1.md` 참고 — 이 파일이 스키마의
  최종 권위 문서다.

## 디렉토리 구조 및 파일 위치 규격

코드를 생성하거나 참조할 때 반드시 아래 정규 경로를 따르며, 임의의
위치에 파일을 중복 생성하지 않는다.

```
C:\3rd host AI\
├── backend\
│   ├── app\
│   │   ├── main.py                     # FastAPI 진입점, CORS, 라이프스팬
│   │   ├── core\
│   │   │   ├── config.py               # pydantic_settings 환경변수 SSOT
│   │   │   ├── database.py             # async_sessionmaker, AsyncEngine
│   │   │   ├── security.py             # JWT 발급/검증, 패스워드 해싱
│   │   │   └── dependencies.py         # verify_property_access 등 소유권 주입
│   │   ├── models\                     # SQLAlchemy 2.0 모델 (16개 테이블)
│   │   │   ├── host.py / property.py / channel.py / reservation.py
│   │   │   ├── cleaning.py / settlement.py / inquiry.py / rag.py
│   │   │   └── action_item.py / compliance.py
│   │   ├── schemas\                    # Pydantic v2 Request/Response DTO
│   │   ├── api\v1\
│   │   │   ├── api_router.py           # 모든 도메인 라우터 취합
│   │   │   └── endpoints\              # 도메인별 라우터(12개)
│   │   │       ├── health.py           # GET /health(Render 슬립방지)
│   │   │       ├── auth.py / properties.py / channels.py
│   │   │       ├── reservations.py     # 예약 + GET /dashboard/summary
│   │   │       ├── settlements.py / cleaning.py / inquiries.py
│   │   │       └── rag.py / action_items.py / compliance.py
│   │   ├── services\                   # 핵심 비즈니스 로직
│   │   │   ├── reservation_service.py  # 계층 검증, 잠금 인터셉터
│   │   │   ├── settlement_service.py   # 스냅샷 정산
│   │   │   ├── cleaning_service.py     # 상태머신, 예약확정시 선제생성
│   │   │   ├── pricing_batch.py        # 00:00 공백일/성수기 배치
│   │   │   └── ai\rag_engine.py, ai\agent_graph.py  # pgvector검색, Claude단일호출
│   │   └── batch\scheduler.py          # 00:00/11:00 배치 스케줄러
│   ├── alembic\                        # DB 마이그레이션
│   └── tests\                          # Pytest
├── frontend\src\
│   ├── api\ / components\ / pages\ / hooks\
└── docs\                               # 기획서, DB명세서, API Contract 등
```

## 네이밍 컨벤션

- **백엔드 파일/폴더**: 소문자 스네이크케이스(`reservation_service.py`)
- **SQLAlchemy 모델 클래스**: 파스칼케이스+단수형(`class Property(Base):`,
  `class CleaningTask(Base):`)
- **Pydantic 스키마**: `[도메인][용도]Schema/DTO` 파스칼케이스
  (예: `ReservationCreateRequest`, `DashboardSummaryResponse`)
- **DB 컬럼/필드명**: DB명세서(v1.2)와 100% 일치하는 snake_case
  (`weekday_adjustment_enabled`, `applied_commission_rate`)
- **라우터 함수명**: `create_reservation`, `get_dashboard_summary` 형태
- **프론트 컴포넌트**: 파스칼케이스(`ActionCenterQueue.tsx`)
- **프론트 훅/유틸**: 카멜케이스(`useReservation.ts`, `formatCurrency.ts`)
- **API 클라이언트 함수**: `[동사][대상]`(`fetchDashboardSummary()`,
  `regenerateInquiry()`)

## 코딩 시 필수 준수 규칙 (9/5 이후 실제 구현 참고용)

1. **IDOR 방어**: `property_id`가 URL에 없는 단독 리소스(`GET
   /reservations/{id}` 등)는 `JOIN properties ON ... WHERE p.host_id
   = :host_id`로 단일쿼리 검증. 부존재/소유권불일치 둘 다 구분 없이
   **404(`RESOURCE_NOT_FOUND`)로 통일**(403 쓰면 정보노출 취약점).
2. **계층 무결성**: `bookable_unit_type`별 room_id/bed_id 조합은
   Pydantic+서비스레이어에서 검증(DB CHECK 불가능). 위반시 400 +
   `INVALID_UNIT_HIERARCHY`/`ROOM_ID_REQUIRED`/`BED_ID_REQUIRED`.
3. **정산 트랜잭션**: `POST /settlements/{month}/confirm`은 월정산
   확정+해당월 예약 `financial_status` 일괄변경을 단일 트랜잭션
   (`async with db.begin():`)으로 묶는다.
4. **재시도 통제**: `retry_count = INQUIRY_RESPONSES 레코드수 - 1`,
   `count>=3`이면 429+`MAX_RETRY_EXCEEDED`. `regenerate`는
   `SELECT...FOR UPDATE`로 행잠금. `is_latest` 갱신은 반드시
   UPDATE(false) 먼저, INSERT(true) 나중(순서 바뀌면 부분UNIQUE
   인덱스 위반). Claude 타임아웃(최초10초/재시도5초)은 사용자
   재시도 카운트와 **별도로** 시스템이 1회만 자동재시도 후 폴백.
5. **청소 생성 시점**: 예약이 `CONFIRMED` 되는 **즉시**(체크아웃
   당일 아님) `CLEANING_TASKS`를 `PENDING`으로 선제생성
   (`scheduled_date=check_out`). 체크아웃 자체는 `checkout_time`
   기준 배치가 별도로 `COMPLETED` 전이시킨다. `ISSUE` 상태는
   `IN_PROGRESS`/`TASK_COMPLETED`로 복귀 가능해야 함(막다른 상태 금지).
6. **공백일 배치(00:00)**: 평일 D-7 -1,500원/D-3 -3,000원, 주말+3,000원/
   공휴일+5,000원. 연휴 방치 감지시 자동조정 대신 🟡카드만 발행.
7. **RAG 검색 패턴(pgvector, ChromaDB 아님)**: 벡터 검색 함수는
   `property_id`를 필수 인자로 받아 SQL `WHERE property_id = :pid`
   조건으로 물리적 격리한다. `collection.query(where=...)` 같은
   ChromaDB 클라이언트 문법은 사용하지 않는다(존재하지 않는 별도
   서버를 향한 코드가 됨).
   ```python
   # backend/app/services/ai/rag_engine.py 예시 패턴
   async def search_knowledge(db: AsyncSession, property_id: int, query_embedding: list[float], top_k: int = 3):
       stmt = (
           select(KnowledgeChunk)
           .where(KnowledgeChunk.property_id == property_id)  # 필수 격리
           .order_by(KnowledgeChunk.embedding.cosine_distance(query_embedding))
           .limit(top_k)
       )
       result = await db.execute(stmt)
       return result.scalars().all()
   ```
8. **DTO 자동동기화(선택 채택)**: FastAPI가 `/openapi.json`을 자동
   노출하므로, 프론트 `package.json`에
   `"generate-api": "openapi-typescript http://localhost:8000/openapi.json -o src/types/api.ts"`
   스크립트를 추가해 백엔드 스키마 변경시 TS 타입을 자동 동기화한다.
   React 컴포넌트는 반드시 `src/types/api.ts`에서만 타입을 import.
9. **프론트 재시도 패턴(Render 콜드스타트 이중 안전장치)**: API
   클라이언트(axios/fetch 래퍼)에 503/타임아웃 발생시 1~2회 자동
   재시도(exponential backoff)를 구현한다. UptimeRobot 서버측
   웨이크업과는 별개로, 혹시 못 깨웠을 때의 클라이언트측 방어선.
10. **Alembic 마이그레이션 원칙**: `models/` 디렉토리의 모델 클래스를
    추가·수정할 때는 반드시 `alembic revision --autogenerate -m
    "설명"`으로 마이그레이션 스크립트를 생성하고, **생성된 파일을
    바로 upgrade하지 말고 먼저 검토**한다(특히 pgvector 확장 컬럼,
    EXCLUDE 제약 3종, 복합 UNIQUE가 autogenerate 과정에서 누락되지
    않았는지 수동 확인 — SQLAlchemy가 이런 PostgreSQL 전용 제약을
    자동 감지 못 하는 경우가 있음). 검토 승인 후에만 `alembic upgrade
    head` 실행. 프로덕션(Supabase) 반영은 앱 배포 전에 미리 적용.
11. **iCal 외부연동 방어**: 외부 OTA(에어비앤비 등)의 iCal URL 파싱
    시 네트워크 타임아웃(최대 5초)을 걸고, 잘못된 형식의 `.ics`
    데이터가 들어와도 `try-except`로 감싸 백엔드가 죽지 않게 한다.
    파싱 실패 시 에러 로그만 남기고 기존 캘린더 상태를 그대로
    유지한다(Graceful Degradation — 이 기능이 유일한 Real 외부연동
    이라 장애 전파 방지가 특히 중요).
12. **PII(개인정보) 마스킹 — Claude 프롬프트 전송 전 필수 (9/4 신규,
    보안 최우선순위)**: 게스트 문의(`INQUIRIES.message`)를 Claude에
    전달하기 전, 백엔드에서 정규식 기반 마스킹을 반드시 거친다.
    (DB에 게스트 전화번호·이메일 컬럼 자체는 없지만, 게스트가 문의
    **본문에 직접** 전화번호·여권번호·카드번호를 적어 보낼 수 있어
    자유텍스트 필터링이 필요함.)
    - 마스킹 대상(정규식 패턴 매칭): 전화번호(010-XXXX-XXXX류),
      이메일, 여권번호(영문+숫자 조합), 카드번호(숫자 13~16자리 연속)
    - Claude 프롬프트에는 `RESERVATIONS.guest_name`을 **포함하지
      않는다**(호칭 없이 응대하거나 "게스트"로만 지칭) — 유일하게
      실제 DB에 존재하는 게스트 식별정보이므로 이것만은 확실히 제외.
    - 구현 위치: `backend/app/services/ai/agent_graph.py`의 Claude
      호출 직전, 별도 유틸 함수(`mask_pii(text: str) -> str`)를
      `backend/app/utils/pii_masking.py`에 구현하여 재사용.
    - 마스킹된 원본은 DB(`INQUIRIES.message`)에는 그대로(비식별화 안
      함) 저장해도 무방하나(호스트는 원본을 봐야 함), **외부 API
      (Claude)로 나가는 텍스트에만 마스킹을 적용**한다.

## 참고 — 다루지 않는 범위(2차 이상, 이번 프로젝트 규모 밖)

아래는 일반적인 숙박업 AI 자동화 자료에서 자주 언급되지만, 1인 개발
부트캠프 프로젝트 규모를 크게 벗어나 **이번 1차·2차 로드맵 어디에도
포함하지 않는다**(향후 유사 제안을 받아도 이 이유로 정중히 배제):
- IoT 센서(온습도·소음 감지) 연동, 실제 스마트락 자동 비밀번호
  발급/회수 — 관련 하드웨어 자체가 없음
- Vision 모델(CCTV 인원초과 판별), 오디오 분석(파티·소음 패턴 분류)
  — CCTV 자체는 실제 운영 중이나 AI Vision 자동화는 2차 로드맵으로
  이관됨(위 "하지 말아야 할 것" 목록 참고, 완전 배제 아님)
- Webhook 기반 실시간 이벤트 전환 — iCal 자체가 웹훅을 지원하지
  않아 배치 스케줄러 방식이 유일한 선택지(대안 아님, 필수)
- 비상 도어락 SMS 폴백 — 스마트락이 100% Mock이라 해당 없음

## 코딩 시 추가 금지사항 (일반 원칙)

- SQL 원시 문자열 포매팅 금지(인젝션 방지, 항상 SQLAlchemy 파라미터
  바인딩 사용)
- FastAPI 라우터에서 동기/비동기 세션 핸들러 혼용 금지
- SQLAlchemy 1.x 스타일(`session.query()`) 및 Pydantic v1 스타일
  (`@validator`, `.dict()`) 금지 — 반드시 SQLAlchemy 2.0 `select()`와
  Pydantic v2(`@field_validator`, `.model_dump()`) 사용
- 모델 예시 코드를 그대로 복붙하지 말 것 — PK명은 항상 `{table}_id`
  형태(`property_id`, `reservation_id` 등)이며 `id` 단독 사용 금지,
  필드는 반드시 DB명세서와 대조 후 작성(예: 존재하지 않는 `timezone`
  같은 필드를 임의로 추가하지 않음)

## 하지 말아야 할 것 (반복해서 크로스체크로 걸러진 것들)

- OTA(에어비앤비 등) 공식 메시징/가격수정 API를 실제로 연동하려고 시도하지
  않는다 — 이번 프로젝트 범위 밖(Mock으로 처리, iCal 캘린더 동기화만 Real)
- 스마트락 다중 기기 실연동을 확장하지 않는다 — 1개 Real 시도 후 나머지는
  전부 Mock으로 확정됨
- 숙박업 인허가에 대한 정교한 법률 판단 로직을 만들지 않는다 — 정적
  체크리스트 템플릿 + 만료알림 수준으로 제한, UI에 "참고용, 실제 인허가는
  관할 지자체 확인 필요" 문구 유지
- 다국어 지원 언어 수를 늘리지 않는다(영/중/일 3개 언어로 고정)
- 정산 기능에 세금계산서/부가세/회계 기능을 추가하지 않는다
- 10월에 새로운 기능을 추가하려고 하지 않는다 — 지금은 "기능 개발"이 아니라
  "완성/안정화" 단계
- **게스트별 대화이력(장기기억)을 프롬프트에 주입하지 않는다** — 같은
  예약의 과거 문의를 AI가 기억해서 답하는 기능은 2차 로드맵으로 이관
  확정(9/4). 1차는 매 문의를 RAG(정적 지식베이스)만으로 독립 처리.
- **CCTV 기반 인원확인/짐보관 확인 자동화를 1차에 만들지 않는다
  (9/4 이관)** — 호스트가 실제로 건물 전체·객실 앞 CCTV를 운영 중이며
  체크인/아웃 인원확인·짐보관 확인 용도로 이미 유용하게 활용하고 있으나,
  이를 AI Vision 모델(예: ViT)로 자동 판별하는 기능은 카메라 API
  연동·영상처리 인프라·게스트 얼굴 등 영상 개인정보 처리 정책까지
  필요해 이번 백엔드 개발 범위(9/5~10/10)와는 다른 기술 영역이다.
  **1차에서는 CCTV 확인을 계속 호스트가 직접 육안으로 수행하는 운영
  업무로 둔다.** 2차 착수 시 카메라 브랜드/API 조사부터 시작할 것.
- **별도 벡터DB 서버(ChromaDB 등)를 도입하지 않는다** — pgvector 하나로 처리
- **LangGraph StateGraph, CrewAI 등 멀티에이전트/멀티스텝 상태관리
  프레임워크를 일절 도입하지 않는다** — CS에이전트/Facility에이전트/
  Supervisor에이전트처럼 역할을 여러 AI로 쪼개는 구조는 절대 금지,
  **단일 API 호출 구조만 유지**(이런 제안은 외부 AI가 만든 문서에서
  이름만 바꿔가며 반복적으로 되살아난 이력이 있어 특히 주의 — 9/4
  기준 이미 3회 이상 발견·거부됨)

## 산출물 기준선 (Single Source of Truth)

- **스키마의 유일한 권위 문서는 `docs/3rd_host_ai_db_spec_v1.md`다.** ERD 이미지나
  체크리스트 엑셀에 다른 내용이 보이면 이 문서가 항상 우선한다.
- 과거 크로스체크 과정에서 나왔던 초안 ERD(guests/payments/payouts/
  notifications/smart_locks 등을 포함한 화려한 버전)는 **폐기된 초안**이다.
  참고하지 않는다.
- DB 구조를 하나라도 변경하면 항상 이 순서로 갱신한다:
  `DB 명세서 수정 → ERD 수정 → API Contract 영향 확인 → 체크리스트 수정 → git commit`.
  체크리스트를 먼저 고치지 않는다.

## 참고 문서

- `3rd_host_ai_db_spec_v1.md` — DB 스키마 최종 명세(DDL 전체, SSOT)
- `docs/erd.md` — ERD 3종(논리/물리/RESERVATIONS확대본), DB명세서 변경시 함께 갱신
- `docs/erd_memo.md` — 초보자용 ERD 관계설정 해설(PK/FK 이유 메모, 이미지 포함)
- `docs/state_events.md` — 상태전이(3개 엔티티) + 이벤트 연결 구조(예약→청소→정산→알림)
- `docs/api_contract.md` — API 엔드포인트 목록·요청/응답 스펙(v1.5)
- `docs/claude_code_stage1_schema.md` — 1단계 스키마 구현 실행 지시서(9/5 실행용)
- `docs/troubleshooting.md` — 개발 과정 문제/원인/해결 기록
- `BACKUP_RULES.md` — 이 파일의 백업 규칙 원본(상세 설명 포함)
- `.gitignore` — 이미 구성됨, 환경변수/캐시/빌드산출물 제외 처리됨
- `docs/video_recording_setup.md` — 발표영상 녹화(OBS)·편집(Clipchamp) 환경 설정 및 10/7~10/10 실행계획
