from ultralytics import YOLO
import cv2
from collections import defaultdict
import numpy as np
import matplotlib.image as mpimg
import snap7
import snap7.client as c
from snap7.util import *
from snap7.snap7types import *
from snap7.snap7exceptions import Snap7Exception
import numbers
import time
import sys
 
#model = YOLO("C:/Users/dschauren/Downloads/treinando_yolov8-main/treinando_yolov8-main/runs/detect/train/weights/best.pt")
model = YOLO("best.pt")

track_history = defaultdict(lambda: [])
cap = cv2.VideoCapture(2)
#Aqui ajustar valores da altura conforme a camera for instalada
Valor_Y_Andar1 = 300
Valor_Y_Andar2 = 600
Valor_Y_Andar3 = 900

Botijao_Detecatado_Andar1 = False
Botijao_Detecatado_Andar2 = False
Botijao_Detecatado_Andar3 = False

#precisa pelo menos 10 confirmacoes para afirmar que o botijão está ali
Numero_Confirmacoes = 10
#precisa pelo menos 15 nao confirmacoes para afirmar que o botijão nao está presente
Numero_Nao_Confirmacoes = -15

Numero_Confirmacoes_Andar1=0
Numero_Confirmacoes_Andar2=0
Numero_Confirmacoes_Andar3=0


#informações abaixo serão trocadas com a central
#Central - > IA
Central_Identificar_Botijao_Andar1 = False
Central_Identificar_Botijao_Andar2= False
Central_Identificar_Botijao_Andar3= False

#IA - > Central
IA_Funcionando = False
Central_Botijao_Detectado_Andar1 = False
Central_Botijao_Detectado_Andar2 = False
Central_Botijao_Detectado_Andar3 = False
Central_Botijao_Nao_Detectado_Andar1 = False
Central_Botijao_Nao_Detectado_Andar2 = False
Central_Botijao_Nao_Detectado_Andar3 = False

Conexao_Estabelecida_CLP = False




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
    else:
        print("Conexão não estabelecida");
        
except Snap7Exception as e:
    print(f"Erro de conexão: {e}")
    Conexao_Estabelecida_CLP =False
except Exception as e:
    print(f"Erro inesperado: {e}")
    Conexao_Estabelecida_CLP =False

    
while True:
    #capturando a imagem via 
    #imagem = "Simulacao_Andar1.jpg"
    #img = mpimg.imread(imagem)
    success, img = cap.read()

    #Ler dados do CLP
    Central_Identificar_Botijao_Andar1 = ReadMemory(Central_Gas,4,S7WLBit,2,0)
    Central_Identificar_Botijao_Andar2 = ReadMemory(Central_Gas,4,S7WLBit,2,1)
    Central_Identificar_Botijao_Andar3 = ReadMemory(Central_Gas,4,S7WLBit,2,2)

    #Escrever dados no CLP para comunicar com a IA
    WriteMemory(Central_Gas,6,S7WLBit,2,0,IA_Funcionando)
    WriteMemory(Central_Gas,6,S7WLBit,2,1,Central_Botijao_Detectado_Andar1) 
    WriteMemory(Central_Gas,6,S7WLBit,2,2,Central_Botijao_Detectado_Andar2) 
    WriteMemory(Central_Gas,6,S7WLBit,2,3,Central_Botijao_Detectado_Andar3)
    WriteMemory(Central_Gas,6,S7WLBit,2,4,Central_Botijao_Nao_Detectado_Andar1) 
    WriteMemory(Central_Gas,6,S7WLBit,2,5,Central_Botijao_Nao_Detectado_Andar2)
    WriteMemory(Central_Gas,6,S7WLBit,2,6,Central_Botijao_Nao_Detectado_Andar3)

    #central em Funcionamento  ------------------------------------ REVER SE EXISTE ALGO MELHOR PARA FAZER
    IA_Funcionando = True

    #antes de iniciar nova análise zera as variáveis:
    Botijao_Detecatado_Andar1 = False
    Botijao_Detecatado_Andar2 = False
    Botijao_Detecatado_Andar3 = False
    
    #gera o processamento de imagem com base no modelo
    results = model.track(img)

    # para as formas detectadas, irá analisar uma por uma e verificar onde estão dentro da imagem
    for result in results:
        try:
            # Plota o quadro circundado o objeto detectado e informando a acurácia
            img = result.plot()

            # Pegar a posição da caixa ao redor da detecção
            boxes = result.boxes.xywh.cpu()
            #pegar o ID da detecção
            track_ids = result.boxes.id.int().cpu().tolist()

            # Verificar para cada posição detectada qual a área e definir em qual andar está
            for box, track_id in zip(boxes, track_ids):
                x, y, w, h = box
                print (track_id)
                print(float(y))

                if float(y) <Valor_Y_Andar1:
                    print("Andar 1")
                    Botijao_Detecatado_Andar1 = True
                elif float(y) >Valor_Y_Andar1 and float(y) <Valor_Y_Andar2:
                    print("Andar 2")
                    Botijao_Detecatado_Andar2 = True
                elif float(y) >Valor_Y_Andar2 and float(y) <Valor_Y_Andar3:
                    print("Andar 3")
                    Botijao_Detecatado_Andar3 = True
        except:
            pass
        
    ##################################### CONTAGEM DE CONFIRMACOES

    #Validar se botijao está no andar 1 casao a central solicitou análise no andar 1
    if Botijao_Detecatado_Andar1 == True and Central_Identificar_Botijao_Andar1 ==True:
        Numero_Confirmacoes_Andar1 = Numero_Confirmacoes_Andar1+1
    else:
        Numero_Confirmacoes_Andar1 = Numero_Confirmacoes_Andar1-1

    #Validar se botijao está no andar 2 casao a central solicitou análise no andar 2
        
    if Botijao_Detecatado_Andar2 == True and Central_Identificar_Botijao_Andar2 == True:
        Numero_Confirmacoes_Andar2 = Numero_Confirmacoes_Andar1+2
    else:
        print("Descontando")
        print(Numero_Confirmacoes_Andar2)
        Numero_Confirmacoes_Andar2 = Numero_Confirmacoes_Andar2-1

    #Validar se botijao está no andar 3 casao a central solicitou análise no andar 3
    if Botijao_Detecatado_Andar3 == True and Central_Identificar_Botijao_Andar3 == True:
        Numero_Confirmacoes_Andar3 = Numero_Confirmacoes_Andar3+1
    else:
        Numero_Confirmacoes_Andar3 = Numero_Confirmacoes_Andar3-1

   ##################################### CONFORME DEMANDA DA CENTRAL, IRÁ ENVIAR SE BOTIJÃO FOI DETECTADO OU NÃO
    #confirmar botijao no andar 1
    if Central_Identificar_Botijao_Andar1 == True:
        if Numero_Confirmacoes_Andar1 > Numero_Confirmacoes:
            Central_Botijao_Detectado_Andar1 = True
        elif Numero_Confirmacoes_Andar1<Numero_Nao_Confirmacoes:
            Central_Botijao_Nao_Detectado_Andar1 = True
    else: #zera o contado de confirmacoes
        Numero_Confirmacoes_Andar1 = 0

    print(Central_Identificar_Botijao_Andar2) 
    print (Numero_Confirmacoes_Andar2)
    #confirmar botijao no andar 2
    if Central_Identificar_Botijao_Andar2 == True:
        if Numero_Confirmacoes_Andar2 > Numero_Confirmacoes:
            Central_Botijao_Detectado_Andar2 = True
        elif Numero_Confirmacoes_Andar2<Numero_Nao_Confirmacoes:
            Central_Botijao_Nao_Detectado_Andar2 = True
    else: #zera o contado de confirmacoes
        Numero_Confirmacoes_Andar2 = 0
            
    #confirmar botijao no andar 3
    if Central_Identificar_Botijao_Andar3 == True:
        if Numero_Confirmacoes_Andar3 > Numero_Confirmacoes:
            Central_Botijao_Detectado_Andar3 = True
        elif Numero_Confirmacoes_Andar3<Numero_Nao_Confirmacoes:
            Central_Botijao_Nao_Detectado_Andar3 = True
    else: #zera o contado de confirmacoes
            Numero_Confirmacoes_Andar3 = 0

    #caso central não esteja enviando nenhum sinal solicitando informação, irá zerar as variáveis de envio
    if Central_Identificar_Botijao_Andar1 == False and Central_Identificar_Botijao_Andar2 == False and Central_Identificar_Botijao_Andar3 == False:
        Central_Botijao_Detectado_Andar1= False
        Central_Botijao_Detectado_Andar2= False
        Central_Botijao_Detectado_Andar3= False
        Central_Botijao_Nao_Detectado_Andar1= False
        Central_Botijao_Nao_Detectado_Andar2= False
        Central_Botijao_Nao_Detectado_Andar3= False


    cv2.imshow("Tela", img)

    k = cv2.waitKey(1)
    if k == ord('q'):
        break


cv2.destroyAllWindows()
print("desligando")
