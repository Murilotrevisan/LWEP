# Generate the nanopb C bindings from the SHARED neutral schema.
#
# Reads ../schema/lwep.proto AND ../schema/lwep.options. The .options file pins
# static sizes (fully-qualified `lwep.<Message>.<field>` names) so the generated
# structs use fixed arrays and need no dynamic allocation.
#
# Uses the vendored nanopb generator (no `pip install nanopb` required). Set
# $env:NANOPB_DIR to override the location. Requires protoc + python on PATH.
# Output: lwep.pb.c, lwep.pb.h  (git-ignored)
$ErrorActionPreference = "Stop"
$here   = Split-Path -Parent $MyInvocation.MyCommand.Path
$schema = Resolve-Path (Join-Path $here "..\schema")
$nanopb = if ($env:NANOPB_DIR) { $env:NANOPB_DIR } else { Join-Path $here "..\..\third_party\nanopb" }

python "$nanopb\generator\nanopb_generator.py" -I "$schema" -D "$here" lwep.proto
Write-Host "Generated lwep.pb.c / lwep.pb.h in $here"
