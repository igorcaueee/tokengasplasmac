#!/bin/bash

exec > /home/raspgas1/CLP/logs_execucao.log 2>&1

cd "$(dirname "$0")"  # Garante que o script rode na pasta correta



# Ativa o ambiente virtual do Python (se necessário)

source myenv/bin/activate  # Descomente se estiver usando um venv



#python Programa_AI_Detectar_Botijao.py &

#sleep 2

#python teste_clp.py & 

#python Pagamento_MQTT.py &

python Pagamento_IA.py &

sleep 2



npx electron . --no-sandbox

sleep 5

#echo "Script rodou em $(date)" >> /home/raspgas1/CLP/totem_boot_log.txt

#nohup /usr/local/bin/ngrok start --all --config /home/raspgas1/.config/ngrok/ngrok.yml > ngrok.log 2>&1 &

./ngrok.sh &
