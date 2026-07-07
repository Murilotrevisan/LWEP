# LWEP protobuf/nanopb C++ harness build.
#
# Prereqs:
#   * g++ and make (Windows: MSYS2/MinGW-w64; Linux/macOS: system toolchain)
#   * a nanopb checkout at NANOPB_DIR (default ../../third_party/nanopb) that
#     provides BOTH the generator (generator/nanopb_generator.py) and the runtime
#     sources (pb_encode.c / pb_decode.c / pb_common.c / pb.h).
#     Get it with: ../../tools/setup-generators.ps1  (or clone it yourself).
#
# Usage:
#   make generate      # produce lwep.pb.c / lwep.pb.h from ../schema (needs protoc + python)
#   make               # build ./main (main.exe on Windows)
#   make clean

CXX        ?= g++
CXXFLAGS   ?= -pipe -O2 -Wall -Wextra -std=c++11
NANOPB_DIR ?= ../../third_party/nanopb

# If the shell provides no temp dir (some minimal/sandboxed environments), point
# the compiler at a writable one so it doesn't fall back to an unwritable path.
ifeq ($(strip $(TMPDIR)$(TMP)$(TEMP)),)
  export TMPDIR := $(CURDIR)
  export TMP    := $(CURDIR)
  export TEMP   := $(CURDIR)
endif

# --- Windows detection: works for native make (OS) and MSYS2/Cygwin make (uname) ---
ifeq ($(OS),Windows_NT)
  WIN := 1
endif
ifneq (,$(findstring _NT,$(shell uname -s 2>/dev/null)))
  WIN := 1
endif

GEN     := lwep.pb.c lwep.pb.h
RUNTIME := $(NANOPB_DIR)/pb_encode.c $(NANOPB_DIR)/pb_decode.c $(NANOPB_DIR)/pb_common.c
INC     := -I. -I$(NANOPB_DIR)

ifdef WIN
  BIN    := main.exe
  LDLIBS := -lws2_32
else
  BIN    := main
  LDLIBS :=
endif

all: $(BIN)

$(BIN): main.cpp $(GEN)
	$(CXX) $(CXXFLAGS) $(INC) main.cpp lwep.pb.c $(RUNTIME) -o $(BIN) $(LDLIBS)

# Generate directly from the vendored nanopb generator (reads ../schema/lwep.proto
# + lwep.options). No pip install required. PowerShell users can run generate.ps1.
generate $(GEN):
	python $(NANOPB_DIR)/generator/nanopb_generator.py -I ../schema -D . lwep.proto

clean:
	-rm -f $(BIN) main main.exe lwep.pb.c lwep.pb.h *.o

.PHONY: all generate clean
