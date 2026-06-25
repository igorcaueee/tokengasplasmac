const { app, BrowserWindow, ipcMain } = require('electron');
require('dotenv').config();
const axios = require("axios");
const multer = require("multer");
const mqtt = require('mqtt');
const express = require('express');
const bodyParser = require('body-parser');
const cors = require('cors');
const fs = require('fs');
const nodemailer = require('nodemailer');
const PORT = 3000;

const storage = multer.memoryStorage();
const upload = multer({ storage: storage });
let mainWindow;
let token = process.env.TOKEN;
let urlPix = `https://api.mercadopago.com/v1/payments/`;

// Criar um servidor Express apenas uma vez
const server = express();
server.use(bodyParser.json());
server.use(cors());

// Conectar ao broker MQTT local
const client = mqtt.connect('mqtt://localhost');
const topic = 'central/1';

// Rota que recebe uma imagem, converte para base64 e envia para o Google API
server.post("/image-analysis", upload.single("image"), async (req, res) => {

    // let responded = false;
    // let respondedExecuted = false;
    // const timeout = setTimeout(() => {
    //     if (!responded && !respondedExecuted) {
    //         client.publish(topic, "Aguarde mais um pouco\nAnalisando o Botijão........", { qos: 1 });
    //         console.log("Mensagem MQTT enviada: Tempo de resposta excedeu 15 segundos");
    //         respondedExecuted = true
    //     }
    // }, 5000);

  // Função para validar e padronizar o JSON retornado
const normalizeResponse = (data) => {
  let img = data;

  // Caso o JSON venha encapsulado em uma chave "CNH" ou outra, pegar o primeiro objeto
  if (typeof data === "object" && Object.keys(data).length === 1) {
    const firstKey = Object.keys(data)[0];
    if (typeof data[firstKey] === "object") {
      img = data[firstKey];
    }
  }

  return {
    status: img.status || "False",
  };
};

const BOTIJAO_PROMPT = "Atue como um sistema de visão computacional industrial de alta precisão para checkout da Liquigás. Sua tarefa é validar EXCLUSIVAMENTE botijões de gás de cozinha padrão P13 (13kg) ou P45 (45kg). \n CONTEXTO VISUAL: \n O botijão estará dentro de um cesto/grade metálica de transporte. Use as dimensões do cesto como referência de escala. \n REGRAS DE CLASSIFICAÇÃO: \n 1. CRITÉRIOS DE ACEITE (status: \"True\"): \n - Deve ser um botijão P13 ou P45 REAL. \n - O P13 deve ocupar quase toda a largura do cesto central (preenchimento lateral robusto). \n - Presença de aro superior (alça) de proteção largo e soldado, proporcional ao corpo cilíndrico. \n - Textura metálica com marcas de uso, pintura (azul, cinza/prateado ou amarelo) e desgaste real. \n 2. CRITÉRIOS DE REJEIÇÃO OBRIGATÓRIA (status: \"False\"): \n - LIQUINHO (P2/P5): Rejeite botijões pequenos. Identifique-os se houver muito espaço vazio nas laterais ou no topo do cesto. O Liquinho é visivelmente mais baixo e \"fino\" que o P13. \n - ACESSÓRIOS DE CAMPING: Se o botijão tiver um fogareiro ou bocal direto de rosca fina (comum em P2), rejeite. \n - SABOTAGEM: Brinquedos, miniaturas, fotos de botijões, desenhos ou cestos vazios. \n - OBSTRUÇÃO TOTAL: Se não for possível confirmar o tamanho P13 devido a obstruções severas. \n INSTRUÇÃO DE SAÍDA: \n Retorne estritamente um JSON PURO no formato: {\"status\": \"True\"} para P13/P45 ou {\"status\": \"False\"} para Liquinhos ou outros objetos. Não adicione explicações.";

const requestOpenRouterAPI = async (base64Image, mimetype, model) => {
  const response = await axios.post(
    'https://openrouter.ai/api/v1/chat/completions',
    {
      model,
      messages: [{
        role: 'user',
        content: [
          { type: 'text', text: BOTIJAO_PROMPT },
          { type: 'image_url', image_url: { url: `data:${mimetype};base64,${base64Image}` } }
        ]
      }],
      temperature: 0.0,
      max_tokens: 256,
    },
    {
      headers: {
        Authorization: `Bearer ${process.env.OPENROUTER_KEY}`,
        'Content-Type': 'application/json',
      },
      timeout: 15000,
    }
  );
  const text = response.data.choices[0]?.message?.content || '{}';
  const jsonText = text.replace(/```json\n?/g, '').replace(/```/g, '').trim();
  return JSON.parse(jsonText);
};

const sendFailureEmail = async (erros) => {
  const transporter = nodemailer.createTransport({
    service: 'gmail',
    auth: { user: process.env.EMAIL_USER, pass: process.env.EMAIL_PASS },
  });
  await transporter.sendMail({
    from: process.env.EMAIL_USER,
    to: process.env.EMAIL_TO,
    subject: '[GásPuro Totem] Falha total na validação de IA',
    text: `Todas as APIs de visão falharam em ${new Date().toISOString()}.\n\nErros:\n${erros.map((e, i) => `${i + 1}. ${e}`).join('\n')}`,
  });
};

    try {
    if (!req.file) {
      client.publish(topic, "Erro de captura.\nNenhuma imagem capturada", { qos: 1 });
      return res.status(400).json({ error: "Nenhuma imagem capturada" });
    }

    // Converte a imagem recebida para base64
    const base64Image = req.file.buffer.toString("base64");

    let parsedJson;
    const erros = [];
    let apiResponse;

    const orModel1 = process.env.OPENROUTER_MODEL_1 || 'nvidia/nemotron-nano-12b-v2-vl:free';
    const orModel2 = process.env.OPENROUTER_MODEL_2 || 'nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free';
    const orModel3 = process.env.OPENROUTER_MODEL_3 || 'google/gemma-4-31b-it:free';

    // Tentativa 1: OpenRouter modelo 1
    try {
      apiResponse = await requestOpenRouterAPI(base64Image, req.file.mimetype, orModel1);
    } catch (e1) {
      erros.push(`OpenRouter ${orModel1}: ${e1.message}`);
      console.error(`[IA] ${orModel1} falhou, tentando ${orModel2}...`);

      // Tentativa 2: OpenRouter modelo 2
      try {
        apiResponse = await requestOpenRouterAPI(base64Image, req.file.mimetype, orModel2);
      } catch (e2) {
        erros.push(`OpenRouter ${orModel2}: ${e2.message}`);
        console.error(`[IA] ${orModel2} falhou, tentando ${orModel3}...`);

        // Tentativa 3: OpenRouter modelo 3
        try {
          apiResponse = await requestOpenRouterAPI(base64Image, req.file.mimetype, orModel3);
        } catch (e3) {
          erros.push(`OpenRouter ${orModel3}: ${e3.message}`);
          console.error('[IA] Todas as APIs falharam. Enviando e-mail de alerta...');
          sendFailureEmail(erros).catch(emailErr =>
            console.error('[IA] Falha ao enviar e-mail de alerta:', emailErr.message)
          );
          client.publish(topic, 'Erro de conexão.\nTodas as APIs de validação falharam. Equipe técnica notificada.', { qos: 1 });
          return res.status(500).json({ error: 'Todas as APIs de validação falharam. Equipe técnica notificada.' });
        }
      }
    }

    parsedJson = normalizeResponse(apiResponse);

    if (parsedJson.status === "True" || parsedJson.status === "False") {
      return res.json(parsedJson);
    }

    // Resposta com status inválido
    client.publish(topic, "Erro de processamento de Imagem.\nNão foi possível processar a imagem corretamente", { qos: 1 });
    res.status(400).json({ error: "Erro de processamento de Imagem. Não foi possível processar a imagem corretamente." });

  } catch (error) {
    console.error("Erro:", error);
    client.publish(topic, `Erro de conexão.\nOcorreu um erro ao gerar o conteúdo: ${error}`, { qos: 1 });
    res.status(500).json({ error: "Erro de conexão. Ocorreu um erro ao gerar o conteúdo" });
  }
});

// Criar uma rota para receber webhooks
server.post('/webhook', async (req, res) => {
    console.log("Webhook recebido:", req.body);

    const ip = req.headers['x-forwarded-for'] || req.socket.remoteAddress;

    console.log('IP --> ', ip)
 
   //  if (ip.includes("18.213.114.129")) {

    const stateValue = req.body.state;
    let status

    if ('action' in req.body) { // Verifica se a chave 'action' existe no objeto
        const action = req.body.action;
        const paymentId = req.body.data.id;

        if (action === "payment.updated") {
            try {
                const response = await fetch(`${urlPix}/${paymentId}`, {
                    method: "GET",
                    headers: { Authorization: `Bearer ${token}` }
                });

                if (!response.ok) throw new Error("Erro ao chamar a API");

                const data = await response.json();
                console.log(`Pagamento atualizado. ID: ${paymentId}`);

                // Publica a mensagem no MQTT com base no status da API
                const message = (data.status === 'approved') ? 'APPROVED' : data.status;
                client.publish(topic, message, { qos: 1 });

            } catch (error) {
                console.error("Erro na requisição:", error);
            }
        }
    } else if (stateValue) {

        //SUCESSO
        status = req.body.payment.state
        if (stateValue === 'FINISHED' && status.toUpperCase() === 'APPROVED') {
              client.publish(topic, status.toString().toUpperCase(), { qos: 1 });
        }
        //TRANSAÇÃO NÃO AUTORIZADA
         if (stateValue === 'FINISHED' && status.toUpperCase() === 'REJECTED') {
              client.publish(topic, status.toString().toUpperCase(), { qos: 1 });
        }
        //CANCELADO PELO USUARIO OU SISTEMA
            if (stateValue === 'CANCELED') {
              client.publish(topic, stateValue.toString(), { qos: 1 });
        }
        // Publica a mensagem com o estado recebido caso não seja um evento de pagamento
      
    }

  
        // } else {
        //     console.log('Webhook não Autorizado - Não é o Mercado Pago')
        // }
          res.status(200).send({ success: true, message: "Webhook recebido com sucesso!" });
});


server.listen(PORT, () => {
    console.log(`Servidor webhook rodando na porta ${PORT}`);
});

client.on('connect', () => {
    console.log('Conectado ao MQTT Broker');
    client.subscribe('central/1', (err) => {
        if (!err) {
            console.log('Inscrito no tópico central/1');
        }
    });
});

client.on('message', (topic, message) => {
    const msg = message.toString();
    console.log(`Recebido do MQTT: ${msg}`);

    // Envia a mensagem para o frontend (caso o app tenha sido iniciado)
    if (mainWindow) {
        mainWindow.webContents.send('mqtt-message', msg);
    }
});

app.whenReady().then(() => {
    mainWindow = new BrowserWindow({
        // width: 1920,
        // height: 1080,
          width: 800,
         height: 600,
        // fullscreen: true,
        // frame: false,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false
        }
    });

    mainWindow.loadFile('index.html');
});

// Evento de publicação via MQTT
ipcMain.on('mqtt-publish', (event, topic, message) => {
    client.publish(topic, message);
});

    //LISTA DE IPs MP
        // 100.24.202.16
        // 23.20.84.99
        // 34.236.9.110
        // 34.235.173.218
        // 34.236.26.249
        // 18.213.114.129
        // 54.88.218.97
        // 18.215.140.160
        // 18.206.34.84
        // 209.225.49.0–209.225.49.255
        // 216.33.197.0–216.33.197.255
        // 216.33.196.0–216.33.196.255
        // 63.128.82.0–63.128.82.255
        // 63.128.83.0–63.128.83.255
        // 63.128.94.0–63.128.94.255
