// LWEP protobuf tester — C++ harness over the nanopb (C) generated code.
//
// Demonstrates encoding/decoding the four catalog messages on the "embedded"
// side with NO dynamic memory allocation: every buffer here is stack/static and
// the nanopb structs use fixed arrays (pinned by ../schema/lwep.options).
//
// Build:  make            (see Makefile)
// Run  :  main server <port>
//         main client <host> <port>
//
// The C++ layer only provides sockets + main(); all message (de)serialization is
// the generated C code (lwep.pb.c) + nanopb runtime (pb_encode/pb_decode/pb_common).

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>

#include "lwep.pb.h"
#include "pb_encode.h"
#include "pb_decode.h"

#ifdef _WIN32
#  include <winsock2.h>
#  include <ws2tcpip.h>
#  ifdef _MSC_VER
#    pragma comment(lib, "ws2_32.lib")   // MSVC auto-link; g++ uses -lws2_32 (see Makefile)
#  endif
typedef SOCKET sock_t;
#  define CLOSESOCK closesocket
#else
#  include <arpa/inet.h>
#  include <netinet/in.h>
#  include <sys/socket.h>
#  include <unistd.h>
typedef int sock_t;
#  define INVALID_SOCKET (-1)
#  define CLOSESOCK close
#endif

// msg_type ids (see ../../common/framing.md)
enum { T_SENSOR = 1, T_WAVEFORM = 2, T_STATUS = 3, T_TELEMETRY = 4 };
static const size_t MAX_FRAME = 512;  // largest payload (TelemetryPacket) fits easily

// ---------------------------------------------------------------- sockets
static bool recv_exact(sock_t s, uint8_t *buf, size_t n) {
    size_t got = 0;
    while (got < n) {
        int r = recv(s, (char *)buf + got, (int)(n - got), 0);
        if (r <= 0) return false;
        got += (size_t)r;
    }
    return true;
}

static bool send_all(sock_t s, const uint8_t *buf, size_t n) {
    size_t sent = 0;
    while (sent < n) {
        int r = send(s, (const char *)buf + sent, (int)(n - sent), 0);
        if (r <= 0) return false;
        sent += (size_t)r;
    }
    return true;
}

static bool send_frame(sock_t s, uint8_t msg_type, const uint8_t *payload, uint32_t len) {
    uint8_t hdr[5];
    uint32_t be = htonl(len);
    memcpy(hdr, &be, 4);
    hdr[4] = msg_type;
    return send_all(s, hdr, 5) && (len == 0 || send_all(s, payload, len));
}

// returns payload length, or -1 on error/close; sets msg_type
static long recv_frame(sock_t s, uint8_t *msg_type, uint8_t *payload, size_t cap) {
    uint8_t hdr[5];
    if (!recv_exact(s, hdr, 5)) return -1;
    uint32_t be;
    memcpy(&be, hdr, 4);
    uint32_t len = ntohl(be);
    *msg_type = hdr[4];
    if (len > cap) return -1;
    if (len && !recv_exact(s, payload, len)) return -1;
    return (long)len;
}

// ---------------------------------------------------------------- nanopb helpers
static uint32_t encode_msg(const pb_msgdesc_t *fields, const void *src, uint8_t *buf, size_t cap) {
    pb_ostream_t st = pb_ostream_from_buffer(buf, cap);
    if (!pb_encode(&st, fields, src)) {
        fprintf(stderr, "encode error: %s\n", PB_GET_ERROR(&st));
        exit(2);
    }
    return (uint32_t)st.bytes_written;
}

static bool decode_msg(const pb_msgdesc_t *fields, void *dst, const uint8_t *buf, uint32_t len) {
    pb_istream_t st = pb_istream_from_buffer(buf, len);
    if (!pb_decode(&st, fields, dst)) {
        fprintf(stderr, "decode error: %s\n", PB_GET_ERROR(&st));
        return false;
    }
    return true;
}

// ---------------------------------------------------------------- builders
static lwep_SensorReading make_sensor(void) {
    lwep_SensorReading m = lwep_SensorReading_init_zero;
    m.id = 4097;
    m.sensor_type = lwep_SensorType_TEMPERATURE;
    m.value = 23.5f;
    m.value_precise = 23.481523;
    m.timestamp = 1720224000000ULL;
    m.is_valid = true;
    m.raw_count = -12345;
    strcpy(m.label, "cabin-temp");
    return m;
}

static lwep_Waveform make_waveform(void) {
    lwep_Waveform m = lwep_Waveform_init_zero;
    m.channel = 3;
    const int16_t s[] = {0, 100, -100, 32767, -32768, 5, 6, 7, 8, 9};
    m.samples_count = 10;
    memcpy(m.samples, s, sizeof(s));
    const float g[] = {1.0f, 0.5f, 0.25f, 2.0f};
    m.gains_count = 4;
    memcpy(m.gains, g, sizeof(g));
    m.tags_count = 3;
    strcpy(m.tags[0], "ch3");
    strcpy(m.tags[1], "raw");
    strcpy(m.tags[2], "v2");
    m.checksum = 0xDEADBEEFu;
    return m;
}

static lwep_DeviceStatus make_status(void) {
    lwep_DeviceStatus m = lwep_DeviceStatus_init_zero;
    m.device_id = 0x2A2A;
    m.flags = (1u << 0) | (1u << 2) | (6u << 4) | (87u << 8);  // 0x5765
    m.error_code = 0;
    return m;
}

static lwep_TelemetryPacket make_telemetry(void) {
    lwep_TelemetryPacket m = lwep_TelemetryPacket_init_zero;
    m.has_header = true;
    m.header.version = 2;
    m.header.seq = 42;
    m.header.source_addr = 0x00A5;
    m.has_reading = true;
    m.reading = make_sensor();
    m.has_waveform = true;
    m.waveform = make_waveform();
    m.has_status = true;
    m.status = make_status();
    m.extra_readings_count = 2;
    lwep_SensorReading &e0 = m.extra_readings[0];
    e0 = lwep_SensorReading_init_zero;
    e0.id = 1; e0.sensor_type = lwep_SensorType_PRESSURE; e0.value = 101.3f;
    e0.value_precise = 101.325; e0.timestamp = 1720224000001ULL; e0.is_valid = true;
    e0.raw_count = 2048; strcpy(e0.label, "baro");
    lwep_SensorReading &e1 = m.extra_readings[1];
    e1 = lwep_SensorReading_init_zero;
    e1.id = 2; e1.sensor_type = lwep_SensorType_HUMIDITY; e1.value = 45.0f;
    e1.value_precise = 45.0; e1.timestamp = 1720224000002ULL; e1.is_valid = false;
    e1.raw_count = 0; strcpy(e1.label, "rh");
    const uint8_t p[] = {0x01, 0x02, 0x03, 0x04, 0xFF, 0xFE, 0xFD, 0x00};
    m.payload.size = sizeof(p);
    memcpy(m.payload.bytes, p, sizeof(p));
    return m;
}

// ---------------------------------------------------------------- compare
static bool eq_sensor(const lwep_SensorReading &a, const lwep_SensorReading &b) {
    return a.id == b.id && a.sensor_type == b.sensor_type && a.value == b.value &&
           a.value_precise == b.value_precise && a.timestamp == b.timestamp &&
           a.is_valid == b.is_valid && a.raw_count == b.raw_count &&
           strcmp(a.label, b.label) == 0;
}
static bool eq_waveform(const lwep_Waveform &a, const lwep_Waveform &b) {
    if (a.channel != b.channel || a.checksum != b.checksum ||
        a.samples_count != b.samples_count || a.gains_count != b.gains_count ||
        a.tags_count != b.tags_count) return false;
    for (pb_size_t i = 0; i < a.samples_count; i++) if (a.samples[i] != b.samples[i]) return false;
    for (pb_size_t i = 0; i < a.gains_count; i++) if (a.gains[i] != b.gains[i]) return false;
    for (pb_size_t i = 0; i < a.tags_count; i++) if (strcmp(a.tags[i], b.tags[i])) return false;
    return true;
}
static bool eq_status(const lwep_DeviceStatus &a, const lwep_DeviceStatus &b) {
    return a.device_id == b.device_id && a.flags == b.flags && a.error_code == b.error_code;
}
static bool eq_telemetry(const lwep_TelemetryPacket &a, const lwep_TelemetryPacket &b) {
    if (a.header.version != b.header.version || a.header.seq != b.header.seq ||
        a.header.source_addr != b.header.source_addr) return false;
    if (!eq_sensor(a.reading, b.reading) || !eq_waveform(a.waveform, b.waveform) ||
        !eq_status(a.status, b.status)) return false;
    if (a.extra_readings_count != b.extra_readings_count) return false;
    for (pb_size_t i = 0; i < a.extra_readings_count; i++)
        if (!eq_sensor(a.extra_readings[i], b.extra_readings[i])) return false;
    if (a.payload.size != b.payload.size) return false;
    return memcmp(a.payload.bytes, b.payload.bytes, a.payload.size) == 0;
}

// ---------------------------------------------------------------- server dump
static void dump(uint8_t t, const uint8_t *payload, uint32_t len) {
    switch (t) {
        case T_SENSOR: {
            lwep_SensorReading m = lwep_SensorReading_init_zero;
            if (decode_msg(lwep_SensorReading_fields, &m, payload, len))
                printf("[server] SensorReading id=%u type=%d value=%.3f label='%s'\n",
                       m.id, (int)m.sensor_type, m.value, m.label);
            break;
        }
        case T_WAVEFORM: {
            lwep_Waveform m = lwep_Waveform_init_zero;
            if (decode_msg(lwep_Waveform_fields, &m, payload, len))
                printf("[server] Waveform ch=%u samples=%u gains=%u tags=%u checksum=0x%08X\n",
                       m.channel, m.samples_count, m.gains_count, m.tags_count, m.checksum);
            break;
        }
        case T_STATUS: {
            lwep_DeviceStatus m = lwep_DeviceStatus_init_zero;
            if (decode_msg(lwep_DeviceStatus_fields, &m, payload, len))
                printf("[server] DeviceStatus dev=0x%04X flags=0x%X err=%u\n",
                       m.device_id, m.flags, m.error_code);
            break;
        }
        case T_TELEMETRY: {
            lwep_TelemetryPacket m = lwep_TelemetryPacket_init_zero;
            if (decode_msg(lwep_TelemetryPacket_fields, &m, payload, len))
                printf("[server] TelemetryPacket seq=%u extra=%u payload=%u bytes\n",
                       m.header.seq, m.extra_readings_count, (unsigned)m.payload.size);
            break;
        }
        default: printf("[server] unknown type %u\n", t);
    }
}

// re-encode a received payload (decode then encode) to echo it back
static uint32_t reencode(uint8_t t, const uint8_t *in, uint32_t len, uint8_t *out, size_t cap) {
    switch (t) {
        case T_SENSOR: { lwep_SensorReading m = lwep_SensorReading_init_zero;
            decode_msg(lwep_SensorReading_fields, &m, in, len);
            return encode_msg(lwep_SensorReading_fields, &m, out, cap); }
        case T_WAVEFORM: { lwep_Waveform m = lwep_Waveform_init_zero;
            decode_msg(lwep_Waveform_fields, &m, in, len);
            return encode_msg(lwep_Waveform_fields, &m, out, cap); }
        case T_STATUS: { lwep_DeviceStatus m = lwep_DeviceStatus_init_zero;
            decode_msg(lwep_DeviceStatus_fields, &m, in, len);
            return encode_msg(lwep_DeviceStatus_fields, &m, out, cap); }
        case T_TELEMETRY: { lwep_TelemetryPacket m = lwep_TelemetryPacket_init_zero;
            decode_msg(lwep_TelemetryPacket_fields, &m, in, len);
            return encode_msg(lwep_TelemetryPacket_fields, &m, out, cap); }
    }
    return 0;
}

// ---------------------------------------------------------------- roles
static int run_server(int port) {
    sock_t srv = socket(AF_INET, SOCK_STREAM, 0);
    int yes = 1;
    setsockopt(srv, SOL_SOCKET, SO_REUSEADDR, (const char *)&yes, sizeof(yes));
    sockaddr_in a{};
    a.sin_family = AF_INET;
    a.sin_addr.s_addr = INADDR_ANY;
    a.sin_port = htons((uint16_t)port);
    if (bind(srv, (sockaddr *)&a, sizeof(a)) != 0) { perror("bind"); return 1; }
    listen(srv, 1);
    printf("[server] listening on :%d\n", port);
    sock_t c = accept(srv, nullptr, nullptr);
    printf("[server] client connected\n");
    static uint8_t in[MAX_FRAME], out[MAX_FRAME];
    uint8_t t;
    long len;
    int count = 0;
    while ((len = recv_frame(c, &t, in, sizeof(in))) >= 0) {
        dump(t, in, (uint32_t)len);
        uint32_t olen = reencode(t, in, (uint32_t)len, out, sizeof(out));
        if (!send_frame(c, t, out, olen)) break;
        count++;
    }
    printf("[server] done, echoed %d message(s)\n", count);
    CLOSESOCK(c);
    CLOSESOCK(srv);
    return 0;
}

template <typename T>
static bool one_roundtrip(sock_t s, const char *name, uint8_t t,
                          const pb_msgdesc_t *fields, const T &msg,
                          bool (*eq)(const T &, const T &)) {
    static uint8_t out[MAX_FRAME], in[MAX_FRAME];
    uint32_t olen = encode_msg(fields, &msg, out, sizeof(out));
    if (!send_frame(s, t, out, olen)) return false;
    uint8_t rt;
    long len = recv_frame(s, &rt, in, sizeof(in));
    if (len < 0) return false;
    T echo;
    memset(&echo, 0, sizeof(echo));
    bool ok = (rt == t) && decode_msg(fields, &echo, in, (uint32_t)len) && eq(msg, echo);
    printf("[client] %-16s %s\n", name, ok ? "PASS" : "FAIL");
    return ok;
}

static int run_client(const char *host, int port) {
    sock_t s = socket(AF_INET, SOCK_STREAM, 0);
    sockaddr_in a{};
    a.sin_family = AF_INET;
    a.sin_port = htons((uint16_t)port);
    inet_pton(AF_INET, host, &a.sin_addr);
    if (connect(s, (sockaddr *)&a, sizeof(a)) != 0) { perror("connect"); return 1; }
    printf("[client] connected to %s:%d\n", host, port);
    bool ok = true;
    ok &= one_roundtrip<lwep_SensorReading>(s, "SensorReading", T_SENSOR,
            lwep_SensorReading_fields, make_sensor(), eq_sensor);
    ok &= one_roundtrip<lwep_Waveform>(s, "Waveform", T_WAVEFORM,
            lwep_Waveform_fields, make_waveform(), eq_waveform);
    ok &= one_roundtrip<lwep_DeviceStatus>(s, "DeviceStatus", T_STATUS,
            lwep_DeviceStatus_fields, make_status(), eq_status);
    ok &= one_roundtrip<lwep_TelemetryPacket>(s, "TelemetryPacket", T_TELEMETRY,
            lwep_TelemetryPacket_fields, make_telemetry(), eq_telemetry);
    printf("[client] %s\n", ok ? "ALL PASS" : "FAILURES PRESENT");
    CLOSESOCK(s);
    return ok ? 0 : 1;
}

int main(int argc, char **argv) {
#ifdef _WIN32
    WSADATA w;
    WSAStartup(MAKEWORD(2, 2), &w);
#endif
    int rc = 1;
    if (argc >= 3 && strcmp(argv[1], "server") == 0) {
        rc = run_server(atoi(argv[2]));
    } else if (argc >= 4 && strcmp(argv[1], "client") == 0) {
        rc = run_client(argv[2], atoi(argv[3]));
    } else {
        fprintf(stderr, "usage: %s server <port> | client <host> <port>\n", argv[0]);
    }
#ifdef _WIN32
    WSACleanup();
#endif
    return rc;
}
