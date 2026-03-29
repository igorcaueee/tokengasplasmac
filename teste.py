from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import requests
import time
from threading import Timer
from ultralytics import YOLO
import matplotlib.image as mpimg

app = FastAPI()
model = YOLO("treinando_yolov8-main.rar")
#model = YOLO("C:/Users/dschauren/Downloads/treinando_yolov8-main/treinando_yolov8-main/runs/detect/train/weights/best.pt")

# Variáveis globais de estado
estado = {
    "Portas_Aberta_Andar1": 0,
    "Portas_Aberta_Andar2": 0,
    "Portas_Aberta_Andar3": 0,
    "Iniciar_Atendimento": 0,
    "Analisar_Andar1": 0,
    "Analisar_Andar2": 0,
    "Analisar_Andar3": 0
}

# Webhook da aplicação externa (modifique com sua URL real)
WEBHOOK_URL = "https://sua-aplicacao.com/webhook"

# Modelo para receber dados da API
class DadosEntrada(BaseModel):
    andar: int
    iniciar: bool = False
    analisar: bool = False

# Função para enviar dados ao webhook
def enviar_webhook(payload: dict):
    try:
        requests.post(WEBHOOK_URL, json=payload)
    except Exception as e:
        print(f"Erro ao enviar webhook: {e}")

# Função para análise com timeout e webhook
def analisar_botijao(andar: int):
    andar_key = f"Analisar_Andar{andar}"
    estado[andar_key] = 1
    enviar_webhook({"evento": "analise_iniciada", "andar": andar})

    imagem = f"Simulacao_Andar{andar}.jpg"
    img = mpimg.imread(imagem)
    results = model.track(img)

    botijao_detectado = any(result.boxes for result in results)
    
    if botijao_detectado:
        enviar_webhook({"evento": "botijao_detectado", "andar": andar})
    else:
        enviar_webhook({"evento": "botijao_nao_detectado", "andar": andar})

    estado[andar_key] = 0

# Função para verificar portas abertas antes de iniciar atendimento
def verificar_portas():
    return all(estado[f"Portas_Aberta_Andar{i}"] == 0 for i in range(1, 4))

@app.post("/iniciar")
def iniciar_atendimento(dados: DadosEntrada, background_tasks: BackgroundTasks):
    if not verificar_portas():
        raise HTTPException(status_code=400, detail="Por favor, feche todas as portas antes de iniciar.")

    if dados.iniciar:
        estado["Iniciar_Atendimento"] = 1
        enviar_webhook({"evento": "atendimento_iniciado", "andar": dados.andar})
        background_tasks.add_task(analisar_botijao, dados.andar)
        return {"status": "Atendimento iniciado e análise em andamento."}
    return {"status": "Nenhuma ação iniciada."}

@app.post("/atualizar_porta/{andar}/{status}")
def atualizar_porta(andar: int, status: int):
    if andar not in range(1, 4):
        raise HTTPException(status_code=400, detail="Andar inválido.")

    estado[f"Portas_Aberta_Andar{andar}"] = status
    enviar_webhook({"evento": "status_porta_alterado", "andar": andar, "status": status})
    return {"status": "Status da porta atualizado."}

@app.get("/status")
def obter_status():
    return estado
