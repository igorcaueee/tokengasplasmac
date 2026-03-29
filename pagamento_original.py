import snap7.client as c
from snap7.util import *
from snap7.snap7types import *
import numbers
import time
import sys
import os


#Pagamento -> Central
Pagamento_Funcionando=False
Iniciar_Atendimento = False
Pagamento_Autorizado = False
Pagamento_Rejeitado = False


#Central -> Pagamento
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
Manutencao_Andamento =  False
Central_Em_Alarme = False

def ReadMemory(plc,byte,datatype,db,bit=0,tam_st=0):
    if datatype=='String':
        result = plc.read_area(areas['DB'],db,byte,tam_st+2)
        return get_string(result,0,tam_st+2)
    else:
        result = plc.read_area(areas['DB'],db,byte,datatype)
    if datatype==S7WLBit:
        return get_bool(result,0,bit)
    elif datatype==S7WLByte or datatype==S7WLWord:
        return get_int(result,0)
    elif datatype==S7WLReal:
        return get_real(result,0)
    elif datatype==S7WLDWord:
        return get_dword(result,0)
    else:
        return None

def WriteMemory(plc,byte,datatype,db,bit,valor):
    resultado = plc.read_area(areas['DB'],db,byte,datatype)
    if datatype==S7WLBit:
        set_bool(resultado,0,bit,valor)
    elif datatype==S7WLByte or datatype==S7WLWord:
        set_int(resultado,0,valor)
    elif datatype==S7WLReal:
        set_real(resultado,0,valor)
    elif datatype==S7WLDWord:
        set_dword(resultado,0,valor)
    plc.write_area(areas["DB"],db,byte,resultado)

#abrir comunicação com o CLP
try:
    Central_Gas = c.Client()
    Central_Gas.connect("192.168.0.1",0,1)
    if Central_Gas.get_connected():
        print("Conexão estabelecida com sucesso!")
        Conexao_Estabelecida_CLP = True
        
except Snap7Exception as e:
    print(f"Erro de conexão: {e}")
    Conexao_Estabelecida_CLP =False
except Exception as e:
    print(f"Erro inesperado: {e}")
    Conexao_Estabelecida_CLP =False
        
while True:

    #dados para enviar    
    WriteMemory(Central_Gas,2,S7WLBit,2,0,Pagamento_Funcionando)
    WriteMemory(Central_Gas,2,S7WLBit,2,1,Iniciar_Atendimento)
    WriteMemory(Central_Gas,2,S7WLBit,2,2,Pagamento_Autorizado)
    WriteMemory(Central_Gas,2,S7WLBit,2,3,Pagamento_Rejeitado)

        
    #dados para Receber
    Porta_Aberta_Andar1 = ReadMemory(Central_Gas,0,S7WLBit,2,0)
    Porta_Aberta_Andar2 = ReadMemory(Central_Gas,0,S7WLBit,2,1)
    Porta_Aberta_Andar3 = ReadMemory(Central_Gas,0,S7WLBit,2,2)
    Andar1_Destravado_InserirBotijao = ReadMemory(Central_Gas,0,S7WLBit,2,3)
    Andar2_Destravado_InserirBotijao = ReadMemory(Central_Gas,0,S7WLBit,2,4)
    Andar3_Destravado_InserirBotijao = ReadMemory(Central_Gas,0,S7WLBit,2,5)
    Alerta_Tempo_Inatividade = ReadMemory(Central_Gas,0,S7WLBit,2,6)
    Analisando_Botijao = ReadMemory(Central_Gas,0,S7WLBit,2,7)
    Botijao_Aceito = ReadMemory(Central_Gas,1,S7WLBit,2,0)
    Botijao_Rejeitado = ReadMemory(Central_Gas,1,S7WLBit,2,1)
    Andar1_Destravado_RetirarBotijao = ReadMemory(Central_Gas,1,S7WLBit,2,2)
    Andar2_Destravado_RetirarBotijao = ReadMemory(Central_Gas,1,S7WLBit,2,3)
    Andar3_Destravado_RetirarBotijao = ReadMemory(Central_Gas,1,S7WLBit,2,4)
    Manutencao_Andamento =  ReadMemory(Central_Gas,1,S7WLBit,2,5)
    Central_Em_Alarme =  ReadMemory(Central_Gas,1,S7WLBit,2,6)
