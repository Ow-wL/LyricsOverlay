# LyricsOverlay exe 빌드 스크립트
#
#   .\build.ps1
#
# 1) venv의 PyInstaller로 main.spec을 빌드해 dist\LyricsOverlay.exe를 만듭니다.
# 2) (선택) 코드 서명 인증서가 설정돼 있으면 signtool로 서명합니다.
#      $env:LYRICSOVERLAY_SIGN_THUMBPRINT = "<인증서 지문>"   # 인증서 저장소에 설치된 인증서
#    서명이 없으면 Windows SmartScreen이 '알 수 없는 게시자' 경고를 띄울 수 있습니다.
# 3) dist\LyricsOverlay.exe.sha256.txt에 SHA-256 체크섬을 남깁니다.
#    릴리스에 함께 올리면, 받은 사람이 파일이 바뀌지 않았는지 확인할 수 있습니다:
#      Get-FileHash .\LyricsOverlay.exe -Algorithm SHA256

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "venv가 없습니다. INSTALL.md의 설치 방법대로 venv를 만들고 requirements-build.txt를 설치하세요."
}

# 오픈소스 고지(THIRD_PARTY_NOTICES.txt)를 지금 설치된 패키지 기준으로 다시 만듭니다.
& $python tools\make_notices.py
if ($LASTEXITCODE -ne 0) { throw "오픈소스 고지 생성 실패" }

# PyInstaller는 진행 로그를 stderr로 씁니다. Windows PowerShell 5.1은 출력을 리디렉션하면 이것을
# 오류로 바꿔 'Stop'에서 멈추므로, 이 단계만 Continue로 두고 종료 코드로 성공 여부를 판단합니다.
$ErrorActionPreference = "Continue"
& $python -m PyInstaller main.spec --noconfirm 2>&1 | ForEach-Object { "$_" }
$buildExit = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if ($buildExit -ne 0) { throw "PyInstaller 빌드 실패 (종료 코드 $buildExit)" }

$exe = Join-Path $PSScriptRoot "dist\LyricsOverlay.exe"

# 자체 점검: 빌드한 exe가 창·글꼴·아이콘·고지 파일을 제대로 갖췄는지 (실제 설정·데이터는 건드리지 않음)
$smokeReport = Join-Path $PSScriptRoot "dist\smoke-test.txt"
if (Test-Path $smokeReport) { Remove-Item $smokeReport -Force }  # 지난 빌드의 보고서를 이번 결과로 착각하지 않게
$smoke = Start-Process -FilePath $exe -ArgumentList '--smoke-test', "`"$smokeReport`"" -PassThru -Wait
if (Test-Path $smokeReport) {
    Get-Content -Encoding UTF8 $smokeReport | ForEach-Object { Write-Host "  $_" }
} else {
    throw "자체 점검이 보고서를 남기지 못하고 끝났습니다 (종료 코드 $($smoke.ExitCode)). exe가 시작하다 멈췄을 수 있습니다."
}
if ($smoke.ExitCode -ne 0) { throw "자체 점검 실패 (종료 코드 $($smoke.ExitCode))" }

# 릴리스에 함께 올릴 고지 파일
Copy-Item THIRD_PARTY_NOTICES.txt (Join-Path $PSScriptRoot "dist\THIRD_PARTY_NOTICES.txt") -Force

if ($env:LYRICSOVERLAY_SIGN_THUMBPRINT) {
    $signtool = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if (-not $signtool) { throw "signtool.exe를 찾을 수 없습니다 (Windows SDK 필요)." }
    & $signtool.Source sign /sha1 $env:LYRICSOVERLAY_SIGN_THUMBPRINT /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 $exe
    if ($LASTEXITCODE -ne 0) { throw "코드 서명 실패" }
    Write-Host "코드 서명 완료"
} else {
    Write-Host "코드 서명 건너뜀 (LYRICSOVERLAY_SIGN_THUMBPRINT 미설정)"
}

$hash = (Get-FileHash $exe -Algorithm SHA256).Hash
"$hash  LyricsOverlay.exe" | Out-File -Encoding ascii (Join-Path $PSScriptRoot "dist\LyricsOverlay.exe.sha256.txt")
Write-Host "완료: $exe"
Write-Host "SHA-256: $hash"
