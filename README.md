
# check.AI — Detector de Claims

> Cole uma notícia (ou o link de um post/reel do Instagram) e veja **quais frases trazem afirmações que podem ser checadas**. Clique em uma frase destacada para receber perguntas para pensar, fontes encontradas e dicas de como verificar por conta própria.

**Equipe Octopus** — Jhenyfer da Silva Souza, Lucas Anand Mazotti Ferretti, Tárcio A. C. Quissanga, Gabriel Passarela Silva, Matheus Vasconcellos da Silva, Vitória Pereira Bagatin.

> ⚠️ O check.AI **não diz se uma informação é verdadeira ou falsa**. Ele aponta o que vale checar e estimula o pensamento crítico; a conclusão é de quem lê.

---

## O que o check.AI faz

- **Detecta claims:** divide o texto em sentenças e usa um classificador de machine learning (Naive Bayes + TF-IDF) para marcar as que são afirmações verificáveis (*claims*).
- **Apoia o pensamento crítico:** ao clicar em uma claim, mostra o tipo de afirmação, perguntas para refletir (ordenadas por prioridade), fontes encontradas na web e passos para checar.
- **Mostra o assunto provável:** um cartão indica sobre o que a notícia parece tratar (ex.: "Política", "Economia"), usando um modelo de tópicos não supervisionado (CTM) ou, se ele não estiver disponível, palavras-chave.
- **Aceita texto ou link do Instagram:** para links, a legenda do post/reel é extraída automaticamente.
- **Interface:** abas *Link* / *Texto*, contador de caracteres, botão **Apagar tudo**, cursor em forma de lupa sobre as claims e histórico das análises no navegador (`localStorage`).

## Como funciona

```
Navegador (Visual/)                         API FastAPI (backend/)
┌────────────────────┐   POST /api/analisar  ┌───────────────────────────────────────┐
│ texto ou link      │ ────────────────────► │ 1. (link) extrai legenda – instaloader │
│                    │                       │ 2. segmenta sentenças (spaCy + regras) │
│ frases destacadas  │ ◄──────────────────── │ 3. resolve pronomes (correferência)    │
│ + cartão de assunto│   sentenças + classe  │ 4. 5 features + TF-IDF → Naive Bayes   │
│                    │   + assunto           │ 5. regras ajustam casos de dúvida      │
│                    │                       │ 6. assunto (CTM ou palavras-chave)     │
│ clique em claim    │   POST /api/verificar │                                        │
│                    │ ────────────────────► │ busca na web (DuckDuckGo) + regras e   │
│ cartão de checagem │ ◄──────────────────── │ templates de perguntas (sem LLM)       │
└────────────────────┘                       └───────────────────────────────────────┘
```

### Os modelos

**1. Classificador de claims (supervisionado)** — `backend/modelo_pipeline_completo.pkl`

| Item | Configuração |
|---|---|
| Algoritmo | `MultinomialNB(alpha=2.0)` |
| Texto | `TfidfVectorizer(max_df=0.95, min_df=2, ngram_range=(1,2), strip_accents='unicode')` — vocabulário de 7.803 termos |
| Features numéricas | `qtd_palavras`, `densidade_entidades`, `densidade_verbos`, `tem_numero`, `e_pergunta` (reescaladas com `MinMaxScaler`) |
| Entrada do modelo | TF-IDF concatenado às 5 features |
| Dados | 2.174 sentenças da Folha de S. Paulo (dataset *scrapy_folha*), rotuladas à mão (≈ 50% claim / 50% não claim); split 70/15/15, `random_state=42` |
| Desempenho no teste | acurácia ≈ 0,70 · F1 ≈ 0,69 · ROC-AUC ≈ 0,78 |

Após o modelo, `main.py` aplica regras de ajuste: perguntas e frases com menos de 4 palavras viram *não claim*; frases com probabilidade ≥ 0,30, ≥ 5 palavras e número ou verbo de atribuição ("disse", "segundo"…) viram *claim*.

**2. Modelo de tópicos (não supervisionado)** — CombinedTM (*Contextualized Topic Models*)

SBERT `distiluse-base-multilingual-cased-v1` (512 dimensões) + bag-of-words (5.000 termos), 6 tópicos, 20 épocas, treinado em notícias da Folha. Os nomes dos tópicos foram atribuídos manualmente; o tópico 2 não ficou interpretável e é ocultado.

**3. Pré-processamento (spaCy `pt_core_news_lg`)**

- **Segmentação própria:** o parser foi removido e substituído por regras determinísticas (pontuação final, 129 abreviações, pares de aspas/parênteses balanceados).
- **Correferência:** pronomes (ele/ela/eles/elas, este/esse/aquele…) são trocados pelo antecedente mais provável, com pontuação por função sintática, distância, animação do verbo e similaridade de vetores. Na dúvida, o pronome original é mantido.

**4. Cartão de checagem (sem LLM)**

Entidades (PER/ORG/LOC) são extraídas da frase, as características da afirmação (entidade, atribuição anônima, número, previsão, opinião, fato) definem o tipo e as perguntas, e as fontes vêm de uma busca no DuckDuckGo (região Brasil), classificadas pela relação com a claim e sinalizadas se forem fontes primárias ou redes sociais.

## Estrutura do repositório

```
projeto finaL/
├── Visual/                          # Front-end (HTML/CSS/JS puro)
│   ├── index.html                   # Página
│   ├── style.css, rag.css           # Estilos
│   ├── script.js                    # Abas, chamadas à API, renderização, histórico
│   └── polvo.js / polvo.css         # Animação do polvo e cursor de lupa
└── backend/                         # API em FastAPI
    ├── app/
    │   ├── main.py                  # Endpoints, regras de ajuste e orquestração
    │   ├── nlp_pipeline.py          # Segmentação, correferência e features (spaCy)
    │   ├── classificador.py         # Carrega e executa o pipeline TF-IDF + Naive Bayes
    │   ├── criticidade.py           # Tipos de afirmação, perguntas, alertas e fontes
    │   ├── categoria.py             # Assunto provável (CTM + palavras-chave)
    │   └── instagram.py             # Extração da legenda de posts/reels
    ├── modelo_pipeline_completo.pkl # Classificador de claims (scikit-learn 1.6.1)
    ├── tp_preparation.pkl           # Preparação do CTM
    ├── ctm_model_production.pkl     # (opcional) modelo CTM treinado
    ├── ctm_vocab_production.pkl     # (opcional) vocabulário do CTM
    ├── requirements.txt
    ├── requirements-ctm.txt         # (opcional) dependências do CTM
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

A API sobe em `http://localhost:7860` (documentação interativa em `/docs`). A primeira inicialização é lenta porque o spaCy carrega dois pipelines.

> Use `scikit-learn==1.6.1` (já fixado no `requirements.txt`): o classificador foi salvo nessa versão e outras podem gerar avisos ou erros ao carregar o `.pkl`.

### 2. Front-end

Abra `projeto finaL/Visual/index.html` no navegador (ou use a extensão *Live Server* do VS Code). O front-end chama `http://localhost:7860`; para publicar, troque esse endereço em `Visual/script.js` pelo da API no ar.

### 3. (Opcional) Modelo de tópicos CTM

```bash
pip install -r requirements-ctm.txt   # torch (CPU), sentence-transformers, contextualized-topic-models
```

Coloque `ctm_model_production.pkl` e `ctm_vocab_production.pkl` em `backend/`. Ao iniciar, o terminal mostra `CTM carregado.` quando está ativo. Sem os arquivos ou as bibliotecas, a API usa as categorias por palavras-chave automaticamente (o cartão indica a fonte usada).

### Docker / Hugging Face Spaces

```bash
cd "projeto finaL/backend"
docker build -t checkai .
docker run -p 7860:7860 checkai
```

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

- **Back-end:** Python, FastAPI, spaCy (`pt_core_news_lg`), scikit-learn, pandas, scipy, DuckDuckGo Search (`ddgs`), instaloader.
- **Modelo de tópicos:** CombinedTM com embeddings `distiluse-base-multilingual-cased-v1`.
- **Front-end:** HTML, CSS e JavaScript puros.
- **Deploy do back-end:** Docker (Hugging Face Spaces, porta 7860).

## Limitações conhecidas

- O classificador acerta cerca de 7 em cada 10 frases: é um **apoio**, não um árbitro. Foi treinado só com notícias da Folha; em legendas de redes sociais o desempenho pode ser menor.
- O dataset é pequeno (2.174 frases), tem frases duplicadas e foi rotulado sem medida formal de concordância entre anotadores.
- A segmentação pode errar com muitas abreviações, aspas, apóstrofos (ex.: *O'Connell*) ou texto sem pontuação, o que afeta a detecção.
- `tem_numero` marca qualquer dígito (não distingue data, valor ou porcentagem).
- A busca na web traz o que o DuckDuckGo devolve; a ferramenta descreve as fontes, mas **não verifica a veracidade**.
- A extração de legendas do Instagram depende de o post ser público e de a plataforma permitir o acesso; se falhar, cole o texto manualmente.
- Os nomes dos tópicos do CTM foram atribuídos manualmente e precisam ser revistos se o modelo for retreinado.

## Ética e privacidade

O texto enviado é processado pela API e a frase clicada é enviada a um mecanismo de busca externo. O histórico fica apenas no navegador do usuário. A ferramenta não classifica veracidade nem avalia veículos ou pessoas.
