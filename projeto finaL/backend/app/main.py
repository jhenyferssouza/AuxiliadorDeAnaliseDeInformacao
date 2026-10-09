import re
from pathlib import Path
from typing import Optional

from ddgs import DDGS
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .classificador import Classificador
from .categoria import carregar_ctm, categorizar
from .criticidade import montar
from .instagram import obter_legenda_instagram
from .nlp_pipeline import analisar_texto, nlp_full


class VerificacaoEntrada(BaseModel):
    sentenca: str


MODEL_PATH = Path(__file__).resolve().parent.parent / "modelo_pipeline_completo.pkl"
modelo = Classificador(MODEL_PATH)

MAX_CHARS = 6000
MAX_SENTENCAS = 80

app = FastAPI(title="API de análise de sentenças")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- Regras que ajustam a decisão do modelo ----
ATRIBUICAO = re.compile(r"\b(afirm\w+|diss\w+|declar\w+|anunci\w+|revel\w+|divulg\w+|informou|informaram|"
                        r"segundo|de acordo com|aprov\w+|determin\w+|decidiu|decidiram|prendeu|prenderam|"
                        r"confirm\w+|admitiu|alegou|denunci\w+)\b", re.I)
DADO = re.compile(r"\d")


def classe_positiva(classes):
    if 1 in classes:
        return 1, next((c for c in classes if c != 1), 0)
    pos = next((c for c in classes if str(c).lower() in ("claim", "verdadeiro", "sim")), None)
    neg = next((c for c in classes if c != pos), None)
    return pos, neg


def ajustar_por_regras(sentenca, classe, p_claim, pos, neg):
    """Devolve a classe final. As regras só ajudam em casos de dúvida do modelo."""
    palavras = len(sentenca.split())
    # 1) perguntas e frases muito curtas nunca são claims
    if sentenca.strip().endswith("?") or palavras < 4:
        return neg
    # 2) se o modelo está em dúvida (>= 30% claim) e a frase tem número ou atribuição, vira claim
    if p_claim >= 0.30 and palavras >= 5 and (DADO.search(sentenca) or ATRIBUICAO.search(sentenca)):
        return pos
    return classe


class Entrada(BaseModel):
    url: Optional[str] = None    # link de post/reel do Instagram
    texto: Optional[str] = None  # ou o texto direto


@app.on_event("startup")
def _preparar():
    carregar_ctm()  # carrega o CTM uma vez


@app.get("/")
@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/analisar")
def analisar(e: Entrada):
    texto = (e.texto or "").strip()
    origem = "texto"

    if not texto and e.url:
        texto, status = obter_legenda_instagram(e.url)
        origem = "instagram"
        if texto is None:
            raise HTTPException(422, f"{status}. Cole o texto da legenda no campo de texto.")

    if not texto:
        raise HTTPException(400, "Envie 'url' ou 'texto'.")

    texto = texto[:MAX_CHARS]
    linhas = analisar_texto(texto)[:MAX_SENTENCAS]
    if not linhas:
        raise HTTPException(422, "Nenhuma sentença encontrada.")

    probas = modelo.proba(linhas)
    classes = modelo.classes

    pos, neg = classe_positiva(classes)
    resultado = []
    for l, p in zip(linhas, probas):
        i = int(p.argmax())
        classe_final = classes[i]
        if pos is not None and neg is not None:
            p_claim = float(p[classes.index(pos)])
            classe_final = ajustar_por_regras(l["sentenca"], classes[i], p_claim, pos, neg)
        resultado.append({
            "sentenca_original": l["sentenca_original"],
            "sentenca_corrigida": l["sentenca"],
            "classe": classe_final,
            "confianca": float(p[i]),
            "probabilidades": {str(c): float(x) for c, x in zip(classes, p)},
        })

    categorias, fonte_categoria = categorizar(texto)
    return {"origem": origem, "categorias": categorias, "fonte_categoria": fonte_categoria, "classes": classes, "total": len(resultado), "sentencas": resultado}


@app.post("/api/verificar")
def verificar_claim(entrada: VerificacaoEntrada):
    claim = entrada.sentenca.strip()[:1000]
    if not claim:
        raise HTTPException(400, "Sentença vazia.")

    # 1. Pesquisa na internet (retrieval)
    try:
        with DDGS() as ddgs:
            resultados = list(ddgs.text(claim, region="br-pt", max_results=8))
    except Exception as e:
        print("ERRO NA BUSCA:", e)
        raise HTTPException(502, "Falha ao pesquisar na internet. Tente novamente.")

    fontes = [r for r in resultados if r.get("href")]
    if not fontes:
        return {"sem_fontes": True}

    # 2. Apoio ao pensamento crítico por regras e templates 
    # Entidades (pessoas, organizações, lugares) para priorizar as perguntas
    entidades = [e.text for e in nlp_full(claim).ents if e.label_ in ("PER", "ORG", "LOC")]
    return montar(claim, fontes, entidades=entidades)
