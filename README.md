
# check.AI — Detector de Claims
# Equipe: 
Octopus
# Membros: 
Jhenyfer da Silva Souza, 
Lucas Anand Mazotti Ferretti, 
Tárcio A. C. Quissanga,
Gabriel Passarela Silva,
Matheus Vasconcellos da Silva,
Vitória Pereira Bagatin;

---

## O que o check.AI faz

- **Detecta claims:** divide o texto em sentenças e usa um modelo de machine learning para marcar as que são afirmações verificáveis (*claims*) e as que não são verificáveis(*Não-Claims*).
- **Apoia o pensamento crítico:** ao clicar em uma claim, mostra o tipo de afirmação, perguntas para refletir (ordenadas por prioridade), fontes encontradas na web e passos para checar. **A ferramenta não diz se a frase é verdadeira ou falsa** — a conclusão é de quem lê.
- **Mostra o assunto provável:** um cartão avisa sobre o que a notícia parece tratar (ex.: "Política", "Economia"), usando um modelo de tópicos não supervisionado (CTM) ou, se ele não estiver disponível, palavras-chave.
- **Aceita texto ou link do Instagram:** para links, a legenda do post/reel é extraída automaticamente.
- **Guarda histórico** das análises no navegador (`localStorage`).

## Como funciona (visão geral)

```
Navegador (Visual/)                         API FastAPI (backend/)
┌────────────────────┐   POST /api/analisar  ┌──────────────────────────────────────┐
│ texto ou link      │ ────────────────────► │ 1. (link) extrai legenda – instaloader│
│                    │                       │ 2. segmenta sentenças (spaCy)         │
│ frases destacadas  │ ◄──────────────────── │ 3. resolve pronomes (correferência)   │
│ + cartão de assunto│   sentenças + classe  │ 4. extrai features → classificador    │
│                    │   + assuntos          │ 5. regras ajustam casos de dúvida     │
│                    │                       │ 6. assunto (CTM ou palavras-chave)    │
│ clique em claim    │   POST /api/verificar │                                       │
│                    │ ────────────────────► │ busca na web (DuckDuckGo) + regras e  │
│ cartão de checagem │ ◄──────────────────── │ templates de perguntas (sem LLM)      │
└────────────────────┘                       └──────────────────────────────────────┘
```

## Estrutura do repositório

```
projeto finaL/
├── Visual/                         # Front-end (HTML/CSS/JS puro)
│   ├── index.html                  # Página
│   ├── style.css                   # Estilos
│   ├── script.js                   # Lógica: abas, chamadas à API, renderização, histórico
│   ├── polvo.js / polvo.css        # Animação do polvo e cursor de lupa nas claims
│   └── rag.css                     # Estilos do cartão de checagem
└── backend/                        # API em FastAPI
    ├── app/
    │   ├── main.py                 # Endpoints, regras de ajuste e orquestração
    │   ├── nlp_pipeline.py         # Segmentação, correferência e features (spaCy)
    │   ├── criticidade.py          # Tipos de afirmação, perguntas, alertas e fontes
    │   ├── categoria.py            # Assunto provável (CTM + palavras-chave)
    │   └── instagram.py            # Extração da legenda de posts/reels
    ├── modelo_pipeline_completo.pkl  # Classificador de claims (scikit-learn)
    ├── ctm_model_production.pkl      # (opcional) Modelo de tópicos CTM treinado
    ├── ctm_vocab_production.pkl      # (opcional) Vocabulário do CTM
    ├── requirements.txt
    ├── requirements-ctm.txt          # (opcional) dependências do CTM
    └── Dockerfile
```

## Como rodar localmente

### 1. Backend

Requer Python 3.11+.

```bash
cd "projeto finaL/backend"
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download pt_core_news_lg
uvicorn app.main:app --host 0.0.0.0 --port 7860
```

A API sobe em `http://localhost:7860` (documentação interativa em `/docs`).

### 2. Front-end

Abra `projeto finaL/Visual/index.html` no navegador (ou use a extensão *Live Server* do VS Code).
O front-end chama `http://localhost:7860`; para publicar, troque esse endereço em `Visual/script.js` pelo da API no ar.

### 3. (Opcional) Modelo de tópicos CTM

Para o cartão de assunto usar o modelo não supervisionado em vez de palavras-chave:

```bash
pip install -r requirements-ctm.txt   # torch (CPU), sentence-transformers, contextualized-topic-models
```

e coloque `ctm_model_production.pkl` e `ctm_vocab_production.pkl` em `backend/`. Ao iniciar, o terminal mostra `CTM carregado.` quando está ativo. Sem os arquivos ou as bibliotecas, a API usa palavras-chave automaticamente.

## API

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/health` | Verifica se a API está no ar |
| `POST` | `/api/analisar` | Recebe `{ "texto": "..." }` ou `{ "url": "..." }` e devolve as sentenças classificadas, o assunto e a origem |
| `POST` | `/api/verificar` | Recebe `{ "sentenca": "..." }` e devolve o cartão de checagem (tipo, perguntas, alertas, fontes) |

Exemplo de resposta de `/api/analisar` (resumido):

```json
{
  "origem": "texto",
  "categorias": ["Política"],
  "fonte_categoria": "ctm",
  "sentencas": [
    { "sentenca_corrigida": "…", "classe": 1, "confianca": 0.87 }
  ]
}
```

Limites: texto de até 5000 caracteres no site (6000 na API) e 80 sentenças por análise.

## Tecnologias

- **Back-end:** Python, FastAPI, spaCy (`pt_core_news_lg`), scikit-learn, pandas, DuckDuckGo Search (`ddgs`), instaloader.
- **Modelo de tópicos:** Contextualized Topic Model (CombinedTM) com embeddings `distiluse-base-multilingual-cased-v1`, treinado em notícias da Folha (6 tópicos).
- **Front-end:** HTML, CSS e JavaScript puros.
- **Deploy do back-end:** Docker (Hugging Face Spaces, porta 7860).

## Limitações conhecidas

- A segmentação de sentenças pode errar em textos com muitas abreviações, aspas ou formatação irregular, o que afeta a detecção de claims.
- O classificador é estatístico: pode errar. As regras extras (`main.py`) só ajudam em casos de dúvida.
- A busca na web traz o que o DuckDuckGo devolve; a ferramenta descreve as fontes, mas **não verifica a veracidade**.
- A extração de legendas do Instagram depende de o post ser público e de a plataforma permitir o acesso; se falhar, cole o texto manualmente.
- Os nomes dos tópicos do CTM foram atribuídos manualmente e precisam ser revistos se o modelo for retreinado.
