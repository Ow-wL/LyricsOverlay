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

# PyInstaller는 진행 로그를 stderr로 씁니다. Windows PowerShell 5.1은 출력을 리디렉션하면 이것을
# 오류로 바꿔 'Stop'에서 멈추므로, 이 단계만 Continue로 두고 종료 코드로 성공 여부를 판단합니다.
$ErrorActionPreference = "Continue"
& $python -m PyInstaller main.spec --noconfirm 2>&1 | ForEach-Object { "$_" }
$buildExit = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if ($buildExit -ne 0) { throw "PyInstaller 빌드 실패 (종료 코드 $buildExit)" }

$exe = Join-Path $PSScriptRoot "dist\LyricsOverlay.exe"

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
