# Generate the Python protobuf bindings from the shared neutral schema.
#
# Requires: protoc on PATH  (and `pip install protobuf` to run the harness).
# Output:   lwep_pb2.py  (git-ignored)
$ErrorActionPreference = "Stop"
$here   = Split-Path -Parent $MyInvocation.MyCommand.Path
$schema = Join-Path $here "..\schema"

protoc --proto_path="$schema" --python_out="$here" "$schema\lwep.proto"
Write-Host "Generated lwep_pb2.py in $here"
