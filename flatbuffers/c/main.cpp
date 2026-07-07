// LWEP flatbuffers tester — C++ harness over the FlatCC (C) generated code.
//
// Read path is zero-copy and allocation-free (flatcc readers index directly into
// the received buffer). The build path uses the default flatcc_builder (which
// allocates emitter pages via malloc); on a microcontroller you would init the
// builder with a custom emitter/allocator backed by a static buffer — the field
// calls stay identical. Everything here uses fixed-size static/stack frame buffers.
//
// Build:  make            (see Makefile, needs FLATCC_DIR)
// Run  :  main server <port>   |   main client <host> <port>
//
// NOTE: builder/reader function names follow flatcc's generated API for schema
// namespace `lwep`. If your flatcc version differs, adjust accordingly.

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>

#include "lwep_builder.h"
#include "lwep_verifier.h"

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

enum { T_SENSOR = 1, T_WAVEFORM = 2, T_STATUS = 3, T_TELEMETRY = 4 };
static const size_t MAX_FRAME = 1024;

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
static bool send_frame(sock_t s, uint8_t t, const uint8_t *payload, uint32_t len) {
    uint8_t hdr[5];
    uint32_t be = htonl(len);
    memcpy(hdr, &be, 4);
    hdr[4] = t;
    return send_all(s, hdr, 5) && (len == 0 || send_all(s, payload, len));
}
static long recv_frame(sock_t s, uint8_t *t, uint8_t *payload, size_t cap) {
    uint8_t hdr[5];
    if (!recv_exact(s, hdr, 5)) return -1;
    uint32_t be;
    memcpy(&be, hdr, 4);
    uint32_t len = ntohl(be);
    *t = hdr[4];
    if (len > cap) return -1;
    if (len && !recv_exact(s, payload, len)) return -1;
    return (long)len;
}

// ---------------------------------------------------------------- canonical values
struct SensorVals {
    uint16_t id; int type; float value; double value_precise;
    uint64_t timestamp; bool is_valid; int32_t raw_count; const char *label;
};
static const SensorVals SENSOR = {4097, lwep_SensorType_TEMPERATURE, 23.5f,
                                  23.481523, 1720224000000ULL, true, -12345, "cabin-temp"};
static const int16_t SAMPLES[] = {0, 100, -100, 32767, -32768, 5, 6, 7, 8, 9};
static const float GAINS[] = {1.0f, 0.5f, 0.25f, 2.0f};
static const char *TAGS[] = {"ch3", "raw", "v2"};
static const SensorVals EXTRA[] = {
    {1, lwep_SensorType_PRESSURE, 101.3f, 101.325, 1720224000001ULL, true, 2048, "baro"},
    {2, lwep_SensorType_HUMIDITY, 45.0f, 45.0, 1720224000002ULL, false, 0, "rh"},
};
static const uint8_t PAYLOAD[] = {0x01, 0x02, 0x03, 0x04, 0xFF, 0xFE, 0xFD, 0x00};

// ---------------------------------------------------------------- builders
static void put_sensor(flatcc_builder_t *B, const SensorVals &s) {
    lwep_SensorReading_id_add(B, s.id);
    lwep_SensorReading_sensor_type_add(B, (lwep_SensorType_enum_t)s.type);
    lwep_SensorReading_value_add(B, s.value);
    lwep_SensorReading_value_precise_add(B, s.value_precise);
    lwep_SensorReading_timestamp_add(B, s.timestamp);
    lwep_SensorReading_is_valid_add(B, s.is_valid);
    lwep_SensorReading_raw_count_add(B, s.raw_count);
    lwep_SensorReading_label_create_str(B, s.label);
}
static lwep_SensorReading_ref_t ref_sensor(flatcc_builder_t *B, const SensorVals &s) {
    lwep_SensorReading_start(B);
    put_sensor(B, s);
    return lwep_SensorReading_end(B);
}

static void put_waveform(flatcc_builder_t *B) {
    lwep_Waveform_channel_add(B, 3);
    lwep_Waveform_samples_create(B, SAMPLES, sizeof(SAMPLES) / sizeof(SAMPLES[0]));
    lwep_Waveform_gains_create(B, GAINS, sizeof(GAINS) / sizeof(GAINS[0]));
    lwep_Waveform_tags_start(B);
    for (unsigned i = 0; i < sizeof(TAGS) / sizeof(TAGS[0]); i++)
        lwep_Waveform_tags_push_create_str(B, TAGS[i]);
    lwep_Waveform_tags_end(B);
    lwep_Waveform_checksum_add(B, 0xDEADBEEFu);
}
static lwep_Waveform_ref_t ref_waveform(flatcc_builder_t *B) {
    lwep_Waveform_start(B);
    put_waveform(B);
    return lwep_Waveform_end(B);
}

static void put_status(flatcc_builder_t *B) {
    lwep_DeviceStatus_device_id_add(B, 0x2A2A);
    lwep_DeviceStatus_flags_add(B, (1u << 0) | (1u << 2) | (6u << 4) | (87u << 8));
    lwep_DeviceStatus_error_code_add(B, 0);
}
static lwep_DeviceStatus_ref_t ref_status(flatcc_builder_t *B) {
    lwep_DeviceStatus_start(B);
    put_status(B);
    return lwep_DeviceStatus_end(B);
}

// Build one message as the buffer root; returns encoded size (copied into `out`).
static uint32_t build_root(flatcc_builder_t *B, uint8_t t, uint8_t *out, size_t cap) {
    flatcc_builder_reset(B);
    switch (t) {
        case T_SENSOR:
            lwep_SensorReading_start_as_root(B);
            put_sensor(B, SENSOR);
            lwep_SensorReading_end_as_root(B);
            break;
        case T_WAVEFORM:
            lwep_Waveform_start_as_root(B);
            put_waveform(B);
            lwep_Waveform_end_as_root(B);
            break;
        case T_STATUS:
            lwep_DeviceStatus_start_as_root(B);
            put_status(B);
            lwep_DeviceStatus_end_as_root(B);
            break;
        case T_TELEMETRY: {
            lwep_SensorReading_ref_t reading = ref_sensor(B, SENSOR);
            lwep_Waveform_ref_t waveform = ref_waveform(B);
            lwep_DeviceStatus_ref_t status = ref_status(B);
            lwep_SensorReading_ref_t e0 = ref_sensor(B, EXTRA[0]);
            lwep_SensorReading_ref_t e1 = ref_sensor(B, EXTRA[1]);
            lwep_TelemetryPacket_start_as_root(B);
            lwep_TelemetryPacket_header_create(B, 42, 0x00A5, 2);  // seq, source_addr, version
            lwep_TelemetryPacket_reading_add(B, reading);
            lwep_TelemetryPacket_waveform_add(B, waveform);
            lwep_TelemetryPacket_status_add(B, status);
            lwep_TelemetryPacket_extra_readings_start(B);
            lwep_TelemetryPacket_extra_readings_push(B, e0);
            lwep_TelemetryPacket_extra_readings_push(B, e1);
            lwep_TelemetryPacket_extra_readings_end(B);
            lwep_TelemetryPacket_payload_create(B, PAYLOAD, sizeof(PAYLOAD));
            lwep_TelemetryPacket_end_as_root(B);
            break;
        }
        default: return 0;
    }
    size_t size = flatcc_builder_get_buffer_size(B);
    if (size > cap || !flatcc_builder_copy_buffer(B, out, cap)) {
        fprintf(stderr, "build/copy failed (size=%zu cap=%zu)\n", size, cap);
        exit(2);
    }
    return (uint32_t)size;
}

// ---------------------------------------------------------------- compare (reader vs canonical)
static bool eq_sensor(lwep_SensorReading_table_t r, const SensorVals &s) {
    return r && lwep_SensorReading_id(r) == s.id &&
           (int)lwep_SensorReading_sensor_type(r) == s.type &&
           lwep_SensorReading_value(r) == s.value &&
           lwep_SensorReading_value_precise(r) == s.value_precise &&
           lwep_SensorReading_timestamp(r) == s.timestamp &&
           (bool)lwep_SensorReading_is_valid(r) == s.is_valid &&
           lwep_SensorReading_raw_count(r) == s.raw_count &&
           strcmp(lwep_SensorReading_label(r), s.label) == 0;
}

static bool verify_echo(uint8_t t, const uint8_t *buf, uint32_t len) {
    switch (t) {
        case T_SENSOR: {
            if (lwep_SensorReading_verify_as_root(buf, len)) return false;
            return eq_sensor(lwep_SensorReading_as_root(buf), SENSOR);
        }
        case T_WAVEFORM: {
            if (lwep_Waveform_verify_as_root(buf, len)) return false;
            lwep_Waveform_table_t w = lwep_Waveform_as_root(buf);
            flatbuffers_int16_vec_t sm = lwep_Waveform_samples(w);
            flatbuffers_float_vec_t gn = lwep_Waveform_gains(w);
            flatbuffers_string_vec_t tg = lwep_Waveform_tags(w);
            if (lwep_Waveform_channel(w) != 3 || lwep_Waveform_checksum(w) != 0xDEADBEEFu)
                return false;
            if (flatbuffers_int16_vec_len(sm) != 10 || flatbuffers_float_vec_len(gn) != 4 ||
                flatbuffers_string_vec_len(tg) != 3) return false;
            for (size_t i = 0; i < 10; i++)
                if (flatbuffers_int16_vec_at(sm, i) != SAMPLES[i]) return false;
            for (size_t i = 0; i < 4; i++)
                if (flatbuffers_float_vec_at(gn, i) != GAINS[i]) return false;
            for (size_t i = 0; i < 3; i++)
                if (strcmp(flatbuffers_string_vec_at(tg, i), TAGS[i]) != 0) return false;
            return true;
        }
        case T_STATUS: {
            if (lwep_DeviceStatus_verify_as_root(buf, len)) return false;
            lwep_DeviceStatus_table_t d = lwep_DeviceStatus_as_root(buf);
            return lwep_DeviceStatus_device_id(d) == 0x2A2A &&
                   lwep_DeviceStatus_flags(d) == 0x5765u &&
                   lwep_DeviceStatus_error_code(d) == 0;
        }
        case T_TELEMETRY: {
            if (lwep_TelemetryPacket_verify_as_root(buf, len)) return false;
            lwep_TelemetryPacket_table_t tp = lwep_TelemetryPacket_as_root(buf);
            lwep_PacketHeader_struct_t h = lwep_TelemetryPacket_header(tp);
            if (!h || lwep_PacketHeader_seq(h) != 42 ||
                lwep_PacketHeader_source_addr(h) != 0x00A5 ||
                lwep_PacketHeader_version(h) != 2) return false;
            if (!eq_sensor(lwep_TelemetryPacket_reading(tp), SENSOR)) return false;
            lwep_SensorReading_vec_t ev = lwep_TelemetryPacket_extra_readings(tp);
            if (lwep_SensorReading_vec_len(ev) != 2) return false;
            if (!eq_sensor(lwep_SensorReading_vec_at(ev, 0), EXTRA[0])) return false;
            if (!eq_sensor(lwep_SensorReading_vec_at(ev, 1), EXTRA[1])) return false;
            flatbuffers_uint8_vec_t pl = lwep_TelemetryPacket_payload(tp);
            if (flatbuffers_uint8_vec_len(pl) != sizeof(PAYLOAD)) return false;
            for (size_t i = 0; i < sizeof(PAYLOAD); i++)
                if (flatbuffers_uint8_vec_at(pl, i) != PAYLOAD[i]) return false;
            return true;
        }
    }
    return false;
}

// ---------------------------------------------------------------- server dump
static void dump(uint8_t t, const uint8_t *buf, uint32_t len) {
    switch (t) {
        case T_SENSOR: {
            if (lwep_SensorReading_verify_as_root(buf, len)) { printf("[server] bad SensorReading\n"); return; }
            lwep_SensorReading_table_t r = lwep_SensorReading_as_root(buf);
            printf("[server] SensorReading id=%u type=%d value=%.3f label='%s'\n",
                   lwep_SensorReading_id(r), (int)lwep_SensorReading_sensor_type(r),
                   lwep_SensorReading_value(r), lwep_SensorReading_label(r));
            break;
        }
        case T_WAVEFORM: {
            if (lwep_Waveform_verify_as_root(buf, len)) { printf("[server] bad Waveform\n"); return; }
            lwep_Waveform_table_t w = lwep_Waveform_as_root(buf);
            printf("[server] Waveform ch=%u samples=%u gains=%u tags=%u checksum=0x%08X\n",
                   lwep_Waveform_channel(w),
                   (unsigned)flatbuffers_int16_vec_len(lwep_Waveform_samples(w)),
                   (unsigned)flatbuffers_float_vec_len(lwep_Waveform_gains(w)),
                   (unsigned)flatbuffers_string_vec_len(lwep_Waveform_tags(w)),
                   lwep_Waveform_checksum(w));
            break;
        }
        case T_STATUS: {
            if (lwep_DeviceStatus_verify_as_root(buf, len)) { printf("[server] bad DeviceStatus\n"); return; }
            lwep_DeviceStatus_table_t d = lwep_DeviceStatus_as_root(buf);
            printf("[server] DeviceStatus dev=0x%04X flags=0x%X err=%u\n",
                   lwep_DeviceStatus_device_id(d), lwep_DeviceStatus_flags(d),
                   lwep_DeviceStatus_error_code(d));
            break;
        }
        case T_TELEMETRY: {
            if (lwep_TelemetryPacket_verify_as_root(buf, len)) { printf("[server] bad TelemetryPacket\n"); return; }
            lwep_TelemetryPacket_table_t tp = lwep_TelemetryPacket_as_root(buf);
            printf("[server] TelemetryPacket seq=%u extra=%u payload=%u bytes\n",
                   lwep_PacketHeader_seq(lwep_TelemetryPacket_header(tp)),
                   (unsigned)lwep_SensorReading_vec_len(lwep_TelemetryPacket_extra_readings(tp)),
                   (unsigned)flatbuffers_uint8_vec_len(lwep_TelemetryPacket_payload(tp)));
            break;
        }
        default: printf("[server] unknown type %u\n", t);
    }
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
    static uint8_t in[MAX_FRAME];
    uint8_t t;
    long len;
    int count = 0;
    // The read path is zero-copy; we echo the verified buffer back unchanged
    // (a valid FlatBuffer). The Python flatbuffers server demonstrates full
    // re-encode; here we keep the embedded side minimal.
    while ((len = recv_frame(c, &t, in, sizeof(in))) >= 0) {
        dump(t, in, (uint32_t)len);
        if (!send_frame(c, t, in, (uint32_t)len)) break;
        count++;
    }
    printf("[server] done, echoed %d message(s)\n", count);
    CLOSESOCK(c);
    CLOSESOCK(srv);
    return 0;
}

static int run_client(const char *host, int port) {
    sock_t s = socket(AF_INET, SOCK_STREAM, 0);
    sockaddr_in a{};
    a.sin_family = AF_INET;
    a.sin_port = htons((uint16_t)port);
    inet_pton(AF_INET, host, &a.sin_addr);
    if (connect(s, (sockaddr *)&a, sizeof(a)) != 0) { perror("connect"); return 1; }
    printf("[client] connected to %s:%d\n", host, port);

    flatcc_builder_t B;
    flatcc_builder_init(&B);
    static uint8_t out[MAX_FRAME], in[MAX_FRAME];
    const struct { uint8_t t; const char *name; } msgs[] = {
        {T_SENSOR, "SensorReading"}, {T_WAVEFORM, "Waveform"},
        {T_STATUS, "DeviceStatus"}, {T_TELEMETRY, "TelemetryPacket"},
    };
    bool all_ok = true;
    for (auto &m : msgs) {
        uint32_t olen = build_root(&B, m.t, out, sizeof(out));
        send_frame(s, m.t, out, olen);
        uint8_t rt;
        long len = recv_frame(s, &rt, in, sizeof(in));
        bool ok = (len >= 0) && (rt == m.t) && verify_echo(m.t, in, (uint32_t)len);
        printf("[client] %-16s %s\n", m.name, ok ? "PASS" : "FAIL");
        all_ok &= ok;
    }
    flatcc_builder_clear(&B);
    printf("[client] %s\n", all_ok ? "ALL PASS" : "FAILURES PRESENT");
    CLOSESOCK(s);
    return all_ok ? 0 : 1;
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
