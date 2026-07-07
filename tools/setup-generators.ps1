# Prepare the two C code generators this lab depends on.
#
# nanopb and flatcc are git SUBMODULES pinned to release tags (see .gitmodules):
#   third_party/nanopb  @ nanopb-0.4.9.1   (generator script + runtime .c/.h)
#   third_party/flatcc  @ v0.6.1           (schema compiler + runtime)
#
# This script:
#   1. initializes/updates the submodules to their pinned commits, then
#   2. builds the flatcc compiler (bin/flatcc.exe) + runtime (lib/libflatccrt.a)
#      directly with gcc — no CMake required.
# nanopb needs no build (its generator is a Python script, its runtime is compiled
# by protobuf/c/Makefile).
#
# Run from an MSYS2/MinGW shell that has git, gcc and ar on PATH:
#   powershell -ExecutionPolicy Bypass -File tools/setup-generators.ps1
$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..")
Set-Location $root

# ---- 1. fetch submodules at their pinned tags ----
Write-Host "Initializing submodules (nanopb, flatcc)..."
git submodule update --init --recursive
$flatcc = Join-Path $root "third_party\flatcc"
$nanopb = Join-Path $root "third_party\nanopb"
if (-not (Test-Path (Join-Path $nanopb "generator\nanopb_generator.py"))) {
    throw "nanopb submodule missing — run 'git submodule update --init' manually."
}

# ---- 2. build flatcc (v0.6.1) with gcc ----
$flatccExe = Join-Path $flatcc "bin\flatcc.exe"
if (-not (Test-Path $flatccExe)) {
    Write-Host "Building flatcc compiler + runtime with gcc..."
    Push-Location $flatcc
    New-Item -ItemType Directory -Force -Path bin, lib | Out-Null

    $inc = @("-Iexternal", "-Iinclude", "-Iconfig")
    # v0.6.1 hashing uses cmetrohash64 (unlike newer master which uses xxhash inline).
    $compilerSrc = @(
        "external/hash/cmetrohash64.c","external/hash/str_set.c","external/hash/ptr_set.c"
        (Get-ChildItem "src/compiler/hash_tables/*.c" | ForEach-Object { $_.FullName })
        "src/compiler/fileio.c","src/compiler/parser.c","src/compiler/semantics.c",
        "src/compiler/coerce.c","src/compiler/flatcc.c",
        "src/compiler/codegen_c.c","src/compiler/codegen_c_reader.c","src/compiler/codegen_c_sort.c",
        "src/compiler/codegen_c_builder.c","src/compiler/codegen_c_verifier.c","src/compiler/codegen_c_sorter.c",
        "src/compiler/codegen_c_json_parser.c","src/compiler/codegen_c_json_printer.c",
        "src/runtime/builder.c","src/runtime/emitter.c","src/runtime/refmap.c",
        "src/cli/flatcc_cli.c"
    )
    & gcc -O2 @inc @compilerSrc -o bin/flatcc.exe
    if ($LASTEXITCODE -ne 0) { throw "flatcc compiler build failed" }

    $rt = @("src/runtime/builder.c","src/runtime/emitter.c","src/runtime/refmap.c",
            "src/runtime/verifier.c","src/runtime/json_parser.c","src/runtime/json_printer.c")
    & gcc -O2 -Iinclude -Iconfig -c @rt
    if ($LASTEXITCODE -ne 0) { throw "flatcc runtime build failed" }
    & ar rcs lib/libflatccrt.a builder.o emitter.o refmap.o verifier.o json_parser.o json_printer.o
    Remove-Item *.o -Force
    Pop-Location
    Write-Host "flatcc built: $flatccExe"
} else { Write-Host "flatcc already built." }

& $flatccExe --version
Write-Host "Generators ready under third_party/ (nanopb + flatcc pinned to release tags)."
