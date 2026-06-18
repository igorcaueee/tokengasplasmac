---
name: totem-gaspuro
description: Contexto do projeto Totem GásPuro — automação de máquina de autoatendimento de gás (CLP Siemens via Snap7 + Electron/MQTT + validação por IA Gemini + pagamento Mercado Pago). Use ao trabalhar neste repositório (tokengasplasmac).
---

# Totem GásPuro

Automação de uma **máquina de autoatendimento de venda de gás (botijões)**. O cliente insere
um botijão em uma de **3 portas/andares**, uma IA valida se é um botijão P13/P45 válido, o cliente
paga (PIX / Débito / Crédito) e a máquina libera o botijão. A interação física Humano→Máquina
(sensores, travas, motores das portas) é feita por um **CLP Siemens**; o Python conversa com ele
via **Snap7** e coordena IA, MQTT e pagamento.

**Ambiente de produção:** Raspberry Pi rodando Linux, 3 câmeras USB (uma por andar), CLP na rede
`192.168.0.x`. O boot é feito por `start.sh`.

## Ciclo de uma transação (visão alta)

```
Cliente toca INICIAR → CLP destrava a porta do andar → cliente insere botijão →
câmera do andar captura imagem → Gemini valida (P13/P45?) → resultado escrito no CLP →
cliente escolhe pagamento → Mercado Pago → webhook APPROVED/REJECTED →
CLP libera/devolve o botijão → reset
```

## Arquivos canônicos (produção) vs legado

| Arquivo | Papel |
|---------|-------|
| `Pagamento_IA.py` | **Orquestrador principal.** Loop de polling do CLP (Snap7), captura de imagem (OpenCV), pub/sub MQTT. É o que `start.sh` executa. |
| `index.js` | App **Electron** + servidor **Express:3000**. Rota `/image-analysis` (chama Gemini) e `/webhook` (recebe Mercado Pago). Ponte MQTT ↔ front via IPC. |
| `index.html` | UI do totem (INICIAR / PIX / Débito / Crédito / QR Code). Faz as chamadas ao Mercado Pago. Preço em `value = 12500` (R$ 125,00). |
| `start.sh` | Boot no Raspberry: ativa venv `myenv`, sobe `Pagamento_IA.py`, depois `electron . --no-sandbox`, depois `ngrok.sh`. |
| `ngrok.sh` | Expõe o webhook do Mercado Pago via ngrok. |
| `package.json` | Deps Node (electron, express, mqtt, axios, multer, uuid…). |
| `snap7/` + `libsnap7.so` | Biblioteca de comunicação com o CLP. |

**Legado / NÃO mexer como se fosse produção** (são backups/experimentos): `Pagamento.py`,
`Pagamento copy.py`, `pagamento_original.py`, `Pagamento_MQTT.py`, `Pagamento_MQTT_COMENTADO.py`,
`Pagamento_IA.py.BKP`/`.save`, `PIA.py`, `teste_clp.py`, `teste.py`.
**YOLO legado** (substituído pelo Gemini): `Programa_AI_Detectar_Botijao.py`, `best.pt`,
`Detectar_Camera.py`, `webcam_*teste*.py`.
**Lixo versionado indevidamente** (ver "Limpeza pendente"): `yolo-env/`, `cv2/`, `np`, `sudo`,
`download*`, `wget-log*`, `gemini_payload.json`, `foto_capturada_*.jpg`, `Simulacao_Andar*.jpg`,
`totem_boot_log.txt`, `index.html.save`.

> ⚠️ Variantes antigas (`PIA.py`, `teste_clp.py`) usam um mapeamento de `Passo` e de DBs
> **diferente** do de produção. Sempre confie em `Pagamento_IA.py` como fonte da verdade.

## Arquitetura

```
┌──────────────┐  IPC   ┌──────────────────────┐
│ index.html   │◄──────►│ index.js (Electron)  │
│ (UI do totem)│        │ Express :3000        │
└──────────────┘        │  /image-analysis     │──► Google Gemini (valida botijão)
                        │  /webhook            │◄── Mercado Pago (status pgto, via ngrok)
                        └──────────┬───────────┘
                                   │ MQTT (tópico central/1, broker localhost:1883)
                                   ▼
                        ┌──────────────────────┐
                        │ Pagamento_IA.py       │
                        │ (orquestrador)        │
                        │  - Snap7 ◄──► CLP     │──► CLP Siemens 192.168.0.1 (DB2/DB4)
                        │  - OpenCV ◄── câmeras │──► 3 câmeras USB (1 por andar)
                        └──────────────────────┘
```

Tudo se comunica por **MQTT** no tópico `central/1`. O `index.js` é o único que fala com
serviços externos (Gemini, Mercado Pago); o `Pagamento_IA.py` é o único que fala com o CLP.

## Máquina de estados — `Passo` (lido do CLP)

O `Pagamento_IA.py` faz polling a cada ~2s, lê a WORD `Passo` (`DB2.byte0`) e `Analisar_Andar`
(`DB2.byte2`, vale 1/2/3 = andar) e reage:

| Passo | Significado | Ação do Python |
|-------|-------------|----------------|
| 1 | Tela inicial | publica `INICIAR` |
| 3 | Inserir botijão | "Insira o Botijão na Porta {andar}" |
| 4 | Fechar porta | "Fechar porta {andar}" |
| 5 / 7 | Iniciando / carregando | mensagens de espera |
| 8 | **Análise da imagem** | captura imagem da câmera do andar → `POST /image-analysis` → Gemini → escreve resultado no CLP |
| 9 | **Pagamento** | escolha de forma, aguarda webhook `APPROVED`/`REJECTED`; timeout `Time_Wait = 10` ciclos |
| 11 / 12 / 19 | Aguardar retirada | "Aguardando Retirada…" + publica `FORCAR_RESET` |
| 13 / 15 / 20 | Botijão retirado | "Botijão Retirado" + reset() |
| 17 | Devolvendo botijão | mensagem de espera |
| 18 | Destravar porta | "Destravar porta {andar}" |

## Mapa de memória do CLP (Snap7)

Conexão: `Central_Gas.connect("192.168.0.1", 0, 1)` → **rack 0, slot 1**, porta TCP 102.

Helpers em `Pagamento_IA.py`: `ReadMemory(byte, datatype, db, bit=0)` e
`WriteMemory(byte, datatype, db, bit, valor)`. Tipos: `S7WLBit`, `S7WLByte`, `S7WLWord`,
`S7WLDWord`, `S7WLReal`.

**Leitura (CLP → Python), em DB2:**

| Sinal | Endereço | Tipo |
|-------|----------|------|
| `Passo` | `DB2` byte 0 | WORD |
| `Analisar_Andar` (1/2/3) | `DB2` byte 2 | WORD |
| `Manutencao_Andamento` | `DB2` byte 4, bit 5 | BIT |
| `Central_Em_Alarme` / `Alerta_Tempo_Inatividade` | `DB2` byte 4, bit 6 | BIT |

**Escrita (Python → CLP):**

| Sinal | Endereço | Quando |
|-------|----------|--------|
| `Pagamento_Funcionando` | `DB2` byte 4, bit 7 | a cada ciclo (heartbeat) |
| `INICIA` (iniciar atendimento) | `DB2` byte 4, bit 4 | ao receber `INICIA` do front |
| Botijão **aceito** | `DB4` byte 0, bit 0 | Gemini retornou `True` |
| Botijão **rejeitado** | `DB4` byte 0, bit 1 | Gemini retornou `False`/erro |
| Pagamento **autorizado** | `DB4` byte 0, bit 2 | webhook `APPROVED` |
| Pagamento **rejeitado** | `DB4` byte 0, bit 3 | webhook `REJECTED`/timeout |

> Histórico: o código tem muitas linhas comentadas com `WriteMemory(4,S7WLBit,2,...) #ANTIGO`.
> Esse era o mapeamento antigo (resultado em DB2). **Produção escreve resultado em DB4.**

## MQTT — tópico único `central/1` (broker `localhost:1883`)

**Front → Python:** `INICIA`, `PIX`, `DEBITO`, `CREDITO`, `CANCELED`,
`Cancelando cobrança ....`, `FORCAR_RESET`.

**Python → Front (status, exibidos no totem):** `INICIAR`, `Insira o Botijão na Porta X`,
`Fechar porta X`, `Analisando o Botijão...`, `Botijão Aceito!`, `Botijão Rejeitado`,
`Escolha uma forma de pagamento (N)`, `Aguardando Pagamento...`, `Pagamento Aceito`,
`Pagamento Rejeitado, devolvendo o Botijão`, `Aguardando Retirada do Botijão na porta X`,
`Botijão Retirado`, `Destravar porta X`, `Central em Manutencao`, `Central em Alarme`.

**Webhook Mercado Pago** (`index.js` `/webhook`) traduz o callback em `APPROVED` / `REJECTED` /
`CANCELED` e publica no `central/1`.

## Validação por IA (Gemini)

- Feita **inteiramente no `index.js`**, rota `POST /image-analysis` → chama
  `https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent`
  (chave via `process.env.KEY`).
- Prompt valida **botijões P13 (13kg) / P45 (45kg)** dentro de um cesto metálico; **rejeita**
  Liquinho (P2/P5), acessórios de camping, brinquedos/fotos (sabotagem) e obstrução total.
- Resposta esperada: `{"status": "True"}` (aceita) ou `{"status": "False"}` (rejeita).
- O `Pagamento_IA.py` recebe esse status e escreve em `DB4` (aceito/rejeitado); o CLP decide
  travar/destravar.
- **YOLO (`best.pt`) é legado** — não participa do fluxo de produção atual.

## Pagamento (Mercado Pago)

Disparado pelo `index.html` ao receber a forma de pagamento via MQTT (token/POS em `.env`):
- **PIX** → `POST https://api.mercadopago.com/v1/payments` → renderiza `qr_code_base64` na tela.
- **Débito/Crédito** → `POST .../point/integration-api/devices/{POS}/payment-intents` (maquineta física).
- `payment_id` é salvo em `localStorage` (usado para cancelamento via `DELETE`).
- Confirmação chega assíncrona no `/webhook` do `index.js`, que publica `APPROVED`/`REJECTED`.

## Como rodar / deploy

1. Pré-requisitos no Raspberry: broker MQTT (Mosquitto) em `localhost:1883`, venv Python `myenv`
   (com `snap7`, `paho-mqtt`, `opencv-python`, `requests`), `node_modules` instalados, ngrok configurado.
2. Variáveis em `.env` (NÃO versionado): `TOKEN` (Mercado Pago), `POS` (device da maquineta),
   `KEY` (Google Gemini).
3. `./start.sh` sobe, na ordem: `Pagamento_IA.py` → `electron . --no-sandbox` → `ngrok.sh`.
4. Câmeras são endereçadas por caminho USB fixo (`/dev/v4l/by-path/...-usb-0:1.2/1.4/1.1...`),
   uma por andar (ver `cameras` em `Pagamento_IA.py`).

## Pontos de atenção / segurança

- Validação de IP do webhook do Mercado Pago está **comentada** em `index.js` (qualquer origem aceita).
- Electron com `nodeIntegration: true` e `contextIsolation: false` (sem isolamento).
- E-mail do pagador PIX fixo: `totem@totem.purogas.br` (`index.html`).
- IP do CLP fixo (`192.168.0.1`) e endereços de câmera fixos — quebram se o hardware/rede mudar.
- Segredos só existem no `.env` da máquina; nunca commitar.

## Limpeza pendente (proposta — confirmar antes de executar)

O `.gitignore` já cobre `venv/`, `myenv/`, `.env`, `node_modules/`, `*.log`. Ainda estão
versionados indevidamente: `yolo-env/` (venv inteira), `cv2/`, `best.pt` (~6 MB), `np`, `sudo`,
`download*`, `wget-log*`, `gemini_payload.json`, `foto_capturada_*.jpg`, `*.swp`, `totem_boot_log.txt`.
Plano: adicionar esses ao `.gitignore`, `git rm --cached` neles, e mover variantes/YOLO legados
para uma pasta `legado/`. (Não executar sem o Gabriel pedir.)
