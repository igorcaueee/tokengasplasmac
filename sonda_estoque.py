#!/usr/bin/env python3
# sonda_estoque.py -- SOMENTE LEITURA. Nunca escreve no CLP.
#
# Objetivo: descobrir se o estado dos slots (V = vazio / S = sem botijao / C = cheio)
# esta exposto em algum DB legivel via Snap7 e em qual endereco, para depois o
# Pagamento_IA.py conseguir detectar "estoque zerado" (nenhum C) e bloquear/avisar.
#
# NOTA: este CLP NAO suporta list_blocks / get_block_info ("CPU : Function not
# available"), mas leitura direta por endereco (read_area) FUNCIONA. Por isso a
# sonda descobre os DBs por FORCA-BRUTA: tenta ler cada numero de DB; se a leitura
# der certo, o DB existe.
#
# Uso (na Raspberry, com a maquina ligada e o venv ativo):
#   source myenv/bin/activate
#   python sonda_estoque.py dump    -> descobre os DBs e despeja os bytes em hex
#   python sonda_estoque.py watch   -> mostra quais bytes MUDAM quando voce mexe num slot
#
# No modo "watch", deixe rodando e ENTAO tire/coloque um botijao num slot (ou mude
# pela HMI Auten). Os bytes que mudarem apontam o DB/byte do estoque. Anote qual
# valor corresponde a V, S e C.

import sys
import time
import datetime

import snap7
from snap7.snap7types import S7AreaDB

IP, RACK, SLOT = "192.168.0.1", 0, 1

# Faixa de numeros de DB a investigar e tamanhos testados (do maior pro menor).
DB_RANGE = range(0, 61)
SIZES = [2048, 1024, 512, 256, 128, 64, 32, 16, 8, 4, 2, 1]


def conectar():
    cli = snap7.client.Client()
    cli.connect(IP, RACK, SLOT)
    print("Conectado a", IP)
    return cli


def descobrir_dbs(cli):
    """Retorna {db_number: tamanho_legivel} testando leitura direta (force-brute)."""
    dbs = {}
    for db in DB_RANGE:
        for s in SIZES:
            try:
                cli.read_area(S7AreaDB, db, 0, s)
                dbs[db] = s
                break
            except Exception:
                continue
    print("DBs legiveis (numero: ~bytes):", dbs)
    return dbs


def snapshot(cli, dbs):
    snap = {}
    for db, size in dbs.items():
        try:
            snap[db] = (size, bytes(cli.read_area(S7AreaDB, db, 0, size)))
        except Exception as e:
            print(f"  DB{db}: erro ao ler ({e})")
    return snap


def modo_dump(cli, dbs):
    for db, (size, data) in snapshot(cli, dbs).items():
        print(f"\n=== DB{db} (~{size} bytes) ===")
        print(data.hex(" "))


def modo_watch(cli, dbs):
    prev = snapshot(cli, dbs)
    print("Observando... ENQUANTO roda, tire/coloque um botijao num slot. Ctrl+C pra sair.")
    while True:
        time.sleep(2)
        cur = snapshot(cli, dbs)
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        for db in dbs:
            if db in prev and db in cur and prev[db][1] != cur[db][1]:
                a, b = prev[db][1], cur[db][1]
                for i in range(min(len(a), len(b))):
                    if a[i] != b[i]:
                        print(f"[{ts}] DB{db} byte {i}: {a[i]:#04x} -> {b[i]:#04x}")
        prev = cur


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "dump"
    cli = conectar()
    try:
        dbs = descobrir_dbs(cli)
        if not dbs:
            print("Nenhum DB legivel encontrado na faixa", DB_RANGE)
            return
        if mode == "watch":
            modo_watch(cli, dbs)
        else:
            modo_dump(cli, dbs)
    finally:
        cli.disconnect()


if __name__ == "__main__":
    main()
