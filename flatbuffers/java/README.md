# flatbuffers/java — reference target

Java is generated from the **same** `../schema/lwep.fbs` as Python and FlatCC.
It is not part of the live TCP tester; this is a smoke check that the schema
produces a cross-language-compatible buffer.

## Prerequisites

- `flatc` on PATH
- `flatbuffers-java-<version>.jar` from Maven Central. Set `$FB_JAR` below.
  ```sh
  curl -sSLO https://repo1.maven.org/maven2/com/google/flatbuffers/flatbuffers-java/25.2.10/flatbuffers-java-25.2.10.jar
  ```
- a JDK (`javac`, `java`) — validated with Temurin JDK 17

> On MSYS2, convert the jar path to Windows form for Java:
> `FB_JAR=$(cygpath -w /path/to/flatbuffers-java-25.2.10.jar)`.
>
> **Version alignment:** the FlatBuffers runtime jar must match your `flatc`.
> A newer `flatc` emits `Constants.FLATBUFFERS_<ver>()` version-guard calls that
> won't exist in an older runtime jar. If `javac` fails on that symbol, either use
> a matching jar or neutralize the guard in the generated (git-ignored) files:
> `sed -i 's/Constants\.FLATBUFFERS_[0-9_]*();//' lwep/*.java`.

## Generate

```powershell
# from this folder
flatc --java -o . ..\schema\lwep.fbs
# -> ./lwep/*.java  (SensorReading.java, Waveform.java, ...)  (git-ignored)
```

## Compile + run

```sh
javac -cp "$FB_JAR" lwep/*.java Example.java
java  -cp ".:$FB_JAR" Example          # Windows: use ';' instead of ':'
# -> writes sensor.bin
```

## Verify cross-language interop

Decode the Java-produced bytes with the Python bindings:

```python
import sys; sys.path.insert(0, "../python")
from lwep import SensorReading
buf = open("sensor.bin", "rb").read()
sr = SensorReading.SensorReading.GetRootAs(buf, 0)
print(sr.Id(), sr.Label(), sr.Value())   # 4097 b'cabin-temp' 23.5
```

Matching output confirms Java and Python agree on the same neutral schema.

> Note: FlatBuffers Java uses signed storage types for unsigned fields (`ushort`
> is added as `short`, `ubyte` as `byte`). If your flatc version generates
> different `add*` signatures, adjust the casts in `Example.java`.
