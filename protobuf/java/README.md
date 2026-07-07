# protobuf/java — reference target

Java is generated from the **same** `../schema/lwep.proto` as Python and nanopb.
It is not part of the live TCP tester; this is a smoke check that the schema
produces a cross-language-compatible wire format.

## Prerequisites

- `protoc` on PATH
- `protobuf-java-<version>.jar` matching your `protoc` (e.g. protoc 35.1 →
  `protobuf-java-4.35.1.jar` from Maven Central). Set `$PB_JAR` below.
  ```sh
  curl -sSLO https://repo1.maven.org/maven2/com/google/protobuf/protobuf-java/4.35.1/protobuf-java-4.35.1.jar
  ```
- a JDK (`javac`, `java`) — validated with Temurin JDK 17

> On MSYS2, convert the jar path to Windows form for Java:
> `PB_JAR=$(cygpath -w /path/to/protobuf-java-4.35.1.jar)` (Java doesn't
> understand `/c/...` MSYS paths).

## Generate

```powershell
# from this folder
protoc --proto_path=..\schema --java_out=. ..\schema\lwep.proto
# -> ./lwep/Lwep.java  (git-ignored)
```

## Compile + run

```sh
javac -cp "$PB_JAR" lwep/Lwep.java Example.java
java  -cp ".:$PB_JAR" Example          # Windows: use ';' instead of ':'
# -> writes sensor.bin
```

## Verify cross-language interop

Decode the Java-produced bytes with the Python bindings:

```python
import sys; sys.path.insert(0, "../python")
import lwep_pb2
m = lwep_pb2.SensorReading()
m.ParseFromString(open("sensor.bin", "rb").read())
print(m)          # should show id=4097, label="cabin-temp", value=23.5, ...
```

Matching output confirms Java and Python agree on the same neutral schema.
