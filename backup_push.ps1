# ============================================
#   Host ON AI - 일일 마감 백업 스크립트
# ============================================

Set-Location "C:\3rd host AI"

Write-Host "[1/3] Git 상태 확인 중..." -ForegroundColor Cyan
git status

Write-Host ""
$commitMsg = Read-Host "커밋 메시지를 입력하세요 (예: 9/5 작업 완료)"

Write-Host ""
Write-Host "[2/3] Git 커밋 + Push 중... (C:\3rd host AI -> GitHub)" -ForegroundColor Cyan
git add -A
git commit -m "$commitMsg"
git push

Write-Host ""
Write-Host "[3/3] Desktop 소스코드 폴더로 로컬 백업 복사 중..." -ForegroundColor Cyan
Write-Host "       (C:\3rd host AI -> Desktop\3차 프로젝트\소스코드)"

robocopy "C:\3rd host AI" "C:\Users\Donga\Desktop\3차 프로젝트\소스코드" /MIR /XD .git node_modules __pycache__ .venv /XF *.pyc /NFL /NDL /NJH /NJS

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  완료! 3곳 전부 동기화됐습니다:" -ForegroundColor Green
Write-Host "  1. C:\3rd host AI (Cowork 작업공간, 원본)"
Write-Host "  2. GitHub (원격 저장소)"
Write-Host "  3. Desktop\3차 프로젝트\소스코드 (로컬 백업)"
Write-Host "============================================" -ForegroundColor Green

Read-Host "엔터를 누르면 종료합니다"
