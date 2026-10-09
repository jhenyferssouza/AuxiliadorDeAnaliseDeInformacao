"""Apoio ao pensamento crítico sem LLM: regras + templates + sinais da busca.

Nada aqui diz se uma afirmação é verdadeira ou falsa. O módulo classifica o tipo
da frase, devolve perguntas e passos de checagem, e descreve com neutralidade
o que os resultados da busca mostram (domínio, número citado, fonte primária).
"""
import re
from urllib.parse import urlparse

# Domínios que costumam hospedar documentos primários (órgãos, estudos, leis)
PRIMARIAS = ("gov.br", "jus.br", "leg.br", "mp.br", "edu.br", "scielo.br", "doi.org", "who.int", "un.org")
# Redes sociais: repetem informação sem checagem
REDES = ("instagram.com", "facebook.com", "x.com", "twitter.com", "tiktok.com", "youtube.com", "kwai.com")


def numeros(s: str) -> list[str]:
    return [n.strip() for n in re.findall(r"\d+(?:[.,]\d+)?\s?%?", s)]


# ORDEM DE PRIORIDADE das características (a primeira da lista vem primeiro).
# Para mudar a prioridade, basta reordenar esta lista.
PRIORIDADE = [
    "entidade",
    "atribuicao_a_fontes_anonimas",
    "dado_estatistico",
    "previsao_ou_promessa",
    "opiniao_ou_interpretacao",
]
# Quantas perguntas/itens vêm da característica principal e da secundária
N_PRINCIPAL = 2
N_SECUNDARIA = 1


def caracteristicas(s: str, entidades: list[str] | None = None) -> list[str]:
    """Todas as características da frase, já ordenadas por prioridade."""
    t = s.lower()
    achou = set()
    if entidades:
        achou.add("entidade")
    if re.search(r"\b(segundo|de acordo com)\s+(fontes|especialistas|interlocutores|pessoas)|\b(especialistas|fontes)\s+(afirmam|dizem|apontam)", t):
        achou.add("atribuicao_a_fontes_anonimas")
    if numeros(s):
        achou.add("dado_estatistico")
    if re.search(r"\b(vai|irá|irão|será|serão|deve|devem|promete|prometeu|pretende)\b", t):
        achou.add("previsao_ou_promessa")
    if re.search(r"\b(acho|acredito|parece|deveria|na minha opinião|a meu ver)\b", t):
        achou.add("opiniao_ou_interpretacao")
    ordenadas = [c for c in PRIORIDADE if c in achou]
    return ordenadas or ["fato_verificavel"]


def tipo(s: str, entidades: list[str] | None = None) -> str:
    return caracteristicas(s, entidades)[0]


TEMPLATES = {
    "entidade": {
        "resumo": "Esta frase envolve pessoas, instituições ou lugares. Vale conferir quem são e o que de fato fizeram ou disseram.",
        "perguntas": [
            "Quem são as pessoas ou instituições citadas e que papel têm nesse caso?",
            "O que foi atribuído a elas aparece em declaração ou documento oficial?",
            "Quem mais poderia confirmar essa versão?",
        ],
        "como": [
            "Procure o que as pessoas ou instituições citadas declararam nos canais oficiais.",
        ],
    },
    "dado_estatistico": {
        "resumo": "Esta frase traz um número. Números dependem de quem mediu, quando e como.",
        "perguntas": [
            "Esse número é absoluto ou proporção? Em relação a quê?",
            "Qual seria um valor de comparação razoável?",
            "Quem teria interesse em divulgar esse número?",
        ],
        "como": [
            "Procure o relatório ou a tabela original, não a notícia sobre ele.",
            "Confira a data e a metodologia na própria fonte.",
        ],
    },
    "atribuicao_a_fontes_anonimas": {
        "resumo": "A frase atribui a informação a pessoas ou grupos não identificados.",
        "perguntas": [
            "Quem seriam essas pessoas e que interesse teriam?",
            "O que mudaria se elas tivessem nome?",
            "Outros veículos independentes chegaram à mesma informação?",
        ],
        "como": [
            "Procure uma nota oficial ou documento primário.",
            "Veja se os veículos que repetem a notícia têm origem comum.",
        ],
    },
    "previsao_ou_promessa": {
        "resumo": "Esta frase fala do futuro ou de uma promessa. Ainda não dá para saber se se cumpre.",
        "perguntas": [
            "O que precisaria acontecer para isso se cumprir?",
            "Promessas parecidas no passado foram cumpridas?",
            "Quem ganha se as pessoas acreditarem nisso?",
        ],
        "como": [
            "Procure o documento oficial (lei, plano, nota) onde o compromisso aparece.",
            "Anote a data para conferir depois se aconteceu.",
        ],
    },
    "opiniao_ou_interpretacao": {
        "resumo": "Esta frase parece uma opinião ou interpretação, não um fato que um documento confirme.",
        "perguntas": [
            "Que dado levaria alguém a pensar o contrário?",
            "Quem defende essa visão e por quê?",
            "O que é fato e o que é interpretação nessa frase?",
        ],
        "como": [
            "Separe os fatos citados e cheque cada um.",
            "Procure uma visão diferente, de uma fonte de outro perfil.",
        ],
    },
    "fato_verificavel": {
        "resumo": "Esta frase afirma um fato que pode ser conferido em registros ou documentos.",
        "perguntas": [
            "Que evidência mostraria que isso aconteceu?",
            "Quem estava em posição de saber?",
            "Veículos independentes relatam o mesmo?",
        ],
        "como": [
            "Busque o registro primário (nota oficial, decisão, boletim).",
            "Compare pelo menos duas fontes de origens diferentes.",
        ],
    },
}


def dominio(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _palavras(s: str) -> set[str]:
    return set(re.findall(r"\w{5,}", s.lower()))


def relacao(claim: str, r: dict) -> tuple[str, str]:
    """Descreve (sem concluir) como o trecho encontrado se relaciona com a frase."""
    corpo = f"{r.get('title') or ''} {r.get('body') or ''}".lower()
    chave = _palavras(claim)
    cobertura = len(chave & _palavras(corpo)) / max(1, len(chave))
    if cobertura < 0.25:
        return "nao_trata", "O trecho encontrado parece falar de outro assunto."

    nums = numeros(claim)
    if nums:
        compacto = corpo.replace(" ", "")
        if any(n.replace(" ", "") in compacto for n in nums):
            return "cita_numero", "O trecho menciona o mesmo número. Confira o contexto na página."
        return "sem_numero", "Trata do tema, mas o trecho não mostra o número citado. Abra a página."
    return "trata_do_tema", "Trata do mesmo tema. Leia a página para ver o que diz."


def alertas(fontes: list[dict]) -> list[str]:
    doms = [f["dominio"] for f in fontes]
    out = []
    if len(set(doms)) < 2:
        out.append("Todos os resultados vêm do mesmo site: isso não é confirmação independente.")
    if not any(d.endswith(PRIMARIAS) for d in doms):
        out.append("Nenhum resultado é fonte primária (órgão oficial, estudo, documento).")
    if any(d.endswith(REDES) for d in doms):
        out.append("Há resultados de redes sociais, que repetem informação sem checagem.")
    return out


def _combinar(chave: str, cars: list[str], principal: int, demais: int, maximo: int) -> list[str]:
    """Itens da característica de maior prioridade primeiro, depois das demais.
    Não adapta o texto à frase: só define a ORDEM em que as perguntas aparecem."""
    saida = []
    for i, car in enumerate(cars):
        for item in TEMPLATES[car][chave][: principal if i == 0 else demais]:
            if item not in saida:
                saida.append(item)
    return saida[:maximo]


def montar(claim: str, fontes_brutas: list[dict], max_fontes: int = 5, entidades: list[str] | None = None) -> dict:
    cars = caracteristicas(claim, entidades)
    t = cars[0]
    tpl = TEMPLATES[t]

    fontes = []
    for r in fontes_brutas:
        rel, obs = relacao(claim, r)
        fontes.append({
            "titulo": r.get("title"),
            "dominio": dominio(r["href"]),
            "href": r["href"],
            "relacao": rel,
            "observacao": obs,
        })

    # Fontes primárias primeiro, redes sociais por último (sort é estável)
    fontes.sort(key=lambda f: (not f["dominio"].endswith(PRIMARIAS), f["dominio"].endswith(REDES)))
    fontes = fontes[:max_fontes]

    return {
        "tipo": t,
        "caracteristicas": cars,
        "resumo_tipo": tpl["resumo"],
        "alertas": alertas(fontes),
        "perguntas": _combinar("perguntas", cars, N_PRINCIPAL, N_SECUNDARIA, 4),
        "como_verificar": _combinar("como", cars, 1, 1, 2),
        "fontes": fontes,
    }
