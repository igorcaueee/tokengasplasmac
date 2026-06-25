// Teste standalone do fallback OpenRouter
// Uso: node test_openrouter.js [caminho-da-imagem]
// Exemplo: node test_openrouter.js foto_capturada_1.jpg

require('dotenv').config();
const axios = require('axios');
const fs = require('fs');
const path = require('path');

const BOTIJAO_PROMPT = "Atue como um sistema de visão computacional industrial de alta precisão para checkout da Liquigás. Sua tarefa é validar EXCLUSIVAMENTE botijões de gás de cozinha padrão P13 (13kg) ou P45 (45kg). \n CONTEXTO VISUAL: \n O botijão estará dentro de um cesto/grade metálica de transporte. Use as dimensões do cesto como referência de escala. \n REGRAS DE CLASSIFICAÇÃO: \n 1. CRITÉRIOS DE ACEITE (status: \"True\"): \n - Deve ser um botijão P13 ou P45 REAL. \n - O P13 deve ocupar quase toda a largura do cesto central (preenchimento lateral robusto). \n - Presença de aro superior (alça) de proteção largo e soldado, proporcional ao corpo cilíndrico. \n - Textura metálica com marcas de uso, pintura (azul, cinza/prateado ou amarelo) e desgaste real. \n 2. CRITÉRIOS DE REJEIÇÃO OBRIGATÓRIA (status: \"False\"): \n - LIQUINHO (P2/P5): Rejeite botijões pequenos. Identifique-os se houver muito espaço vazio nas laterais ou no topo do cesto. O Liquinho é visivelmente mais baixo e \"fino\" que o P13. \n - ACESSÓRIOS DE CAMPING: Se o botijão tiver um fogareiro ou bocal direto de rosca fina (comum em P2), rejeite. \n - SABOTAGEM: Brinquedos, miniaturas, fotos de botijões, desenhos ou cestos vazios. \n - OBSTRUÇÃO TOTAL: Se não for possível confirmar o tamanho P13 devido a obstruções severas. \n INSTRUÇÃO DE SAÍDA: \n Retorne estritamente um JSON PURO no formato: {\"status\": \"True\"} para P13/P45 ou {\"status\": \"False\"} para Liquinhos ou outros objetos. Não adicione explicações.";

const imagePath = process.argv[2] || 'foto_capturada_1.jpg';

async function testModel(base64Image, model) {
  console.log(`\n--- Testando modelo: ${model} ---`);
  const start = Date.now();
  try {
    const response = await axios.post(
      'https://openrouter.ai/api/v1/chat/completions',
      {
        model,
        messages: [{
          role: 'user',
          content: [
            { type: 'text', text: BOTIJAO_PROMPT },
            { type: 'image_url', image_url: { url: `data:image/jpeg;base64,${base64Image}` } }
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
        timeout: 30000,
      }
    );
    const elapsed = Date.now() - start;
    const text = response.data.choices[0]?.message?.content || '{}';
    const jsonText = text.replace(/```json\n?/g, '').replace(/```/g, '').trim();
    const result = JSON.parse(jsonText);
    console.log(`✓ OK (${elapsed}ms) → resposta: ${JSON.stringify(result)}`);
    return true;
  } catch (err) {
    const elapsed = Date.now() - start;
    const status = err.response?.status || 'sem resposta';
    const detail = err.response?.data ? JSON.stringify(err.response.data).slice(0, 200) : err.message;
    console.log(`✗ FALHOU (${elapsed}ms) → HTTP ${status}: ${detail}`);
    return false;
  }
}

async function main() {
  if (!process.env.OPENROUTER_KEY) {
    console.error('OPENROUTER_KEY não encontrada no .env');
    process.exit(1);
  }

  if (!fs.existsSync(imagePath)) {
    console.error(`Imagem não encontrada: ${imagePath}`);
    console.error('Uso: node test_openrouter.js <caminho-da-imagem>');
    process.exit(1);
  }

  const base64Image = fs.readFileSync(imagePath).toString('base64');
  console.log(`Imagem: ${path.resolve(imagePath)} (${(base64Image.length / 1024).toFixed(0)} KB base64)`);
  console.log(`Chave OpenRouter: ${process.env.OPENROUTER_KEY.slice(0, 20)}...`);

  const model1 = process.env.OPENROUTER_MODEL_1 || 'nvidia/nemotron-nano-12b-v2-vl:free';
  const model2 = process.env.OPENROUTER_MODEL_2 || 'nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free';
  const model3 = process.env.OPENROUTER_MODEL_3 || 'google/gemma-4-31b-it:free';

  await testModel(base64Image, model1);
  await testModel(base64Image, model2);
  await testModel(base64Image, model3);

  console.log('\nTeste finalizado.');
}

main();
