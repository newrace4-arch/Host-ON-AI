# 3rd Host AI — 백업 & 버전관리 원칙 (필독, 예외 없음)

> 이 문서는 프로젝트 시작(9/1)부터 제출(10/10)까지 **절대 어기면 안 되는 규칙**입니다.
> AI(Claude/Gemini)가 코드를 잘못 수정하거나, 크로스체크 결과를 반영하다 기존 기능이
> 깨지는 경우 — **되돌릴 수 있는 유일한 방법은 이전 커밋뿐입니다.** 백업이 없으면
> 되돌릴 방법 자체가 없습니다.

---

## 원칙 1. "기능 하나 완성 = 커밋 하나"

작은 단위로 자주 커밋합니다. 하루가 끝날 때 한 번에 몰아서 커밋하지 않습니다.

```bash
# 기능 하나가 실제로 동작하는 것을 확인한 직후
git add .
git commit -m "feat: iCal 동기화 중복예약 감지 구현"
```

**커밋 전 셀프 체크(10초)**
- [ ] 방금 만든 기능이 실제로 동작하는가? (돌려보지 않고 커밋 금지)
- [ ] `.env`, API 키, 비밀번호 등이 코드에 하드코딩되어 있지 않은가?
- [ ] 불필요한 `console.log`/`print` 디버깅 코드가 남아있지 않은가?

## 원칙 2. AI에게 코드 수정을 맡기기 "직전"에 반드시 커밋

Claude나 Gemini에게 리팩토링·버그수정·구조변경을 요청하기 전, **그 순간의 상태를
먼저 커밋**합니다. AI의 수정이 잘못됐을 때 즉시 되돌릴 지점을 만들어두는 것입니다.

```bash
# AI에게 큰 수정을 맡기기 전
git add . && git commit -m "checkpoint: AI 리팩토링 요청 전"

# AI 수정 결과가 별로면
git reset --hard HEAD~1
# 또는 특정 커밋으로
git log --oneline    # 커밋 목록 확인
git reset --hard <되돌릴 커밋 해시>
```

## 원칙 3. 매주 금요일(크로스체크 날) = 버전 태그

지금까지처럼 크로스체크로 큰 구조 변경이 있었던 시점마다 태그를 남깁니다.

```bash
git tag -a v0.1 -m "1단계 데이터모델 확정"
git tag -a v0.2 -m "2단계 기반인프라 완료"
git push origin --tags
```

발표 직전 최종본은 반드시 태그로 고정합니다.

```bash
git tag -a v1.0-submission -m "10/10 제출본"
git push origin v1.0-submission
```

## 원칙 4. Local / GitHub / 배포(Render·Vercel) — 3가지 상태를 구분

| 상태 | 의미 | 확인 방법 |
|---|---|---|
| Local | 지금 내 컴퓨터에 있는 코드 | `git status` |
| GitHub | 원격 저장소에 push된 코드 | `git log origin/main` |
| 배포본 | 실제로 Render/Vercel에서 돌아가는 코드 | 배포 URL 접속해서 직접 확인 |

**이 세 가지가 항상 같은 상태라고 가정하지 마세요.** local에서 잘 되는데 GitHub엔
push 안 했거나, GitHub엔 최신인데 배포는 예전 버전인 경우가 실제로 자주 생깁니다.
하루 끝날 때 `git push`까지 했는지 확인하는 걸 습관화하세요.

## 원칙 4-1. 매일 아침 VS코드 파일리스트 확인 (9/2 사고로 신설)

**한 번은 ERD 파일이 아예 Git 추적 밖에 있어서, 최신화 여부를 아무도 확인
못 하는 사고가 있었습니다.** 파일이 "어딘가에는 있다"와 "Git으로 관리되고
있어서 언제든 상태를 확인할 수 있다"는 완전히 다릅니다. 매일 작업 시작 전
VS코드 Explorer를 펴고 아래를 확인하세요.

- [ ] `docs` 폴더 안에 있어야 할 핵심 문서 4개가 다 보이는가?
  (`3rd_host_ai_db_spec_v1.md` / `erd.md` / `claude_code_stage1_schema.md`
  / `troubleshooting.md`)
- [ ] "M"(Modified) 표시가 붙은 파일이 있다면, 어제 뭘 고쳤는지 기억나는가?
  기억이 안 나면 커밋하기 전에 `git diff 파일명`으로 먼저 확인한다.
- [ ] DB 구조를 하나라도 바꾼 날은 **명세서 → ERD → 체크리스트** 순서로
  3곳 전부 갱신했는지 확인한다. (CLAUDE.md의 문서 변경관리 원칙과 동일)
- [ ] 새로 만든 파일이 있다면, `git status`에서 `Untracked files`로 잡히는지
  확인한다 — 안 잡히면 `.gitignore`에 실수로 걸려있는 건 아닌지 점검.

## 원칙 5. Feature Freeze 이후(10/8 24시~)는 별도 브랜치로만 수정

```bash
git checkout -b hotfix/demo-data-fix
# 수정 후
git checkout main
git merge hotfix/demo-data-fix
```

이렇게 하면 실수로 main이 깨져도 Freeze 시점 커밋으로 바로 돌아갈 수 있습니다.

## 원칙 6. 절대 하지 말 것

- ❌ "일단 되니까 나중에 커밋하자" — 나중은 오지 않습니다
- ❌ 큰 변경을 한 번에 몰아서 커밋 (문제 생겼을 때 원인 특정 불가)
- ❌ `.env` 파일을 `git add .`로 실수로 커밋 (→ `.gitignore`가 막아주지만, 이미 한 번
  커밋된 적 있다면 `.gitignore`에 넣어도 계속 추적됨 — 아래 확인 명령 사용)

```bash
# .env가 이미 커밋 이력에 남아있는지 확인
git log --all --full-history -- .env

# 만약 있다면 (반드시 비밀번호/키 재발급 후) 이력에서 제거
git rm --cached .env
git commit -m "chore: .env 추적 제거"
```

---

## 지금 당장 해야 할 것 (9/1 첫 작업)

```bash
cd 프로젝트폴더
git init
# 위에서 받은 .gitignore 파일을 프로젝트 루트에 넣기
git add .gitignore
git commit -m "chore: 초기 .gitignore 설정"
git branch -M main
git remote add origin <본인 GitHub 저장소 URL>
git push -u origin main
```

---

## 참고: 이 규칙을 계속 기억하게 하려면

지금 이 대화에서는 제가 이 규칙을 계속 인지하고 있지만, **새 대화를 시작하면 이전
대화 내용을 자동으로 기억하지 못합니다** (메모리 기능이 꺼져 있는 상태). 매번
"백업 규칙 지켜서 진행해줘"라고 언급해주시거나, 설정에서 메모리 기능을 켜두시면
다음 대화에서도 이 원칙을 자동으로 참고하게 할 수 있습니다.
