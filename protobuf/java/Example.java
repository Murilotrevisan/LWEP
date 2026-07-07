// Minimal LWEP protobuf example (Java) — reference target, not part of the live
// tester. Encodes the canonical SensorReading and writes the raw bytes to
// sensor.bin so another language (e.g. Python) can decode it, proving the same
// .proto yields a compatible wire format across Java / Python / C.
//
// Generate + compile + run: see README.md in this folder.

import lwep.Lwep.SensorReading;
import lwep.Lwep.SensorType;
import java.io.FileOutputStream;

public class Example {
    public static void main(String[] args) throws Exception {
        SensorReading reading = SensorReading.newBuilder()
                .setId(4097)
                .setSensorType(SensorType.TEMPERATURE)
                .setValue(23.5f)
                .setValuePrecise(23.481523)
                .setTimestamp(1720224000000L)
                .setIsValid(true)
                .setRawCount(-12345)
                .setLabel("cabin-temp")
                .build();

        try (FileOutputStream out = new FileOutputStream("sensor.bin")) {
            reading.writeTo(out);
        }
        System.out.println("Wrote " + reading.getSerializedSize()
                + " bytes to sensor.bin (decode with Python to verify interop)");
    }
}
