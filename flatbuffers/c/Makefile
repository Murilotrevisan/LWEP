# LWEP flatbuffers/FlatCC C++ harness build.
#
# Prereqs:
#   * g++ and make (Windows: MSYS2/MinGW-w64)
#   * a built flatcc checkout at FLATCC_DIR (default ../../third_party/flatcc) with
#       bin/flatcc(.exe)     the schema compiler
#       include/             flatcc runtime headers
#       lib/libflatccrt.a    the runtime library
#     Get + build it with: ../../tools/setup-generators.ps1
#
# Usage:
#   make generate      # produce lwep_reader.h / lwep_builder.h / lwep_verifier.h
#   make               # build ./main (main.exe on Windows)
#   make clean

CXX        ?= g++
CXXFLAGS   ?= -pipe -O2 -Wall -Wextra -std=c++11
FLATCC_DIR ?= ../../third_party/flatcc

# If the shell provides no temp dir (some minimal/sandboxed environments), point
# the compiler at a writable one so it doesn't fall back to an unwritable path.
ifeq ($(strip $(TMPDIR)$(TMP)$(TEMP)),)
  export TMPDIR := $(CURDIR)
  export TMP    := $(CURDIR)
  export TEMP   := $(CURDIR)
endif

ifeq ($(OS),Windows_NT)
  WIN := 1
endif
ifneq (,$(findstring _NT,$(shell uname -s 2>/dev/null)))
  WIN := 1
endif

FLATCC := $(FLATCC_DIR)/bin/flatcc
GEN    := lwep_reader.h lwep_builder.h lwep_verifier.h
INC    := -I. -I$(FLATCC_DIR)/include
LIB    := -L$(FLATCC_DIR)/lib -lflatccrt

ifdef WIN
  BIN    := main.exe
  LDLIBS := $(LIB) -lws2_32
else
  BIN    := main
  LDLIBS := $(LIB)
endif

all: $(BIN)

$(BIN): main.cpp $(GEN)
	$(CXX) $(CXXFLAGS) $(INC) main.cpp -o $(BIN) $(LDLIBS)

# `-a` generates reader + builder + verifier from ../schema/lwep.fbs.
generate $(GEN):
	$(FLATCC) -a -o . ../schema/lwep.fbs

clean:
	-rm -f $(BIN) main main.exe lwep_*.h flatbuffers_common_*.h *.o

.PHONY: all generate clean
