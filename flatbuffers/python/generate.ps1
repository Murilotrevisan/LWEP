# Generate the Python FlatBuffers bindings from the shared neutral schema.
#
# Requires: flatc on PATH  (and `pip install flatbuffers` >= 2.0 to run harness).
# Output:   lwep/  package with SensorReading.py, Waveform.py, ...  (git-ignored)
$ErrorActionPreference = "Stop"
$here   = Split-Path -Parent $MyInvocation.MyCommand.Path
$schema = Join-Path $here "..\schema\lwep.fbs"

flatc --python -o "$here" "$schema"
Write-Host "Generated lwep/ Python package in $here"
