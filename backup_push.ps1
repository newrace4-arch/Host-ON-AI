# ============================================
#   Host ON AI - 일일 마감 백업 스크립트
# ============================================
#
#  하는 일   (1) 미커밋 변경 확인  (2) GitHub push  (3) Desktop 미러백업
#
#  ※ 이 스크립트는 **커밋하지 않는다.** 이미 만들어 둔 커밋을 push만 한다.
#     근거: CLAUDE.md 규칙 1 "기능 하나 = 커밋 하나". 백업 스크립트가
#     커밋 단위를 만들면 그 규칙이 구조적으로 지켜질 수 없다. 커밋은
#     작업할 때 성격별로 나눠서 만든다.
#
#  9/10 수정 (9/9 devlog 이월 (15) 결함 4건)
#     1) /XD 에서 .git 제거 - 커밋 이력이 들어가야 '백업'이다
#     2) /XF 에 .env 추가   - 비밀값이 Desktop 사본으로 새지 않게
#     3) git add -A + git commit 제거 - 규칙 1과 충돌
#     4) git push 실패 시 백업을 건너뛰고 중단

$RepoPath   = "C:\3rd host AI"
$MirrorPath = "C:\Users\Donga\Desktop\3차 프로젝트\미러백업"

Set-Location $RepoPath

# ---------------------------------------------------------------
# [1/3] 미커밋 변경 확인 - 있으면 중단
# ---------------------------------------------------------------
Write-Host "[1/3] Git 상태 확인 중..." -ForegroundColor Cyan
git status --short

$dirty = git status --porcelain
if ($dirty) {
    Write-Host ""
    Write-Host "=== 중단: 커밋하지 않은 변경이 있습니다 ===" -ForegroundColor Red
    Write-Host "이 스크립트는 커밋하지 않습니다(CLAUDE.md 규칙 1)."
    Write-Host "위 변경을 성격별로 나눠 커밋한 뒤 다시 실행하세요."
    Write-Host ""
    Read-Host "엔터를 누르면 종료합니다"
    exit 1
}
Write-Host "  미커밋 변경 없음." -ForegroundColor Green

# ---------------------------------------------------------------
# [2/3] GitHub push - 실패하면 백업하지 않고 중단
# ---------------------------------------------------------------
Write-Host ""
Write-Host "[2/3] GitHub push 중... ($RepoPath -> origin)" -ForegroundColor Cyan
git push
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "=== 중단: git push 실패 (exit $LASTEXITCODE) ===" -ForegroundColor Red
    Write-Host "원격에 반영되지 않은 채 미러백업만 갱신하면,"
    Write-Host "'백업했다'고 믿는데 원격에는 없는 상태가 됩니다."
    Write-Host "네트워크와 인증을 확인하고 다시 실행하세요."
    Write-Host ""
    Read-Host "엔터를 누르면 종료합니다"
    exit 1
}
Write-Host "  push 완료." -ForegroundColor Green

# ---------------------------------------------------------------
# [3/3] Desktop 미러백업
# ---------------------------------------------------------------
Write-Host ""
Write-Host "[3/3] Desktop 미러백업 갱신 중..." -ForegroundColor Cyan
Write-Host "       ($RepoPath -> $MirrorPath)"

#  /XD 에 .git 을 넣지 않는다 - 커밋 이력이 통째로 들어가야 '백업'이다.
#     .git 을 빼면 파일 사본일 뿐이라 GitHub 장애 시 복구 수단이 못 된다.
#  .backup/ 도 빼지 않는다 - 8-2 0번의 엑셀 검증 기준선인데 .gitignore
#     대상이라 git에 없다. 여기서 빼면 사본이 세상에 하나뿐이 된다.
#     커밋 전 편집 중 상태를 담고 있어 git으로 대체되지 않는다(29번 사고).
#  .env 계열은 반드시 제외한다. .env.example 은 이름이 달라 그대로 복사된다.
$roboArgs = @(
    "$RepoPath", "$MirrorPath", "/MIR",
    "/XD", "node_modules", "__pycache__", ".venv",
    "/XF", "*.pyc", ".env", "*.pem", "*.key",
    "/NFL", "/NDL", "/NJH", "/NJS"
)
robocopy @roboArgs

$rc = $LASTEXITCODE
if ($rc -ge 8) {
    Write-Host ""
    Write-Host "=== 경고: robocopy 오류 (exit $rc) ===" -ForegroundColor Red
    Write-Host "미러백업이 완전하지 않을 수 있습니다. 위 메시지를 확인하세요."
    Write-Host ""
    Read-Host "엔터를 누르면 종료합니다"
    exit 1
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  완료! 3곳 전부 동기화됐습니다:" -ForegroundColor Green
Write-Host "  1. C:\3rd host AI (작업 원본)"
Write-Host "  2. GitHub (원격 저장소)"
Write-Host "  3. Desktop\3차 프로젝트\미러백업"
Write-Host "     - .git 포함(커밋 이력 O) / .env 제외 / .backup 포함" -ForegroundColor DarkGray
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "  ※ 이 스크립트는 커밋하지 않습니다. 커밋은 작업할 때 성격별로." -ForegroundColor DarkGray

Read-Host "엔터를 누르면 종료합니다"
