# Sparkit BD Agent quick start script (PowerShell)

param(
    [switch]$SkipTests,
    [switch]$CoreTests
)

$projectPath = "C:\Users\vince\PythonProject\sparkit-bd-agent"
$envName = "sparkit-bd"

Set-Location $projectPath

Write-Host "[1/4] Activating conda env: $envName" -ForegroundColor Cyan
conda activate $envName
if ($LASTEXITCODE -ne 0) {
    Write-Host "Conda activation failed. Try: conda init powershell, then reopen PowerShell." -ForegroundColor Red
    exit 1
}

Write-Host "[2/4] Python version" -ForegroundColor Cyan
python -V
if ($LASTEXITCODE -ne 0) {
    Write-Host "Python check failed." -ForegroundColor Red
    exit 1
}

Write-Host "[3/4] Dependency sanity check" -ForegroundColor Cyan
python -c "import httpx,openai,fastapi,langgraph,pytest; print('env ok')"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Dependency check failed." -ForegroundColor Red
    exit 1
}

if (-not $SkipTests) {
    Write-Host "[4/4] Running tests" -ForegroundColor Cyan
    if ($CoreTests) {
        python -m pytest -q test_researcher.py test_scorer.py test_emailer.py
    } else {
        python -m pytest -q
    }

    if ($LASTEXITCODE -ne 0) {
        Write-Host "Tests failed." -ForegroundColor Yellow
        exit $LASTEXITCODE
    }

    Write-Host "All good." -ForegroundColor Green
} else {
    Write-Host "[4/4] Tests skipped by -SkipTests" -ForegroundColor Yellow
}
