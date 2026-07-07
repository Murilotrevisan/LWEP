// Minimal LWEP FlatBuffers example (Java) — reference target, not part of the
// live tester. Encodes the canonical SensorReading and writes the buffer to
// sensor.bin so another language (e.g. Python) can decode it, proving the same
// .fbs yields a compatible buffer across Java / Python / C.
//
// Generate + compile + run: see README.md in this folder.

import com.google.flatbuffers.FlatBufferBuilder;
import lwep.SensorReading;
import lwep.SensorType;
import java.io.FileOutputStream;

public class Example {
    public static void main(String[] args) throws Exception {
        FlatBufferBuilder b = new FlatBufferBuilder(64);
        int label = b.createString("cabin-temp");

        SensorReading.startSensorReading(b);
        SensorReading.addId(b, (short) 4097);          // ushort stored as short
        SensorReading.addSensorType(b, SensorType.TEMPERATURE);
        SensorReading.addValue(b, 23.5f);
        SensorReading.addValuePrecise(b, 23.481523);
        SensorReading.addTimestamp(b, 1720224000000L);
        SensorReading.addIsValid(b, true);
        SensorReading.addRawCount(b, -12345);
        SensorReading.addLabel(b, label);
        int off = SensorReading.endSensorReading(b);
        b.finish(off);

        byte[] data = b.sizedByteArray();
        try (FileOutputStream out = new FileOutputStream("sensor.bin")) {
            out.write(data);
        }
        System.out.println("Wrote " + data.length
                + " bytes to sensor.bin (decode with Python to verify interop)");
    }
}
