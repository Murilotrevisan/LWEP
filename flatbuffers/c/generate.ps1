# Generate the FlatCC C bindings from the SHARED neutral schema.
#
# `-a` generates reader + builder + verifier. The read path is zero-copy/no-alloc.
#
# Uses the vendored flatcc compiler. Set $env:FLATCC_DIR to override its location.
# Build flatcc first with ../../tools/setup-generators.ps1.
# Output: lwep_reader.h, lwep_builder.h, lwep_verifier.h,
#         flatbuffers_common_reader.h, flatbuffers_common_builder.h  (git-ignored)
$ErrorActionPreference = "Stop"
$here   = Split-Path -Parent $MyInvocation.MyCommand.Path
$schema = Join-Path $here "..\schema\lwep.fbs"
$flatcc = if ($env:FLATCC_DIR) { $env:FLATCC_DIR } else { Join-Path $here "..\..\third_party\flatcc" }

& "$flatcc\bin\flatcc.exe" -a -o "$here" "$schema"
Write-Host "Generated FlatCC headers in $here"
