# 🏠 Host ON AI (호스트온)
> **1인 멀티호스트를 위한 AI 기반 숙소 운영 자동화 플랫폼**[cite: 4, 5]  
> *Always-On Operations for Multi-Property Hosts*[cite: 4]

---

## 📌 프로젝트 소개
**Host ON AI**는 외국인관광 도시민박업, 호스텔, 한옥체험업 등 **서로 다른 숙박업 유형의 숙소를 여러 개 운영하는 1인 멀티호스트**를 위한 통합 운영 AI Agent 서비스입니다[cite: 5].  
분산된 OTA 예약 일정 동기화부터 24시간 다국어 게스트 응대, 규칙 기반 데일리 액션 관리, 3단계 정산 파이프라인까지 숙소 운영 전반을 자율화합니다[cite: 4, 5].

---

## ✨ 핵심 기능

### 1. 📬 Host ON Inbox (AI 게스트 응대)[cite: 4]
- **숙소별 지식베이스(RAG) 격리:** 숙소 간 하우스룰/FAQ 교차 오답을 원천 차단하는 `property_id` 스코프 격리[cite: 5].
- **1회 통합 추론:** 단 1회의 LLM 호출로 의도 분류, RAG 기반 답변 생성, 운영 위험도 분류, 3개국어(영/중/일) 응답 동시 반환[cite: 5].
- **로컬 무료 임베딩:** 외부 유료 임베딩 API 의존성 없이 비용 0원으로 고속 벡터 검색[cite: 5].

### 2. 🚦 Host ON Action (3색 데일리 액션 센터)[cite: 4]
- AI 판단이 아닌 **100% 규칙 기반(Rule-based)**으로 호스트가 오늘 처리할 업무를 명확히 분류[cite: 5]:
  - 🔴 **지금처리 (RED):** 체크인 임박 미청소, 비인가 얼리체크인 요청 등 긴급 건
  - 🟡 **오늘확인 (YELLOW):** 정산 단가 불일치 예외 보정, 수기 예약 확인
  - 🟢 **자동처리 (GREEN):** 도어락 비밀번호 자동 발송, 표준 FAQ 자동 답변 완료 건

### 3. 📅 Channel & Calendar Sync (iCal 동기화)[cite: 4]
- **비실시간 일정 동기화:** 에어비앤비 등 주요 OTA의 iCal 피드 파싱을 통한 일정 동기화 및 충돌 감지[cite: 5].
- **PostgreSQL 배타 제약조건:** `EXCLUDE USING GIST` 제약을 통해 동일 유닛(Property/Room/Bed)의 중복 예약 원천 차단[cite: 5].

### 4. 💰 Host ON Settlement (스마트 정산 파이프라인)[cite: 4]
- **2026 단일 수수료 정책 반영:** 한국 에어비앤비 개편 기준(호스트 부담 15.5%) 기본 적용 및 동적 수수료 설정 지원.
- **3단계 정산 체계:** `자동 추정(ESTIMATED)` → `일괄 확인(CONFIRMED)` → `예외 보정(MANUALLY_ADJUSTED)` 단계별 관리[cite: 5].
- **월간 Clamping 집계:** 월 경계를 걸치는 예약의 점유 박수 절단 및 실가동률 정확 산출.

### 5. 🧹 Operations & Compliance (청소 및 인허가 관리)
- **체크아웃 연동 청소 상태머신:** 예약 1건당 청소 태스크(1:1) 자동 발행 및 비품 부족 체크.
- **숙박업 인허가 관리:** 업종별(도시민박/호스텔 등) 법정 서류 만료 주기 사전 알림[cite: 5].

---

## 🛠 기술 스택

### Backend & Database
- **Framework:** FastAPI (Python)[cite: 5]
- **ORM / Migration:** SQLAlchemy, Alembic[cite: 5]
- **Database:** PostgreSQL (로컬: Docker Postgres, 프로덕션: Supabase)[cite: 5]
- **Authentication:** JWT + bcrypt[cite: 5]

### AI & Agent
- **LLM Engine:** Claude API (Anthropic)[cite: 5]
- **Orchestration:** LangChain, LangGraph[cite: 5]
- **Embedding:** 로컬 오픈소스 임베딩 모델 (sentence-transformers)[cite: 5]
- **Vector Search:** Supabase pgvector / 로컬 벡터 검색[cite: 5]

### Frontend & Deployment
- **Frontend:** React, Tailwind CSS, Axios[cite: 5]
- **Hosting:** Vercel (Frontend), Render (Backend)[cite: 5]
- **External Integration:** Solapi/Aligo 문자 API (Mock/Real 격리), 공공데이터포털 API[cite: 5]

---

## 🧱 데이터 모델 구조 (ERD 개요)
총 16개 테이블로 구성되어 있으며, 숙소 공간 계층과 운영 데이터를 완벽히 격리합니다:
- **계층 구조:** `HOSTS` → `PROPERTIES` → `ROOMS` → `BEDS`
- **운영/채널:** `CHANNEL_CONNECTIONS` ↔ `RESERVATIONS` ↔ `CLEANING_TASKS`
- **AI/RAG:** `KNOWLEDGE_CHUNKS` (숙소별 RAG), `INQUIRIES` → `INQUIRY_RESPONSES` (1:N + `is_latest`)[cite: 5]
- **업무/정산:** `ACTION_ITEMS`, `FINANCIAL_CONFIGS`, `MONTHLY_SETTLEMENTS`, `CHECKLIST_ITEMS`

---

## 🚀 빠른 시작 (Getting Started)

### 1. Backend 설정
```bash
# 1) 가상환경 생성 및 활성화
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2) 의존성 설치
pip install -r requirements.txt

# 3) 환경변수 설정 (.env 파일 생성)
cp .env.example .env

# 4) DB 마이그레이션 적용
alembic upgrade head

# 5) FastAPI 서버 가동
uvicorn main:app --reload --port 8000