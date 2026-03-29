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
global Passo
webcam = "/dev/video4"
processando_imagem = False

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
            #if Botijao_Aceito == "True":
                  Botijao_Aceito = True
                  #WriteMemory(4,S7WLBit,2,0,1) #ANTIGO
                  WriteMemory(0,S7WLBit,4,0,1)
                  time.sleep(1)
            else:
                  #Botijao_Aceito = True # Para testes
                  #WriteMemory(4,S7WLBit,2,0,1)
                  Botijao_Rejeitado = True
                  #WriteMemory(4,S7WLBit,2,1,1) #MEMORIA ANTIGA
                  WriteMemory(0,S7WLBit,4,1,1)
                  time.sleep(1)
        else:
            print(f"Erro na resposta da API")
            Botijao_Rejeitado = True
            WriteMemory(0,S7WLBit,4,1,1)
            time.sleep(1)

        print("Resposta da API:", response_data)
        print("Botijão Aceito:", Botijao_Aceito)
        print("Botijão Rejeitado:", Botijao_Rejeitado)
       # return Botijao_Aceito
    except requests.exceptions.RequestException as e:
        Botijao_Rejeitado = True
        #WriteMemory(4,S7WLBit,2,1,1) #ANTIGO
        WriteMemory(0,S7WLBit,4,1,1)
        time.sleep(1)
        print("Erro ao enviar imagem:", e)

Central_Gas = None
Conexao_Estabelecida_CLP = False

# Funcao para abrir comunicacao com o CLP
def conectar_clp():
     global Central_Gas, Conexao_Estabelecida_CLP
     try:
         Central_Gas = c.Client()
         Central_Gas.connect("192.168.0.1", 0, 1)
         if Central_Gas.get_connected():
             print("Conexao estabelecida com sucesso!")
             Conexao_Estabelecida_CLP = True
         else:
             print("Falha na Conexao com o CLP!")
             Conexao_Estabelecida_CLP = False
     except Snap7Exception as e:
         print(f"Erro de Conexao: {e}")
         Conexao_Estabelecida_CLP = False
     except Exception as e:
         print(f"Erro inesperado: {e}")
         Conexao_Estabelecida_CLP = False

topic = "central/1"
Iniciado = False
Wait = 0
Show = 0
Insert_Botijao = 0
Time_Botijao = 5
Time_Wait = 10
Intent = 0
Pagamento_Funcionando = True #
Iniciar_Atendimento = False
Metodo_Pagamento = False
Pix = False
#Passo = 1

Pagamento_Autorizado = False
Pagamento_Rejeitado = False

# Funcao de callback chamada quando o cliente conecta ao broker
def on_connect(client, userdata, flags, rc):
    print(f"Conectado ao broker com codigo {rc}")

# Funcao de callback chamada quando uma mensagem nao recebida
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
    global Passo

  

    print(f"Mensagem recebida: {msg.payload.decode()}")

    #TESTE ->> if  msg.payload.decode() in ["1","3","4","5","7","8","9","11","12","13","15","19","20"]:
            #   Passo = int(msg.payload.decode())
            #   print(f"MUDANDDO PASSO PARA {Passo}")

    if  msg.payload.decode() == "Cancelando cobrança ....":
           Pagamento_Rejeitado = True
           #WriteMemory(4,S7WLBit,2,3,1) #ANTIGO
           # WriteMemory(0,S7WLBit,4,3,1) PAGAMENTO REJEIADO
           WriteMemory(0,S7WLBit,4,1,1) # Botijao rejeitado
           time.sleep(1)
           print("XXXXXXXXXXX CANCELANDO COBRANCA -------------")
           #print(f"{WriteMemory(4,S7WLBit,2,3,1)}")
           #reset()

    if "Erro" in msg.payload.decode():
        time.sleep(4)
        reset()

    if  msg.payload.decode() == "INICIA":
            Iniciado = True
            Iniciar_Atendimento = True
            WriteMemory(4,S7WLBit,2,4,1)
            time.sleep(1)
            
    if  msg.payload.decode() == "CANCELED":
          #WriteMemory(4,S7WLBit,2,3,1) Antigo
          WriteMemory(0,S7WLBit,4,1,1)
          print("CANCELADO !!!!!!!!!!!!!!!!!!!!!!!")
          #print(f"{WriteMemory(4,S7WLBit,2,3,1)}") 

    if  msg.payload.decode() == "PIX" or msg.payload.decode() == "DEBITO" or msg.payload.decode() == "CREDITO":
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
        WriteMemory(0,S7WLBit,4,0,0)
        time.sleep(0.1)
        WriteMemory(0,S7WLBit,4,1,0)
        time.sleep(0.1)
        WriteMemory(0,S7WLBit,4,3,0)
        time.sleep(0.1)
        WriteMemory(0,S7WLBit,4,2,0)
        time.sleep(1)
        print("Forcando Reset dos estados!")    

        
    if Passo == 9:
        print(f"ENTROU NA ANLISE DE PAGAEMNTO $$$$$$$$$$$$$$$$$$$$")
        if  msg.payload.decode() == "APPROVED":
                print("DENTRO DE APROVADO  ======+==++++++++++++++++++++++++++")
                Pagamento_Autorizado = True 
                Pagamento_Rejeitado = False
                #WriteMemory(4,S7WLBit,2,2,1) Antigo
                WriteMemory(0,S7WLBit,4,2,1)
                time.sleep(1)

        elif  msg.payload.decode() == "REJECTED":
                Pagamento_Autorizado = False  
                Pagamento_Rejeitado = True    
                #WriteMemory(4,S7WLBit,2,3,) Antigo
                WriteMemory(0,S7WLBit,4,3,1)  
                time.sleep(1)              
         

client = mqtt.Client()

client.on_connect = on_connect
client.on_message = on_message

client.connect("localhost", 1883, 60)
client.subscribe(f"central/1")
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
    Manutencao_Andamento =  False
    Central_Em_Alarme = False 

def ReadMemory(byte, datatype, db, bit=0, tam_st=0):
     global Central_Gas
     if not Conexao_Estabelecida_CLP or Central_Gas is None:
         print("Erro: CLP nao conectado!")
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
         print(f"Erro ao ler memoria do CLP: {e}")
         return None

def WriteMemory(byte, datatype, db, bit, valor):
     global Central_Gas
     if not Conexao_Estabelecida_CLP or Central_Gas is None:
         print("Erro: CLP nao conectado!")
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
         print(f"Erro ao escrever na memoria do CLP: {e}")

    
conectar_clp()

while True:
        time.sleep(2)
        print(f"entrou no while")
        #dados para enviar
        WriteMemory(4,S7WLBit,2,7,Pagamento_Funcionando)

    #----------------- INICIO ---------------------------------------   

        Analisar_Andar = ReadMemory(2,S7WLWord,2,0)
        time.sleep(1)
        Passo = ReadMemory(0,S7WLWord,2,0)
        time.sleep(1)
        
        #Passo = 1
        print(f"MEMORIA **************")
        print(f"{Analisar_Andar}")
        print(f"{Passo}")

        if Passo == 1:
             client.publish(f"central/1", "INICIAR")
             print("INICIAR")
             continue

        if  Passo == 3:
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

        if  Passo == 4:
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
#------- ALERTA INATIVIDADE -------------------------------------

        #Alerta_Tempo_Inatividade = False
        Alerta_Tempo_Inatividade = ReadMemory(4,S7WLBit,2,6)

        if  Passo == 5:
              print(f"Iniciando Processo...")
              client.publish(f"central/1", f"Iniciando Processo...") 
              continue

        if  Passo == 7:
              print(f"Carregando o Botijão. Por favor, aguarde...")
              client.publish(f"central/1", f"Carregando o Botijão. Por favor, aguarde...") 
              continue

        if  Alerta_Tempo_Inatividade == True:
              client.publish(f"central/1", "Cliente Insira o Botijão.....")
              print(f"Cliente Insira o Botijão.....")
              time.sleep(5)
              continue

        print(f"ANALISE PROXIMO DO 8 ->>>>>>>")
        print(f"{Passo}")

        if Passo == 8: 
            print("ENTROU NA ANLISE  **********")
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
                3: camera3,
            }

            if 'camera' not in locals():
              camera = 1 #Valor padrao

            resultado = cameras.get(camera)()  # Chama a Funcao correspondente
            
            print(f"ID CAMERA -> {camera}")
            print(f"PATH CAM -> {resultado}")
            if not os.path.exists(resultado):
              print(f"ERRO CRITICO: O caminho {resultado} nao foi encontrado no sistema!")
            Insert_Botijao += 1

            webcam = resultado
            print(f"subprocess.check_output(cmd, shell=True, text=True).strip()")
            print(f"WEBCAM {webcam}")   

            client.publish(f"central/1", f"Analisando o Botijão, Por favor, Aguarde........")
            print(f"Analisando o Botijão, Por favor, Aguarde........")
            print("Botijao ACEITO VARIAVEL - ANTES ", Botijao_Rejeitado)
            print("Botijao REJEITADO VARIAVEL - ANTES", Botijao_Rejeitado)
            print(f"WEBCAM? {webcam}")

            if not processando_imagem:
                frame = capture_image(webcam)
                if frame is not None:
                    processamento_imagem = True
                    print("Enviando para API...")
                    send_image(frame)
                    processando_imagem = False
            else:
                print("Já existe uma análise em curso, aguardando resposta da API...")
            #continue
            
        Analisar_Andar = ReadMemory(2,S7WLWord,2,0)
        time.sleep(1)
        Passo = ReadMemory(0,S7WLWord,2,0)
        time.sleep(1)
        #Analisar_Andar = 2#ReadMemory(2,S7WLWord,2,0)
        #Passo = ReadMemory(0,S7WLWord,2,0)

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
       
       #if Passo == 14:
			 #client.publish(f"central/1", f"Botijão Retirado")
             #client.publish(f"central/1", f"FORCAR_RESET")
             #reset()
             #continue 
        
        if Passo == 13 or Passo == 15 or Passo == 20:
              client.publish(f"central/1", f"Botijão Retirado")
              client.publish(f"central/1", f"FORCAR_RESET")
              reset()
              continue 

        if  Botijao_Aceito == True and Show == 0: 
              Show = 1
              Metodo_Pagamento = False
              Pagamento_AUtorizado = False
              Pagamento_Rejeitado = False
              #WriteMemory(0,4,1,0)
              client.publish(f"central/1", "Botijão Aceito!")
              print(f"Botijão Aceito!")
              time.sleep(3)

        if  Botijao_Rejeitado == True and Show == 0:
              Show = 1
              client.publish(f"central/1", "Botijão Rejeitado")
              print(f"Botijão Rejeitado")
              time.sleep(5)
              #continue

        if  Passo == 9 and Metodo_Pagamento == False:
              Pagamento_AUtorizado = False
              Pagamento_Rejeitado = False
              client.publish(f"central/1", f"Escolha uma forma de pagamento ({Time_Wait - Wait})")
              print(f"Escolha uma forma de pagamento ({Time_Wait - Wait})")
              Wait += 1

              if Wait >= Time_Wait:
                          client.publish(f"central/1", f"Tempo Expirado!")
                          print(f"Tempo Expirado!")
                          #WriteMemory(4,S7WLBit,2,1,1) #ANTIGO
                          #WriteMemory(0,S7WLBit,4,1,1) BOTIJAO REJEITADO NAO FOI
                          WriteMemory(0,S7WLBit,4,3,1) #PAGAMENTO REJEITADO
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
                WriteMemory(4,S7WLBit,2,1,1)
                time.sleep(2)
                reset()

        #------------ LOGICA BASE PAGAMENTO ACEITO --------------

	
		
        if Passo == 9 and Pagamento_Autorizado == True:
            client.publish(f"central/1", "Pagamento Aceito")
            print(f"Pagamento Aceito")
            #WriteMemory(4,S7WLBit,2,2,1)  #ANTIGO
            WriteMemory(0,S7WLBit,4,2,0)    
            time.sleep(0.1)  
            Pagamento_Rejeitado = False
            Pagamento_Autorizado = False        
            time.sleep(2)
            #client.publish(f"central/1", f"FORCAR_RESET")
            #reset()
            continue

        if Passo == 9 and Pagamento_Rejeitado == True:
            client.publish(f"central/1", "Pagamento Rejeitado, devolvendo o Botijão")
            Pagamento_Autorizado = False
            Pagamento_Rejeitado = False
            #WriteMemory(4,S7WLBit,2,3,1) #ANTIGO
            WriteMemory(0,S7WLBit,4,3,0)
            time.sleep(3)
            print(f"Pagamento Rejeitado, devolvendo o Botijão")
           
     
        #----------- RESET ---------------------------------------
            #FAZER TESTE
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

        #----------- OUTROS ------------------------------------    
        #Manutencao_Andamento = False
        Manutencao_Andamento = ReadMemory(4,S7WLBit,2,5)
        time.sleep(1)

        if Manutencao_Andamento == True:
                client.publish(f"central/1", "Central em Manutencao")
                print(f"Central em Manutencao")

        #Central_Em_Alarme = False
        Central_Em_Alarme = ReadMemory(4,S7WLBit,2,6)
        time.sleep(1)

        if Central_Em_Alarme == True:
                client.publish(f"central/1", "Central em Alarme")
                print(f"Central em Alarme")
