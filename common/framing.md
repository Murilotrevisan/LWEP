# Wire Framing

Both Protobuf and FlatBuffers produce a **raw byte payload** with no built-in
message boundary or type discriminator. Over a TCP stream we therefore wrap every
payload in a tiny fixed header so the receiver knows how many bytes to read and
how to interpret them.

## Frame layout

```
 offset  size  field       description
 ------  ----  ----------  -------------------------------------------------
   0      4    length      payload byte count, uint32, BIG-ENDIAN
   4      1    msg_type    message discriminator, uint8 (see table)
   5      N    payload     serialized message bytes (length == `length`)
```

Total frame size on the wire = `5 + length` bytes.

- `length` counts **only the payload**, not the 5-byte header.
- Big-endian (network byte order) for the length so C (`htonl`/`ntohl`) and
  Python (`struct.pack('>I', ...)`) agree without extra config.

## Message type ids

| id | message         | catalog                                  |
|----|-----------------|------------------------------------------|
| 1  | `SensorReading` | [messages/01-scalars.md](../messages/01-scalars.md)   |
| 2  | `Waveform`      | [messages/02-vectors.md](../messages/02-vectors.md)   |
| 3  | `DeviceStatus`  | [messages/03-bitfields.md](../messages/03-bitfields.md) |
| 4  | `TelemetryPacket`| [messages/04-nested-all.md](../messages/04-nested-all.md) |

## Reference pseudocode

Send:
```
header = pack_uint32_be(len(payload)) + pack_uint8(msg_type)
socket.send_all(header + payload)
```

Receive:
```
hdr      = recv_exact(5)
length   = unpack_uint32_be(hdr[0:4])
msg_type = hdr[4]
payload  = recv_exact(length)
```

`recv_exact(n)` loops on `recv` until exactly `n` bytes have arrived (TCP may
deliver a frame in several chunks). All harnesses in this repo implement this
identical framing so any language can talk to any other.

## Tester protocol

The **client** sends messages 1→4, each as one frame. For every frame the
**server** decodes the payload, prints a field dump, then **echoes** the message
back re-encoded (same `msg_type`). The client decodes the echo and asserts
field-by-field equality against what it sent. Any mismatch → non-zero exit code.
