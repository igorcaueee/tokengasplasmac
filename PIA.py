import snap7.client as c
from snap7.util import *
from snap7.snap7types import *
from snap7.snap7exceptions import *
import numbers
import time
import sys
import os
import paho.mqtt.client as mqtt
import requests
import cv2
import subprocess

URL = "http://localhost:3000/image-analysis"
#Instalar v4l2-ctl 
global webcam
webcam = "/dev/video4"
# Capturar a imagem da webcam
def capture_image(device_path):
    cap = cv2.VideoCapture(device_path)  # 0 para a primeira webcam USB
    if not cap.isOpened():
        client.publish(f"central/1", "Erro ao acessar a camera")
        print("Erro ao acessar a webcam")
        return None

    ret, frame = cap.read()
    client.publish(f"central/1", "Capturando imagem do Botijão.....")
    cap.release()  # Liberar a câmera

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
        response_data = response.json()  # Converte a resposta JSON em um dicionário

        if "status" in response_data:
            Botijao_Aceito = response_data["status"] == "True"  # Atualiza a variável
            if Botijao_Aceito == "True":
                  Botijao_Aceito = True
                  WriteMemory(1,S7WLBit,2,0,Botijao_Aceito)
            else:
                 #  Botijao_Aceito = True # Para testes
                  Botijao_Rejeitado = True
                  WriteMemory(1,S7WLBit,2,1,Botijao_Rejeitado)
        
        print("Resposta da API:", response_data)
        print("Botijão Aceito:", Botijao_Aceito)
        print("Botijão Aceito:", Botijao_Rejeitado)
        return Botijao_Aceito
    except requests.exceptions.RequestException as e:
        Botijao_Rejeitado = True
        WriteMemory(1,S7WLBit,2,1,Botijao_Rejeitado)
        print("Erro ao enviar imagem:", e)

Central_Gas = None
Conexao_Estabelecida_CLP = False

# Função para abrir comunicação com o CLP
def conectar_clp():
     global Central_Gas, Conexao_Estabelecida_CLP
     try:
         Central_Gas = c.Client()
         Central_Gas.connect("192.168.0.1", 0, 1)
         if Central_Gas.get_connected():
             print("ConexÃ£o estabelecida com sucesso!")
             Conexao_Estabelecida_CLP = True
         else:
             print("Falha na conexÃ£o com o CLP!")
             Conexao_Estabelecida_CLP = False
     except Snap7Exception as e:
         print(f"Erro de conexÃ£o: {e}")
         Conexao_Estabelecida_CLP = False
     except Exception as e:
         print(f"Erro inesperado: {e}")
         Conexao_Estabelecida_CLP = False

topic = "central/1"
Iniciado = False
Wait = 0
Insert_Botijao = 0
Time_Botijao = 5
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
    global Pagamento_Funcionando
    global Iniciar_Atendimento
    global Iniciado
    global Pagamento_Autorizado
    global Pagamento_Rejeitado
    global Metodo_Pagamento
    global Pix
    global Central_Gas
    global Tipo

  

    print(f"Mensagem recebida: {msg.payload.decode()}")

    if  msg.payload.decode() == "Cancelando cobrança ....":
           Pagamento_Rejeitado = True
           #Pagamento_Rejeitado = 
           WriteMemory(2,S7WLBit,2,3,Pagamento_Rejeitado)
           reset()

    if "Erro" in msg.payload.decode():
        time.sleep(4)
        reset()

    if  msg.payload.decode() == "INICIA":
            Iniciado = True
            Iniciar_Atendimento = True
            WriteMemory(4,S7WLBit,2,4,Iniciar_Atendimento)
            
    if  msg.payload.decode() == "CANCELED":
            reset()  

    if  msg.payload.decode() == "PIX" or msg.payload.decode() == "DEBITO" or msg.payload.decode() == "CREDITO":
            Metodo_Pagamento = True  
            if msg.payload.decode() == "PIX": 
                  Pix = True  
            else:
                  Tipo = msg.payload.decode()  
            
    if Intent == 1:
        if  msg.payload.decode() == "APPROVED":
                Pagamento_Autorizado = True 
                Pagamento_Rejeitado = False

        if  msg.payload.decode() == "REJECTED":
                Pagamento_Autorizado = False  
                Pagamento_Rejeitado = True                     
         

# Inicializando o cliente MQTT
client = mqtt.Client()

# Configurando o callback de conexÃ£o
client.on_connect = on_connect
client.on_message = on_message

# Conectando ao broker (localhost:1883 sem usuÃ¡rio e senha)
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
    global Insert_Botijao, Wait, Andar1_Destravado_RetirarBotijao, Andar2_Destravado_RetirarBotijao, Andar3_Destravado_RetirarBotijao
    global Manutencao_Andamento, Central_Em_Alarme
    Pagamento_Autorizado = False
    Metodo_Pagamento = False
    Pix = False
    Pagamento_Rejeitado = False
    Iniciar_Atendimento = False
    Iniciado = False
    Insert_Botijao = 0
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



# # Função para ler memória do CLP
def ReadMemory(byte, datatype, db, bit=0, tam_st=0):
     global Central_Gas
     if not Conexao_Estabelecida_CLP or Central_Gas is None:
         print("Erro: CLP nÃ£o conectado!")
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
         print(f"Erro ao ler memÃ³ria do CLP: {e}")
         return None

# Função para escrever na memória do CLP
def WriteMemory(byte, datatype, db, bit, valor):
     global Central_Gas
     if not Conexao_Estabelecida_CLP or Central_Gas is None:
         print("Erro: CLP nÃ£o conectado!")
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
         print(f"Erro ao escrever na memÃ³ria do CLP: {e}")

    
conectar_clp()

        
while True:
        time.sleep(2)

        #dados para enviar    
        WriteMemory(2,S7WLBit,2,0,Pagamento_Funcionando)
        WriteMemory(2,S7WLBit,2,2,Pagamento_Autorizado)
 
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
    
            continue
        

        #------------------- INFORMAR PORTA PARA O USUARIO -----------------

        #Andar1_Destravado_InserirBotijao = False#True
        Andar1_Destravado_InserirBotijao = ReadMemory(0,S7WLBit,2,3)
        #Andar2_Destravado_InserirBotijao = False#True
        Andar2_Destravado_InserirBotijao = ReadMemory(0,S7WLBit,2,4)
        #Andar3_Destravado_InserirBotijao = True#False
        Andar3_Destravado_InserirBotijao = ReadMemory(0,S7WLBit,2,5)
        Analisar_Andar = ReadMemory(2,S7WLWord,2,0)
        Passo = ReadMemory(0,S7WLWord,0,0)

        if Intent == 0:

            if  Passo == 3 and Andar1_Destravado_InserirBotijao == True and Iniciado == True and Insert_Botijao == 0:
                        camera = 1
                        Analise_Disponivel = True
                        client.publish(f"central/1", "Insira o Botijão na Porta 1")
                        print(f"Insira o Botijão na Porta 1 ({Time_Botijao - Insert_Botijao})")
                        client.publish(f"central/1", f"Insira o Botijão na Porta 1 ({Time_Botijao - Insert_Botijao})")
                        Insert_Botijao += 1
                        if Insert_Botijao > Time_Botijao:
                               print(f"Entrou no if inatividade")
                               Alerta_Tempo_Inatividade = ReadMemory(0,S7WLBit,2,6)
                               Insert_Botijao = 0
                            
                              
                        continue

            if  Passo == 3 and Andar2_Destravado_InserirBotijao == True and Iniciado == True and Insert_Botijao == 0:
                        camera = 2
                        print(f"CAMERA ---- {camera}")
                        Analise_Disponivel = True
                        client.publish(f"central/1", "Insira o Botijão na Porta 2")
                        print(f"Insira o Botijão na Porta 2 ({Time_Botijao - Insert_Botijao})")
                        client.publish(f"central/1", f"Insira o Botijão na Porta 2 ({Time_Botijao - Insert_Botijao})")
                        Insert_Botijao += 1
                        if Insert_Botijao > Time_Botijao:
                               print(f"Entrou no if inatividade")
                               Alerta_Tempo_Inatividade = ReadMemory(0,S7WLBit,2,6)
                               Insert_Botijao = 0
                        continue

            if  Passo == 3 and Andar3_Destravado_InserirBotijao == True and Iniciado == True and Insert_Botijao == 0:
                        camera = 3
                        print(f"CAMERA ---- {camera}")
                        Analise_Disponivel = True
                        client.publish(f"central/1", "Insira o Botijão na Porta 3")
                        print(f"Insira o Botijão na Porta 3 ({Time_Botijao - Insert_Botijao})")
                        client.publish(f"central/1", f"Insira o Botijão na Porta 3 ({Time_Botijao - Insert_Botijao})")
                        Insert_Botijao += 1
                        if Insert_Botijao > Time_Botijao:
                               print(f"Entrou no if inatividade")
                               Alerta_Tempo_Inatividade = ReadMemory(0,S7WLBit,2,6)
                               Insert_Botijao = 0
                        continue

#------- ALERTA INATIVIDADE -------------------------------------

            #Alerta_Tempo_Inatividade = False
            Alerta_Tempo_Inatividade = ReadMemory(0,S7WLBit,2,6)

            Insert_Botijao = 0

            if  Alerta_Tempo_Inatividade == True and Analise_Disponivel == True:
                client.publish(f"central/1", "Cliente Insira o Botijão.....")
                print(f"Cliente Insira o Botijão.....")

                time.sleep(5)
                continue

            else:
            #----------  Analise de Botijao --------------------------------
               #Analisando_Botijao = True
               Analisando_Botijao = ReadMemory(0,S7WLBit,2,7)
            Analisar_Andar = ReadMemory(4,S7WLBit,2,0)
            print(f"ANALISE ->>>>>>>")
            print(f"{Analisando_Botijao}")
            if Passo == 2: #and Analisar_Andar == True and Analisando_Botijao == True and Analise_Disponivel == True:  
                print("ENTORU NA ANLISE  **********")
                def camera1():
                    #Analisar_Andar1 = ReadMemory(0,)
                    return "/dev/v4l/by-path/platform-fd500000.pcie-pci-0000:01:00.0-usb-0:1.2:1.0-video-index0"
                def camera2():
                    return "/dev/v4l/by-path/platform-fd500000.pcie-pci-0000:01:00.0-usb-0:1.4:1.0-video-index0"
                def camera3():
                    return "/dev/v4l/by-path/platform-fd500000.pcie-pci-0000:01:00.0-usb-0:1.1:1.0-video-index0"

                cameras = {
                    1: camera1, 
                    2: camera2,  
                    3: camera3  
                }

                resultado = cameras.get(camera, camera1)()  # Chama a função correspondente
                cmd = resultado
                print("PATH CAM -> ", resultado)
                Insert_Botijao += 1

                webcam = subprocess.check_output(cmd, shell=True, text=True).strip()
                print(f"subprocess.check_output(cmd, shell=True, text=True).strip()")
                print(f"WEBCAM {webcam}")   

                client.publish(f"central/1", f"Analisando o Botijão, Por favor, Aguarde........")
                print(f"Analisando o Botijão, Por favor, Aguarde........({Time_Botijao - Insert_Botijao})")
            if Passo == 1:
                client.publish(f"central/1", f"Carregando Botijão, Por favor, Aguarde......")
                print(f"Carregando Botijão, Por favor, Aguarde........({Time_Botijao - Insert_Botijao})")
                #reset()
                continue

            if Passo == 3:
              client.publish(f"central/1", f"Devolvendo Botijão, Por favor Aguarde.....")
            if Passo == 4:
              andar = ReadMemory(2,S7WLWord,2,0)
              if andar == 1:
                client.publish(f"central/1", f"Destravando porta 1")
              if andar == 2:
                client.publish(f"central/1", f"Destravando porta 2")
              if andar == 3:
                client.publish(f"central/1", f"Destravando porta 3")
                
             
            #Botijao_Aceito = "Antes"
            print("Botijao ACEITO VARIAVEL - ANTES ", Botijao_Rejeitado)
            print("Botijao REJEITADO VARIAVEL - ANTES", Botijao_Rejeitado)
            print(f"WEBCAM? {webcam}")


            frame = capture_image(webcam)
            if frame is not None:
                send_image(frame)

            Insert_Botijao += 1
            if Insert_Botijao > 15: #Insert_Botijao > Time_Botijao:
                client.publish(f"central/1", f"Aguarde mais um pouco\nAnalisando o Botijão........");
                print(f"Entrou no if inatividade")
                #Alerta_Tempo_Inatividade = True
                #Alerta_Tempo_Inatividade = ReadMemory(0,S7WLBit,2,6)
                Insert_Botijao = 0
                    
            #Botijao_Aceito = ReadMemory(1,S7WLBit,2,0)
            #Botijao_Rejeitado = ReadMemory(1,S7WLBit,2,1)

            print("Botijao ACEITO VARIAVEL ", Botijao_Aceito)
            print("Botijao REJEITADO VARIAVEL ", Botijao_Rejeitado)


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
            Analisar_Andar = False
            #Iniciado = False

            continue

        if Intent == 1 and Metodo_Pagamento == False:
            client.publish(f"central/1", f"Escolha uma forma de pagamento ({Time_Wait - Wait})")
            print(f"Escolha uma forma de pagamento ({Time_Wait - Wait})")
            Wait += 1

            if Wait >= Time_Wait:
                        client.publish(f"central/1", f"Tempo Expirado!")
                        print(f"Tempo Expirado!")
                        Wait = 0
                        time.sleep(4)
                        reset()
            
            continue 


        if Intent == 1 and Pagamento_Autorizado == False and Pagamento_Rejeitado == False:

            Wait += 1
            if Pix == True:
                client.publish(f"central/1", f"Aguardando Pagamento {Time_Wait - Wait}\nEscaneie o QRCode para concluir o pagamento")
                print(f"Aguardando Pagamento {Time_Wait - Wait}")
            else:
                client.publish(f"central/1", f"Aguardando Pagamento com Cartão de {Tipo} {Time_Wait - Wait}\nSe necessÃ¡rio, clique em\n \"Cobrar\" e/ou \"Ir ao InÃ­cio\" \nna Maquineta")
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
        Manutencao_Andamento = False
        #Manutencao_Andamento = ReadMemory(1,S7WLBit,2,5)

        if Manutencao_Andamento == True:
                client.publish(f"central/1", "Central em Manutenção")
                print(f"Central em Manutenção")

        Central_Em_Alarme = False
        #Central_Em_Alarme = ReadMemory(1,S7WLBit,2,6)

        if Central_Em_Alarme == True:
                client.publish(f"central/1", "Central em Alarme")
                print(f"Central em Alarme")

