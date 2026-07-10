# Plano — GUI Tkinter para validar interop Python ↔ C (Protobuf/nanopb e FlatBuffers/FlatCC)

## Context

O repositório LWEP já tem harnesses de round-trip (Python e C++) para as 4 mensagens do
catálogo, mas eles rodam com valores **fixos (canônicos)** e sem interface. O usuário quer
uma **GUI (Tkinter)** para, a partir do Python, escolher **papel** (server/client) e **IDL**
(protobuf/flatbuffer) e:

- **server** → o Python é a **origem**: seleciona uma mensagem, altera seus valores e vê
  **como ela foi montada na serialização** (bytes/hex + campos).
- **client** → o Python é o **destino**: vê as **mensagens recebidas** e **como foram
  parseadas** (campos).
- Em ambos os modos o outro lado é o **programa gerado em C**, para validar que os dados são
  coerentes entre linguagens.

Decisões confirmadas com o usuário:
1. Papéis exatamente assim (server=edita/serializa, client=recebe/parse); o C assume o papel
   oposto **automaticamente**.
2. A GUI faz **auto-spawn** do `main.exe` em C e **captura o stdout** dele (é a prova visual de
   que o C decodificou/validou os dados do Python).
3. Edição **simples primeiro**: `SensorReading` e `DeviceStatus` totalmente editáveis;
   `Waveform` e `TelemetryPacket` partem dos valores canônicos (edição de vetores/aninhados
   fica para depois) — mas as 4 podem ser serializadas/enviadas e recebidas/parseadas.
4. **(revisão do usuário)** O server FlatBuffers em C passa a **re-encodar** (decodifica →
   reconstrói o buffer via flatcc builder → ecoa o re-encodado), simétrico ao protobuf — assim o
   echo também prova o decode do lado C. Requer editar `flatbuffers/c/main.cpp` e **recompilar** o
   `main.exe`.
5. **(revisão do usuário)** Após aprovação, este plano é adicionado ao repo como
   `docs/gui-interop-plan.md`.

### Ambiente verificado
- Python real: `C:\msys64\ucrt64\bin\python.exe` (3.14.6) com **tkinter 8.6**, **flatbuffers
  25.12.19**, **protobuf 7.35.1**. (O `python` no PATH é o stub quebrado da Microsoft Store —
  não usar.)
- Binários C **já compilados e rodando**: [protobuf/c/main.exe](protobuf/c/main.exe) e
  [flatbuffers/c/main.exe](flatbuffers/c/main.exe), CLI `main {server <port> | client <host> <port>}`.
- Código Python gerado presente: [protobuf/python/lwep_pb2.py](protobuf/python/lwep_pb2.py) e o
  pacote [flatbuffers/python/lwep/](flatbuffers/python/lwep/).
- `make` não está no PATH, mas **não é necessário** (os `.exe` já existem). `protoc`/`flatc`/`g++`
  estão no msys64 caso precise regenerar.

## Mapeamento de papéis (o núcleo do design — sem alterar o C)

| GUI (Python) | Python faz | Peer C (auto-spawn) | Papel TCP |
|---|---|---|---|
| **server** | edita → serializa → **envia** → recebe echo → compara | `main server <port>` (decodifica, faz dump no stdout, ecoa) | Python = **client** conecta em 127.0.0.1:`port` |
| **client** | **escuta** → recebe → parseia → ecoa de volta | `main client 127.0.0.1 <port>` (envia os 4 canônicos, checa echo) | Python = **server** faz `listen(port)` |

Assim o C fica **inalterado**: reaproveitamos os `main.exe` existentes. A coerência é provada nos
dois sentidos: Python-encode→C-decode (modo server) e C-encode→Python-decode (modo client).

> Nota FlatBuffers: hoje o `main server` em C ecoa o buffer sem re-encodar. **Vamos alterá-lo**
> (ver seção "Alteração no C") para decodificar → reconstruir → ecoar o buffer re-encodado,
> ficando simétrico ao protobuf: o echo passa a provar o decode do lado C nas duas IDLs (o stdout
> do C continua exibido como prova adicional).

## Arquitetura / arquivos novos (pasta `gui/` na raiz)

Um app Tkinter único, com núcleo reutilizável. O **único** arquivo de código existente alterado é
`flatbuffers/c/main.cpp` (ver "Alteração no C"); os demais harnesses ficam intactos.

- **`gui/wire.py`** — framing idêntico ao dos harnesses (`recv_exact`, `recv_frame`,
  `send_frame`) + `hexdump(bytes)->str`. Espelha
  [common/framing.md](common/framing.md) e o código já em
  [protobuf/python/server.py:25-47](protobuf/python/server.py#L25-L47).

- **`gui/codecs.py`** — camada neutra de IDL:
  - `CANON` (dicts, mesmos valores de [flatbuffers/python/lwepfb.py:20-53](flatbuffers/python/lwepfb.py#L20-L53)
    e [protobuf/python/client.py:48-94](protobuf/python/client.py#L48-L94), com enum como `int`).
  - `FIELD_SCHEMA` para as mensagens editáveis (`SensorReading`, `DeviceStatus`): por campo
    `{key, label, kind: int|uint|float|double|bool|enum|string, min/max/bytes, enum_choices}`.
    `Waveform`/`TelemetryPacket` marcadas como "somente canônico" (exibidas read-only).
  - `PbCodec` — usa `lwep_pb2` (adiciona `protobuf/python` ao `sys.path`); `encode(t, dict)->bytes`,
    `decode(t, bytes)->dict`, `dump(dict)->str`. Converte dict↔mensagem espelhando os builders de
    [protobuf/python/client.py](protobuf/python/client.py) para manter o **mesmo formato de dict**
    dos FlatBuffers (form e comparação ficam compartilhados).
  - `FbCodec` — **reaproveita** [flatbuffers/python/lwepfb.py](flatbuffers/python/lwepfb.py)
    (`encode`/`decode`/`NAMES`) via import (adiciona `flatbuffers/python` ao `sys.path`).
  - `get_codec(idl)` fábrica; ambos expõem a mesma interface e o mesmo shape de dict.

- **`gui/cpeer.py`** — gerência do subprocesso C: monta o comando
  (`<idl>/c/main.exe server <port>` ou `client 127.0.0.1 <port>`), faz spawn com
  `C:\msys64\ucrt64\bin` **prependado ao PATH** (para as DLLs UCRT), e lê o `stdout` em uma
  **thread** empurrando linhas para uma `queue.Queue`. Descobre os caminhos a partir da raiz do
  repo (`__file__`). `start()/stop()`.

- **`gui/app.py`** — aplicação Tkinter (entrypoint). Topo: rádios **IDL** (protobuf/flatbuffer)
  e **papel** (server/client) + host/porta (default 127.0.0.1:9001). Toda I/O de rede roda em
  **thread worker**; resultados voltam à UI por `queue.Queue` + `root.after(50, poll)` (Tkinter é
  single-thread). Layout:
  - **Modo server (editor):** seletor de mensagem (1–4); painel de edição gerado pelo
    `FIELD_SCHEMA` (Entry/Checkbutton/OptionMenu, com validação; Waveform/Telemetry read-only
    canônico); botão **Serializar & Enviar**. Painéis de saída: "Serialização (Python)" com
    `len` + **hexdump** + dump de campos; "Echo re-parseado" com PASS/FAIL; "Saída do C (stdout)".
  - **Modo client (receptor):** botão **Escutar & Receber**; ao conectar, auto-spawn do
    `main client`. Lista/tree "Mensagens recebidas + parse (Python)" (por mensagem: nome, hexdump
    recebido, campos parseados) + Python ecoa de volta; painel "Saída do C (stdout)" mostrando os
    `PASS`/`ALL PASS` do cliente C.

- **`gui/forms.py`** — construtor de formulário dirigido por `FIELD_SCHEMA`: cria os widgets,
  valida e lê de volta para o dict (levanta erro amigável em entrada inválida, ex.: `flags` em hex,
  faixa de `uint16`). (Pode ficar dentro de `app.py` se preferir menos arquivos; mantido separado
  pela clareza do gerador de form.)

- **`gui/README.md`** — como abrir (com o caminho do python do msys64), a tabela de mapeamento de
  papéis, e o que cada painel mostra.

- **`run-gui.ps1`** (raiz) — atalho: `& "C:\msys64\ucrt64\bin\python.exe" gui\app.py` (evita o stub
  quebrado do `python` da Store).

## Fluxos detalhados

**server (Python encode → C decode):** editar dict → `codec.encode` → mostrar `len`+hex+campos →
auto-spawn `main server <port>` → conectar (retry até subir) → `send_frame` → `recv_frame` do echo
→ `codec.decode(echo)` → comparar com o enviado (normalizando float32 como em
[flatbuffers/python/client.py:43-55](flatbuffers/python/client.py#L43-L55)) → PASS/FAIL. Conexão
fica aberta para reenviar após novas edições; botão "Encerrar" fecha o socket (o server C finaliza
e imprime `done, echoed N`).

**client (C encode → Python decode):** `bind`+`listen(port)` → auto-spawn `main client 127.0.0.1
<port>` → para cada frame recebido: `codec.decode` → exibir campos+hex → **re-encodar e ecoar**
(para o cliente C validar) → ao final, stdout do C mostra `ALL PASS`.

## Alteração no C (FlatBuffers) — re-encode no server

Editar [flatbuffers/c/main.cpp](flatbuffers/c/main.cpp) para o `run_server` **decodificar e
reconstruir** o buffer antes de ecoar (hoje ecoa `in` inalterado em
[flatbuffers/c/main.cpp:319-322](flatbuffers/c/main.cpp#L319-L322)):

- Inicializar um `flatcc_builder_t B` no `run_server` (como o `run_client` já faz) + buffer estático
  `out[MAX_FRAME]`.
- Adicionar `reencode(t, in, len, &B, out, cap)`: para cada tipo, **ler** os campos do buffer
  recebido com os readers `lwep_*` já usados no `dump`/`verify_echo` e **reconstruir** com os
  builders `lwep_*_start_as_root/_add/_end_as_root`. Cobre os 4 tipos (inclui `Waveform` com
  `samples/gains/tags`, e `TelemetryPacket` aninhado com `extra_readings`/`payload`), espelhando o
  `decode`+`encode` do [flatbuffers/python/lwepfb.py](flatbuffers/python/lwepfb.py). Os helpers
  `put_*` de canônicos podem ser generalizados para receber valores lidos, ou usar funções
  `reenc_*` dedicadas.
- No loop do server, trocar `send_frame(c, t, in, len)` por `send_frame(c, t, out, reencode(...))`.
- `MAX_FRAME` (1024) comporta o telemetry re-encodado.

**Recompilar:** `make -C flatbuffers/c` usando `C:\msys64\usr\bin\make` (ou `mingw32-make`) — o
runtime `third_party/flatcc/lib/libflatccrt.a` e `flatcc.exe` já existem. O protobuf C não muda
(já re-encoda).

## Reuso (evitar código novo)
- Framing: espelha `recv_exact/recv_frame/send_frame` já existentes (idênticos em todos os
  harnesses).
- FlatBuffers: importa e reusa `lwepfb.encode/decode/NAMES/CANON` — fonte única de verdade.
- Protobuf: espelha os builders de `client.py` (`make_sensor`/`make_status`/...) porém dirigidos por
  dict (editável), reaproveitando `lwep_pb2`.
- Valores canônicos e enum `SensorType` (0..4) idênticos entre as duas IDLs → um único `CANON`/form
  serve para ambas.

## Entregável de documentação
Após aprovação, gravar este plano em **`docs/gui-interop-plan.md`** (ao lado de
[docs/lwep-plan.md](docs/lwep-plan.md)).

## Testes automatizados (gate de entrega)
Suíte headless que exercita **os mesmos módulos** `wire`/`codecs`/`cpeer` que a GUI usa (por isso o
núcleo é separado do Tkinter), sem cliques. Arquivos:

- **`gui/tests/interop_test.py`** — runner autocontido (sem pytest; asserts + resumo `ALL PASS` +
  `sys.exit(0/1)`, no estilo de [protobuf/python/client.py](protobuf/python/client.py)):
  - **A. Unit (sem rede):** para cada IDL ∈ {protobuf, flatbuffer} × `msg_type` ∈ 1..4:
    `assert codec.decode(t, codec.encode(t, CANON[t])) == norm(CANON[t])` (normalizando float32).
  - **B. Interop Python→C (modo server):** auto-spawn `<idl>/c/main.exe server <port>`; conectar;
    para cada `t`: enviar `encode(CANON[t])`, receber echo, `assert decode(echo)==norm`; ao fechar,
    `assert` que o C saiu com `done, echoed 4`. (Cobre o **re-encode novo do FB C**.)
  - **C. Interop C→Python (modo client):** `listen(port)`; auto-spawn `<idl>/c/main.exe client
    127.0.0.1 <port>`; aceitar; para cada um dos 4 frames: `decode`, `assert == norm(CANON)`,
    re-encodar e ecoar; `assert` processo C sai `0` e stdout contém `ALL PASS`.
  - Porta distinta por caso (evita TIME_WAIT); timeouts para não travar; mata o subprocesso em erro.
- **`run-tests.ps1`** (raiz) — recompila o FB C (`make -C flatbuffers/c`) e roda
  `C:\msys64\ucrt64\bin\python.exe gui\tests\interop_test.py`, propagando o exit code.

Matriz total: **2 IDLs × 4 mensagens × (unit + 2 sentidos de interop)** = 24 casos, todos devem
passar (exit 0).

## Definition of Done
A entrega **só é considerada pronta** quando `run-tests.ps1` conclui com **`ALL PASS` e exit 0**
(todos os 24 casos sem falha). Os passos manuais abaixo são *smoke checks* visuais, não substituem a
suíte automatizada.

## Verification (end-to-end)
Primeiro **recompilar o FB C**: `make -C flatbuffers/c`; confirmar `main.exe` gerado sem erros.
Rodar a suíte: `powershell -File run-tests.ps1` → exigir `ALL PASS`.
Depois, smoke visual — abrir a GUI com `C:\msys64\ucrt64\bin\python.exe gui\app.py` (ou `run-gui.ps1`).
1. **server + protobuf + SensorReading:** alterar `label` e `value` → Serializar & Enviar →
   conferir hex + `len`; no painel "Saída do C" ver `[server] SensorReading ... value=... label='...'`
   refletindo a edição; echo **PASS**.
2. **server + flatbuffer + DeviceStatus:** editar `flags` (hex) → enviar → agora o C **re-encoda**;
   confirmar echo **PASS** (round-trip) e o dump do C refletindo os valores. Repetir com `Waveform`
   e `TelemetryPacket` canônicos para exercitar o re-encode dos vetores/aninhados no C.
3. **client + protobuf:** Escutar & Receber → `main client` sobe sozinho e envia as 4 → painel Python
   lista as 4 mensagens parseadas; "Saída do C" mostra `ALL PASS`.
4. **client + flatbuffer:** idem (4 parseadas + `ALL PASS`).
5. **Robustez:** entrada inválida (ex.: `id` fora de uint16) mostra erro de validação sem travar;
   porta em uso mostra mensagem clara; ao fechar a janela, o subprocesso C é finalizado.

## Notas / riscos
- Firewall: `bind/connect` em loopback normalmente não dispara prompt; se disparar, permitir.
- `main.exe` precisa de `C:\msys64\ucrt64\bin` no PATH (DLLs UCRT) — tratado pelo spawner.
- Sincronização de spawn no modo server: conectar com pequeno retry até o server C imprimir
  "listening" / aceitar a conexão.
- Escopo consciente (decisão 3): no modo client, o cliente C só envia os **4 canônicos** (não há
  edição do lado C sem alterar o C) — o objetivo ali é validar o **parse do Python** sobre bytes
  produzidos em C.
