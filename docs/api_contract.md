# Host ON (AI) — API Contract v2.3 (9/9 인증 스펙 확정)

> `docs/3rd_host_ai_db_spec_v1.md`(**v1.3**) 16개 테이블을 기준으로 작성.
> **v2.2→v2.3 변경 (9/9 인증 설계 — 코드가 먼저 있고 설계가 나중인 역순 상황)**:
> 1. **401과 404의 경계 명시**(0절). 그동안 "소유권 불일치와 부존재를
>    404로 통일"만 있었고 **401을 언제 쓰는지가 없었다.** 권한 문제에
>    401을 반환하면 프론트가 세션 만료로 오인해 로그아웃시킨다.
>    로그인 실패(`INVALID_CREDENTIALS`)와 세션 만료(`UNAUTHORIZED`)를
>    코드로 구분해, 프론트의 두 갈래 처리(9/8 구현)와 맞췄다.
> 2. **1절 인증 스펙 전면 확정**(1.1~1.4절). 기존 1절은 표 3행과
>    `POST /auth/login` 예시 하나뿐이었고 signup·me 스펙, 토큰 만료,
>    비밀번호 정책, 에러 코드가 전부 없었다.
> 3. 로그인·회원가입 응답을 **`{ access_token, token_type, host }`**로
>    통일. 기존 예시는 `host_id`·`name`을 평면으로 두고 `token_type`이
>    없었다. 프론트 axios 인터셉터가 봉투를 전제로 언래핑하도록 이미
>    구현돼 있어(9/8) 봉투 자체는 변경 없다.
> 4. 만료 **1440분(24시간)**, **리프레시 토큰 미제공**, 비밀번호
>    **8~72자**(bcrypt 72바이트 절삭), 에러 코드 5종 확정.
> 5. 회원가입 성공 시 **토큰을 함께 반환**해 바로 로그인 상태가 된다.
> 6. `GET /auth/me` 스펙 확정(1.4절) — 새로고침 시 사용자 정보 복원용.
>    **401과 네트워크 오류를 구분**해, 후자에서는 토큰을 지우지 않는다.
>    Render 슬립·재시작이 잦아 구분하지 않으면 서버가 잠깐 불안정한
>    것만으로 로그아웃된다.
> 7. **로그아웃 서버 엔드포인트를 만들지 않는다**(1.5절). JWT가 무상태라
>    발급된 토큰을 무효화할 수 없다. 프론트에서 토큰을 지운다.
> 8. 비밀번호를 **8~64자 + UTF-8 72바이트 이하**로 확정(1.1절). 한글은
>    한 글자가 3바이트라 25자만 넘어도 bcrypt 한계를 초과하므로 글자 수
>    검증만으로는 못 막는다. `PASSWORD_TOO_LONG` 코드 추가.
> 9. **`OAuth2PasswordRequestForm`을 쓰지 않는다**(1.6절). 폼 인코딩과
>    평면 응답이 우리 JSON·봉투 계약과 어긋난다.
> 10. 시연 전 재로그인 지침(1.7절).
> **DB 스키마 변경 없음** — `host` 3필드는 전부 `HOSTS` 실재 컬럼이다.
> **v2.1→v2.2 변경 (9/8 컴플라이언스 화면 배치 변경)**:
> 1. 10절에 **호출 위치 명시** — `/settings` 인허가 탭과 액션센터 카드
>    양쪽에서 호출된다. `/compliance` 전용 화면을 `/settings` 4번째
>    탭으로 흡수했다(`docs/ui_design.md` 2절, 라우트 12→11).
>    **엔드포인트·요청·응답은 하나도 바뀌지 않았다.** 화면 배치만 바뀐
>    것이므로 기능 축소가 아니다.
> 2. `POST /properties/{property_id}/checklist-items`는 **필요하다는 것만
>    확정**하고 요청 스펙은 구현 시점(10/1~07)으로 미뤘다. 미정의 항목으로
>    10절에 기록.
> **v2.0→v2.1 변경 (9/8 응답 스펙 미정의 건 해소)**:
> 1. `GET /properties/{property_id}/rooms`·`GET /rooms/{room_id}/beds`
>    **응답 스펙 신규 확정**(2.1·2.2절). 9/13 구현 선행 작업.
>    `bookable_unit_type`이 `PROPERTY`인 숙소는 **빈 배열이 정상**임을
>    명시하고, 침대 목록의 정식 경로가 `/properties/{id}/beds`가 아니라
>    `/rooms/{room_id}/beds`임을 확인(`BEDS`에 `property_id` 컬럼 없음).
> 2. `GET`·`POST /properties/{property_id}/channels` **응답·요청 스펙
>    신규 확정**(3.1·3.2절). 9/10 구현 선행 작업.
> 3. **`ical_url`을 원문으로 노출하지 않고 마스킹**(`ical_url_masked`).
>    iCal export URL은 인증 없이 예약 일정 전체를 읽을 수 있는 비밀
>    URL이라 자격증명에 준해 다룬다.
> 4. `rooms`·`beds`·`channels` 세 목록 모두 **`meta` 없음**. 0절 규약의
>    예외이며, 근거는 건수가 아니라 용도(선택지 입력)와 구조적 상한
>    (`channel_enum` 3값 × `UNIQUE(property_id, channel)`)이다.
> 5. `400 ICAL_URL_REQUIRED`·`400 INVALID_CHANNEL` 신규 에러 코드.
>    **DB 스키마 변경 없음** — 세 절의 모든 필드가 기존 컬럼이다.
> **v1.9→v2.0 변경 (9/8 대시보드 구현 선행 작업)**:
> 1. **목록 응답 `meta` 규약 신설**(0절). `?page`/`size` 파라미터는 있었으나
>    응답에 총건수·페이지 정보를 담는 방법이 없었다. `GET /properties`는
>    구조적으로 페이지네이션 대상이 아니므로 예외로 명시.
> 2. `GET /properties/{property_id}/action-items` **응답 스펙 신규 확정**(9절).
>    9필드 전부 `ACTION_ITEMS` 실재 컬럼이며 파생 필드 없음. 정렬·쿼리
>    파라미터·`category` 값 현황·생성 경로도 함께 기록.
> 3. `PATCH /action-items/{id}/resolve` **요청·응답 스펙 확정**(9절).
>    `status`는 항상 `RESOLVED`로 전이하며, **가격 계열 액션에는 400으로
>    거부하는 서버 가드**를 둔다.
> 4. 가격 추천 카드 승인 시 호출 경로 명시(13절) — `resolve`가 아니라 `apply`.
> **v1.8→v1.9 변경 (9/7 크로스체크에서 발견)**:
> 1. `conflict_count`를 **키 고정·값 nullable** 계약으로 정정(4.1절).
>    v1.8은 "계산 실패 시 필드를 생략"이라고 적었으나 같은 절이 "응답
>    11필드"를 명시하고 있어 모순이었다.
> 2. `today_turnover_count` 집계 시 **`IS NOT DISTINCT FROM`** 사용을
>    명시(4.1절). PROPERTY 단위 예약은 `room_id`/`bed_id`가 NULL이라
>    일반 등호 비교로는 집계되지 않는다.
> **v1.7→v1.8 변경 (9/7 UI/UX 설계 중 확정)**:
> 1. `GET /properties/{property_id}/dashboard/summary` **응답 스펙 신규 확정**(4절).
>    9/7 확인 결과 이 엔드포인트는 표 한 행만 있고 응답 스펙이 문서 어디에도
>    없었다. 이 문서가 응답 스펙의 원본(SSOT)이 된다. 필드 11개 전부 기존
>    컬럼 집계이며 **DB 스키마 변경 없음**.
> 2. `GET /properties` **응답 스펙 신규 확정**(2절). 마찬가지로 응답 예시가
>    없던 엔드포인트다.
> 3. **통합 대시보드 조회 방식 명시**(4절) — 교차 숙소 집계 엔드포인트를
>    추가하지 않고 프론트가 N병렬 호출 후 합산한다.
> **v1.6→v1.7 변경 (9/5 예약 서비스 레이어 구현 중 확정)**:
> 1. 교차 판매단위 기간 충돌 에러를 `409 RESERVATION_OVERLAP`으로 명시(4절).
>    DB EXCLUDE가 같은 단위끼리만 막는다는 사실은 명세서에 있었으나,
>    그때 무엇을 반환할지가 API Contract에 없어 구현 시 새로 확정했다.
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
- **목록 응답 메타 규약 (v2.0 신설)**: **페이지네이션 파라미터(`page`,
  `size`)를 지원하는 컬렉션 엔드포인트**는 `meta` 객체를 포함한다.
  ```json
  { "data": [ ... ],
    "meta": { "total": 47, "page": 1, "size": 20 },
    "error": null }
  ```
  근거: 부분만 받아온 응답에서 `data` 길이로는 전체 건수를 알 수 없다.

  > **예외**: 목록이 아니라 **전체 컬렉션을 반환하는 것이 API의 목적**인
  > 엔드포인트는 `meta`를 생략하고 기존 형식을 유지한다.
  >
  > 해당 예 — **`GET /properties`**: `PropertySwitcher` 드롭다운과 대시보드
  > 병렬 호출의 **입력**으로서 항상 전체를 반환해야 하므로 페이지네이션이
  > 구조적으로 적용될 수 없다. 일부만 받으면 전환 목록에 숙소가 누락되고
  > 대시보드 합산에서도 빠진다.
  >
  > 이 예외는 **건수가 적어서가 아니라 용도 때문**이다. 향후 숙소 수가 크게
  > 늘어 목록 자체를 페이지네이션해야 할 상황이 오면 이 문장을 근거로
  > 재검토한다.
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
- **401과 404의 경계 (v2.3 신설)** — 두 코드는 **원인이 다르고 프론트의
  대응도 다르다.** 섞이면 사용자가 이유 없이 로그아웃된다.

  | HTTP | code | 언제 |
  |---|---|---|
  | **401** | `UNAUTHORIZED` | **인증 자체가 실패한 경우에만.** 토큰이 없거나, 만료됐거나, 서명이 유효하지 않다 |
  | **401** | `INVALID_CREDENTIALS` | 로그인 시 이메일·비밀번호가 틀렸다(1절) |
  | **404** | `RESOURCE_NOT_FOUND` | **인증은 유효하나** 그 리소스가 없거나 내 것이 아니다. 두 상황을 구분하지 않는다 |
  | 403 | — | **쓰지 않는다.** "권한이 없다"를 알려주는 순간 리소스 존재 여부가 노출된다 |

  > ⚠️ **백엔드 구현 시 이 경계를 반드시 지킨다.** 권한 문제에 401을
  > 반환하면 프론트가 **세션 만료로 오인해 토큰을 지우고 로그아웃시킨다.**
  > 남의 숙소 id를 한 번 잘못 눌렀을 뿐인데 로그인이 풀린다.

  **프론트의 401 처리는 두 갈래다(9/8 구현 확정).**

  | 대상 | 인스턴스 | 동작 |
  |---|---|---|
  | 일반 API | `client` / `api` | 토큰을 지우고 `/login`으로 **리다이렉트**(세션 만료). 이미 `/login`이면 리다이렉트하지 않는다 — 무한 루프 방지 |
  | 로그인·회원가입 | `authClient` / `authApi` | **리다이렉트하지 않는다.** 호출부가 `try/catch`로 잡아 화면에 메시지만 표시한다 |

  > 같은 401이지만 **로그인 실패는 "다시 입력하세요"이고 세션 만료는
  > "다시 로그인하세요"**다. 전자에 리다이렉트를 걸면 로그인 화면에서
  > 로그인 화면으로 튕기는 것처럼 보인다. 그래서 인스턴스를 나눴다
  > (`frontend/src/api/client.ts`). `code`가 다르므로 서버 응답만으로도
  > 구분할 수 있다.

---

## 1. 인증 (HOSTS)

| Method | Endpoint | 설명 |
|---|---|---|
| POST | `/auth/signup` | 회원가입 |
| POST | `/auth/login` | 로그인, JWT 발급 |
| GET | `/auth/me` | 현재 로그인한 호스트 정보 |

### 1.1 공통 — `host` 객체와 토큰 (v2.3 신규 확정)

**모든 인증 응답은 0절의 공통 봉투를 그대로 쓴다.** 예외를 두지 않는다 —
프론트의 axios 응답 인터셉터가 봉투를 전제로 언래핑하도록 이미 구현돼
있고(`frontend/src/api/client.ts`, 9/8), 형태가 둘이면 호출부가 두 가지를
다뤄야 한다.

**`host` 객체 3필드** — `HOSTS` 실재 컬럼이며 `password_hash`는 **절대
포함하지 않는다.**

| 필드 | 출처 | 비고 |
|---|---|---|
| `host_id` | `HOSTS.host_id` | |
| `email` | `HOSTS.email` | `UNIQUE NOT NULL` |
| `name` | `HOSTS.name` | `VARCHAR(100) NOT NULL` — 이미 존재하는 컬럼이다(명세서 2.1절) |

> `created_at`은 내리지 않는다 — 화면에서 쓰는 곳이 없다.

**토큰**

| 항목 | 값 | 근거 |
|---|---|---|
| 형식 | JWT (HS256) | `config.py` `JWT_ALGORITHM` |
| 만료 | **1440분 = 24시간** | `config.py` `ACCESS_TOKEN_EXPIRE_MINUTES = 1440` |
| 전달 | `Authorization: Bearer <token>` | 0절 |
| `token_type` | 항상 `"bearer"` | 응답에 포함하되 **프론트는 `Bearer`를 하드코딩**한다(client.ts) |

> **리프레시 토큰은 이번 범위에서 제공하지 않는다.** 만료되면 재로그인한다.
> 24시간이면 하루 운영에 무리가 없고, 리프레시를 넣으면 회전·폐기·저장소를
> 함께 설계해야 한다. P1에서 httpOnly 쿠키 전환과 묶어 검토한다.

**비밀번호 정책**: **8자 이상 64자 이하.** 문자 조합은 강제하지 않는다.

> **bcrypt는 72바이트를 넘는 입력을 조용히 잘라낸다.** 검증에서 거부하지
> 않으면 사용자는 긴 비밀번호를 썼다고 믿지만 실제 강도는 72바이트에서
> 멈추고, 73자째부터는 무엇을 넣어도 같은 해시가 된다. **원인을 알 수
> 없는 종류의 문제**이므로 반드시 명시적으로 거부한다.
>
> 조합 강제를 넣지 않는 이유: 1인 운영자용이고, 규칙이 늘수록 재입력
> 실패만 늘어난다.

**검증은 프론트와 백엔드가 서로 다른 기준으로 한다.**

| 계층 | 기준 | 이유 |
|---|---|---|
| 프론트 | **글자 수 8~64자** | 입력 중 즉시 피드백. 바이트 길이는 사용자가 체감할 수 없는 단위다 |
| 백엔드 | 위에 더해 **UTF-8 인코딩 후 72바이트 이하** | bcrypt의 실제 한계. 글자 수만으로는 못 막는다 |

> ⚠️ **글자 수 상한 64자로는 부족하다.** 한글은 UTF-8에서 한 글자가
> **3바이트**라 **25자만 넘어도 72바이트를 초과**한다(25×3 = 75).
> 즉 "8~64자" 규칙을 통과한 한글 비밀번호가 bcrypt에서 잘릴 수 있다.
> 백엔드의 바이트 검증은 프론트 검증의 중복이 아니라 **다른 조건**이다.
>
> **어느 쪽도 조용히 자르지 않는다.** 초과분을 잘라서 저장하면 사용자는
> 자기가 입력한 비밀번호로 다시 로그인할 수 없는 상황을 만나고 원인을
> 알 수 없다.

**에러 코드**

| HTTP | code | 조건 |
|---|---|---|
| 401 | `INVALID_CREDENTIALS` | 로그인 시 이메일 또는 비밀번호 불일치. **어느 쪽인지 구분하지 않는다** |
| 401 | `UNAUTHORIZED` | 토큰 없음·만료·서명 무효(0절) |
| 409 | `EMAIL_ALREADY_EXISTS` | 회원가입 시 이메일 중복(`UNIQUE` 제약과 일치) |
| 400 | `INVALID_EMAIL_FORMAT` | 이메일 형식 위반 |
| 400 | `INVALID_PASSWORD_FORMAT` | **글자 수** 8자 미만 또는 64자 초과 |
| 400 | `PASSWORD_TOO_LONG` | **UTF-8 바이트 길이** 72바이트 초과(백엔드 전용 판정) |

> `INVALID_CREDENTIALS`가 이메일/비밀번호를 구분하지 않는 이유: 구분하면
> 이메일만 바꿔가며 **가입된 계정을 열거**할 수 있다. 화면 문구도 하나로
> 통일한다(`docs/ui_design.md` 4-1절).

### 1.2 POST /auth/login

```json
// Request
{ "email": "host@example.com", "password": "..." }

// Response 200
{
  "data": {
    "access_token": "eyJ...",
    "token_type": "bearer",
    "host": { "host_id": 1, "email": "host@example.com", "name": "신경주" }
  },
  "error": null
}
```

| HTTP | code |
|---|---|
| 401 | `INVALID_CREDENTIALS` |
| 400 | `INVALID_EMAIL_FORMAT` |

### 1.3 POST /auth/signup

**가입 성공 시 토큰을 함께 반환해 곧바로 로그인 상태가 된다.** 가입 직후
다시 로그인하게 하면 같은 정보를 두 번 입력하게 되고, 화면 흐름도
`/signup → /onboarding`(ui_design 4-2절)이라 중간에 `/login`이 끼어들 자리가
없다.

```json
// Request
{ "email": "host@example.com", "password": "...", "name": "신경주" }

// Response 201  — 1.2와 동일한 구조
{
  "data": {
    "access_token": "eyJ...",
    "token_type": "bearer",
    "host": { "host_id": 1, "email": "host@example.com", "name": "신경주" }
  },
  "error": null
}
```

| 필드 | 필수 | 비고 |
|---|---|---|
| `email` | ✅ | |
| `password` | ✅ | 8~64자 + UTF-8 72바이트 이하(1.1절) |
| `name` | ✅ | **`HOSTS.name`이 `NOT NULL`이므로 선택이 될 수 없다.** 값을 받지 않으면 서버가 무엇을 채울지 정해야 하는데, 그런 기본값을 두지 않는다 |

| HTTP | code |
|---|---|
| 409 | `EMAIL_ALREADY_EXISTS` |
| 400 | `INVALID_EMAIL_FORMAT` / `INVALID_PASSWORD_FORMAT` / `PASSWORD_TOO_LONG` |

### 1.4 GET /auth/me

**왜 필요한가**: 토큰은 `localStorage`에 남지만 **메모리의 사용자 정보는
새로고침하면 사라진다.** 앱 진입 시 이 엔드포인트로 **토큰이 아직
유효한지 확인하고 사용자 정보를 복원**한다. 토큰을 디코딩해 이름을 꺼내
쓰지 않는다 — 만료·서명 검증은 서버만 할 수 있다.

**요청**: `Authorization: Bearer <token>` 헤더만. **바디 없음.**

```json
// Response 200
{ "data": { "host_id": 1, "email": "host@example.com", "name": "신경주" },
  "error": null }
```

`host` 객체(1.1절)를 그대로 반환한다.

**앱 진입 시 호출 순서**

```
웨이크업 게이트(GET /health)  →  토큰이 있으면 GET /auth/me  →  라우터 렌더
```

> 웨이크업이 **먼저**다. 슬립 중인 서버에 `/auth/me`를 보내면 콜드 스타트
> 타임아웃으로 실패하고, 아래 "네트워크 오류" 경로로 빠져 첫 진입마다
> 재시도 화면을 보게 된다(11절 웨이크업 게이트).
> 토큰이 아예 없으면 `/auth/me`를 호출하지 않고 바로 `/login`이다.

**실패 처리 — 401과 네트워크 오류를 반드시 구분한다**

| 실패 유형 | 토큰 | 화면 |
|---|---|---|
| **401 `UNAUTHORIZED`** | **지운다** | `/login`으로 이동 |
| **네트워크 오류·타임아웃**(응답 자체가 없음) | **지우지 않는다** | "서버와 연결할 수 없습니다" + **[다시 시도]** |

> ⚠️ **이 둘을 구분하지 않으면 서버가 잠깐 불안정한 것만으로 사용자가
> 로그아웃된다.** Render 무료 플랜은 15분 무요청 시 슬립하고 재시작도
> 잦으므로 **실제로 발생한다.** 토큰은 멀쩡한데 서버가 응답하지 못한
> 것뿐이고, 지워버리면 서버가 돌아온 뒤에도 다시 로그인해야 한다.
>
> 판정 기준은 프론트의 재시도 로직과 같다 — `error.response`가 없으면
> 네트워크 오류다(`frontend/src/api/client.ts`의 `isRetryable`).

### 1.5 로그아웃 — 서버 엔드포인트를 만들지 않는다

**`POST /auth/logout` 같은 엔드포인트를 두지 않는다.**

> **JWT는 무상태(stateless)이므로 서버가 이미 발급한 토큰을 무효화할 수
> 없다.** 무효화하려면 폐기 목록(블랙리스트)을 서버에 저장하고 요청마다
> 조회해야 하는데, 그 순간 무상태의 이점이 사라지고 저장소·만료 정리까지
> 함께 설계해야 한다.

로그아웃은 **프론트에서 처리한다** — `localStorage`의 토큰을 지우고
(`clearAccessToken()`) `/login`으로 이동한다. 진입점은 Header의 계정
메뉴다(`docs/ui_design.md` 5절).

> ⚠️ **한계**: 토큰이 탈취된 경우 **만료(24시간) 전까지 유효하다.**
> 로그아웃해도 그 토큰 자체는 살아 있다. 리프레시 토큰과 블랙리스트를
> 두지 않은 이번 범위의 한계이며, P1 확장 시 httpOnly 쿠키 전환과 함께
> 검토한다.

### 1.6 구현 주의 (9/11 인증 구현 대비)

**`OAuth2PasswordRequestForm`을 쓰지 않는다.**

FastAPI 예제에서 흔히 쓰이지만 **우리 계약과 두 군데가 어긋난다.**

| 항목 | 표준 OAuth2 폼 | 이 프로젝트 |
|---|---|---|
| 요청 | `application/x-www-form-urlencoded`, 필드명 **`username`**·`password` | **JSON 바디**, 필드명 **`email`**·`password` |
| 응답 | `{ "access_token": "...", "token_type": "bearer" }` **평면** | 0절 **봉투** `{ data, error }` |

그대로 쓰면 프론트가 `Content-Type: application/json`으로 보내는 요청을
받지 못하고(client.ts 기본 헤더), 응답도 봉투를 벗기는 인터셉터와
어긋난다. **Pydantic 스키마로 JSON 바디를 받고 응답도 직접 구성한다.**

> 이 API는 우리 프론트만 사용하므로 표준 폼을 벗어나도 문제되지 않는다.
> 외부 OAuth2 클라이언트를 받을 계획이 없다.
>
> ※ **`OAuth2PasswordBearer`(요청 헤더에서 토큰을 꺼내는 의존성)는 그대로
> 써도 된다.** 그것은 토큰 추출용이라 응답 형식과 무관하다. 다만
> `tokenUrl` 인자는 Swagger UI 표시용일 뿐 실제 동작에 관여하지 않는다.

### 1.7 시연 전 확인 (10/12 발표 대비)

> **발표·시연 전에는 반드시 재로그인해 토큰을 갱신한다.** 만료가
> 24시간이므로 **전날 로그인한 상태로 시연하면 도중에 만료**되어 화면이
> `/login`으로 튄다. 리프레시 토큰이 없어 자동 연장되지 않는다(1.1절).

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

**GET /properties 응답 예시 (v1.8 신규 확정)**

```json
{
  "data": [
    { "property_id": 1, "name": "강남 3룸 독채",
      "accommodation_type": "URBAN_HOMESTAY", "bookable_unit_type": "PROPERTY" },
    { "property_id": 2, "name": "홍대 호스텔",
      "accommodation_type": "HOSTEL", "bookable_unit_type": "BED" }
  ],
  "error": null
}
```

| 필드 | 출처 | 용도 |
|---|---|---|
| `property_id` | `PROPERTIES.property_id` | 라우팅 키, 대시보드 병렬 호출 대상 식별 |
| `name` | `PROPERTIES.name` | PropertySwitcher 드롭다운 표시 텍스트 |
| `accommodation_type` | `PROPERTIES.accommodation_type` | 동명 숙소 구분 + 유형 뱃지 표시 |
| `bookable_unit_type` | `PROPERTIES.bookable_unit_type` | **예약 생성 모달이 room_id/bed_id 필수 여부를 이 값으로 분기**한다 |

> `bookable_unit_type`을 목록에 포함하는 이유: 4절의 400 에러 3종
> (`INVALID_UNIT_HIERARCHY`/`ROOM_ID_REQUIRED`/`BED_ID_REQUIRED`)이 전부 이 값을
> 기준으로 판정되므로, 목록에 없으면 예약 모달을 열 때마다 숙소 상세를
> 재호출해야 한다.
>
> `address`·`base_price`·`lower_bound_price`·`checkin_time`·`checkout_time`·
> `*_adjustment_enabled`는 **포함하지 않는다** — `/settings` 화면 소관이며,
> 드롭다운에는 쓰이지 않는다.
>
> **요약 지표(오픈 액션 수·오늘 체크인 건수 등)를 이 응답에 넣지 않는다.**
> 4절 `dashboard/summary`가 "캐싱 없이 매요청 실시간 집계 — 개별 API와 항상
> 일치 보장"을 명시하고 있어, 같은 지표를 목록 API에도 두면 두 API가 서로
> 다른 시점의 값을 반환해 그 보장이 깨진다.

### 2.1 GET /properties/{property_id}/rooms 응답 스펙 (v2.1 신규 확정)

> 9/8 확인 결과 2절 표에 한 행만 있고 응답 스펙이 없었다
> (troubleshooting 23번). 9/13 객실·침대 관리 구현의 선행 작업으로
> 확정한다. **필드는 전부 `ROOMS` 실재 컬럼이며 DB 스키마 변경은 없다.**

**이 엔드포인트가 의미를 갖는 조건**

`bookable_unit_type`이 **`ROOM` 또는 `BED`인 숙소에서만** 의미가 있다.
`PROPERTY` 단위 숙소(독채 통대여)는 객실을 나누어 팔지 않으므로
**`rooms`가 비어 있는 것이 정상 상태**다.

| `bookable_unit_type` | 기대 응답 |
|---|---|
| `PROPERTY` | `"data": []` — **정상**이다. 404가 아니다 |
| `ROOM` | 객실 N건 |
| `BED` | 객실 N건(각 객실 하위에 침대가 있음) |

> **빈 배열을 에러나 EMPTY 상태로 처리하지 않는다.** PROPERTY 숙소에서
> 객실이 0건인 것은 데이터가 없는 것이 아니라 **그 숙소에 객실 개념이
> 없는 것**이다. 등록을 유도하는 EmptyState를 띄우면 안 된다
> (`docs/ui_design.md` 5절 `EmptyState`는 "데이터 0건 안내"용이다).

**용도**: 캘린더의 **예약 생성 모달이 `room_id` 선택지를 채울 때** 쓴다
(`docs/ui_design.md` 4-5절). 모달은 `bookable_unit_type`이 `ROOM`이면
`room_id`를, `BED`면 `room_id`+`bed_id`를 필수로 요구하며, 값이 없거나
계층이 어긋나면 4절의 400 3종(`INVALID_UNIT_HIERARCHY` /
`ROOM_ID_REQUIRED` / `BED_ID_REQUIRED`)이 반환된다. 온보딩 위저드
(`docs/ui_design.md` 4-3절)도 등록 직후 결과 확인에 같은 응답을 쓴다.

```json
{
  "data": [
    { "room_id": 11, "room_name": "101호", "capacity": 4 },
    { "room_id": 12, "room_name": "102호", "capacity": 2 },
    { "room_id": 13, "room_name": "201호", "capacity": null }
  ],
  "error": null
}
```

| 필드 | 출처 | 비고 |
|---|---|---|
| `room_id` | `ROOMS.room_id` | 예약 생성 시 `room_id`로 그대로 전달 |
| `room_name` | `ROOMS.room_name` | 선택지 표시 텍스트. 같은 숙소 안에서 유일(`UNIQUE(property_id, room_name)`) |
| `capacity` | `ROOMS.capacity` | **nullable 컬럼이므로 `null`이 올 수 있다.** 미입력 상태이며 0명이라는 뜻이 아니다 |

> `property_id`는 **응답에 넣지 않는다** — 경로에 이미 있다.
> `created_at`도 넣지 않는다 — 선택지를 채우는 것이 이 API의 용도이며
> 등록 시각을 쓰는 화면이 없다.
>
> **`capacity`의 `null`과 `0`을 화면에서 구분한다.** `null`은 "미입력",
> `0`은 있을 수 없는 값이다(4.1절 `conflict_count`와 같은 취급).

**meta 없음** — 0절 규약상 `meta`는 페이지네이션 파라미터(`page`·`size`)를
지원하는 컬렉션에만 붙는다. 이 엔드포인트는 **예약 모달 선택지의 입력**
이므로 항상 전체를 반환해야 한다. 일부만 받으면 존재하는 객실이 선택지에서
누락되어 예약을 만들 수 없다. `GET /properties`와 **같은 이유의 예외**다.

### 2.2 GET /rooms/{room_id}/beds 응답 스펙 (v2.1 신규 확정)

> **경로 주의**: 침대 목록의 정식 경로는 `/properties/{id}/beds`가 아니라
> **`/rooms/{room_id}/beds`**다(위 2절 표). `BEDS`에는 `property_id`
> 컬럼이 없고 `room_id`만 있으므로(DB명세서 2.4절), 숙소 단위로 침대를
> 직접 조회하는 경로는 존재하지 않는다.

`bookable_unit_type`이 **`BED`인 숙소에서만** 의미가 있다. `ROOM` 단위
숙소의 객실은 침대를 나누어 팔지 않으므로 빈 배열이 정상이다.

```json
{
  "data": [
    { "bed_id": 101, "bed_label": "A" },
    { "bed_id": 102, "bed_label": "B" }
  ],
  "error": null
}
```

| 필드 | 출처 | 비고 |
|---|---|---|
| `bed_id` | `BEDS.bed_id` | 예약 생성 시 `bed_id`로 그대로 전달 |
| `bed_label` | `BEDS.bed_label` | 같은 객실 안에서 유일(`UNIQUE(room_id, bed_label)`) |

> `room_id`·`created_at`은 넣지 않는다(2.1절과 같은 이유).
> `meta`도 없다(같은 이유).

**소유권 검증**: 이 경로에는 `property_id`가 없다. 0절 규칙에 따라 조회
쿼리 자체에 소유권 조건을 묶는다.

```sql
SELECT b.* FROM beds b
JOIN rooms r ON b.room_id = r.room_id
JOIN properties p ON r.property_id = p.property_id
WHERE b.room_id = :room_id AND p.host_id = :current_host_id
```

> 타인 소유 `room_id`와 존재하지 않는 `room_id`를 **구분하지 않고**
> 둘 다 `404 RESOURCE_NOT_FOUND`를 반환한다(403 금지 — 0절).
>
> ⚠️ **빈 배열과 404를 혼동하지 않는다.** 내 소유 객실인데 침대가 없으면
> `200 + "data": []`, 남의 객실이거나 없는 객실이면 `404`다.

> **POST 요청 바디(`POST /properties/{id}/rooms`,
> `POST /rooms/{room_id}/beds`)는 이 절에서 정의하지 않았다.** 9/13 객실·
> 침대 관리 구현 시 확정한다. 표에 행이 있다는 것이 요청 스펙이 정의됐다는
> 뜻은 아니다(troubleshooting 23번의 교훈).

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

### 3.1 GET /properties/{property_id}/channels 응답 스펙 (v2.1 신규 확정)

> 9/8 확인 결과 3절 표에 한 행만 있고 응답 스펙이 없었다
> (troubleshooting 23번). 9/10 채널 연동 구현의 선행 작업으로 확정한다.
> **필드는 전부 `CHANNEL_CONNECTIONS` 실재 컬럼이며 DB 스키마 변경은 없다.**

```json
{
  "data": [
    { "connection_id": 7, "channel": "AIRBNB",
      "ical_url_masked": "https://www.airbnb.com/calendar/ical/****.ics?s=****7890",
      "external_property_id": "12345678",
      "sync_status": "SYNCED",
      "last_synced_at": "2026-09-09T03:00:00Z",
      "last_error_message": null,
      "created_at": "2026-08-31T10:12:00Z" },
    { "connection_id": 8, "channel": "BOOKING_COM",
      "ical_url_masked": "https://ical.booking.com/v1/export?t=****cd12",
      "external_property_id": null,
      "sync_status": "FAILED",
      "last_synced_at": "2026-09-09T03:00:00Z",
      "last_error_message": "iCal URL 응답 없음(timeout 5s)",
      "created_at": "2026-09-02T09:40:00Z" }
  ],
  "error": null
}
```

| 필드 | 출처 | 비고 |
|---|---|---|
| `connection_id` | `CHANNEL_CONNECTIONS.connection_id` | `DELETE /channels/{id}`·`POST /channels/{id}/sync` 호출 키 |
| `channel` | `.channel` | `AIRBNB` / `BOOKING_COM` / `NAVER` 3값 |
| `ical_url_masked` | `.ical_url`의 **마스킹 표현** | 원본을 그대로 내리지 않는다 — 아래 별도 항목 참조 |
| `external_property_id` | `.external_property_id` | nullable. OTA 측 숙소 식별자 |
| `sync_status` | `.sync_status` | `SYNCING` / `SYNCED` / `FAILED` / `STALE` 4값 |
| `last_synced_at` | `.last_synced_at` | **컬럼명은 `last_sync_at`이 아니라 `last_synced_at`이다.** nullable(최초 동기화 전) |
| `last_error_message` | `.last_error_message` | `sync_status`가 `FAILED`가 아니면 항상 `null`(v1.3 운용 규칙) |
| `created_at` | `.created_at` | 연동 등록 시각 |

> `property_id`는 응답에 넣지 않는다 — 경로에 이미 있다.

**meta 없음 — 이 엔드포인트는 페이지네이션 대상이 아니다**

0절 규약상 `meta`는 `page`·`size`를 지원하는 컬렉션에만 붙는다. 이
엔드포인트는 지원하지 않으므로 `meta`도 없다.

> **근거는 "건수가 적어서"가 아니라 구조적 상한이다.** `channel_enum`은
> 값이 3개(`AIRBNB`/`BOOKING_COM`/`NAVER`)이고 DB에
> `UNIQUE(property_id, channel)`이 걸려 있어(DB명세서 2.5절, "MVP: 채널당
> 연결 1개로 제한") **숙소당 행 수의 상한이 3으로 고정**된다. 페이지를
> 나눌 대상 자체가 생길 수 없다.
>
> 또한 `/settings` 채널연동 탭은 3개 채널의 연동 여부를 **한 화면에 모두**
> 보여주므로(`docs/ui_design.md` 2-11·4-11절), 일부만 받으면 "연동 안 됨"과
> "이번 페이지에 없음"을 구분할 수 없게 된다. `GET /properties`와 같은
> 계열의 예외다.
>
> 향후 `channel_enum`에 값이 대폭 추가되면 이 문장을 근거로 재검토한다.

**`ical_url`을 원문 그대로 노출하지 않는다 (마스킹)**

`ical_url`은 **인증 없이 접근 가능한 비밀 URL**이다. Airbnb·Booking.com의
iCal export URL은 URL 자체가 자격증명 역할을 해서, 값을 아는 사람은
누구나 그 숙소의 **예약 일정 전체(체크인·체크아웃 날짜, 예약 건수)를
읽을 수 있다.** 로그인도 토큰도 필요 없다.

| 판단 근거 | 내용 |
|---|---|
| CLAUDE.md 백업규칙 3·7번 | `.env`·API 키·비밀번호는 커밋·노출 금지 — iCal URL은 성격이 같다 |
| CLAUDE.md 코딩규칙 12번 | 외부로 나가는 텍스트에서 민감정보를 제거한다는 같은 취지 |
| 이 문서 3절 기존 규칙 | `sync-errors` 응답에 이미 *"스택트레이스나 내부 URL은 이 필드에 넣지 않는다(정보노출 방지)"* — **같은 문서 안의 선례** |

> **소유권 검증을 통과한 호스트 본인 요청인데 왜 가리는가**: 응답은
> 요청자만 보는 것이 아니라 브라우저 개발자도구·네트워크 로그·스크린샷·
> 화면공유에 그대로 남는다. **10/12 발표 영상에 실제 iCal URL이 찍히면
> 회수할 수 없다.** 호스트가 화면에서 확인해야 하는 것은 "어느 채널이
> 연동돼 있고 동기화가 되고 있는가"이지 URL 문자열 자체가 아니다.

**마스킹 규칙**: 스킴과 호스트명은 그대로 두고, 경로·쿼리의 값은 **마지막
4자만 남기고 `****`로 대체**한다. 호스트가 "어느 채널의 어떤 연동인지"
식별하는 데는 충분하고, 값을 복원할 수는 없다.

> **필드명을 `ical_url`이 아니라 `ical_url_masked`로 둔다.** 이름이
> `ical_url`이면 프론트가 이 값을 실제 URL로 착각해 링크로 걸거나 다시
> 서버에 보낼 수 있다. 이름에 마스킹 사실을 박아 그 실수를 막는다.
>
> **원문 전체를 반환하는 엔드포인트는 만들지 않는다.** URL을 바꿔야 하면
> `DELETE /channels/{id}` 후 다시 `POST`한다(3절 표에 `PATCH`가 없는 것과
> 일치). 마스킹된 값을 그대로 다시 `POST`하지 않도록 프론트는 재등록 시
> 입력란을 **빈 칸으로 시작**한다.

### 3.2 POST /properties/{property_id}/channels 요청·응답 스펙 (v2.1 신규 확정)

**요청**

```json
{
  "channel": "AIRBNB",
  "ical_url": "https://www.airbnb.com/calendar/ical/12345678.ics?s=abc1234567890",
  "external_property_id": "12345678"
}
```

| 필드 | 필수 | 출처 | 비고 |
|---|---|---|---|
| `channel` | ✅ | `.channel` | 3값 외에는 `400 INVALID_CHANNEL` |
| `ical_url` | ✅ | `.ical_url` | 없으면 `400 ICAL_URL_REQUIRED`(v2.1 신규 코드) |
| `external_property_id` | — | `.external_property_id` | 생략 시 `null` |

> **`ical_url`은 DB에서 nullable인데 요청에서는 필수로 둔다.** 컬럼이
> nullable인 것은 향후 iCal이 아닌 연동 방식을 대비한 여지이고, 지금
> 시점에 이 엔드포인트의 용도는 **iCal URL 등록** 하나뿐이다(3절 표).
> URL 없이 만든 연결은 동기화할 대상이 없어 `SYNCING` 상태로 영원히
> 남는다. DB 제약을 바꾸지 않고 **API 레이어에서만** 필수로 강제한다.

**응답 (201)**

생성된 연결 1건을 3.1절과 **같은 필드 구성**으로 반환한다(`ical_url`은
여기서도 마스킹). 등록 직후에는 아직 동기화 전이므로
`sync_status`는 DB 기본값인 `SYNCING`, `last_synced_at`과
`last_error_message`는 `null`이다.

```json
{
  "data": { "connection_id": 9, "channel": "NAVER",
            "ical_url_masked": "https://ical.naver.com/export?k=****ef34",
            "external_property_id": null,
            "sync_status": "SYNCING",
            "last_synced_at": null,
            "last_error_message": null,
            "created_at": "2026-09-10T11:05:00Z" },
  "error": null
}
```

**에러**

| HTTP | code | 조건 |
|---|---|---|
| 400 | `INVALID_CHANNEL` | `channel`이 3값이 아님 |
| 400 | `ICAL_URL_REQUIRED` | `ical_url` 누락 또는 빈 문자열 |
| 409 | `CHANNEL_ALREADY_CONNECTED` | 같은 `property_id`+`channel` 중복(위 3절 기존 규칙, `UNIQUE(property_id, channel)`) |
| 404 | `RESOURCE_NOT_FOUND` | 타인 소유이거나 없는 `property_id` |

> **URL 유효성을 등록 시점에 검증하지 않는다.** iCal 응답을 확인하려면
> 외부 네트워크 호출이 필요한데, 코딩규칙 11번이 그 호출에 5초 타임아웃과
> `try-except`를 요구한다. 등록 요청을 그만큼 붙잡아 두는 대신
> `SYNCING`으로 저장하고, 실패는 배치 동기화가 `FAILED` +
> `last_error_message`로 남긴다(v1.3 운용 규칙). 호스트는 채널연동 탭에서
> 그 결과를 본다.

---

### 3.3 POST /channels/{connection_id}/sync 응답 스펙 (v2.4 신규 확정)

> 9/10 구현 시 이 엔드포인트에는 3절 표 한 줄만 있고 **응답 스펙이 없었다.**
> 이 절이 응답 스펙의 원본(SSOT)이다. 건수는 전부 **집계값**이라 DB 스키마
> 변경을 요구하지 않는다.

**동기화 실패는 이 엔드포인트의 실패가 아니다.** 외부 서버가 응답하지
않거나 깨진 데이터를 보낸 것은 호스트가 조치할 일이지 요청 자체의 오류가
아니므로 **200으로 응답**하고 `sync_status=FAILED`와 `last_error_message`로
결과를 알린다(Graceful Degradation, 코딩규칙 11). `404`는 연결이 없거나
타인 소유일 때만 난다.

```json
{
  "data": { "connection_id": 7,
            "sync_status": "SYNCED",
            "last_synced_at": "2026-09-10T03:14:30Z",
            "last_error_message": null,

            "created_count": 2,
            "updated_count": 1,
            "unchanged_count": 5,
            "skipped_no_room_count": 0,
            "skipped_overlap_count": 0,
            "failed_count": 0,

            "invalid_event_count": 1 },
  "error": null
}
```

**건수 필드 — 사유별로 나눈다 (v2.4)**

| 필드 | 뜻 | 호스트가 할 일 |
|---|---|---|
| `created_count` | 새로 만든 예약 | — |
| `updated_count` | 기간·게스트명이 바뀌어 갱신 | — |
| `unchanged_count` | 이미 반영돼 있고 변경 없음 | **없음(정상)** |
| `skipped_no_room_count` | **객실 미지정** — `bookable_unit_type`이 `ROOM`/`BED`인 숙소 | **구조적 한계.** 피드를 고쳐도 해결되지 않는다 |
| `skipped_overlap_count` | **기간 겹침** — 처리 방침 미정의 | 캘린더 확인 |
| `failed_count` | 예상 못 한 오류 | **서버 로그 확인 필요** |
| `invalid_event_count` | 피드에서 **버려진 이벤트** 수(UID·날짜 누락, 종료<=시작) | 피드 제공처 확인 |

> **왜 하나로 묶지 않는가**: `skipped: 3` 하나로는 **"이미 반영돼서 넘어간
> 것"과 "객실을 몰라서 못 넣은 것"이 구분되지 않는다.** 앞은 아무것도 안
> 해도 되고 뒤는 조치가 필요한데, 같은 숫자로 보이면 호스트가 판단할 수
> 없다.
>
> **`invalid_event_count`만 층이 다르다.** 나머지 여섯은 **예약 반영
> 단계**의 결과이고 이것은 **피드 파싱 단계**의 결과다. 파싱에서 버려진
> 건은 애초에 반영 시도조차 되지 않는다 — 이 값을 응답에 넣지 않으면
> **10건짜리 피드에서 3건이 버려져도 호스트에게는 7건만 처리된 것으로
> 보인다.**

> **`skipped_no_room_count`가 0이 아니라는 것은** 그 숙소가 `ROOM`/`BED`
> 단위인데 iCal이 객실을 알려주지 않는다는 뜻이다. iCal 피드에는 객실
> 식별자가 없고 `CHANNEL_CONNECTIONS`에도 객실을 담을 자리가 없어
> **현재 구조로는 자동 반영이 불가능**하다. 처리 방침은 **r49(9/12)**에서
> 정한다.

---

## 4. 예약 (RESERVATIONS) ⭐ 핵심

| Method | Endpoint | 설명 |
|---|---|---|
| GET | `/properties/{property_id}/reservations` | 예약 목록(캘린더용, 기간 필터, `is_conflict` 플래그 포함) |
| GET | `/reservations/{reservation_id}` | 예약 상세 |
| POST | `/reservations` | 예약 생성(iCal 동기화 또는 수동, bookable_unit_type 검증 포함) |
| PATCH | `/reservations/{reservation_id}/status` | 예약상태/환불상태/정산상태 개별 수정 |
| GET | `/properties/{property_id}/dashboard/summary` | 대시보드 통합 요약(캘린더요약+오픈액션수+오늘turnover건수, **캐싱 없이 매요청 실시간 집계** — 개별 API와 항상 일치 보장) |

### 4.1 GET /properties/{property_id}/dashboard/summary 응답 스펙 (v1.8 신규 확정)

> 9/7 확인 결과 이 엔드포인트는 위 표 한 행만 있고 응답 스펙이 문서 어디에도
> 없었다. **이 절이 응답 스펙의 원본(SSOT)이다.** 아래 11개 필드는 전부 기존
> 16개 테이블의 실재 컬럼에서 집계하며 **DB 스키마 변경을 요구하지 않는다.**

```json
{
  "data": {
    "property_id": 1,
    "property_name": "강남 3룸 독채",

    "today_checkin_count": 2,
    "today_checkout_count": 1,
    "today_turnover_count": 1,

    "open_action_count": 5,
    "red_now_count": 1,
    "yellow_today_count": 2,
    "green_auto_count": 2,

    "cleaning_pending_count": 2,
    "cleaning_issue_count": 0,

    "conflict_count": 1        // 계산 실패 시 null
  },
  "error": null
}
```

| 필드 | 집계 근거 |
|---|---|
| `property_id` / `property_name` | `PROPERTIES.property_id` / `PROPERTIES.name`. 프론트가 3~5개 숙소분을 병렬 호출해 합산하므로 **어느 숙소의 응답인지 식별이 필요**하다 |
| `today_checkin_count` | `RESERVATIONS` `WHERE check_in = CURRENT_DATE AND reservation_status IN ('CONFIRMED','MODIFIED')`. 인덱스 `idx_reservations_dates(property_id, check_in, check_out)` |
| `today_checkout_count` | `RESERVATIONS` `WHERE check_out = CURRENT_DATE` (같은 인덱스) |
| `today_turnover_count` | **같은 `(property_id, room_id, bed_id)` 조합**에서 당일 체크아웃 예약과 당일 체크인 예약이 **둘 다 존재하는 단위의 수**. 아래 정의 참고 |
| `open_action_count` | `ACTION_ITEMS` `WHERE status = 'OPEN'` (`action_status_enum`, 명세서 2.15절) |
| `red_now_count` / `yellow_today_count` / `green_auto_count` | `ACTION_ITEMS` `WHERE status='OPEN' GROUP BY risk_level` (`action_risk_level_enum`: `RED_NOW`/`YELLOW_TODAY`/`GREEN_AUTO`, 명세서 111행). 인덱스 `idx_action_items_property_status(property_id, status, risk_level)`가 **정확히 이 쿼리 형태와 일치** |
| `cleaning_pending_count` | `CLEANING_TASKS` `WHERE task_status IN ('PENDING','ASSIGNED','IN_PROGRESS')`. 인덱스 `idx_cleaning_tasks_property_status` |
| `cleaning_issue_count` | `CLEANING_TASKS` `WHERE task_status = 'ISSUE'` |
| `conflict_count` | `is_conflict = true`인 예약 수. `is_conflict`는 **DB 컬럼이 아니라 서버가 매 조회 시 계산하는 파생 필드**다(본 절 `GET /reservations/{id}` 주석 참고) |

**`today_turnover_count` 정의 (실제 운영 규칙 기반)**

체크아웃 **11:00** / 체크인 **16:00** 운영이므로, 같은 판매단위에서 당일
퇴실과 당일 입실이 겹치면 **청소 가용 시간이 5시간뿐**이고 당일 청소 완료가
필수가 된다. 그래서 이 건수는 단순 `today_checkout_count`와 **다른 개념**이며,
호스트가 오늘 반드시 처리해야 할 작업량을 나타낸다.

> **15:00 비밀번호 안내 메시지는 이 집계와 무관하다.** 그것은 turnover 여부와
> 관계없이 도는 별도 알림 스케줄이므로 `today_turnover_count`에 포함하지 않는다.

> ※ **PROPERTY 단위 판매 예약은 `room_id`·`bed_id`가 NULL이다.** SQL에서
> `NULL = NULL`은 참이 아니므로 일반 등호 비교로는 PROPERTY 단위 숙소의
> turnover가 집계되지 않는다. 조합 비교에는 **`IS NOT DISTINCT FROM`**을
> 사용한다. `COALESCE(room_id, 0)` 같은 트릭은 사용하지 않는다(CLAUDE.md
> 핵심 데이터 모델 원칙에서 이미 폐기 결정됨).

**`conflict_count` 포함 이유와 실패 처리**

iCal을 여러 OTA에서 받는 구조상 더블부킹이 실제로 발생 가능하며, 호스트가
대시보드에서 **가장 먼저 알아야 할 정보**다(숙소별 캘린더를 일일이 열어보게
해서는 안 된다). 다만 파생 필드이므로 계산에 실패할 수 있다.

**키는 항상 포함한다. 계산 실패 시 값을 `null`로 반환한다.** 나머지 10개
필드는 정상 값으로 반환한다(Graceful Degradation) — CLAUDE.md의 iCal
외부연동 방어 원칙과 같은 계열로, 일부 실패가 화면 전체를 못 쓰게 만들지
않는다.

> **필드를 생략하지 않는 이유**: 프론트에서 키가 없으면 `undefined`가 되어
> 조건부 렌더링 방어 코드가 늘어난다. `null`이면 **"계산 못 함"과 "0건"이
> 구분**되고, 위에 명시한 **11필드 고정 계약도 유지**된다.
> (v1.8은 "이 필드만 생략"이라고 적어 11필드 고정과 모순이었다 — v1.9 정정)

**포함하지 않는 필드**

`staying_count`(현재 투숙 중)는 넣지 않는다. 나머지 지표가 전부 "오늘 무엇을
해야 하는가"인 반면 투숙 중 인원은 호스트의 행동을 유발하지 않으며, 3~5개
숙소분을 합산해 표시하는 화면에서 필드 수를 늘리면 KPI 영역이 과밀해진다.

**UI 표기 규칙**

`risk_level`을 화면에 표시할 때 문구는 **"위험도"가 아니라 "우선순위"**를 쓴다
(CLAUDE.md: "ActionItems.risk_level은 AI의 법적/안전 판단이 아니라 규칙기반 운영
우선순위다").

> `RED_NOW` 판정의 "체크인 임박" 기준 시각은 **`PROPERTIES.checkin_time`에서
> 읽는다**. 숙소마다 체크인 시각이 다를 수 있으므로 하드코딩하지 않는다.
> (실제 판정 로직 구현은 10/6 액션센터 태스크 소관이며, 여기서는 원칙만 남긴다)

**체크인/체크아웃 시각과 turnover의 관계**

`PROPERTIES.checkin_time` / `checkout_time`은 숙소별 설정값이며, 스키마
기본값(`'15:00'`)과 실제 운영값은 다를 수 있다. 아래는 개발자가 실제 운영
중인 숙소(마포, PROPERTY 단위 판매)의 규칙으로, turnover 지표가 필요한
배경이다.

> ⚠️ **아래 규칙은 두 층으로 나뉜다. 이 구분을 반드시 지킬 것.**

**(1) 게스트 고지 사항 — 공식 규정**

- 체크아웃 11:00
- 체크인 16:00
- 비밀번호 안내 발송 15:00
- 조기 체크인 / 연장 체크아웃을 원하는 경우 **2일 전 사전협의 필수**
- **연장·조기 이용 시 1시간당 2만원의 추가요금이 발생할 수 있음**
  (숙소 안내·예약 확인 메시지에 비고로 항상 표시한다)

**(2) 호스트 내부 재량 — 게스트에게 고지하지 않음**

아래는 호스트가 그날 상황을 보고 개별 판단하는 사항이며, 사전에 안내하거나
시스템이 자동으로 노출하지 않는다.

- 12:00까지의 체크아웃 연장 가능 여부
  (청소 직원 일정이 사전 배치되어 12:00이 실질 한계. 게스트가 먼저
  문의하지 않으면 안내하지 않는다)
- 15:00 조기 체크인 수용 여부
- 당일 체크아웃이 없는 단위의 12:00 이후 체크인 수용 여부
- 실무상 1~2시간 정도 배려하는 관행
- 추가요금의 실제 부과 여부

**🔴 AI 게스트 응대에서의 취급**

**(2)의 내용은 `KNOWLEDGE_CHUNKS`에 등록하지 않는다.** RAG 검색 결과에
포함되면 AI가 호스트를 대신해 재량 사항을 약속하게 되며, 이는 호스트가 그날
상황(청소 일정, 다음 예약)을 보고 판단해야 할 문제다. 지식베이스에는 (1)의
공식 규정만 등록한다.

조기 체크인·연장 체크아웃 문의가 들어오면 AI는 "2일 전 사전협의가 필요하며
추가요금이 발생할 수 있다"는 공식 안내까지만 하고, 수용 여부는 호스트 승인
대기로 넘긴다.

**turnover가 제약하는 것**

청소 일정이 사전 배치되므로 체크아웃 측 한계(12:00)는 turnover 유무와
무관하게 동일하다. turnover가 실제로 제약하는 것은 **체크인 측**이다.
turnover가 없는 단위는 12:00부터 체크인을 받을 수 있으나, turnover가 발생한
단위는 청소가 끝나야 하므로 16:00을 지켜야 한다.

즉 `today_turnover_count`는 단순 집계가 아니라, **호스트가 그날 해당 단위의
체크인 시각을 앞당길 수 있는지를 판정하는 내부 지표**다. 게스트에게 노출되는
값이 아니다.

**구현 시 주의**

- 시각을 하드코딩하지 않는다. `PROPERTIES.checkin_time` / `checkout_time`에서
  읽는다.
- 추가요금(1시간당 2만원)은 호스트 재량이므로 **자동 부과·자동 계산 로직을
  만들지 않는다.** 현재 스키마에 저장할 컬럼이 없으며 이번 범위에서 추가하지
  않는다.
- 2일 전 사전협의 요청은 현재 시스템이 관리하지 않는다. 호스트가 채널
  메시지로 직접 처리하는 운영 업무다.
- 15:00 비밀번호 발송은 turnover 집계에 포함하지 않는다. 다만 체크인 1시간
  전이므로 향후 액션센터 `RED_NOW` 판정(체크인 임박 + 청소 미완료)의 기준점
  후보다. 실제 판정은 10/6 액션센터 태스크 소관이며 여기서는 배경으로만
  기록한다.

### 4.2 통합 대시보드 조회 방식 (v1.8 신규 명시)

대시보드는 **전체 숙소 통합 뷰**다. 백엔드에 교차 숙소 집계 엔드포인트를
**새로 만들지 않는다.** 프론트가 `GET /properties`로 목록을 받은 뒤 각 숙소의
`dashboard/summary`를 **병렬 호출해 합산**한다. 숙소 하나의 호출이 실패해도
나머지는 정상 렌더링한다.

근거:
1. 기검증된 백엔드(16테이블, `reservation_service.py`, 회귀테스트 20개 통과)를
   전혀 건드리지 않는다 — 안정성 우선.
2. 각 호출이 단일 숙소 쿼리이므로 **명세서 611행의 성능 보증 범위 안**에 있다
   ("조인 1회로 충분하며, 위 인덱스로 성능 문제 없이 동작합니다").
3. P1에서 숙소 수가 크게 늘면 통합 엔드포인트를 추가할 수 있고, 그때 필요한
   인덱스는 **이미 전부 존재한다**(`idx_properties_host`,
   `idx_reservations_property`, `idx_reservations_dates`,
   `idx_cleaning_tasks_property_status`, `idx_action_items_property_status`).
   즉 지금 결정이 나중을 막지 않는다.

> **PropertySwitcher는 대시보드의 필터가 아니다.** 개별 화면(캘린더/청소/정산
> 등)에 들어갈 때의 **컨텍스트 전환 도구**다.

---

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

> **[v1.7 추가] 교차 판매단위 기간 충돌은 `409 Conflict`, code
> `RESERVATION_OVERLAP`**. DB의 EXCLUDE 제약 3종은 **같은 판매단위끼리만**
> 겹침을 막으므로(PROPERTY↔PROPERTY, ROOM↔ROOM, BED↔BED), 독채 예약과 그
> 하위 객실/침대 예약 사이의 충돌은 `POST /reservations` 서비스 레이어가
> 직접 조회해 차단한다(명세서 2.6.1절 경고, troubleshooting.md 1번).
> 응답 message에는 충돌한 예약번호를 함께 담는다.
>
> | 상황 | HTTP | code |
> |---|---|---|
> | 같은 숙소에서 기간이 겹치는 다른 단위 예약 존재 | 409 | `RESERVATION_OVERLAP` |
> | 동시성으로 DB EXCLUDE에 걸린 경우(마지막 방어선) | 409 | `RESERVATION_OVERLAP` |
>
> 겹침 판정은 반개구간이다 — **체크아웃일과 다음 예약의 체크인일이 같은 날인
> 연박 이어짐은 충돌이 아니다**(EXCLUDE의 `tsrange` 판정과 동일).

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
> 전이되는 즉시 서버가 자동 트리거, `scheduled_at`=해당 예약의
> `check_out`과 숙소 `checkout_time`을 결합한 실제 체크아웃 시각으로 미리
> 세팅, 별도 생성 API 없음 — UNIQUE 제약과 일치, 9/3 정정).
> ※ 이 컬럼은 v1.3에서 `scheduled_date` → `scheduled_at`으로 개명됐다
> (타입은 `TIMESTAMPTZ` 그대로). 응답 JSON 키도 `scheduled_at`을 쓴다.

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

> **생성 엔드포인트(`POST`)가 없다.** `ACTION_ITEMS`는 **시스템 배치·트리거로만
> 생성**되며(청소 지연 감지, 서류 만료 임박, 가격 조정 추천 등) 호스트가 직접
> 추가하지 않는다. 화면에도 "액션 추가" 기능을 두지 않는다.

### 9.1 GET /properties/{property_id}/action-items 응답 스펙 (v2.0 신규 확정)

**응답 9필드는 전부 `ACTION_ITEMS` 실재 컬럼이며 파생 필드가 없다.**

```json
{
  "data": [
    {
      "action_id": 91,
      "property_id": 1,
      "reservation_id": 501,
      "risk_level": "RED_NOW",
      "category": "CLEANING_DELAY",
      "title": "체크인 2시간 전인데 청소 미완료",
      "content": "강남 3룸 독채 · 오늘 16:00 체크인",
      "status": "OPEN",
      "created_at": "2026-09-08T09:12:00Z"
    }
  ],
  "meta": { "total": 47, "page": 1, "size": 20 },
  "error": null
}
```

| 필드 | 출처 컬럼(명세서 2.15절) | 타입 |
|---|---|---|
| `action_id` | `action_id` | BIGSERIAL |
| `property_id` | `property_id` | BIGINT NOT NULL |
| `reservation_id` | `reservation_id` | BIGINT **nullable**(서류만료 등 예약과 무관한 건) |
| `risk_level` | `risk_level` | `action_risk_level_enum` NOT NULL |
| `category` | `category` | VARCHAR(50) NOT NULL |
| `title` | `title` | TEXT NOT NULL |
| `content` | `content` | TEXT nullable |
| `status` | `status` | `action_status_enum` NOT NULL DEFAULT `'OPEN'` |
| `created_at` | `created_at` | TIMESTAMPTZ NOT NULL DEFAULT `now()` |

**쿼리 파라미터**

| 파라미터 | 근거 |
|---|---|
| `status` | 기존(위 표에 이미 있음) |
| `risk_level` | **v2.0 신규** — 아래 근거 참고 |
| `page` / `size` | 0절 공통 규약 |

> `risk_level` 필터는 인덱스
> `idx_action_items_property_status(property_id, status, risk_level)`의
> **세 번째 키**다. **`status`와 함께 사용할 때 인덱스로 커버되며**, `status`
> 없이 `risk_level`만 필터하면 앞 키를 건너뛰어 인덱스 효율이 떨어진다.
> **두 필터를 함께 쓰는 것을 전제한다.**
>
> **`category` 필터는 1차에 넣지 않는다.** 인덱스에 없어 필터링 시 인덱스를
> 못 쓰며, `/actions` 화면의 카테고리 탭은 프론트에서 처리한다.
>
> **`limit` 파라미터를 신설하지 않는다.** 0절의 `size`가 같은 역할을 하며
> 의미가 겹친다.

**정렬**

```sql
ORDER BY risk_level ASC, created_at DESC
```

`action_risk_level_enum`이 `RED_NOW` → `YELLOW_TODAY` → `GREEN_AUTO` 순으로
선언돼 있어 **PostgreSQL의 ENUM 비교가 선언 순서를 따른다.** 별도 `CASE` 문이
불필요하다.

> ※ `created_at`은 인덱스에 없어 **`risk_level`이 같은 항목 간 정렬은 별도로
> 수행된다.** `property_id` + `status`로 좁힌 뒤라 대상 건수가 적어 실사용에서
> 문제되지 않는다.

> **처리 이력의 한계 (1차 범위)**: `ACTION_ITEMS`에 **`resolved_at` 컬럼이
> 없다.** 따라서 `?status=RESOLVED` 조회는 **처리 시각이 아니라 생성 시각
> (`created_at DESC`) 기준**으로만 정렬된다. 오래전 생성된 항목을 최근에
> 처리한 경우 목록 하단에 남으므로, **"최근에 무엇을 처리했나"는 1차에서
> 제공하지 않는다.** `resolved_at` 추가는 액션센터 구현 시점(10/6)에
> resolve 로직과 함께 다룬다(troubleshooting 24번).

**두 화면이 같은 엔드포인트를 사용한다**

| 화면 | 호출 | 용도 |
|---|---|---|
| `/dashboard` 액션 프리뷰 | `?status=OPEN&size=5` | 조회·이동만(인라인 처리 버튼 없음) |
| `/actions` 전체 큐 | `?status=OPEN&size=20` | 전체 큐와 처리 |

> ※ 대시보드 프리뷰의 **"전체 N건 처리하러 가기"** 표시에는 이 응답의
> `meta.total`이 아니라 **`dashboard/summary`의 `open_action_count`를
> 사용한다.** 대시보드는 이미 `summary`를 호출하므로 같은 숫자를 두 경로로
> 얻을 이유가 없고, **두 값의 조회 시점이 어긋날 수 있다.**
> (`GET /properties`에 요약 지표를 넣지 않기로 한 것과 같은 근거 — 2절 참고)

**`category` 값 현황 (확정하지 않음)**

명세서 2.15절이 `category`를 `VARCHAR(50)`으로 두고 *"category 정의가 아직
세밀하지 않아 DB 제약으로 못박기엔 이름"*이라고 밝히고 있으므로 **허용값을
확정하지 않는다.** 현재 문서에 등장하는 값만 참고로 기록한다.

| 값 | 출처 |
|---|---|
| `CLEANING_DELAY` | 명세서 2.15절 검증 예시 |
| `COMPLIANCE_EXPIRY` | 명세서 2.15절 검증 예시 |
| `PRICE_ADJUSTMENT` | 본 문서 13절 |
| `PRICE_NEGLECT` | 본 문서 13절 |

- **각 기능 구현 시 값이 추가될 수 있다.**
- **신규 `category`를 추가할 때는 이 목록과 프론트 카드 컴포넌트 분기를 함께
  갱신한다.** `VARCHAR`라 **DB가 오타를 막지 못하며**, 오타가 들어가면 "동일
  `reservation_id` + `category` + `status='OPEN'` 조합 재사용" idempotency
  로직이 깨져 **같은 알림이 중복 생성된다**(명세서 2.15절).

### 9.2 PATCH /action-items/{action_id}/resolve 스펙 (v2.0 신규 확정)

**요청 본문 없음** — 경로 파라미터만 받는다.

**응답**: 갱신된 레코드 9필드를 그대로 반환한다(9.1과 동일 구조, 단건).

```json
{ "data": { "action_id": 91, "status": "RESOLVED", "...": "나머지 7필드 동일" },
  "error": null }
```

**`status`는 항상 `RESOLVED`로 전이한다.**

**서버 가드 — 가격 계열 액션 거부**

| 상황 | HTTP | code |
|---|---|---|
| `category`가 `PRICE_ADJUSTMENT` 또는 `PRICE_NEGLECT`인 액션에 호출 | 400 | `PRICE_ACTION_REQUIRES_APPLY` |

가격 카드는 `POST /properties/{property_id}/price-recommendations/apply`를
거쳐야 **Mock 반영이 함께** 이뤄진다. `resolve`만 허용하면 가격 반영 없이
카드만 닫히므로 서버에서 막는다(13절 참고).

**IDOR 방어**: 0절 공통 원칙대로, **소유권 불일치와 부존재를 구분하지 않고
`404 RESOURCE_NOT_FOUND`로 통일**한다. 이 엔드포인트는 경로에 `property_id`가
없으므로 조회 쿼리 자체에 소유권 조건을 묶는다.

> **이 엔드포인트는 `AUTO_RESOLVED`를 세팅하지 않는다.** 시스템이 자동으로
> 닫는 경로로 추정되나 **문서에 로직 정의가 없다**(9/7 확인). ENUM 정의와 ERD
> 표기에만 등장하며 언제 누가 세팅하는지 설명이 없고, `risk_level='GREEN_AUTO'`
> 와의 관계도 미정이다.
>
> **10/6 액션센터 구현 전까지 `GREEN_AUTO` 항목의 실질적 자동 해결은 동작하지
> 않는다.** 트리거 규칙과 함께 그 시점에 확정한다.

---

## 10. 컴플라이언스 (CHECKLIST_ITEMS)

| Method | Endpoint | 설명 |
|---|---|---|
| GET | `/properties/{property_id}/checklist-items` | 체크리스트 목록(만료 임박순 정렬) |
| PATCH | `/checklist-items/{item_id}` | 완료/갱신 처리 |

> **호출 위치는 두 곳이다 (v2.2)**: `/settings` **인허가 탭**(전체 목록
> 조회·항목 추가·정리)과 **액션센터의 서류 만료 카드**(실제 갱신 처리).
> `/compliance` 전용 화면은 두지 않는다 — 9/8에 `/settings` 4번째 탭으로
> 흡수했다(`docs/ui_design.md` 2절·4-11절). **엔드포인트는 그대로다.**
>
> 만료 30일 전 배치가 발행하는 `ACTION_ITEMS` 카드에서 `PATCH`가 그대로
> 호출되므로, 호스트는 화면을 옮기지 않고도 갱신을 끝낼 수 있다.

> **`POST` 요청 스펙은 아직 정의하지 않았다.** 호스트가 인허가 항목을
> **직접 추가할 수 있어야 한다**는 것은 9/8에 확정됐다(설정 탭으로
> 옮기면서 생성 경로가 수동으로 정해짐 — troubleshooting 22번). 그러나
> 요청 바디·검증 규칙은 **컴플라이언스 구현 시점(10/1~07)에 확정**한다.
> 2.2절의 `rooms`·`beds` `POST`와 같은 취급이다 — 표에 행이 있다는 것이
> 요청 스펙이 정의됐다는 뜻은 아니다(troubleshooting 23번의 교훈).

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

**`action-items`와의 관계 및 호출 경로 (v2.0 명시)**

두 엔드포인트는 **같은 레코드를 가리킨다.** 가격 추천은 전용 테이블 없이
`ACTION_ITEMS` 카드로만 표현되므로(위 설계 원칙), 같은 행이
`GET /properties/{id}/action-items`에도 `category='PRICE_ADJUSTMENT'` 또는
`'PRICE_NEGLECT'`로 나타난다.

- `/actions` 화면에서 **가격 카드를 승인할 때는**
  `POST /properties/{property_id}/price-recommendations/apply`를 호출한다.
- **`PATCH /action-items/{action_id}/resolve`를 쓰면 안 된다.** `apply`가 Mock
  반영과 `RESOLVED` 전이를 **함께** 수행하므로, `resolve`만 호출하면 **가격
  반영 없이 카드만 닫힌다.**
- **9.2절의 서버 가드가 이 실수를 막는다**(`400 PRICE_ACTION_REQUIRES_APPLY`).
- **프론트에서도 카드 컴포넌트를 카테고리별로 분리해 각자 자기 엔드포인트를
  호출하게 한다.** 공통 카드에 `onResolve` 하나만 두면 분기를 놓치기 쉽다.

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
