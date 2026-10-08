const btnAnalisar = document.getElementById('btn-analisar');
const btnExemplo = document.getElementById('btn-exemplo');
const inputTexto = document.getElementById('texto-input');
const inputUrl = document.getElementById('url-input'); // Novo campo de URL
const btnTexto = btnAnalisar.querySelector('span');
const areaResultado = document.getElementById('area-resultado');
const divTextoFormatado = document.getElementById('texto-formatado');
const badgeContador = document.getElementById('badge-contador');
const msgErro = document.getElementById('erro');
const histLista = document.getElementById('hist-lista');
const histVazio = document.getElementById('hist-vazio');
const btnLimpar = document.getElementById('btn-limpar');
const menuBtn = document.getElementById('menu-btn');
const menu = document.getElementById('menu');
const btnApagar = document.getElementById('btn-apagar');
const contador = document.getElementById('contador');
const abas = document.querySelectorAll('.tab');
const paineis = { link: document.getElementById('painel-link'), texto: document.getElementById('painel-texto') };
let modo = 'texto';
const MAX_CHARS = 5000;

function definirModo(novo) {
  modo = novo;
  abas.forEach(a => {
    const ativa = a.dataset.modo === novo;
    a.classList.toggle('ativo', ativa);
    a.setAttribute('aria-selected', String(ativa));
  });
  paineis.link.hidden = novo !== 'link';
  paineis.texto.hidden = novo !== 'texto';
  btnTexto.textContent = novo === 'link' ? 'Analisar Link' : 'Analisar Texto';
  mostrarErro('');
  atualizarContador();
  (novo === 'link' ? inputUrl : inputTexto).focus();
}

function atualizarContador() {
  if (modo === 'link') { contador.textContent = ''; return; }
  const n = inputTexto.value.length;
  contador.textContent = `${n}/${MAX_CHARS} caracteres`;
  contador.classList.toggle('limite', n >= MAX_CHARS);
}

abas.forEach(a => a.addEventListener('click', () => definirModo(a.dataset.modo)));
inputTexto.addEventListener('input', atualizarContador);

btnApagar.addEventListener('click', () => {
  inputTexto.value = '';
  inputUrl.value = '';
  mostrarErro('');
  areaResultado.classList.remove('ativo');
  divTextoFormatado.replaceChildren();
  atualizarContador();
  (modo === 'link' ? inputUrl : inputTexto).focus();
});
 
const TEXTO_EXEMPLO = 'O Instituto de Pesquisas divulgou um novo relatório hoje. Segundo os dados, a vacina reduziu as internações em 85%. A população comemorou a notícia nas redes sociais. Especialistas afirmam que o desmatamento na região aumentou 20% no último trimestre. O governo ainda não se pronunciou sobre as medidas que serão tomadas.';
 
function mostrarErro(mensagem) {
  msgErro.textContent = mensagem;
  msgErro.hidden = !mensagem;
}
 
// Faz o pedido real ao seu backend (FastAPI)
async function analisarTexto(texto, url) {
  // NOTA: Usando a porta 7860 de acordo com o que apareceu no seu terminal.
  // Se futuramente o servidor arrancar noutra porta (ex: 8000), altere aqui.
  const resposta = await fetch('http://localhost:7860/api/analisar', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ texto: texto || null, url: url || null })
  });
 
  if (!resposta.ok) {
    const erroData = await resposta.json().catch(() => ({}));
    throw new Error(erroData.detail || 'Erro na comunicação com o servidor.');
  }
 
  const dados = await resposta.json();
 
  // Transforma o formato recebido do backend no formato esperado pela interface visual
  const resultadosFormatados = dados.sentencas.map(item => {
    // Identifica se a classe gerada pelo modelo representa uma "Claim"
    const nomeClasse = String(item.classe).toLowerCase();
    const eClaim = item.classe === 1 || nomeClasse === 'claim' || nomeClasse === 'verdadeiro' || nomeClasse === 'sim';
    
    return {
      sentenca: item.sentenca_corrigida,
      is_claim: eClaim
    };
  });
 
  return { resultados: resultadosFormatados, origem: dados.origem, categorias: dados.categorias || [] };
}
 
function urlGoogle(sentenca) {
  return 'https://www.google.com/search?q=' + encodeURIComponent(sentenca);
}
 
// ---------- Verificação assistida (pensamento crítico) ----------
const ROTULO_TIPO = {
  entidade: 'Envolve pessoas ou instituições',
  fato_verificavel: 'Fato verificável',
  dado_estatistico: 'Dado estatístico',
  atribuicao_a_fontes_anonimas: 'Atribuída a fontes anônimas',
  opiniao_ou_interpretacao: 'Opinião ou interpretação',
  previsao_ou_promessa: 'Previsão ou promessa'
};
const ROTULO_RELACAO = {
  cita_numero: 'Cita o mesmo número',
  sem_numero: 'Número não aparece no trecho',
  trata_do_tema: 'Trata do tema',
  nao_trata: 'Não trata do tema'
};
 
// Cria elementos com textContent: o conteúdo vem de um LLM alimentado por
// páginas da web, então nunca deve ser interpretado como HTML.
function el(tag, classe, texto) {
  const e = document.createElement(tag);
  if (classe) e.className = classe;
  if (texto !== undefined) e.textContent = texto;
  return e;
}
 
function lista(tag, itens, classe) {
  const l = el(tag, classe);
  (itens || []).forEach(t => l.append(el('li', '', t)));
  return l;
}
 
function secao(titulo, conteudo, classe) {
  const s = el('section', 'rag-sec' + (classe ? ' ' + classe : ''));
  s.append(el('h4', '', titulo), conteudo);
  return s;
}
 
function linkGoogle(sentenca) {
  const a = el('a', 'rag-google', 'Pesquisar no Google');
  a.href = urlGoogle(sentenca);
  a.target = '_blank';
  a.rel = 'noopener noreferrer';
  return a;
}
 
function montarCartao(dados, sentenca) {
  const cartao = document.createDocumentFragment();
 
  if (dados.sem_fontes) {
    cartao.append(
      el('p', 'rag-aviso', 'Não encontramos fontes automaticamente para esta afirmação. Tente pesquisar por conta própria e compare mais de uma origem.'),
      linkGoogle(sentenca)
    );
    return cartao;
  }
 
  // 1. Que tipo de afirmação é
  const topo = el('div', 'rag-topo');
  const chips = el('div', 'rag-chips');
  (dados.caracteristicas?.length ? dados.caracteristicas : [dados.tipo]).forEach(c =>
    chips.append(el('span', 'rag-chip rag-chip-tipo', ROTULO_TIPO[c] || 'Afirmação')));
  topo.append(chips, el('p', 'rag-resumo', dados.resumo_tipo));
  cartao.append(topo);
 
  // 2. Perguntas para pensar (antes de ver as fontes)
  if (dados.perguntas?.length) {
    cartao.append(secao('Perguntas para pensar', lista('ol', dados.perguntas, 'rag-perguntas')));
  }
 
  // 4. Pontos de atenção
  if (dados.alertas?.length) {
    cartao.append(secao('Pontos de atenção', lista('ul', dados.alertas, 'rag-alertas'), 'rag-sec-alerta'));
  }
 
  // 5. Fontes encontradas (recolhidas por padrão)
  if (dados.fontes?.length) {
    const det = el('details', 'rag-fontes');
    det.append(el('summary', '', `O que as fontes encontradas dizem (${dados.fontes.length})`));
    dados.fontes.forEach(f => {
      let url;
      try { url = new URL(f.href); } catch { return; }
      if (url.protocol !== 'https:' && url.protocol !== 'http:') return;
 
      const item = el('div', 'rag-fonte');
      const cab = el('div', 'rag-fonte-cab');
      const a = el('a', 'rag-fonte-link', f.dominio || url.hostname);
      a.href = url.href;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      a.title = f.titulo || '';
      cab.append(a, el('span', `rag-chip rag-rel-${f.relacao}`, ROTULO_RELACAO[f.relacao] || 'Não trata do tema'));
      item.append(cab);
      det.append(item);
    });
    cartao.append(det);
  }
 
  // 6. Como verificar por conta própria
  if (dados.como_verificar?.length) {
    const bloco = el('div');
    bloco.append(lista('ul', dados.como_verificar), linkGoogle(sentenca));
    cartao.append(secao('Como verificar', bloco));
  }
 
  cartao.append(el('p', 'rag-rodape', 'A conclusão é sua.'));
  return cartao;
}
 
async function verificarClaimRAG(sentenca, elementoPai) {
  try {
    const resposta = await fetch('http://localhost:7860/api/verificar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sentenca: sentenca })
    });
 
    const dados = await resposta.json().catch(() => ({}));
    if (!resposta.ok) throw new Error(dados.detail || 'Falha na verificação');
 
    elementoPai.replaceChildren(montarCartao(dados, sentenca));
  } catch (erro) {
    console.error(erro);
    elementoPai.replaceChildren(el('p', 'rag-erro',
      erro instanceof TypeError
        ? 'Não foi possível conectar à API.'
        : `Não foi possível verificar esta afirmação: ${erro.message}`));
  }
}
 
function mostrarAssunto(categorias) {
  const caixa = document.getElementById('cartao-assunto');
  if (!categorias || !categorias.length) { caixa.hidden = true; caixa.replaceChildren(); return; }
  const chips = el('span', 'assunto-chips');
  categorias.forEach(c => chips.append(el('span', 'assunto-chip', c)));
  caixa.replaceChildren(
    el('span', 'assunto-rotulo', 'Esta notícia parece tratar de:'),
    chips,
    el('span', 'assunto-aviso', 'Identificado automaticamente por palavras-chave. É só um apoio para você se situar.')
  );
  caixa.hidden = false;
}

function renderizar(resultados, categorias) {
  mostrarAssunto(categorias);
  const fragmento = document.createDocumentFragment();
  let totalClaims = 0;
 
  resultados.forEach(item => {
    if (item.is_claim === true) {
      // Cria um container para a frase e para o resultado do RAG
      const container = document.createElement('span');
 
      const link = document.createElement('a');
      link.className = 'claim-grifada';
      link.title = 'Clique para verificar esta afirmação com IA';
      link.textContent = item.sentenca;
 
      // Caixa que vai receber a resposta do RAG (escondida por padrão)
      const caixaRAG = document.createElement('div');
      caixaRAG.style.display = 'none';
      caixaRAG.className = 'rag-caixa';
 
      // Evento de clique para ativar o RAG
      link.addEventListener('click', (e) => {
        e.preventDefault();
        if (caixaRAG.style.display === 'none') {
          caixaRAG.style.display = 'block';
          caixaRAG.replaceChildren(el('p', 'rag-carregando', 'Buscando fontes e organizando as evidências…'));
          verificarClaimRAG(item.sentenca, caixaRAG);
        } else {
          caixaRAG.style.display = 'none'; // Fecha a caixa se clicar de novo
        }
      });
 
      container.append(link, caixaRAG);
      fragmento.append(container);
      totalClaims++;
    } else {
      fragmento.append(item.sentenca);
    }
    fragmento.append(' ');
  });
 
  divTextoFormatado.replaceChildren(fragmento);
  badgeContador.textContent = totalClaims === 1 ? '1 claim detectada' : `${totalClaims} claims detectadas`;
  areaResultado.classList.add('ativo');
  areaResultado.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  areaResultado.focus({ preventScroll: true });
}
 
async function enviar() {
  mostrarErro('');
 
  const textoValue = modo === 'texto' ? inputTexto.value.trim() : '';
  const urlValue = modo === 'link' ? inputUrl.value.trim() : '';
 
  if (!textoValue && !urlValue) {
    mostrarErro(modo === 'link' ? 'Por favor, cole o link de um post ou reel do Instagram antes de analisar.' : 'Por favor, cole o texto da notícia antes de analisar.');
    (modo === 'link' ? inputUrl : inputTexto).focus();
    return;
  }
 
  areaResultado.classList.remove('ativo');
  btnTexto.textContent = 'Analisando com IA...';
  btnAnalisar.disabled = true;
 
  try {
    const dados = await analisarTexto(textoValue, urlValue);
    renderizar(dados.resultados, dados.categorias);
    
    const textoParaHistorico = textoValue ? textoValue : `Análise de Link (${dados.origem}): ${urlValue}`;
    adicionarAoHistorico(textoParaHistorico, dados.resultados, dados.categorias);
  } catch (erro) {
    console.error(erro);
    mostrarErro(erro.message);
  } finally {
    btnTexto.textContent = modo === 'link' ? 'Analisar Link' : 'Analisar Texto';
    btnAnalisar.disabled = false;
  }
}
 
btnAnalisar.addEventListener('click', enviar);
btnExemplo.addEventListener('click', () => {
  inputTexto.value = TEXTO_EXEMPLO;
  inputUrl.value = '';
  mostrarErro('');
  atualizarContador();
  inputTexto.focus();
});
 
// ==========================================
// Histórico (salvo no navegador)
// ==========================================
const CHAVE_HISTORICO = 'historico-claims';
const MAX_HISTORICO = 20;
 
function lerHistorico() {
  try { return JSON.parse(localStorage.getItem(CHAVE_HISTORICO)) || []; }
  catch { return []; }
}
 
function salvarHistorico(lista) {
  try { localStorage.setItem(CHAVE_HISTORICO, JSON.stringify(lista)); }
  catch (erro) { console.error(erro); }
}
 
function adicionarAoHistorico(texto, resultados, categorias) {
  const total = resultados.filter(r => r.is_claim === true).length;
  const lista = lerHistorico();
  lista.unshift({ id: Date.now(), data: new Date().toISOString(), texto, resultados, categorias: categorias || [], total });
  salvarHistorico(lista.slice(0, MAX_HISTORICO));
  renderizarHistorico();
}
 
function renderizarHistorico() {
  const lista = lerHistorico();
  histVazio.hidden = lista.length > 0;
  btnLimpar.hidden = lista.length === 0;
 
  histLista.replaceChildren(...lista.map(item => {
    const li = document.createElement('li');
    li.className = 'hist-item';
    li.dataset.id = item.id;
 
    const abrir = document.createElement('button');
    abrir.type = 'button';
    abrir.className = 'hist-abrir';
 
    const meta = document.createElement('span');
    meta.className = 'hist-meta';
    const data = document.createElement('time');
    data.dateTime = item.data;
    data.textContent = new Date(item.data).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
    const badge = document.createElement('span');
    badge.className = 'badge';
    badge.textContent = item.total === 1 ? '1 claim' : `${item.total} claims`;
    meta.append(data, badge);
 
    const trecho = document.createElement('span');
    trecho.className = 'hist-trecho';
    trecho.textContent = item.texto;
 
    abrir.append(meta, trecho);
    abrir.setAttribute('aria-label', `Abrir análise de ${data.textContent}`);
 
    const excluir = document.createElement('button');
    excluir.type = 'button';
    excluir.className = 'hist-del';
    excluir.textContent = '×';
    excluir.setAttribute('aria-label', `Excluir análise de ${data.textContent}`);
 
    li.append(abrir, excluir);
    return li;
  }));
}
 
histLista.addEventListener('click', e => {
  const li = e.target.closest('.hist-item');
  if (!li) return;
  const lista = lerHistorico();
  const item = lista.find(i => String(i.id) === li.dataset.id);
  if (!item) return;
 
  if (e.target.closest('.hist-del')) {
    salvarHistorico(lista.filter(i => i !== item));
    renderizarHistorico();
  } else if (e.target.closest('.hist-abrir')) {
    // Quando abre do histórico, coloca apenas o texto no inputTexto (para limpar o campo link)
    definirModo('texto');
    inputTexto.value = item.texto.slice(0, MAX_CHARS);
    inputUrl.value = '';
    atualizarContador();
    mostrarErro('');
    renderizar(item.resultados, item.categorias);
    document.getElementById('analisador').scrollIntoView({ behavior: 'smooth' });
  }
});
 
btnLimpar.addEventListener('click', () => {
  if (confirm('Apagar todo o histórico de análises?')) {
    salvarHistorico([]);
    renderizarHistorico();
  }
});
 
renderizarHistorico();
 
// ==========================================
// Menu mobile
// ==========================================
function alternarMenu(aberto) {
  menu.classList.toggle('aberto', aberto);
  menuBtn.setAttribute('aria-expanded', String(aberto));
  menuBtn.setAttribute('aria-label', aberto ? 'Fechar menu' : 'Abrir menu');
}
menuBtn.addEventListener('click', () => alternarMenu(!menu.classList.contains('aberto')));
menu.addEventListener('click', e => { if (e.target.closest('a')) alternarMenu(false); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') alternarMenu(false); });