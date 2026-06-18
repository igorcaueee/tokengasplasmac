# -*- coding: utf-8 -*-
"""
Pagamento_IA_SIM.py  —  Simulador ponta a ponta do orquestrador (Pagamento_IA.py)
SEM CLP físico.

Cópia simulável do Pagamento_IA.py: a LÓGICA da máquina de estados é mantida fiel
(mesmo corpo do while-loop, mesmo on_message, mesmo reset()). Só a INFRA é trocada:

  - CLP real (Snap7)   -> FakeCLP (DB2/DB4 em memória) + CLPBrain reativo
  - Broker MQTT (paho) -> FakeMQTT in-process (publish imprime; console vira on_message)

Câmera e IA continuam REAIS:
  - captura via cv2 nos device paths do legado (/dev/video2, /dev/video4, /dev/video0)
  - POST real para http://localhost:3000/image-analysis (index.js precisa estar no ar)

Linhas trocadas em relação à produção estão marcadas com  # === SIM ===

Uso (no Raspberry/Linux):
    python Pagamento_IA_SIM.py --cenario happy   --andar 1
    python Pagamento_IA_SIM.py --cenario ia_reject --andar 2
    python Pagamento_IA_SIM.py --cenario pay_reject --andar 1
    python Pagamento_IA_SIM.py --cenario timeout  --andar 1

Comandos no console (representam o front / cliente):
    INICIA, PIX, DEBITO, CREDITO, APPROVED, REJECTED, CANCELED, FORCAR_RESET
    inserir / retirar  -> adianta os eventos físicos simulados
    sair               -> encerra
"""

import time
import sys
import os
import threading        # === SIM === (threads do FakeCLP/FakeMQTT)
import argparse         # === SIM === (escolha de cenário/andar)
import types            # === SIM === (mensagem MQTT fake)
import requests
import cv2

# === SIM === Sentinelas de tipo no lugar de snap7.snap7types (sem dependência do Snap7)
S7WLBit = 'bit'
S7WLByte = 'byte'
S7WLWord = 'word'
S7WLDWord = 'dword'
S7WLReal = 'real'

URL = "http://localhost:3000/image-analysis"

# === SIM === paths das câmeras vindos do legado/webcam_foto_teste_cam{1,2,3}.py
CAMERA_PATHS = {
    1: "/dev/video2",
    2: "/dev/video4",
    3: "/dev/video0",
}

# === SIM === parâmetros de tempo do simulador.
# Dimensionados ACIMA do período de polling do orquestrador (~5s/iteração, por causa dos
# time.sleep mantidos fiéis à produção), para que cada Passo persista tempo suficiente e seja
# observado/gravado na sequência. Baixe estes valores (e os time.sleep do loop) se quiser um
# run mais rápido.
PHYS_DELAY = 6.0       # tempo simulado de cada evento físico (inserir/fechar/carregar/devolver)
RETRIEVE_DELAY = 6.0   # tempo simulado até o cliente retirar o botijão
GRACE = 12.0           # folga p/ o orquestrador publicar a msg antes do brain avançar (caminhos sem 'clear')

global webcam
global Passo
webcam = "/dev/video4"
processando_imagem = False


# =====================================================================================
# ===  SIM: INFRAESTRUTURA FALSA (CLP + MQTT)  ========================================
# =====================================================================================

class FakeCLP:
    """CLP falso em memória. Guarda DB2 e DB4 como bytearray e mantém 'latches'
    (memória de borda de subida) para o CLPBrain não perder bits que o orquestrador
    seta e limpa rápido demais."""

    def __init__(self):
        self.lock = threading.RLock()
        self.db = {2: bytearray(32), 4: bytearray(32)}
        self.latch = set()  # conjunto de (db, byte, bit) que já foram para 1

    def get_word(self, db, byte):
        with self.lock:
            return int.from_bytes(self.db[db][byte:byte + 2], 'big', signed=True)

    def set_word(self, db, byte, val):
        with self.lock:
            self.db[db][byte:byte + 2] = int(val).to_bytes(2, 'big', signed=True)

    def get_bit(self, db, byte, bit):
        with self.lock:
            return bool((self.db[db][byte] >> bit) & 1)

    def set_bit(self, db, byte, bit, val):
        with self.lock:
            if val:
                self.db[db][byte] |= (1 << bit)
                self.latch.add((db, byte, bit))
            else:
                self.db[db][byte] &= ~(1 << bit) & 0xFF

    def latched(self, db, byte, bit):
        return (db, byte, bit) in self.latch

    def clear_latch(self, db, byte, bit):
        self.latch.discard((db, byte, bit))

    def reset_cycle(self):
        """Volta o CLP ao começo de uma transação: zera DB4, bits de comando e latches.
        Mantém Passo/Analisar_Andar (DB2 byte0/byte2), que o brain controla."""
        with self.lock:
            self.db[4][:] = bytes(len(self.db[4]))
            # limpa bits de comando do DB2 byte4 (INICIA, etc.), preserva Passo/Andar
            self.db[2][4] = 0
            self.latch.clear()


class CLPBrain(threading.Thread):
    """Mini-máquina de estados que IMITA o CLP real: avança o Passo reagindo aos bits
    que o orquestrador grava (DB4/DB2) e simula os eventos físicos por timers."""

    def __init__(self, clp, andar):
        super().__init__(daemon=True)
        self.clp = clp
        self.andar = andar
        self.running = True
        self._t_state = time.time()
        self._last = None
        self._reject_t = None   # quando o brain viu pela 1a vez um bit de rejeição no Passo 9

    def _adv(self, novo_passo):
        self.clp.set_word(2, 0, novo_passo)

    def nudge(self):
        """Força o vencimento do timer físico do estado atual (comandos inserir/retirar)."""
        self._t_state = 0

    def run(self):
        self.clp.set_word(2, 2, self.andar)  # Analisar_Andar
        self._adv(1)                          # Passo inicial
        while self.running:
            p = self.clp.get_word(2, 0)
            if p != self._last:
                self._t_state = time.time()
                self._last = p
            el = time.time() - self._t_state
            self._step(p, el)
            time.sleep(0.1)

    def _step(self, p, el):
        c = self.clp
        if p == 1:
            # aguarda o orquestrador escrever INICIA (DB2 byte4 bit4)
            if c.latched(2, 4, 4):
                c.clear_latch(2, 4, 4)
                self._adv(3)
        elif p == 3:                      # cliente inserindo o botijão
            if el >= PHYS_DELAY:
                self._adv(4)
        elif p == 4:                      # fechando a porta
            if el >= PHYS_DELAY:
                self._adv(5)
        elif p == 5:                      # iniciando
            if el >= PHYS_DELAY:
                self._adv(7)
        elif p == 7:                      # carregando o botijão
            if el >= PHYS_DELAY:
                self._adv(8)
        elif p == 8:                      # análise da imagem (orquestrador escreve em DB4)
            if c.latched(4, 0, 0):        # botijão aceito
                self._adv(9)
            elif c.latched(4, 0, 1):      # botijão rejeitado
                self._adv(17)
        elif p == 9:                      # pagamento
            # --- pagamento autorizado: o orquestrador publica "Pagamento Aceito" e LIMPA o bit
            #     0.2; só avançamos depois da limpeza, garantindo que a msg saiu.
            if c.latched(4, 0, 2):
                if not c.get_bit(4, 0, 2):
                    self._reject_t = None
                    self._adv(11)
                return
            # --- rejeição/cancelamento/timeout -> devolver (Passo 17)
            if c.latched(4, 0, 3) or c.latched(4, 0, 1):
                if self._reject_t is None:
                    self._reject_t = time.time()
                # REJECTED: orquestrador publica "devolvendo o Botijão" e LIMPA o 0.3 -> avança ao limpar
                if c.latched(4, 0, 3) and not c.get_bit(4, 0, 3):
                    self._reject_t = None
                    self._adv(17)
                    return
                # Cancelamento (loopback "Cancelando cobrança" seta 0.1): msg já publicada -> avança
                if c.latched(4, 0, 1):
                    self._reject_t = None
                    self._adv(17)
                    return
                # Timeout sem método (0.3 fica setado, sem clear): espera GRACE p/ a msg sair
                if time.time() - self._reject_t >= GRACE:
                    self._reject_t = None
                    self._adv(17)
        elif p == 17:                     # devolvendo o botijão
            if el >= PHYS_DELAY:
                self._adv(18)
        elif p == 18:                     # destravar porta para devolver
            if el >= PHYS_DELAY:
                c.reset_cycle()
                self._adv(1)
        elif p == 11:                     # aguardando retirada
            if el >= RETRIEVE_DELAY:
                self._adv(13)
        elif p == 13:                     # botijão retirado
            if el >= PHYS_DELAY:
                c.reset_cycle()
                self._adv(1)


class FakeMQTT:
    """Cliente MQTT falso, in-process. publish() imprime as mensagens Python->Front e
    registra no log de sequência; o console (stdin) injeta eventos Front->Python via
    o MESMO on_message de produção."""

    def __init__(self):
        self.on_message = None
        self.on_connect = None
        self._reader_started = False

    # API mínima usada pelo orquestrador -------------------------------------------
    def connect(self, host, port, keepalive):
        if self.on_connect:
            self.on_connect(self, None, None, 0)

    def subscribe(self, topic):
        pass

    def loop_start(self):
        if not self._reader_started:
            self._reader_started = True
            threading.Thread(target=self._reader, daemon=True).start()

    def publish(self, topic, msg):
        print(f"[PY->FRONT] {msg}")
        record_msg(str(msg))
        # === SIM === loopback: na produção o cliente assina E publica em central/1, então
        # suas próprias mensagens (FORCAR_RESET, "Cancelando cobrança ....", "Erro...") voltam
        # para o on_message. Replicamos isso aqui. (on_message não publica -> sem recursão.)
        if self.on_message:
            self.inject(str(msg))

    # injeção de eventos do front via console --------------------------------------
    def inject(self, payload):
        msg = types.SimpleNamespace(topic="central/1", payload=payload.encode("utf-8"))
        if self.on_message:
            self.on_message(self, None, msg)

    def _reader(self):
        for line in sys.stdin:
            cmd = line.strip()
            if not cmd:
                continue
            low = cmd.lower()
            if low == "sair":
                print("Encerrando simulador...")
                os._exit(0)
            if low in ("inserir", "retirar"):
                if BRAIN is not None:
                    BRAIN.nudge()
                    print(f"[FRONT->SIM] evento físico '{low}' adiantado")
                continue
            print(f"[FRONT->PY] {cmd}")
            self.inject(cmd)


# =====================================================================================
# ===  ORQUESTRADOR (cópia fiel do Pagamento_IA.py, infra trocada)  ===================
# =====================================================================================

# Capturar a imagem da webcam
def capture_image(device_path):
    cap = cv2.VideoCapture(device_path)  # 0 para a primeira webcam USB
    if not cap.isOpened():
        client.publish(f"central/1", "Erro ao acessar a camera")
        print("Erro ao acessar a webcam")
        return None

    ret, frame = cap.read()
    client.publish(f"central/1", "Capturando imagem do Botijão.....")
    cap.release()  # Liberar a camera

    if not ret:
        client.publish(f"central/1", "Erro ao capturar a imagem")
        print("Erro ao capturar a imagem")
        return None

    return frame

# Enviar a imagem para o servidor e atualizar o status
def send_image(frame):
    global Botijao_Aceito
    global Botijao_Rejeitado

    Botijao_Aceito = False
    Botijao_Rejeitado = False

    _, img_encoded = cv2.imencode('.jpg', frame)  # Converter imagem para JPEG
    files = {'image': ('webcam.jpg', img_encoded.tobytes(), 'image/jpeg')}

    try:
        response = requests.post(URL, files=files)
        response_data = response.json()  # Converte a resposta JSON em um dicionario
        print("***************** API CAMERA RESPOSTA *****************")
        print(f"{response_data}")
        if "status" in response_data:
            if response_data["status"] == "True":  # Atualiza a variavel
                  Botijao_Aceito = True
                  WriteMemory(0, S7WLBit, 4, 0, 1)
                  time.sleep(1)
            else:
                  Botijao_Rejeitado = True
                  WriteMemory(0, S7WLBit, 4, 1, 1)
                  time.sleep(1)
        else:
            print(f"Erro na resposta da API")
            Botijao_Rejeitado = True
            WriteMemory(0, S7WLBit, 4, 1, 1)
            time.sleep(1)

        print("Resposta da API:", response_data)
        print("Botijão Aceito:", Botijao_Aceito)
        print("Botijão Rejeitado:", Botijao_Rejeitado)
    except requests.exceptions.RequestException as e:
        Botijao_Rejeitado = True
        WriteMemory(0, S7WLBit, 4, 1, 1)
        time.sleep(1)
        print("Erro ao enviar imagem:", e)


Central_Gas = None
Conexao_Estabelecida_CLP = False

# === SIM === conectar_clp vira no-op: o "CLP" é o FakeCLP/CLPBrain em memória
def conectar_clp():
    global Conexao_Estabelecida_CLP
    Conexao_Estabelecida_CLP = True
    print("Conexao estabelecida com sucesso! (FakeCLP em memória)")


topic = "central/1"
Iniciado = False
Wait = 0
Show = 0
Insert_Botijao = 0
Time_Botijao = 5
Time_Wait = 10
Intent = 0
Pagamento_Funcionando = True
Iniciar_Atendimento = False
Metodo_Pagamento = False
Pix = False

Pagamento_Autorizado = False
Pagamento_Rejeitado = False


# Funcao de callback chamada quando o cliente conecta ao broker
def on_connect(client, userdata, flags, rc):
    print(f"Conectado ao broker com codigo {rc}")

# Funcao de callback chamada quando uma mensagem é recebida
def on_message(client, userdata, msg):

    # Pagamento -> Central
    global Pagamento_Funcionando
    global Iniciar_Atendimento
    global Iniciado
    global Pagamento_Autorizado
    global Pagamento_Rejeitado
    global Metodo_Pagamento
    global Pix
    global Central_Gas
    global Tipo
    global Passo

    print(f"Mensagem recebida: {msg.payload.decode()}")

    if msg.payload.decode() == "Cancelando cobrança ....":
        Pagamento_Rejeitado = True
        WriteMemory(0, S7WLBit, 4, 1, 1)  # Botijao rejeitado
        time.sleep(1)
        print("XXXXXXXXXXX CANCELANDO COBRANCA -------------")

    if "Erro" in msg.payload.decode():
        time.sleep(4)
        reset()

    if msg.payload.decode() == "INICIA":
        Iniciado = True
        Iniciar_Atendimento = True
        WriteMemory(4, S7WLBit, 2, 4, 1)
        time.sleep(1)

    if msg.payload.decode() == "CANCELED":
        WriteMemory(0, S7WLBit, 4, 1, 1)
        print("CANCELADO !!!!!!!!!!!!!!!!!!!!!!!")

    if msg.payload.decode() == "PIX" or msg.payload.decode() == "DEBITO" or msg.payload.decode() == "CREDITO":
        Metodo_Pagamento = True
        if msg.payload.decode() == "PIX":
            Pix = True
        else:
            Tipo = msg.payload.decode()

    if msg.payload.decode() == "FORCAR_RESET":
        Pagamento_Autorizado = False
        Pagamento_Rejeitado = False
        Botijao_Aceito = False
        Botijao_Rejeitado = False
        WriteMemory(0, S7WLBit, 4, 0, 0)
        time.sleep(0.1)
        WriteMemory(0, S7WLBit, 4, 1, 0)
        time.sleep(0.1)
        WriteMemory(0, S7WLBit, 4, 3, 0)
        time.sleep(0.1)
        WriteMemory(0, S7WLBit, 4, 2, 0)
        time.sleep(1)
        print("Forcando Reset dos estados!")

    if Passo == 9:
        print(f"ENTROU NA ANLISE DE PAGAEMNTO $$$$$$$$$$$$$$$$$$$$")
        if msg.payload.decode() == "APPROVED":
            print("DENTRO DE APROVADO  ======+==++++++++++++++++++++++++++")
            Pagamento_Autorizado = True
            Pagamento_Rejeitado = False
            WriteMemory(0, S7WLBit, 4, 2, 1)
            time.sleep(1)

        elif msg.payload.decode() == "REJECTED":
            Pagamento_Autorizado = False
            Pagamento_Rejeitado = True
            WriteMemory(0, S7WLBit, 4, 3, 1)
            time.sleep(1)


# Central -> Pagamento

Analise_Disponivel = False
Porta_Aberta_Andar1 = False
Porta_Aberta_Andar2 = False
Porta_Aberta_Andar3 = False
Andar1_Destravado_InserirBotijao = False
Andar2_Destravado_InserirBotijao = False
Andar3_Destravado_InserirBotijao = False
Alerta_Tempo_Inatividade = False
Analisando_Botijao = False
Botijao_Aceito = False
Botijao_Rejeitado = False
Andar1_Destravado_RetirarBotijao = False
Andar2_Destravado_RetirarBotijao = False
Andar3_Destravado_RetirarBotijao = False
Manutencao_Andamento = False
Central_Em_Alarme = False

def reset():
    global Pagamento_Autorizado, Pix, Metodo_Pagamento, Pagamento_Rejeitado, Iniciar_Atendimento, Iniciado, Intent
    global Porta_Aberta_Andar1, Porta_Aberta_Andar2, Porta_Aberta_Andar3
    global Andar1_Destravado_InserirBotijao, Andar2_Destravado_InserirBotijao, Andar3_Destravado_InserirBotijao
    global Alerta_Tempo_Inatividade, Analisando_Botijao, Botijao_Aceito, Botijao_Rejeitado
    global Insert_Botijao, Wait, Andar1_Destravado_RetirarBotijao, Andar2_Destravado_RetirarBotijao, Andar3_Destravado_RetirarBotijao
    global Show, Manutencao_Andamento, Central_Em_Alarme
    Pagamento_Autorizado = False
    Metodo_Pagamento = False
    Pix = False
    Pagamento_Rejeitado = False
    Iniciar_Atendimento = False
    Iniciado = False
    Insert_Botijao = 0
    Wait = 0
    Show = 0
    Intent = 0
    Porta_Aberta_Andar1 = False
    Porta_Aberta_Andar2 = False
    Porta_Aberta_Andar3 = False
    Andar1_Destravado_InserirBotijao = False
    Andar2_Destravado_InserirBotijao = False
    Andar3_Destravado_InserirBotijao = False
    Alerta_Tempo_Inatividade = False
    Analisando_Botijao = False
    Botijao_Aceito = False
    Botijao_Rejeitado = False
    Andar1_Destravado_RetirarBotijao = False
    Andar2_Destravado_RetirarBotijao = False
    Andar3_Destravado_RetirarBotijao = False
    Manutencao_Andamento = False
    Central_Em_Alarme = False


# === SIM === ReadMemory/WriteMemory operam no FakeCLP (mesma assinatura da produção)
def ReadMemory(byte, datatype, db, bit=0, tam_st=0):
    if not Conexao_Estabelecida_CLP or CLP is None:
        print("Erro: CLP nao conectado!")
        return None
    try:
        if datatype == S7WLBit:
            return CLP.get_bit(db, byte, bit)
        elif datatype in (S7WLByte, S7WLWord):
            return CLP.get_word(db, byte)
        elif datatype == S7WLDWord:
            return CLP.get_word(db, byte)
        else:
            return None
    except Exception as e:
        print(f"Erro ao ler memoria do CLP: {e}")
        return None

def WriteMemory(byte, datatype, db, bit, valor):
    if not Conexao_Estabelecida_CLP or CLP is None:
        print("Erro: CLP nao conectado!")
        return
    try:
        if datatype == S7WLBit:
            CLP.set_bit(db, byte, bit, 1 if valor else 0)
        elif datatype in (S7WLByte, S7WLWord):
            CLP.set_word(db, byte, int(valor))
        elif datatype == S7WLDWord:
            CLP.set_word(db, byte, int(valor))
    except Exception as e:
        print(f"Erro ao escrever na memoria do CLP: {e}")


# =====================================================================================
# ===  SIM: GRAVAÇÃO DE SEQUÊNCIA + VEREDITO  ========================================
# =====================================================================================

OBSERVED_PASSOS = []
OBSERVED_MSGS = []
_cycle_started = False

# Subsequência esperada de Passos + mensagem-chave que diferencia o cenário
EXPECTED = {
    "happy":     dict(passos=[1, 3, 8, 9, 11, 13, 1], key="Pagamento Aceito"),
    "ia_reject": dict(passos=[1, 3, 8, 17, 18, 1],    key="Botijão Rejeitado"),
    "pay_reject": dict(passos=[1, 3, 8, 9, 17, 18, 1], key="devolvendo o Botijão"),
    "timeout":   dict(passos=[1, 3, 8, 9, 17, 18, 1], key="Cancelando cobrança"),
}

def record_passo(p):
    if p is None:
        return
    if not OBSERVED_PASSOS or OBSERVED_PASSOS[-1] != p:
        OBSERVED_PASSOS.append(p)

def record_msg(m):
    OBSERVED_MSGS.append(m)

def _is_subsequence(sub, full):
    it = iter(full)
    return all(any(x == y for y in it) for x in sub)

def evaluate(cenario):
    exp = EXPECTED.get(cenario)
    if not exp:
        print(f"[VEREDITO] cenário '{cenario}' sem expectativa definida — só log.")
        return
    seq_ok = _is_subsequence(exp["passos"], OBSERVED_PASSOS)
    key_ok = any(exp["key"] in m for m in OBSERVED_MSGS)
    print("\n================= VEREDITO =================")
    print(f"Cenário        : {cenario}")
    print(f"Passos esperados: {exp['passos']}")
    print(f"Passos observados: {OBSERVED_PASSOS}")
    print(f"Subsequência de Passos .... {'OK' if seq_ok else 'FALHOU'}")
    print(f"Mensagem-chave '{exp['key']}' .... {'OK' if key_ok else 'FALHOU'}")
    print("RESULTADO: " + ("PASSOU ✅" if (seq_ok and key_ok) else "FALHOU ❌"))
    print("===========================================\n")


# =====================================================================================
# ===  LOOP PRINCIPAL DO ORQUESTRADOR  ===============================================
# =====================================================================================

def orchestrator_loop(cenario):
    global Passo, Analisar_Andar, Wait, Show, Insert_Botijao, webcam
    global Alerta_Tempo_Inatividade, Manutencao_Andamento, Central_Em_Alarme
    global Pagamento_Autorizado, Pagamento_Rejeitado, Metodo_Pagamento
    global _cycle_started
    camera = 1  # === SIM === valor padrão (no original é definido nos ramos de Passo)

    while True:
        time.sleep(2)
        print(f"entrou no while")
        # dados para enviar
        WriteMemory(4, S7WLBit, 2, 7, Pagamento_Funcionando)

        # ----------------- INICIO ---------------------------------------
        Analisar_Andar = ReadMemory(2, S7WLWord, 2, 0)
        time.sleep(1)
        Passo = ReadMemory(0, S7WLWord, 2, 0)
        time.sleep(1)

        record_passo(Passo)                                   # === SIM ===
        # === SIM === detecta fim de uma transação (voltou ao Passo 1 após ter avançado)
        if Passo == 1 and _cycle_started:
            evaluate(cenario)
            OBSERVED_PASSOS.clear()
            OBSERVED_MSGS.clear()
            _cycle_started = False
            record_passo(1)
        if Passo is not None and Passo >= 3:
            _cycle_started = True

        print(f"MEMORIA **************")
        print(f"{Analisar_Andar}")
        print(f"{Passo}")

        if Passo == 1:
            client.publish(f"central/1", "INICIAR")
            print("INICIAR")
            continue

        if Passo == 3:
            if Analisar_Andar == 1:
                camera = 1
                print(f"Insira o Botijão na Porta 1")
                client.publish(f"central/1", f"Insira o Botijão na Porta 1")
                continue
            if Analisar_Andar == 2:
                camera = 2
                print(f"Insira o Botijão na Porta 2")
                client.publish(f"central/1", f"Insira o Botijão na Porta 2")
                continue
            if Analisar_Andar == 3:
                camera = 3
                print(f"Insira o Botijão na Porta 3")
                client.publish(f"central/1", f"Insira o Botijão na Porta 3")
                continue

        if Passo == 4:
            if Analisar_Andar == 1:
                camera = 1
                print(f"Fechar Porta 1")
                client.publish(f"central/1", f"Fechar porta 1")
                continue
            if Analisar_Andar == 2:
                camera = 2
                print(f"Fechar Porta 2")
                client.publish(f"central/1", f"Fechar porta 2")
                continue
            if Analisar_Andar == 3:
                camera = 3
                print(f"Fechar Porta 3")
                client.publish(f"central/1", f"Fechar porta 3")
                continue

        # ------- ALERTA INATIVIDADE -------------------------------------
        Alerta_Tempo_Inatividade = ReadMemory(4, S7WLBit, 2, 6)

        if Passo == 5:
            print(f"Iniciando Processo...")
            client.publish(f"central/1", f"Iniciando Processo...")
            continue

        if Passo == 7:
            print(f"Carregando o Botijão. Por favor, aguarde...")
            client.publish(f"central/1", f"Carregando o Botijão. Por favor, aguarde...")
            continue

        if Alerta_Tempo_Inatividade == True:
            client.publish(f"central/1", "Cliente Insira o Botijão.....")
            print(f"Cliente Insira o Botijão.....")
            time.sleep(5)
            continue

        print(f"ANALISE PROXIMO DO 8 ->>>>>>>")
        print(f"{Passo}")

        if Passo == 8:
            print("ENTROU NA ANLISE  **********")

            # === SIM === paths das câmeras do legado em vez de /dev/v4l/by-path/...
            resultado = CAMERA_PATHS.get(camera, CAMERA_PATHS[1])

            print(f"ID CAMERA -> {camera}")
            print(f"PATH CAM -> {resultado}")
            if not os.path.exists(resultado):
                print(f"ERRO CRITICO: O caminho {resultado} nao foi encontrado no sistema!")
            Insert_Botijao += 1

            webcam = resultado
            print(f"WEBCAM {webcam}")

            client.publish(f"central/1", f"Analisando o Botijão, Por favor, Aguarde........")
            print(f"Analisando o Botijão, Por favor, Aguarde........")
            print("Botijao ACEITO VARIAVEL - ANTES ", Botijao_Rejeitado)
            print("Botijao REJEITADO VARIAVEL - ANTES", Botijao_Rejeitado)
            print(f"WEBCAM? {webcam}")

            if not processando_imagem:
                frame = capture_image(webcam)
                if frame is not None:
                    print("Enviando para API...")
                    send_image(frame)
            else:
                print("Já existe uma análise em curso, aguardando resposta da API...")

        Analisar_Andar = ReadMemory(2, S7WLWord, 2, 0)
        time.sleep(1)
        Passo = ReadMemory(0, S7WLWord, 2, 0)
        time.sleep(1)
        record_passo(Passo)                                   # === SIM ===

        if Passo == 11 or Passo == 12 or Passo == 19:
            if Analisar_Andar == 1:
                camera = 1
                print(f"Aguardando Retirada do Botijão na porta 1")
                client.publish(f"central/1", f"Aguardando Retirada do Botijão na porta 1")
                client.publish(f"central/1", f"FORCAR_RESET")
                reset()
                continue
            if Analisar_Andar == 2:
                camera = 2
                print(f"Aguardando Retirada do Botijão na porta 2")
                client.publish(f"central/1", f"Aguardando Retirada do Botijão na porta 2")
                client.publish(f"central/1", f"FORCAR_RESET")
                reset()
                continue
            if Analisar_Andar == 3:
                camera = 3
                print(f"Aguardando Retirada do Botijão na porta 3")
                client.publish(f"central/1", f"Aguardando Retirada do Botijão na porta 3")
                client.publish(f"central/1", f"FORCAR_RESET")
                reset()
                continue

        if Passo == 13 or Passo == 15 or Passo == 20:
            client.publish(f"central/1", f"Botijão Retirado")
            client.publish(f"central/1", f"FORCAR_RESET")
            reset()
            continue

        if Botijao_Aceito == True and Show == 0:
            Show = 1
            Metodo_Pagamento = False
            Pagamento_AUtorizado = False
            Pagamento_Rejeitado = False
            client.publish(f"central/1", "Botijão Aceito!")
            print(f"Botijão Aceito!")
            time.sleep(3)

        if Botijao_Rejeitado == True and Show == 0:
            Show = 1
            client.publish(f"central/1", "Botijão Rejeitado")
            print(f"Botijão Rejeitado")
            time.sleep(5)

        if Passo == 9 and Metodo_Pagamento == False:
            Pagamento_AUtorizado = False
            Pagamento_Rejeitado = False
            client.publish(f"central/1", f"Escolha uma forma de pagamento ({Time_Wait - Wait})")
            print(f"Escolha uma forma de pagamento ({Time_Wait - Wait})")
            Wait += 1

            if Wait >= Time_Wait:
                client.publish(f"central/1", f"Tempo Expirado!")
                print(f"Tempo Expirado!")
                WriteMemory(0, S7WLBit, 4, 3, 1)  # PAGAMENTO REJEITADO
                time.sleep(0.1)
                Wait = 0
                time.sleep(2)
            continue

        if Passo == 9 and Pagamento_Autorizado == False and Pagamento_Rejeitado == False:
            Wait += 1
            if Pix == True:
                client.publish(f"central/1", f"Aguardando Pagamento {Time_Wait - Wait}\nEscaneie o QRCode para concluir o pagamento")
                print(f"Aguardando Pagamento {Time_Wait - Wait}")
            else:
                client.publish(f"central/1", f"Aguardando Pagamento com Cartao de {Tipo} {Time_Wait - Wait}\nSe necessario, clique em\n \"Cobrar\" e/ou \"Ir ao Ini­cio\" \nna Maquineta")
                print(f"Aguardando Pagamento {Time_Wait - Wait}")

            if Wait >= Time_Wait:
                client.publish(f"central/1", f"Cancelando cobrança ....")
                print(f"Cancelando cobrança ....")
                WriteMemory(4, S7WLBit, 2, 1, 1)
                time.sleep(2)
                reset()

        # ------------ LOGICA BASE PAGAMENTO ACEITO --------------

        if Passo == 9 and Pagamento_Autorizado == True:
            client.publish(f"central/1", "Pagamento Aceito")
            print(f"Pagamento Aceito")
            WriteMemory(0, S7WLBit, 4, 2, 0)
            time.sleep(0.1)
            Pagamento_Rejeitado = False
            Pagamento_Autorizado = False
            time.sleep(2)
            continue

        if Passo == 9 and Pagamento_Rejeitado == True:
            client.publish(f"central/1", "Pagamento Rejeitado, devolvendo o Botijão")
            Pagamento_Autorizado = False
            Pagamento_Rejeitado = False
            WriteMemory(0, S7WLBit, 4, 3, 0)
            time.sleep(3)
            print(f"Pagamento Rejeitado, devolvendo o Botijão")

            # ----------- RESET ---------------------------------------
            client.publish(f"central/1", f"FORCAR_RESET")
            reset()
            continue

        if Passo == 17:
            client.publish(f"central/1", f"Devolvendo Botijão, Por favor Aguarde.....")
            continue

        if Passo == 18:
            if Analisar_Andar == 1:
                camera = 1
                print(f"Destravar porta 1")
                client.publish(f"central/1", f"Destravar porta 1")
                continue
            if Analisar_Andar == 2:
                camera = 2
                print(f"Destravar porta 2")
                client.publish(f"central/1", f"Destravar porta 2")
                continue
            if Analisar_Andar == 3:
                camera = 3
                print(f"Destravar Porta 3")
                client.publish(f"central/1", f"Destravar Porta 3")
                continue

        # ----------- OUTROS ------------------------------------
        Manutencao_Andamento = ReadMemory(4, S7WLBit, 2, 5)
        time.sleep(1)
        if Manutencao_Andamento == True:
            client.publish(f"central/1", "Central em Manutencao")
            print(f"Central em Manutencao")

        Central_Em_Alarme = ReadMemory(4, S7WLBit, 2, 6)
        time.sleep(1)
        if Central_Em_Alarme == True:
            client.publish(f"central/1", "Central em Alarme")
            print(f"Central em Alarme")


# =====================================================================================
# ===  SIM: BOOTSTRAP  ===============================================================
# =====================================================================================

CLP = None      # instância global do FakeCLP (usada por Read/WriteMemory)
BRAIN = None    # instância global do CLPBrain (usada pelo reader para 'nudge')
client = None   # instância global do FakeMQTT (mantém o nome 'client' da produção)

def _banner(cenario, andar):
    roteiro = {
        "happy": "INICIA  ->  (aguarde análise)  ->  PIX  ->  APPROVED  ->  (aguarde retirada)",
        "ia_reject": "INICIA  ->  (aponte a câmera p/ algo inválido; IA deve rejeitar)",
        "pay_reject": "INICIA  ->  (aguarde análise)  ->  PIX  ->  REJECTED  (selecione PIX ANTES)",
        "timeout": "INICIA  ->  (aguarde análise)  ->  PIX  ->  NÃO pague; espere 'Cancelando cobrança'",
    }
    print("=" * 70)
    print(f"  SIMULADOR Pagamento_IA  |  cenário={cenario}  andar={andar}")
    print("=" * 70)
    print("  Pré-requisito: index.js no ar em http://localhost:3000 (rota /image-analysis)")
    print("  Comandos do front (digite e ENTER):")
    print("    INICIA  PIX  DEBITO  CREDITO  APPROVED  REJECTED  CANCELED  FORCAR_RESET")
    print("    inserir / retirar  (adianta evento físico)   |   sair")
    print(f"  Roteiro sugerido: {roteiro.get(cenario, '')}")
    print("=" * 70)


def main():
    global CLP, BRAIN, client

    parser = argparse.ArgumentParser(description="Simulador do orquestrador Pagamento_IA.py sem CLP")
    parser.add_argument("--cenario", default="happy",
                        choices=["happy", "ia_reject", "pay_reject", "timeout"])
    parser.add_argument("--andar", type=int, default=1, choices=[1, 2, 3])
    args = parser.parse_args()

    CLP = FakeCLP()
    client = FakeMQTT()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect("localhost", 1883, 60)
    client.subscribe("central/1")
    client.loop_start()

    conectar_clp()

    BRAIN = CLPBrain(CLP, args.andar)
    BRAIN.start()

    _banner(args.cenario, args.andar)
    orchestrator_loop(args.cenario)


if __name__ == "__main__":
    main()
