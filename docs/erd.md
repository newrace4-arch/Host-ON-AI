# Host ON (AI) — ERD (v1.3 최신 반영)

> DB 명세서(`3rd_host_ai_db_spec_v1.md`) 변경 시 이 파일도 함께 갱신할 것.
> 마지막 동기화: **v1.3** (9/4 1단계 검증 반영 — INQUIRIES nullable+단독FK,
> last_error_message / photo_urls 신규 컬럼, ACTION_ITEMS 복합FK)
>
> ⚠️ **2절(물리적 스키마)은 요약본이 아니라 DDL 전수 반영본이다.** 9/4 검증에서
> 컬럼 25개가 누락돼 있던 것을 보충했으므로, 앞으로 명세서에 컬럼을 추가할 때
> 여기도 반드시 같이 추가한다(빠뜨리면 다음 검증에서 또 걸린다).
> 단, `created_at`은 전 테이블 공통이라 ERD에서는 생략한다.
>
> Notion에 붙여넣을 때는 각 코드블록에서 ```mermaid 와 ``` 줄은 빼고
> erDiagram 부터 시작하는 내용만 넣을 것.

---

## 1. 논리적 스키마 (한글)

```mermaid
erDiagram
  호스트 ||--o{ 숙소 : 보유
  숙소 ||--o{ 객실 : 포함
  객실 ||--o{ 침대 : 포함
  숙소 ||--o{ 채널연동 : 연결
  숙소 ||--o{ 문의 : 접수
  숙소 ||--o{ 예약 : 접수
  객실 ||--o{ 예약 : 예약단위
  침대 ||--o{ 예약 : 예약단위
  채널연동 ||--o{ 예약 : 동기화
  숙소 ||--|| 정산설정 : 설정
  숙소 ||--o{ 월별정산 : 요약
  예약 ||--o| 청소작업 : 생성
  예약 |o--o{ 문의 : "연결(선택 - 예약전 사전문의 허용)"
  문의 ||--|| 문의분류 : 분류됨
  문의 ||--o{ 문의응답 : 응답됨
  문의응답 ||--o{ 응답승인 : 요구
  숙소 ||--o{ 지식청크 : 보유
  숙소 ||--o{ 액션아이템 : 발생
  숙소 ||--o{ 체크리스트항목 : 요구

  호스트 {
    코드 호스트아이디 PK
    텍스트 이메일
    텍스트 비밀번호해시
    텍스트 이름
  }
  숙소 {
    코드 숙소아이디 PK
    코드 호스트아이디 FK
    텍스트 숙소명
    목록 숙박업유형 "6종:도시민박·농어촌민박·한옥·호스텔·생활숙박·일반숙박(관광진흥법시행령)"
    목록 판매단위유형
    텍스트 주소
    숫자 기본가격
    숫자 하한가격
    날짜 체크인시각
    날짜 체크아웃시각
    논리 평일자동조정활성화
    논리 연휴자동조정활성화
  }
  객실 {
    코드 객실아이디 PK
    코드 숙소아이디 FK
    텍스트 객실명
    숫자 수용인원
  }
  침대 {
    코드 침대아이디 PK
    코드 객실아이디 FK
    텍스트 침대라벨
  }
  채널연동 {
    코드 연동아이디 PK
    코드 숙소아이디 FK
    목록 채널구분
    텍스트 아이칼주소
    목록 동기화상태
    날짜 마지막동기화시각
  }
  예약 {
    코드 예약아이디 PK
    코드 숙소아이디 FK
    코드 객실아이디 FK
    코드 침대아이디 FK
    코드 연동아이디 FK
    텍스트 외부예약번호
    텍스트 게스트명
    텍스트 게스트언어
    날짜 체크인일자
    날짜 체크아웃일자
    목록 예약상태
    목록 환불상태
    목록 정산상태
    숫자 총금액
    숫자 수수료
    숫자 실정산액
    논리 호스트확인필요여부
  }
  정산설정 {
    코드 설정아이디 PK
    코드 숙소아이디 FK
    목록 수수료구분
    숫자 수수료율
    숫자 기본단가
  }
  월별정산 {
    코드 정산아이디 PK
    코드 숙소아이디 FK
    텍스트 대상연월
    숫자 점유박수
    숫자 가동률
    숫자 총매출
    숫자 실정산액
    숫자 적용수수료율스냅샷
  }
  청소작업 {
    코드 작업아이디 PK
    코드 예약아이디 FK
    목록 청소상태
    텍스트 청소담당자
    논리 비품부족여부
  }
  문의 {
    코드 문의아이디 PK
    코드 예약아이디 FK
    코드 숙소아이디 FK
    텍스트 문의채널
    텍스트 문의내용
    텍스트 언어
  }
  문의분류 {
    코드 분류아이디 PK
    코드 문의아이디 FK
    텍스트 분류카테고리
    목록 위험도
    논리 자동응답가능여부
  }
  문의응답 {
    코드 응답아이디 PK
    코드 문의아이디 FK
    텍스트 응답내용
    논리 최신응답여부
  }
  응답승인 {
    코드 승인아이디 PK
    코드 응답아이디 FK
    목록 승인상태
    코드 승인자
  }
  지식청크 {
    코드 청크아이디 PK
    코드 숙소아이디 FK
    목록 문서유형
    텍스트 본문
    벡터 임베딩벡터
  }
  액션아이템 {
    코드 액션아이디 PK
    코드 숙소아이디 FK
    코드 예약아이디 FK
    목록 우선순위
    텍스트 분류
    목록 처리상태
  }
  체크리스트항목 {
    코드 항목아이디 PK
    코드 숙소아이디 FK
    목록 숙박업유형
    텍스트 항목명
    목록 갱신트리거유형
    날짜 만료일
  }
```

---

## 2. 물리적 스키마 (영문, 실제 DDL 기준)

```mermaid
erDiagram
  HOSTS ||--o{ PROPERTIES : owns
  PROPERTIES ||--o{ ROOMS : contains
  ROOMS ||--o{ BEDS : contains
  PROPERTIES ||--o{ CHANNEL_CONNECTIONS : connects
  PROPERTIES ||--o{ RESERVATIONS : receives
  ROOMS ||--o{ RESERVATIONS : booked_as
  BEDS ||--o{ RESERVATIONS : booked_as
  CHANNEL_CONNECTIONS ||--o{ RESERVATIONS : syncs
  PROPERTIES ||--|| FINANCIAL_CONFIGS : configures
  PROPERTIES ||--o{ MONTHLY_SETTLEMENTS : summarizes
  RESERVATIONS ||--o| CLEANING_TASKS : triggers
  PROPERTIES ||--o{ INQUIRIES : receives
  RESERVATIONS |o--o{ INQUIRIES : "linked_to (nullable, 사전문의 허용)"
  INQUIRIES ||--|| INQUIRY_CLASSIFICATIONS : classified_as
  INQUIRIES ||--o{ INQUIRY_RESPONSES : answered_by
  INQUIRY_RESPONSES ||--o{ INQUIRY_APPROVALS : requires
  PROPERTIES ||--o{ KNOWLEDGE_CHUNKS : has
  PROPERTIES ||--o{ ACTION_ITEMS : generates
  RESERVATIONS |o--o{ ACTION_ITEMS : "linked_to (nullable, 복합FK)"
  PROPERTIES ||--o{ CHECKLIST_ITEMS : requires

  HOSTS {
    bigserial host_id PK
    varchar email UK
    varchar password_hash
    varchar name
  }
  PROPERTIES {
    bigserial property_id PK
    bigint host_id FK
    varchar name
    enum accommodation_type "URBAN_HOMESTAY·RURAL_HOMESTAY·HANOK·HOSTEL·LODGING_FACILITY·GENERAL_LODGING(관광진흥법시행령 제2조1항3호바목)"
    enum bookable_unit_type
    varchar address
    integer base_price
    integer lower_bound_price
    time checkin_time
    time checkout_time
    boolean weekday_adjustment_enabled
    boolean holiday_adjustment_enabled
  }
  ROOMS {
    bigserial room_id PK
    bigint property_id FK
    varchar room_name
    integer capacity
  }
  BEDS {
    bigserial bed_id PK
    bigint room_id FK
    varchar bed_label
  }
  CHANNEL_CONNECTIONS {
    bigserial connection_id PK
    bigint property_id FK
    enum channel
    text ical_url
    varchar external_property_id
    enum sync_status
    timestamptz last_synced_at
    text last_error_message "v1.3 신규: 마지막 동기화 실패 사유"
  }
  RESERVATIONS {
    bigserial reservation_id PK
    bigint property_id FK
    bigint room_id FK
    bigint bed_id FK
    bigint channel_connection_id FK
    varchar external_uid
    varchar guest_name
    varchar guest_language
    date check_in
    date check_out
    timestamptz booked_at
    enum reservation_status
    enum refund_status
    enum financial_status
    integer gross_amount
    integer fee_amount
    integer net_amount
    date expected_settlement_at
    date actual_settlement_at
    boolean host_confirmation_required
  }
  FINANCIAL_CONFIGS {
    bigserial config_id PK
    bigint property_id FK
    enum fee_type
    numeric commission_rate
    varchar fee_source
    integer base_nightly_rate
    boolean vat_included
  }
  MONTHLY_SETTLEMENTS {
    bigserial settlement_id PK
    bigint property_id FK
    char target_month
    integer total_reservations
    integer occupied_nights
    numeric occupancy_rate
    integer gross_revenue
    integer channel_fee
    integer net_payout
    numeric applied_commission_rate
  }
  CLEANING_TASKS {
    bigserial task_id PK
    bigint reservation_id FK "UNIQUE - 예약당 1건(1:1)"
    bigint property_id FK
    enum task_status
    varchar cleaner_name
    boolean amenity_shortage
    timestamptz scheduled_at "check_out + checkout_time 결합한 실제 체크아웃 시각(v1.3 개명)"
    jsonb photo_urls "v1.3 신규: 완료사진 URL 배열(append)"
    timestamptz verified_at
  }
  INQUIRIES {
    bigserial inquiry_id PK
    bigint reservation_id FK "v1.3 nullable - 사전문의 허용"
    bigint property_id FK "v1.3 단독FK 신규추가"
    varchar channel
    text message
    varchar language
  }
  INQUIRY_CLASSIFICATIONS {
    bigserial classification_id PK
    bigint inquiry_id FK
    varchar category
    enum risk_level
    boolean auto_respondable
  }
  INQUIRY_RESPONSES {
    bigserial response_id PK
    bigint inquiry_id FK
    text response_text
    jsonb sources
    varchar language
    boolean is_latest
  }
  INQUIRY_APPROVALS {
    bigserial approval_id PK
    bigint response_id FK
    enum status
    bigint approved_by
    timestamptz approved_at
  }
  KNOWLEDGE_CHUNKS {
    bigserial chunk_id PK
    bigint property_id FK
    enum document_type
    varchar category
    text content
    vector embedding
  }
  ACTION_ITEMS {
    bigserial action_id PK
    bigint property_id FK
    bigint reservation_id FK "v1.3 복합FK로 전환(교차숙소 참조 차단)"
    enum risk_level
    varchar category
    text title
    text content
    enum status
  }
  CHECKLIST_ITEMS {
    bigserial checklist_item_id PK
    bigint property_id FK
    enum accommodation_type
    varchar item_name
    varchar status
    enum renewal_trigger_type
    date expiry_date
  }
```

---

## 3. RESERVATIONS 중심 확대본 (예약↔청소↔문의↔정산)

```mermaid
erDiagram
  PROPERTIES ||--o{ RESERVATIONS : "숙소가 예약 접수"
  RESERVATIONS ||--o| CLEANING_TASKS : "예약확정시 선제생성(1:1, UNIQUE)"
  PROPERTIES ||--o{ INQUIRIES : "숙소 단위 문의 귀속(단독FK)"
  RESERVATIONS |o--o{ INQUIRIES : "게스트 문의 발생(예약연결은 선택)"
  INQUIRIES ||--|| INQUIRY_CLASSIFICATIONS : "AI 1회호출로 분류"
  INQUIRIES ||--o{ INQUIRY_RESPONSES : "응답(1:N+최신플래그)"
  INQUIRY_RESPONSES ||--o{ INQUIRY_APPROVALS : "고위험시 승인요청"
  PROPERTIES ||--|| FINANCIAL_CONFIGS : "숙소별 수수료설정"
  PROPERTIES ||--o{ MONTHLY_SETTLEMENTS : "월별 정산 스냅샷"
  RESERVATIONS ||--o{ ACTION_ITEMS : "규칙기반 알림 생성"
  CLEANING_TASKS ||--o{ ACTION_ITEMS : "청소지연시 알림"

  PROPERTIES {
    bigserial property_id PK
    varchar name
    time checkin_time "체크인 N시간전 알림 계산용"
    boolean weekday_adjustment_enabled "공백일 미세조정 on/off (v1.2)"
    boolean holiday_adjustment_enabled "성수기 방치감지 on/off (v1.2)"
  }
  RESERVATIONS {
    bigserial reservation_id PK
    bigint property_id FK
    date check_in
    date check_out
    enum reservation_status "PENDING·CONFIRMED·MODIFIED·CANCELLED·COMPLETED (MODIFIED는 EXCLUDE 조건절에도 포함)"
    enum refund_status "NONE·PARTIAL·FULL - 상태와 분리"
    enum financial_status "ESTIMATED·CONFIRMED·MANUALLY_ADJUSTED"
    integer gross_amount "iCal 기반 추정치"
  }
  CLEANING_TASKS {
    bigserial task_id PK
    bigint reservation_id FK "UNIQUE, 예약당 1건"
    enum task_status "PENDING~COMPLETED·VERIFIED 둘다 완료취급"
    boolean amenity_shortage
    jsonb photo_urls "완료사진 누적(append, v1.3)"
  }
  INQUIRIES {
    bigserial inquiry_id PK
    bigint reservation_id FK "nullable - 사전문의(v1.3)"
    bigint property_id FK "단독FK - 격리 방어선(v1.3)"
    text message
  }
  INQUIRY_CLASSIFICATIONS {
    bigserial classification_id PK
    bigint inquiry_id FK "UNIQUE, 1:1"
    enum risk_level "LOW·MEDIUM·HIGH"
  }
  INQUIRY_RESPONSES {
    bigserial response_id PK
    bigint inquiry_id FK
    boolean is_latest "재시도 대응용 부분UNIQUE"
  }
  INQUIRY_APPROVALS {
    bigserial approval_id PK
    bigint response_id FK
    enum status "PENDING·APPROVED·REJECTED"
  }
  FINANCIAL_CONFIGS {
    bigserial config_id PK
    bigint property_id FK
    numeric commission_rate "기본 0.155"
  }
  MONTHLY_SETTLEMENTS {
    bigserial settlement_id PK
    bigint property_id FK
    numeric applied_commission_rate "정산당시 값 스냅샷 - Config와 직접FK 없음"
  }
  ACTION_ITEMS {
    bigserial action_id PK
    bigint property_id FK
    bigint reservation_id FK "복합FK(reservation_id,property_id) - 교차숙소 차단(v1.3)"
    enum risk_level "RED_NOW·YELLOW_TODAY·GREEN_AUTO(규칙기반, AI판단 아님)"
    enum status "OPEN·RESOLVED·AUTO_RESOLVED"
  }
```
