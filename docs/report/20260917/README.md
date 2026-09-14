# 9/17(목) 중간보고서 캡처 — 2026-09-14 촬영

**9/17 아침에 이 폴더만 열면 되도록** 각 파일이 무엇을 보여주는지 적어 둔다.
전부 **로컬 실행 화면**이며 배포본이 아니다.

## 파일

| # | 파일 | 무엇을 보여주는가 |
|---|---|---|
| 01 | `01_calendar_conflict.png` | **호스텔(BED 단위) — 교차 충돌.** 배너 *"충돌 2건"* + `⚠ 충돌` 두 줄(**201호 통째** ↔ **201호 B침대**). 침대 A는 정상, 202호는 `(0건)`으로 남는다 |
| 02 | `02_calendar_property.png` | **독채(PROPERTY 단위).** 같은 화면이 판매단위에 따라 **다른 행 구성**을 그린다. *"요금 미설정"*(`net_amount` null)과 `CANCELLED` 표시 |
| 03 | `03_calendar_empty.png` | **빈 상태(10월).** `EmptyState` 3요소 — 원인 · 다음 행동 · 그 행동으로 가는 링크 |
| 04 | `04_dashboard.png` | **대시보드 — `dashboard/summary` 구현 후.** 체크인 1 / 체크아웃 2 / **턴오버 1** / 을지로 **더블부킹 2건** |
| 04b | `04b_dashboard_before.png` | **대시보드 — 구현 전(같은 날 오후).** 두 숙소 모두 *"불러오지 못했습니다"*, 합산 *"2개 중 **0개** 기준"* |
| 05 | `05_swagger.png` | **API 엔드포인트 전체**(`/docs`). `GET /properties/{id}/dashboard/summary`가 reservations 섹션 마지막에 있다 |
| 05-2 | `05_2swagger.png` | **Schemas.** `Envelope[DashboardSummaryResponse]`·`Envelope[ReservationResponse]`·`Envelope[list[ReservationResponse]]` 3종이 실려 있다 |
| 06 | `06_pytest.png` | **회귀 315 passed** |
| 06 | `06_pytest.txt` | 같은 결과 + **파일별 23개** + **오늘 신설 67건** 내역. 보고서에 표로 옮길 때 쓴다 |

## 보고서에서 쓸 만한 짝

- **04b → 04** — 구현 전후. `GET /properties/{id}/dashboard/summary`를 만든 효과가 한 장씩으로 보인다
- **01 + 02** — 같은 화면이 **독채와 호스텔을 다르게 그린다.** *"서로 다른 숙박업 유형을 여러 개 운영하는 1인 멀티호스트"*라는 차별화 포지셔닝의 실물
- **05 + 05-2** — FastAPI가 **코드에서 자동 생성**한 문서다. 문서와 구현이 어긋날 수 없다는 점을 보여준다

## 🔴 쓰기 전에 알아야 할 것 셋

**① `04_dashboard.png`의 「턴오버 1」이 독채 것이다.**
독채 예약은 `room_id`·`bed_id`가 **둘 다 NULL**이라, 판매단위를 등호로
비교하면 이 값이 **영원히 0**이 된다. `IS NOT DISTINCT FROM` 판정이 화면까지
올라온 실물 증거다(api_contract 4.1절, devlog 9/14 3-3절).

**② `02`와 `04`는 시드 상태가 다르다.**
`02`는 **15:59**, `04`는 **16:38** 촬영인데 그 사이 데모 시드에 **오늘 날짜에
걸치는 예약 3건**을 더했다(`04`의 체크인·체크아웃·턴오버를 채우기 위해서다).
그래서 `02`의 독채 목록에는 **3건만** 보이고, `04`의 턴오버를 만든 예약
2건은 들어 있지 않다. **나란히 놓고 교차 검증하지 말 것.**

**③ `06_pytest.png`는 터미널 캡처가 아니다.**
같은 출력을 HTML로 옮겨 만든 화면을 찍은 것이다. **숫자(315 passed /
78.12s)는 실제 실행 결과**이지만 **이미지 자체는 재현**이다. 진짜 터미널
캡처가 필요하면 아래를 돌려 찍는다.

```
cd "C:\3rd host AI\backend"
.\.venv\Scripts\python.exe -m pytest -q --disable-warnings
```

## 개인정보

**없다.** 캡처에 보이는 게스트 이름 9개(김서준·이하윤·박도윤·최지호·정수아·
윤하은·한지우·오서연·배시우)는 전부 `tools/seed_demo.py`가 만든 가짜이고,
숙소명 둘(*"연남 3룸 하우스"*·*"을지로 호스텔"*)도 시드의 것이다.
**실제 운영 숙소·실제 게스트 자료는 한 건도 들어 있지 않다.**
계정은 `demo@hoston.local`이며 화면에 이메일·토큰이 노출된 곳은 없다.

## 다시 찍으려면

```
cd "C:\3rd host AI"
backend\.venv\Scripts\python.exe tools\seed_demo.py     # 데모 데이터 재생성
```

백엔드 8000 · 프론트 5173을 띄우고 `demo@hoston.local` / `demo1234`로
로그인한다. 캘린더 딥링크는 `/calendar?property=<id>`다.
