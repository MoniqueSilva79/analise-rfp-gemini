# 📑 Analisador de RFP para Pré-Vendas (Gemini + Vertex AI)

Ferramenta que lê um edital ou RFP (PDF, TXT ou Markdown) e, em poucos segundos, entrega ao time de pré-vendas:

- **Matriz de conformidade** (`matriz_conformidade.csv`) com todos os requisitos, já separados em obrigatório/desejável e por área
- **Resumo executivo** (`resumo_rfp.md`) com prazos, critérios de julgamento, riscos e perguntas de esclarecimento
- **Nota de Go/No-Go** de 0 a 100 para apoiar a decisão de participar ou não

## 🎯 Problema que resolve
Uma RFP de telecom ou cloud costuma ter dezenas de páginas e um prazo curto. Antes de escrever uma linha da proposta, o time precisa ler tudo, montar a matriz de requisitos, achar as multas e decidir se vale a pena participar. Esse trabalho inicial pode levar dias. Aqui ele vira um primeiro rascunho em minutos, que o especialista revisa.

## 🏗️ Fluxo
```
RFP (PDF/TXT/MD) ──► Gemini no Vertex AI (lê o PDF direto, saída JSON com schema Pydantic)
                         │ cliente · objeto · prazos · requisitos · critérios · riscos · perguntas
                         ▼
                Regras de Go/No-Go (código) ──► matriz_conformidade.csv + resumo_rfp.md
```

## ⚖️ Como a nota de Go/No-Go é calculada
A nota começa em 100 e é descontada por:
| Fator | Desconto |
|---|---|
| Cada risco alto / médio / baixo | 15 / 8 / 3 pontos |
| Cada requisito obrigatório acima de 15 | 1 ponto |
| Julgamento só por menor preço | 10 pontos |

**≥ 70: GO · 50–69: avaliar com a diretoria · < 50: NO-GO.** Os pesos ficam na função `nota_go_no_go()` e devem ser ajustados para a realidade de cada empresa. A IA extrai os fatos, e a régua de decisão continua com o negócio.

## 🧰 Tecnologias
Python · Google Gen AI SDK (`google-genai`) · Gemini no Vertex AI (entrada multimodal em PDF) · Pydantic

## 🚀 Como rodar
```bash
git clone https://github.com/MoniqueSilva79/analise-rfp-gemini.git
cd analise-rfp-gemini
pip install -r requirements.txt

gcloud auth application-default login
export GOOGLE_CLOUD_PROJECT=seu-projeto
export GOOGLE_CLOUD_LOCATION=us-central1

python analisar_rfp.py exemplo/rfp_exemplo.md     # RFP fictícia incluída no repositório
python analisar_rfp.py meu_edital.pdf --saida resultado/
```

## 📂 RFP de exemplo
`exemplo/rfp_exemplo.md` é uma RFP **fictícia** de uma cooperativa de crédito pedindo Teams Phone, troncos SIP e contact center omnicanal, com POC eliminatória e multas por indisponibilidade. É um cenário típico do mercado financeiro brasileiro.

## 🔒 Cuidados
- RFPs reais costumam ter cláusula de confidencialidade: use um projeto do Google Cloud da sua empresa e confira a política interna antes de enviar documentos
- A saída é um **rascunho**: o especialista sempre revisa requisitos e riscos antes da decisão

## 🗺️ Próximos passos
- [ ] Sugerir resposta para cada requisito com base em um catálogo de produtos (RAG)
- [ ] Interface web com Streamlit para arrastar o PDF
- [ ] Exportar a matriz direto para Google Sheets

---
Projeto autoral de **Monique da Silva Cruz**, criado a partir da experiência com RFPs e propostas complexas em pré-vendas de telecom e cloud. Exemplos oficiais do Vertex AI usados como referência de estudo: [GoogleCloudPlatform/vertex-ai-samples](https://github.com/GoogleCloudPlatform/vertex-ai-samples).
