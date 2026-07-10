# LWEP interop test runner (Definition-of-Done gate for the GUI).
#
# 1. Rebuilds the FlatBuffers C harness (which now re-encodes in its server).
# 2. Runs the headless interop suite over the same wire/codecs/cpeer modules the
#    GUI uses: 2 IDLs x 4 messages x (unit + Python->C + C->Python).
#
# The suite's exit code is propagated, so CI / `powershell -File run-tests.ps1`
# fails loudly unless every case passes.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = "C:\msys64\ucrt64\bin\python.exe"

# MSYS2 UCRT64 toolchain: g++ + runtime DLLs (ucrt64\bin) and make + sh (usr\bin).
$env:PATH = "C:\msys64\ucrt64\bin;C:\msys64\usr\bin;$env:PATH"

if (-not (Test-Path $py)) { Write-Error "Python not found at $py"; exit 1 }

Write-Host "== Rebuilding flatbuffers/c (re-encode server) ==" -ForegroundColor Cyan
Push-Location (Join-Path $root "flatbuffers\c")
try { & make } finally { Pop-Location }
if ($LASTEXITCODE -ne 0) { Write-Error "FlatBuffers C build failed"; exit $LASTEXITCODE }

Write-Host "== Running interop suite ==" -ForegroundColor Cyan
& $py (Join-Path $root "gui\tests\interop_test.py")
$code = $LASTEXITCODE
if ($code -eq 0) { Write-Host "run-tests: OK" -ForegroundColor Green }
else { Write-Host "run-tests: FAILURES (exit $code)" -ForegroundColor Red }
exit $code
