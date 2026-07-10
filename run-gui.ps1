# Launch the LWEP Interop GUI.
#
# Uses the MSYS2 UCRT64 Python (which has tkinter + flatbuffers + protobuf). The
# plain `python` on PATH is the broken Microsoft Store stub, so we call the real
# interpreter explicitly and put ucrt64\bin on PATH for the C harness DLLs.
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = "C:\msys64\ucrt64\bin\python.exe"
$env:PATH = "C:\msys64\ucrt64\bin;$env:PATH"

if (-not (Test-Path $py)) { Write-Error "Python not found at $py"; exit 1 }
& $py (Join-Path $root "gui\app.py")
