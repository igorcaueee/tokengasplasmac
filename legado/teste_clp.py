import snap7.client as c
from snap7.util import *
from snap7.snap7types import *
from snap7.snap7exceptions import *
import numbers
import time
import sys
import os
import paho.mqtt.client as mqtt
 
Central_Gas = None
Conexao_Estabelecida_CLP = False
'''
# Dicionário de áreas do CLP
areas = {
    'PE': 0x81,  # Process Inputs
    'PA': 0x82,  # Process Outputs
    'MK': 0x83,  # Marker Memory
    'DB': 0x84,  # Data Block
    'CT': 0x1C,  # Counters
    'TM': 0x1D   # Timers
}
'''
# Função para abrir comunicação com o CLP
def conectar_clp():
    global Central_Gas, Conexao_Estabelecida_CLP
    try:
        Central_Gas = c.Client()
        Central_Gas.connect("192.168.0.1", 0, 1)
        if Central_Gas.get_connected():
            print("Conexão estabelecida com sucesso!")
            Conexao_Estabelecida_CLP = True
	    #regs = clp.read_holding_registers(0, 10)
            #if regs:
	#	print("Dados lidos: ", regs)
	 #   else:
	#	print("erro lçeitura teste")
        else:
            print("Falha na conexão com o CLP!")
            Conexao_Estabelecida_CLP = False
    except Snap7Exception as e:
        print(f"Erro de conexão: {e}")
        Conexao_Estabelecida_CLP = False
    except Exception as e:
        print(f"Erro inesperado: {e}")
        Conexao_Estabelecida_CLP = False

topic = "central/1"
Iniciado = False
Wait = 0
Time_Wait = 65
Intent = 0
Pagamento_Funcionando = True #
Iniciar_Atendimento = False
Metodo_Pagamento = False
Pix = False

Pagamento_Autorizado = False
Pagamento_Rejeitado = False

# Função de callback chamada quando o cliente conecta ao broker
def on_connect(client, userdata, flags, rc):
    print(f"Conectado ao broker com código {rc}")

# Função de callback chamada quando uma mensagem é recebida
def on_message(client, userdata, msg):
    #Pagamento -> Central
    global Pagamento_Funcionando #*****
    global Iniciar_Atendimento
    global Iniciado
    global Pagamento_Autorizado
    global Pagamento_Rejeitado
    global Metodo_Pagamento
    global Pix
    global Central_Gas

  

    print(f"Mensagem recebida: {msg.payload.decode()}")

    if  msg.payload.decode() == "Cancelando cobrança ....":
           Pagamento_Rejeitado = True
           WriteMemory(2,S7WLBit,2,3,Pagamento_Rejeitado)
           reset()

    if  msg.payload.decode() == "INICIA":
            Iniciado = True
            Iniciar_Atendimento = True
            WriteMemory(2,S7WLBit,2,1,Iniciar_Atendimento)
    if  msg.payload.decode() == "CANCELED":
            reset()  

    if  msg.payload.decode() == "PIX" or msg.payload.decode() == "DEBITO" or msg.payload.decode() == "CREDITO":
            Metodo_Pagamento = True  
            if msg.payload.decode() == "PIX": 
                  Pix = True     
            
    if Intent == 1:
        if  msg.payload.decode() == "APPROVED":
                Pagamento_Autorizado = True 
                Pagamento_Rejeitado = False

        if  msg.payload.decode() == "REJECTED":
                Pagamento_Autorizado = False  
                Pagamento_Rejeitado = True                     
         

# Inicializando o cliente MQTT
client = mqtt.Client()

# Configurando o callback de conexão
client.on_connect = on_connect
client.on_message = on_message

# Conectando ao broker (localhost:1883 sem usuário e senha)
client.connect("localhost", 1883, 60)

client.subscribe(f"central/1")

# Iniciando o loop do cliente MQTT em segundo plano
client.loop_start()


#Central -> Pagamento

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
Manutencao_Andamento =  False
Central_Em_Alarme = False

def reset():
    global Pagamento_Autorizado, Pix, Metodo_Pagamento, Pagamento_Rejeitado, Iniciar_Atendimento, Iniciado, Intent
    global Porta_Aberta_Andar1, Porta_Aberta_Andar2, Porta_Aberta_Andar3
    global Andar1_Destravado_InserirBotijao, Andar2_Destravado_InserirBotijao, Andar3_Destravado_InserirBotijao
    global Alerta_Tempo_Inatividade, Analisando_Botijao, Botijao_Aceito, Botijao_Rejeitado
    global Wait, Andar1_Destravado_RetirarBotijao, Andar2_Destravado_RetirarBotijao, Andar3_Destravado_RetirarBotijao
    global Manutencao_Andamento, Central_Em_Alarme
    Pagamento_Autorizado = False
    Metodo_Pagamento = False
    Pix = False
    Pagamento_Rejeitado = False
    Iniciar_Atendimento = False
    Iniciado = False
    Wait = 0
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
    Manutencao_Andamento =  False
    Central_Em_Alarme = False 



# Função para ler memória do CLP
def ReadMemory(byte, datatype, db, bit=0, tam_st=0):
    global Central_Gas
    if not Conexao_Estabelecida_CLP or Central_Gas is None:
        print("Erro: CLP não conectado!")
        return None

    try:
        if datatype == 'String':
            result = Central_Gas.read_area(areas['DB'], db, byte, tam_st+2)
            return get_string(result, 0, tam_st+2)
        else:
            result = Central_Gas.read_area(areas['DB'], db, byte, datatype)

        if datatype == S7WLBit:
            return get_bool(result, 0, bit)
        elif datatype in [S7WLByte, S7WLWord]:
            return get_int(result, 0)
        elif datatype == S7WLReal:
            return get_real(result, 0)
        elif datatype == S7WLDWord:
            return get_dword(result, 0)
        else:
            return None
    except Exception as e:
        print(f"Erro ao ler memória do CLP: {e}")
        return None

# Função para escrever na memória do CLP
def WriteMemory(byte, datatype, db, bit, valor):
    global Central_Gas
    if not Conexao_Estabelecida_CLP or Central_Gas is None:
        print("Erro: CLP não conectado!")
        return

    try:
        resultado = Central_Gas.read_area(areas['DB'], db, byte, datatype)
        if datatype == S7WLBit:
            set_bool(resultado, 0, bit, valor)
        elif datatype in [S7WLByte, S7WLWord]:
            set_int(resultado, 0, valor)
        elif datatype == S7WLReal:
            set_real(resultado, 0, valor)
        elif datatype == S7WLDWord:
            set_dword(resultado, 0, valor)

        Central_Gas.write_area(areas["DB"], db, byte, resultado)
    except Exception as e:
        print(f"Erro ao escrever na memória do CLP: {e}")

    
conectar_clp()

        
while True:
#	if not Central_Gas.get_connected():
#        	print("Erro: CLP não conectado!")
#                exit()

        time.sleep(2)

        #dados para enviar    
        WriteMemory(2,S7WLBit,2,0,Pagamento_Funcionando)
#        WriteMemory(2,S7WLBit,2,1,Iniciar_Atendimento)
        WriteMemory(2,S7WLBit,2,2,Pagamento_Autorizado)
#        WriteMemory(2,S7WLBit,2,3,Pagamento_Rejeitado)
        print("DEBUG ATNDIMENTO", Iniciar_Atendimento)
 
        #dados para Receber
        Porta_Aberta_Andar1 = ReadMemory(0,S7WLBit,2,0)
        Porta_Aberta_Andar2 = ReadMemory(0,S7WLBit,2,1)
        Porta_Aberta_Andar3 = ReadMemory(0,S7WLBit,2,2)

    #----------------- INICIO ---------------------------------------   

        if Porta_Aberta_Andar1 == True:
            client.publish(f"central/1", "Feche a porta 1")
            print(f"Feche a porta 1")
            continue

        if Porta_Aberta_Andar2 == True:
            client.publish(f"central/1", "Feche a porta 2")
            print(f"Feche a porta 2")
            continue

        if Porta_Aberta_Andar3 == True:
            client.publish(f"central/1", "Feche a porta 3")
            print(f"Feche a porta 3")
            continue

        if Porta_Aberta_Andar1 != True and Porta_Aberta_Andar2 != True and Porta_Aberta_Andar3 != True and Iniciado == False:
            client.publish(f"central/1", "INICIAR")
            print("INICIAR")

            #Iniciar_Atendimento = True
    
            continue
        

        #------------------- INFORMAR PORTA PARA O USUARIO -----------------

        Andar1_Destravado_InserirBotijao = ReadMemory(0,S7WLBit,2,3)
        Andar2_Destravado_InserirBotijao = ReadMemory(0,S7WLBit,2,4)
        Andar3_Destravado_InserirBotijao = ReadMemory(0,S7WLBit,2,5)


        if Intent == 0:
            if  Andar1_Destravado_InserirBotijao == True and Iniciado == True:
                        #Iniciar_Atendimento = False
                        Analise_Disponivel = True
                        client.publish(f"central/1", "Insira o Botijão na Porta 1")
                        print(f"Insira o Botijão na Porta 1")
                        continue

            if  Andar2_Destravado_InserirBotijao == True and Iniciado == True:
                        #Iniciar_Atendimento = False
                        Analise_Disponivel = True
                        client.publish(f"central/1", "Insira o Botijão na Porta 2")
                        print(f"Insira o Botijão na Porta 2")
                        continue

            if  Andar3_Destravado_InserirBotijao == True and Iniciado == True:
                        #Iniciar_Atendimento = False
                        Analise_Disponivel = True
                        client.publish(f"central/1", "Insira o Botijão na Porta 3")
                        print(f"Insira o Botijão na Porta 3")


#------- ALERTA INATIVIDADE -------------------------------------

            Alerta_Tempo_Inatividade = ReadMemory(0,S7WLBit,2,6)

            if  Alerta_Tempo_Inatividade == True and Analise_Disponivel == True:
                client.publish(f"central/1", "Usuário Insira o Botijão Não Detectado!")
                print(f"Usuário Insira o Botijão Não Detectado!")
                time.sleep(5)
                continue

            else:
            #----------  Analise de Botijao --------------------------------
                Analisando_Botijao = ReadMemory(0,S7WLBit,2,7)

            if  Analisando_Botijao == True and Analise_Disponivel == True:     

                client.publish(f"central/1", "Analisando o Botijão, Por favor, Aguarde........")
                print(f"Analisando o Botijão, Por favor, Aguarde........")

            Botijao_Aceito = ReadMemory(1,S7WLBit,2,0)
            Botijao_Rejeitado = ReadMemory(1,S7WLBit,2,1)
            print("Botijao REJEITADO VARIAVEL", Botijao_Rejeitado)


        if  Botijao_Aceito == True and Intent == 0:     
            Intent = 1
            client.publish(f"central/1", "Botijão Aceito!")
            print(f"Botijão Aceito!")

            time.sleep(3)

        if  Botijao_Rejeitado == True:
            Intent = 0
            client.publish(f"central/1", "Botijão Rejeitado")
            print(f"Botijão Rejeitado")
            Iniciar_Atendimento = True
            Iniciado = False
            #VOLTAR PARA INICIAR
            continue

        if Intent == 1 and Metodo_Pagamento == False:
            client.publish(f"central/1", f"Escolha uma forma de pagamento ({Time_Wait - Wait})")
            print(f"Escolha uma forma de pagamento ({Time_Wait - Wait})")
            Wait += 1

            if Wait >= Time_Wait:
                        client.publish(f"central/1", f"Tempo Expirado!")
                        print(f"Tempo Expirado!")
                        time.sleep(4)
                        reset()
            
            continue
            
            # COLOCAR O COMANDO QUE IRA VOLTAR PARA ANALISE DE ALGUMA PORTA ABERTA*******


        if Intent == 1 and Pagamento_Autorizado == False and Pagamento_Rejeitado == False:

            Wait += 1
            if Pix == True:
                client.publish(f"central/1", f"Aguardando Pagamento {Time_Wait - Wait}\nEscaneie o QRCode para concluir o pagamento")
                print(f"Aguardando Pagamento {Time_Wait - Wait}")
            else:
                client.publish(f"central/1", f"Aguardando Pagamento {Time_Wait - Wait}\nSe necessário, clique em\n \"Cobrar\" e/ou \"Ir ao Início\" \nna Maquineta")
                print(f"Aguardando Pagamento {Time_Wait - Wait}")
                    
                if Wait >= Time_Wait:
                        client.publish(f"central/1", f"Cancelando cobrança ....")
                        print(f"Cancelando cobrança ....")
                        time.sleep(4)
                        reset()

        #------------ LOGICA BASE PAGAMENTO ACEITO --------------


        if Pagamento_Autorizado == True and Intent == 1:
            client.publish(f"central/1", "Pagamento Aceito")
            print(f"Pagamento Aceito")             
            time.sleep(2)
            Andar1_Destravado_RetirarBotijao = ReadMemory(1,S7WLBit,2,2)
            Andar2_Destravado_RetirarBotijao = ReadMemory(1,S7WLBit,2,3)
            Andar3_Destravado_RetirarBotijao = ReadMemory(1,S7WLBit,2,4)

        if Pagamento_Rejeitado == True and Intent == 1:
            client.publish(f"central/1", "Pagamento Rejeitado, devolvendo o Botijão")
            time.sleep(3)
            print(f"Pagamento Rejeitado, devolvendo o Botijão")
            Pagamento_Autorizado = False
            Andar1_Destravado_RetirarBotijao = ReadMemory(1,S7WLBit,2,2)
            Andar2_Destravado_RetirarBotijao = ReadMemory(1,S7WLBit,2,3)
            Andar3_Destravado_RetirarBotijao = ReadMemory(1,S7WLBit,2,4)
            
        #----------- RESET ---------------------------------------
            reset()
            continue
        

        if   Andar1_Destravado_RetirarBotijao == True and Intent == 1:
            client.publish(f"central/1", "Retirar o Botijão na Porta 1")
            print(f"Retirar o Botijão na Porta 1")
            time.sleep(5)
            reset()

        if   Andar2_Destravado_RetirarBotijao == True and Intent == 1:
            client.publish(f"central/1", "Retirar o Botijão na Porta 2")
            print(f"Retirar o Botijão na Porta 2")
            time.sleep(5)
            reset()

        if   Andar3_Destravado_RetirarBotijao == True and Pagamento_Autorizado == True:
            client.publish(f"central/1", "Retirar o Botijão na Porta 3")
            print(f"Retirar o Botijão na Porta 3")
            time.sleep(5)
            reset()


        #----------- OUTROS ------------------------------------    
        Manutencao_Andamento = ReadMemory(1,S7WLBit,2,5)

        if Manutencao_Andamento == True:
                client.publish(f"central/1", "Central em Manutenção")
                print(f"Central em Manutenção")

        Central_Em_Alarme = ReadMemory(1,S7WLBit,2,6)

        if Central_Em_Alarme == True:
                client.publish(f"central/1", "Central em Alarme")
                print(f"Central em Alarme")
    


