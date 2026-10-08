"""Assunto provável do texto (cartão "esta notícia parece tratar de...").

1) Se existir o modelo CTM treinado (backend/ctm_model_production.pkl + ctm_vocab_production.pkl)
   e as bibliotecas (torch, sentence-transformers, contextualized-topic-models), usa o CTM.
2) Caso contrário (ou se algo falhar), usa palavras-chave. A API nunca quebra por causa disso.

`categorizar` devolve (lista_de_assuntos, fonte).
"""
import io
import pickle
import re
from pathlib import Path

# nome -> (prefixos de palavras, palavras exatas)
CATEGORIAS = {
    "Política": (
        ["govern", "president", "ministr", "senad", "senador", "câmara", "deputad", "eleiç", "eleitor",
         "partid", "congresso", "planalto", "prefeit", "oposiç", "candidat", "polític", "legislativ"],
        ["voto", "votos", "lula", "bolsonaro", "pt", "pl"],
    ),
    "Justiça e segurança": (
        ["supremo", "tribunal", "justiça", "juiz", "juíz", "process", "condenad", "preso", "presa", "polícia",
         "delegad", "inquérito", "denúncia", "crime", "criminos", "ministério público", "habeas", "sentença",
         "investigaç", "operaç", "assassin", "homicíd"],
        ["stf", "stj", "tse", "mpf", "pf", "prisão"],
    ),
    "Economia": (
        ["inflaç", "juros", "econom", "mercado", "banco", "imposto", "tribut", "orçament", "desemprego",
         "salári", "preço", "fiscal", "déficit", "empresa", "receita", "investiment", "financ", "exporta", "importa"],
        ["pib", "selic", "dólar", "bolsa", "ibovespa"],
    ),
    "Saúde": (
        ["vacin", "saúde", "hospital", "doença", "vírus", "médic", "paciente", "internaç", "dengue", "remédio",
         "medicament", "tratament", "epidemi", "pandemi", "sanitár", "cirurgia"],
        ["sus", "covid", "anvisa", "oms"],
    ),
    "Meio ambiente": (
        ["desmat", "amazônia", "clima", "climát", "queimad", "ambiental", "poluiç", "aquecimento", "floresta",
         "emissões", "enchente", "inundaç", "biodivers", "ecológic"],
        ["seca", "chuvas", "ibama"],
    ),
    "Internacional": (
        ["estados unidos", "rússia", "ucrânia", "israel", "europ", "exterior", "sanç", "diplomát", "embaixad",
         "internacional", "estrangeir"],
        ["eua", "china", "gaza", "otan", "onu", "trump", "guerra", "irã"],
    ),
    "Tecnologia": (
        ["inteligência artificial", "algoritm", "internet", "redes sociais", "aplicativ", "tecnolog", "cibernétic",
         "hacker", "plataforma", "big tech", "digital", "desinformaç"],
        ["ia", "tiktok", "instagram", "whatsapp"],
    ),
    "Educação": (
        ["escola", "universidad", "alunos", "aluno", "professor", "ensino", "educaç", "estudante", "vestibular", "faculdade"],
        ["enem", "mec"],
    ),
    "Esportes": (
        ["campeonato", "futebol", "atleta", "olimp", "seleção", "técnico", "torneio", "partida"],
        ["gol", "gols", "copa", "time", "jogo", "jogos"],
    ),
    "Cultura e entretenimento": (
        ["filme", "cantor", "cantora", "música", "artista", "novela", "celebridade", "cinema", "show", "festival", "ator", "atriz"],
        ["série", "disco"],
    ),
}

_PADROES = {
    nome: [re.compile(r"\b" + re.escape(p)) for p in pref] + [re.compile(r"\b" + re.escape(e) + r"\b") for e in exatas]
    for nome, (pref, exatas) in CATEGORIAS.items()
}

MIN_PONTOS = 2  # palavras-chave diferentes necessárias para sugerir um assunto


# ---------------------------------------------------------------------------
# CTM (modelo não supervisionado treinado no notebook, 6 tópicos)
# Os nomes abaixo foram dados olhando as palavras de cada tópico e a conferência
# com as categorias da Folha. CONFIRA/AJUSTE se retreinar o modelo (a ordem muda!).
# None = tópico genérico demais, não mostra nada (cai nas palavras-chave).
# ---------------------------------------------------------------------------
NOMES_TOPICOS_CTM = {
    0: "Cultura e comportamento",   # anos, vida, filme, tempo
    1: "Economia e mercado",        # bilhões, economia, mercado, empresas, banco
    2: None,                        # vigilância, cidadania, comentário... (misto)
    3: "Política",                  # presidente, dilma, câmara, temer, lula, tribunal
    4: "Mundo e sociedade",         # país, governo, trump, polícia, síria
    5: "Esportes",                  # clube, copa, time, seleção, jogo
}
LIMIAR_CTM = 0.35            # probabilidade mínima do tópico principal
LIMIAR_CTM_SECUNDARIO = 0.25
MAX_CHARS_CTM = 3000
BASE = Path(__file__).resolve().parent.parent
ARQ_MODELO = BASE / "ctm_model_production.pkl"
ARQ_VOCAB = BASE / "ctm_vocab_production.pkl"
EMBEDDINGS = "distiluse-base-multilingual-cased-v1"

_ctm = {"tentou": False, "modelo": None, "tp": None}


def _limpar_para_bow(texto: str) -> str:
    """Mesma limpeza do treino (minúsculas, sem URL, só letras). O vocabulário fixo filtra o resto."""
    t = re.sub(r"http\S+|www\S+", " ", texto.lower())
    t = re.sub(r"[^a-zà-ÿ\s]", " ", t)
    return " ".join(w for w in t.split() if len(w) > 2)


def carregar_ctm() -> bool:
    """Tenta carregar o CTM uma única vez. Devolve True se está pronto para uso."""
    if _ctm["tentou"]:
        return _ctm["modelo"] is not None
    _ctm["tentou"] = True
    if not (ARQ_MODELO.exists() and ARQ_VOCAB.exists()):
        print("CTM: arquivos do modelo não encontrados; usando palavras-chave.")
        return False
    try:
        import torch
        from sklearn.feature_extraction.text import CountVectorizer
        from contextualized_topic_models.utils.data_preparation import TopicModelDataPreparation

        class _CPUUnpickler(pickle.Unpickler):
            # o modelo foi salvo no Colab com GPU: força os tensores para CPU
            def find_class(self, module, name):
                if module == "torch.storage" and name == "_load_from_bytes":
                    return lambda b: torch.load(io.BytesIO(b), map_location="cpu")
                return super().find_class(module, name)

        with open(ARQ_MODELO, "rb") as f:
            modelo = _CPUUnpickler(f).load()
        with open(ARQ_VOCAB, "rb") as f:
            vocab = [str(w) for w in pickle.load(f)]

        if hasattr(modelo, "USE_CUDA"):
            modelo.USE_CUDA = False
        if hasattr(modelo, "device"):
            modelo.device = "cpu"
        modelo.num_data_loader_workers = 0

        tp = TopicModelDataPreparation(EMBEDDINGS)
        tp.vectorizer = CountVectorizer(vocabulary=vocab)
        tp.vocab = vocab
        tp.id2token = {i: w for i, w in enumerate(vocab)}

        _ctm["modelo"], _ctm["tp"] = modelo, tp
        print("CTM carregado.")
        return True
    except Exception as e:  # qualquer problema: segue com palavras-chave
        print("CTM indisponível, usando palavras-chave:", repr(e))
        return False


def _categorizar_ctm(texto: str) -> list[str] | None:
    if not carregar_ctm():
        return None
    try:
        trecho = texto[:MAX_CHARS_CTM]
        ds = _ctm["tp"].transform(text_for_contextual=[trecho], text_for_bow=[_limpar_para_bow(trecho)])
        dist = _ctm["modelo"].get_doc_topic_distribution(ds, n_samples=10)[0]
        ordem = sorted(range(len(dist)), key=lambda i: dist[i], reverse=True)
        if dist[ordem[0]] < LIMIAR_CTM or NOMES_TOPICOS_CTM.get(ordem[0]) is None:
            return None
        saida = [NOMES_TOPICOS_CTM[ordem[0]]]
        seg = ordem[1]
        if dist[seg] >= LIMIAR_CTM_SECUNDARIO and NOMES_TOPICOS_CTM.get(seg):
            saida.append(NOMES_TOPICOS_CTM[seg])
        return saida
    except Exception as e:
        print("Falha na inferência do CTM:", repr(e))
        return None


def categorizar(texto: str) -> tuple[list[str], str]:
    """(assuntos, fonte) onde fonte é 'ctm' ou 'palavras-chave'."""
    via_ctm = _categorizar_ctm(texto)
    if via_ctm:
        return via_ctm, "ctm"
    return _categorizar_palavras(texto), "palavras-chave"


def _categorizar_palavras(texto: str, maximo: int = 2) -> list[str]:
    t = texto.lower()
    pontos = {n: sum(1 for p in pads if p.search(t)) for n, pads in _PADROES.items()}
    ordem = sorted(((p, n) for n, p in pontos.items() if p >= MIN_PONTOS), reverse=True)
    if not ordem:
        return []
    melhor = ordem[0][0]
    # só inclui a segunda categoria se for quase tão forte quanto a primeira
    return [n for p, n in ordem[:maximo] if p >= max(MIN_PONTOS, 0.6 * melhor)]
