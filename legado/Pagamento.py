#import snap7.client as c
#from snap7.util import *
#from snap7.snap7types import *
import numbers
import time
import sys
import os
import requests 
 


#Pagamento -> Central
Pagamento_Funcionando=False #*****
Iniciar_Atendimento = False
Iniciado = False
Pagamento_Autorizado = False
Pagamento_Rejeitado = False


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


 # Função para enviar dados via API (webhook)
def send_data_to_webhook(data):
            url = "https://play.svix.com/in/e_SyMydAw43Ay25Ck5QQDUUomegq3/"
            try:
                response = requests.post(url, json=data)
                print(f"Status Code: {response.status_code}")
                print(f"Response Text: {response.text}")
                print(f"Response Headers: {response.headers}")
                if response.status_code == 200 or response.status_code == 204:
                    print("Dados enviados com sucesso!")
                else:
                    print(f"Erro ao enviar dados. Status Code: {response.status_code}, Response Text: {response.text}")
            except Exception as e:
                print(f"Erro ao enviar dados: {e}")



#def ReadMemory(plc,byte,datatype,db,bit=0,tam_st=0):
#    if datatype=='String':
#        result = plc.read_area(areas['DB'],db,byte,tam_st+2)
#        return get_string(result,0,tam_st+2)
#    else:
#        result = plc.read_area(areas['DB'],db,byte,datatype)
#    if datatype==S7WLBit:
#        return get_bool(result,0,bit)
#    elif datatype==S7WLByte or datatype==S7WLWord:
#        return get_int(result,0)
#    elif datatype==S7WLReal:
#        return get_real(result,0)
#    elif datatype==S7WLDWord:
#        return get_dword(result,0)
#    else:
#        return None

#def WriteMemory(plc,byte,datatype,db,bit,valor):
#    resultado = plc.read_area(areas['DB'],db,byte,datatype)
#    if datatype==S7WLBit:
#        set_bool(resultado,0,bit,valor)
#    elif datatype==S7WLByte or datatype==S7WLWord:
#        set_int(resultado,0,valor)
#    elif datatype==S7WLReal:
#        set_real(resultado,0,valor)
#    elif datatype==S7WLDWord:
#        set_dword(resultado,0,valor)
#    plc.write_area(areas["DB"],db,byte,resultado)

#abrir comunicação com o CLP
#try:
#    Central_Gas = c.Client()
#    Central_Gas.connect("192.168.0.1",0,1)
#    if Central_Gas.get_connected():
#        print("Conexão estabelecida com sucesso!")
Conexao_Estabelecida_CLP = True
        
#except Snap7Exception as e:
#    print(f"Erro de conexão: {e}")
#    Conexao_Estabelecida_CLP =False
#except Exception as e:
#    print(f"Erro inesperado: {e}")
#    Conexao_Estabelecida_CLP =False

        
while True:
                time.sleep(1)
        #dados para enviar    
    #    WriteMemory(Central_Gas,2,S7WLBit,2,0,Pagamento_Funcionando)
    #    WriteMemory(Central_Gas,2,S7WLBit,2,1,Iniciar_Atendimento)
    #    WriteMemory(Central_Gas,2,S7WLBit,2,2,Pagamento_Autorizado)
    #    WriteMemory(Central_Gas,2,S7WLBit,2,3,Pagamento_Rejeitado)

            
                #dados para Receber
                #Porta_Aberta_Andar1 = True 
                Porta_Aberta_Andar1 = False 
                #ReadMemory(Central_Gas,0,S7WLBit,2,0)
                Porta_Aberta_Andar2 = False
                #Porta_Aberta_Andar2 = True
                #ReadMemory(Central_Gas,0,S7WLBit,2,1)
                Porta_Aberta_Andar3 = False
                #Porta_Aberta_Andar3 = True
                #ReadMemory(Central_Gas,0,S7WLBit,2,2)

    #----------------- INICIO ---------------------------------------    
                if Porta_Aberta_Andar1 == True:
                    send_data_to_webhook({"status": "Feche a porta 1"})
                    print(f"Feche a porta 1")
                    continue

                if Porta_Aberta_Andar2 == True:
                    send_data_to_webhook({"status": "Feche a porta 2"})
                    print(f"Feche a porta 2")
                    continue

                if Porta_Aberta_Andar3 == True:
                    send_data_to_webhook({"status": "Feche a porta 3"})
                    print(f"Feche a porta 3")
                    continue

                if Porta_Aberta_Andar1 != True and Porta_Aberta_Andar2 != True and Porta_Aberta_Andar3 != True and Iniciado == False:
                    send_data_to_webhook({"status": "INICIAR"})
                    print("INICIAR")
                    #receber atualizacao do status de iniciar
                    Iniciar_Atendimento = True #//////////////////////////////////////////
                    #Iniciar_Atendimento = False
                    Iniciado = True
                    continue
        


   

        #------------------- INFORMAR PORTA PARA O USUARIO -----------------
                #Andar1_Destravado_InserirBotijao = True
                Andar1_Destravado_InserirBotijao = False
                #ReadMemory(Central_Gas,0,S7WLBit,2,3)
                Andar2_Destravado_InserirBotijao = False
                #Andar2_Destravado_InserirBotijao = True
                #ReadMemory(Central_Gas,0,S7WLBit,2,4)
                #Andar3_Destravado_InserirBotijao = False
                Andar3_Destravado_InserirBotijao = True
                #ReadMemory(Central_Gas,0,S7WLBit,2,5)

    
                    #recebe comando api de iniciado
                
                    #send_data_to_webhook({"status": Iniciado})
                if  Andar1_Destravado_InserirBotijao == True and Iniciado == True:
                            Iniciar_Atendimento = False
                            Analise_Disponivel = True
                            send_data_to_webhook({"status": "Insira o Botijão na Porta 1"})
                            print(f"Insira o Botijão na Porta 1")
                            continue

                if  Andar2_Destravado_InserirBotijao == True and Iniciado == True:
                            Iniciar_Atendimento = False
                            Analise_Disponivel = True
                            send_data_to_webhook({"status": "Insira o Botijão na Porta 2"})
                            print(f"Insira o Botijão na Porta 2")
                            continue

                if  Andar3_Destravado_InserirBotijao == True and Iniciado == True:
                            Iniciar_Atendimento = False
                            Analise_Disponivel = True
                            send_data_to_webhook({"status": "Insira o Botijão na Porta 3"})
                            print(f"Insira o Botijão na Porta 3")
                            #continue


        #------- ALERTA INATIVIDADE -------------------------------------

                #Alerta_Tempo_Inatividade = True
                Alerta_Tempo_Inatividade = False
                    #ReadMemory(Central_Gas,0,S7WLBit,2,6)

                if  Alerta_Tempo_Inatividade == True and Analise_Disponivel == True:
                    send_data_to_webhook({"status": "Botijão Não Detectado. Por favor, Insira o Botijão"})
                    print(f"Botijão Não Detectado. Por favor, Insira o Botijão")
                    time.sleep(5)
                    continue

                else:
                #----------  Analise de Botijao --------------------------------
                    Analisando_Botijao = True
                    #ReadMemory(Central_Gas,0,S7WLBit,2,7)
                if  Analisando_Botijao == True and Analise_Disponivel == True:     

                    send_data_to_webhook({"status": "Analisando o Botijão, Por favor, Aguarde........"})
                    print(f"Analisando o Botijão, Por favor, Aguarde........")

                Botijao_Aceito = True  
                #Botijao_Aceito = False  
                #ReadMemory(Central_Gas,1,S7WLBit,2,0)  


                if  Botijao_Aceito == True:     
                # print(f"Botijão Aceito")
                    send_data_to_webhook({"status": "Botijão Aceito - DISPARAR INTENCAO DE PAGAMENTO"})
                    print(f"Botijão Aceito - DISPARAR INTENCAO DE PAGAMENTO")

                if  Botijao_Aceito == False:
                    send_data_to_webhook({"status": "Botijão Rejeitado"})
                    print(f"Botijão Rejeitado")
                    Iniciar_Atendimento = True
                    Iniciado = False
                    #VOLTAR PARA INICIAR
                    continue

                   
                    
                    # COLOCAR O COMANDO QUE IRA VOLTAR PARA ANALISE DE ALGUMA PORTA ABERTA*******


                #Pagamento_Autorizado = True
                #------------ LOGICA BASE PAGAWMNTO ACEITO --------------
                # Recebe webhook/api de confirmacao
            

                if Pagamento_Autorizado == True:
                    send_data_to_webhook({"status": "Pagamento Aceito"})
                    print(f"Pagamento Aceito")
                    Iniciar_Atendimento = True
                    Iniciado = False
                else:
                    send_data_to_webhook({"status": "Pagamento Rejeitado, devolvendo o Botijão"})
                    print(f"Pagamento Rejeitado, devolvendo o Botijão")
                    Pagamento_Autorizado = False

                    

                     #----------- RESET ---------------------------------------
                    Iniciar_Atendimento = False
                    Iniciado = False

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

                    continue

                    # COMANDO PARA LIBERAR A PORTA PARA RETIRAR O BOTIJÃO PELO PAGAMENTO REJEITADO ******
                    # GERAR COMANDO PARA VOLTAR PARA O INICIO DO FLUXO

                Andar1_Destravado_RetirarBotijao = False
                #Andar1_Destravado_RetirarBotijao = True
                #ReadMemory(Central_Gas,1,S7WLBit,2,2)
                Andar2_Destravado_RetirarBotijao = True
                #Andar2_Destravado_RetirarBotijao = False
                #ReadMemory(Central_Gas,1,S7WLBit,2,3)
                Andar3_Destravado_RetirarBotijao = False
                #Andar3_Destravado_RetirarBotijao = True
                #ReadMemory(Central_Gas,1,S7WLBit,2,4)

                if   Andar1_Destravado_RetirarBotijao == True and Pagamento_Autorizado == True:
                    send_data_to_webhook({"status": "Retirar o Botijão na Porta 1"})
                    print(f"Retirar o Botijão na Porta 1")

                if   Andar2_Destravado_RetirarBotijao == True and Pagamento_Autorizado == True:
                    send_data_to_webhook({"status": "Retirar o Botijão na Porta 2"})
                    print(f"Retirar o Botijão na Porta 2")

                if   Andar3_Destravado_RetirarBotijao == True and Pagamento_Autorizado == True:
                    send_data_to_webhook({"status": "Retirar o Botijão na Porta 3"})
                    print(f"Retirar o Botijão na Porta 3")

                

                #----------- OUTROS ------------------------------------    
                Manutencao_Andamento =  True
                #ReadMemory(Central_Gas,1,S7WLBit,2,5)
                Central_Em_Alarme =  True
                #ReadMemory(Central_Gas,1,S7WLBit,2,6)
           

                #print(f"Status final " + {Porta_Aberta_Andar1} + {Porta_Aberta_Andar2} + {Porta_Aberta_Andar1})
                #send_data_to_webhook({"status": "Status final " + {Porta_Aberta_Andar1} + {Porta_Aberta_Andar2} + {Porta_Aberta_Andar1}})



