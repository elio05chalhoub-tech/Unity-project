# =============================================
# AI World Project — NUKE & REBUILD Environment
# =============================================
# This script:
#   1. Purges ALL old virtual environments + __pycache__
#   2. Creates a single clean .venv
#   3. Upgrades pip
#   4. Installs all pip dependencies
#   5. Installs "git-deps" (moge, pytorch3d) from GitHub
#   6. Verifies everything works
# =============================================

$ErrorActionPreference = "Stop"
$BackendDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host '==========================================' -ForegroundColor Cyan
Write-Host '  AI World Project - NUKE AND REBUILD     ' -ForegroundColor Cyan
Write-Host '==========================================' -ForegroundColor Cyan
Write-Host ""

# -------------------------------------------
# Step 1: PURGE — Remove ALL old environments
# -------------------------------------------
Write-Host '[1/6] PURGING old environments + caches...' -ForegroundColor Yellow

# Remove virtual environments
$venvPaths = @(
    (Join-Path $BackendDir "venv"),
    (Join-Path $BackendDir ".venv")
)

foreach ($venvPath in $venvPaths) {
    if (Test-Path $venvPath) {
        Write-Host "  Removing: $venvPath" -ForegroundColor Red
        Remove-Item -Recurse -Force $venvPath
    }
    else {
        Write-Host "  Not found (skip): $venvPath" -ForegroundColor DarkGray
    }
}

# Remove ALL __pycache__ directories recursively
$cacheCount = 0
Get-ChildItem -Path $BackendDir -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | ForEach-Object {
    Remove-Item -Recurse -Force $_.FullName
    $cacheCount++
}
Write-Host "  Removed $cacheCount __pycache__ directories" -ForegroundColor DarkGray

Write-Host "  Purge complete." -ForegroundColor Green
Write-Host ""

# -------------------------------------------
# Step 2: CREATE fresh .venv
# -------------------------------------------
Write-Host '[2/6] Creating fresh virtual environment (.venv)...' -ForegroundColor Yellow

$newVenv = Join-Path $BackendDir ".venv"
py -3.11 -m venv $newVenv

if (-not (Test-Path (Join-Path $newVenv "Scripts\python.exe"))) {
    Write-Host "  ERROR: Failed to create virtual environment!" -ForegroundColor Red
    exit 1
}

Write-Host "  Created: $newVenv" -ForegroundColor Green
Write-Host ""

# -------------------------------------------
# Step 3: UPGRADE pip
# -------------------------------------------
Write-Host '[3/6] Upgrading pip + setuptools + wheel...' -ForegroundColor Yellow

$pipExe = Join-Path $newVenv "Scripts\pip.exe"
$pythonExe = Join-Path $newVenv "Scripts\python.exe"

& $pythonExe -m pip install --upgrade pip setuptools wheel --quiet
Write-Host "  Done." -ForegroundColor Green
Write-Host ""

# -------------------------------------------
# Step 4: INSTALL pip dependencies
# -------------------------------------------
Write-Host "[4/6] Installing dependencies from requirements.txt..." -ForegroundColor Yellow
Write-Host "  (This may take several minutes)" -ForegroundColor DarkGray

$reqFile = Join-Path $BackendDir "requirements.txt"
& $pipExe install -r $reqFile

if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: pip install failed!" -ForegroundColor Red
    Write-Host "  TIP: Make sure PyTorch is installed first via https://pytorch.org" -ForegroundColor Yellow
    exit 1
}

Write-Host "  Done." -ForegroundColor Green
Write-Host ""

# -------------------------------------------
# Step 5: INSTALL Git-Deps (manual installs)
# -------------------------------------------
Write-Host "[5/6] Installing Git-Deps (moge, pytorch3d)..." -ForegroundColor Yellow

# MoGe — Monocular Geometry Estimation (used by HunyuanWorld for depth maps)
Write-Host "  Installing MoGe from GitHub..." -ForegroundColor DarkGray
& $pipExe install git+https://github.com/microsoft/moge.git 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  WARNING: MoGe install failed. You may need to install it manually." -ForegroundColor Yellow
    Write-Host "  Command: pip install git+https://github.com/microsoft/moge.git" -ForegroundColor DarkGray
}
else {
    Write-Host "  MoGe installed." -ForegroundColor Green
}

# PyTorch3D — 3D operations (optional, used for some mesh transforms)
Write-Host "  Installing PyTorch3D from GitHub..." -ForegroundColor DarkGray
& $pipExe install git+https://github.com/facebookresearch/pytorch3d.git 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  WARNING: PyTorch3D install failed. You may need to install it manually." -ForegroundColor Yellow
    Write-Host "  Command: pip install git+https://github.com/facebookresearch/pytorch3d.git" -ForegroundColor DarkGray
}
else {
    Write-Host "  PyTorch3D installed." -ForegroundColor Green
}

Write-Host ""

# -------------------------------------------
# Step 6: VERIFY everything
# -------------------------------------------
Write-Host "[6/6] Verifying installation..." -ForegroundColor Yellow

$verifyScript = @"
import sys
errors = []

# --- Core API ---
try:
    import fastapi
    print(f'  FastAPI:       {fastapi.__version__}')
except ImportError as e:
    errors.append(f'FastAPI: {e}')

try:
    import pydantic
    print(f'  Pydantic:      {pydantic.__version__}')
except ImportError as e:
    errors.append(f'Pydantic: {e}')

try:
    import pydantic_core
    print(f'  Pydantic-Core: {pydantic_core.__version__}')
except ImportError as e:
    errors.append(f'Pydantic-Core: {e}')

# --- NumPy version check (must be < 2.0) ---
try:
    import numpy as np
    ver = tuple(int(x) for x in np.__version__.split('.')[:2])
    if ver[0] >= 2:
        errors.append(f'NumPy {np.__version__} is >= 2.0! HunyuanWorld requires < 2.0')
        print(f'  NumPy:         {np.__version__} (BAD - must be < 2.0!)')
    else:
        print(f'  NumPy:         {np.__version__} (OK < 2.0)')
except ImportError as e:
    errors.append(f'NumPy: {e}')

# --- AI Libraries ---
try:
    import diffusers
    print(f'  Diffusers:     {diffusers.__version__}')
except ImportError as e:
    errors.append(f'Diffusers: {e}')

try:
    import transformers
    print(f'  Transformers:  {transformers.__version__}')
except ImportError as e:
    errors.append(f'Transformers: {e}')

# --- 3D Libraries ---
try:
    import trimesh
    print(f'  Trimesh:       {trimesh.__version__}')
except ImportError as e:
    errors.append(f'Trimesh: {e}')

try:
    import open3d
    print(f'  Open3D:        {open3d.__version__}')
except ImportError as e:
    errors.append(f'Open3D: {e}')

# --- Persistence ---
try:
    import aiosqlite
    print(f'  aiosqlite:     {aiosqlite.__version__}')
except ImportError as e:
    errors.append(f'aiosqlite: {e}')

# --- Result ---
print()
if errors:
    print(f'  FAILED — {len(errors)} error(s):')
    for err in errors:
        print(f'    - {err}')
    sys.exit(1)
else:
    print('  All core imports OK!')
    sys.exit(0)
"@

& $pythonExe -c $verifyScript

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "  Verification FAILED. Check errors above." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host '==========================================' -ForegroundColor Green
Write-Host '  NUKE AND REBUILD COMPLETE!               ' -ForegroundColor Green
Write-Host '==========================================' -ForegroundColor Green
Write-Host ''
Write-Host 'Next steps:' -ForegroundColor Cyan
Write-Host '  1. Activate:  .\.venv\Scripts\Activate.ps1' -ForegroundColor White
Write-Host '  2. Install PyTorch with CUDA:' -ForegroundColor White
Write-Host '     pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121' -ForegroundColor DarkGray
Write-Host '  3. Run server:' -ForegroundColor White
Write-Host '     python -m uvicorn main:app --host 0.0.0.0 --port 8000' -ForegroundColor DarkGray
Write-Host '  4. Test:' -ForegroundColor White
Write-Host '     curl http://localhost:8000/health' -ForegroundColor DarkGray
Write-Host ''
