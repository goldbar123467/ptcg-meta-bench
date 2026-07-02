$ErrorActionPreference = "Stop"

function Fail($Message) {
    Write-Error "ptcg install: $Message"
    exit 1
}

function Get-EnvOrDefault($Name, $Default) {
    $Value = [Environment]::GetEnvironmentVariable($Name)
    if ([string]::IsNullOrWhiteSpace($Value)) { return $Default }
    return $Value
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Fail "Python 3.10 or newer is required. Install Python from python.org, then run this command again."
}
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
if ($LASTEXITCODE -ne 0) {
    Fail "Python 3.10 or newer is required. Your python command is too old."
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Fail "git is required. Install Git for Windows, then run this command again."
}

$PTCG_REPO_URL = Get-EnvOrDefault "PTCG_REPO_URL" "https://github.com/goldbar123467/ptcg-meta-bench.git"
$PTCG_REF = Get-EnvOrDefault "PTCG_REF" "main"
$PTCG_INSTALL_DIR = Get-EnvOrDefault "PTCG_INSTALL_DIR" (Join-Path $env:LOCALAPPDATA "ptcg-meta-bench")
$PTCG_SOURCE_DIR = Join-Path $PTCG_INSTALL_DIR "source"
$PTCG_VENV_DIR = Join-Path $PTCG_INSTALL_DIR "venv"
$PTCG_BIN = Join-Path $PTCG_VENV_DIR "Scripts\ptcg.exe"

New-Item -ItemType Directory -Force -Path $PTCG_INSTALL_DIR | Out-Null

if (Test-Path (Join-Path $PTCG_SOURCE_DIR ".git")) {
    Write-Host "ptcg is already installed at $PTCG_INSTALL_DIR; updating it."
    git -C $PTCG_SOURCE_DIR fetch --all --tags --quiet
} else {
    Write-Host "Installing ptcg into $PTCG_INSTALL_DIR."
    git clone --quiet $PTCG_REPO_URL $PTCG_SOURCE_DIR
    if ($LASTEXITCODE -ne 0) { Fail "Could not clone $PTCG_REPO_URL." }
}

git -C $PTCG_SOURCE_DIR checkout --quiet $PTCG_REF
if ($LASTEXITCODE -ne 0) { Fail "Could not check out $PTCG_REF." }

Write-Host "Creating isolated Python environment."
python -m venv $PTCG_VENV_DIR
if ($LASTEXITCODE -ne 0) { Fail "Could not create a Python virtual environment." }

$VenvPython = Join-Path $PTCG_VENV_DIR "Scripts\python.exe"
& $VenvPython -m pip install --upgrade pip | Out-Null
& $VenvPython -m pip install -e $PTCG_SOURCE_DIR | Out-Null

$PTCG_SDK_ZIP = [Environment]::GetEnvironmentVariable("PTCG_SDK_ZIP")
if (-not [string]::IsNullOrWhiteSpace($PTCG_SDK_ZIP)) {
    if (-not (Test-Path $PTCG_SDK_ZIP)) { Fail "PTCG_SDK_ZIP points to a file that does not exist: $PTCG_SDK_ZIP" }
    $CompetitionDir = Join-Path $PTCG_SOURCE_DIR "data\competition"
    New-Item -ItemType Directory -Force -Path $CompetitionDir | Out-Null
    Copy-Item $PTCG_SDK_ZIP (Join-Path $CompetitionDir "pokemon-tcg-ai-battle.zip") -Force
    & $PTCG_BIN bootstrap --sdk-zip (Join-Path $CompetitionDir "pokemon-tcg-ai-battle.zip") | Out-Null
}

Write-Host "Running ptcg doctor."
& $PTCG_BIN doctor
if ($LASTEXITCODE -ne 0) {
    Fail "ptcg installed, but doctor found a problem. If the SDK is missing, set PTCG_SDK_ZIP to your Kaggle zip and rerun."
}

Write-Host "Running ptcg demo."
& $PTCG_BIN demo
if ($LASTEXITCODE -ne 0) { Fail "ptcg demo failed." }

Write-Host "ptcg installed. Run '$PTCG_BIN' from any PowerShell session."
