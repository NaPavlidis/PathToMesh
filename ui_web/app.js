/* PathToMesh — interface web.
   Os botões chamam a classe Api do app_web.py (window.pywebview.api.<método>) sempre pela
   função chamar('<método>', ...). As etapas e o progresso do Blender chegam do Python por
   window.ptm.evento({...}) (evaluate_js). Os avisos aparecem num modal desta página. */
(function () {
  'use strict';

  var $ = function (id) { return document.getElementById(id); };
  var inicio = null;              // dados do estado_inicial()
  var fila = [];                  // avisos esperando a vez (um modal por vez)
  var aoFecharAviso = null;
  var configBlendAtual = '';

  // ------------------------------------------------------------------ ponte com o Python
  function api() {
    return window.pywebview && window.pywebview.api;
  }

  function chamar(metodo) {
    var args = Array.prototype.slice.call(arguments, 1);
    var ponte = api();
    if (!ponte || typeof ponte[metodo] !== 'function') {
      return Promise.reject(new Error('a ponte com o Python não tem o método ' + metodo));
    }
    return ponte[metodo].apply(ponte, args).catch(function (erro) {
      registrarErro('erro ao chamar ' + metodo, erro);
      mostrarAviso('Erro', 'Não deu para concluir a ação (' + metodo + '):\n' + textoErro(erro), 'erro');
      return new Promise(function () {});    // já avisado: o resto da ação não roda
    });
  }

  function textoErro(erro) {
    if (!erro) return '';
    if (typeof erro === 'string') return erro;
    return erro.message || String(erro);
  }

  function registrarErro(resumo, erro) {
    try {
      var ponte = api();
      if (ponte && ponte.registrar_erro) {
        var p = ponte.registrar_erro(resumo + ': ' + textoErro(erro), (erro && erro.stack) || '');
        if (p && p.catch) p.catch(function () {});   // se nem o log funcionar, não insiste
      }
    } catch (e) { /* sem ponte: nada a fazer */ }
  }

  window.addEventListener('error', function (ev) {
    registrarErro('erro de JavaScript', ev.error || ev.message);
  });
  window.addEventListener('unhandledrejection', function (ev) {
    registrarErro('promessa sem tratamento', ev.reason);
  });

  // ------------------------------------------------------------------ modais de aviso
  function mostrarAviso(titulo, mensagem, tipo, depois) {
    fila.push({ titulo: titulo, mensagem: mensagem, tipo: tipo || 'aviso', depois: depois || null });
    if (fila.length === 1) abrirProximoAviso();
  }

  function abrirProximoAviso() {
    var a = fila[0];
    if (!a) return;
    var modal = document.querySelector('.modal-aviso');
    modal.classList.remove('tipo-aviso', 'tipo-erro', 'tipo-info');
    modal.classList.add('tipo-' + a.tipo);
    var icone = $('aviso-icone');
    var simbolo = { aviso: '#i-aviso', erro: '#i-erro', info: '#i-ok' }[a.tipo] || '#i-aviso';
    icone.querySelector('use').setAttribute('href', simbolo);
    icone.setAttribute('class', 'ic ic-titulo ' + ({ aviso: 'aviso', erro: 'erro', info: 'sucesso' }[a.tipo] || 'aviso'));
    $('aviso-titulo').textContent = a.titulo;
    $('aviso-mensagem').textContent = a.mensagem;
    aoFecharAviso = a.depois;
    $('janela-aviso').hidden = false;
    $('btn-aviso-ok').focus();
  }

  function fecharAviso() {
    $('janela-aviso').hidden = true;
    var depois = aoFecharAviso;
    aoFecharAviso = null;
    fila.shift();
    if (depois) depois();
    if (fila.length) abrirProximoAviso();
  }

  // ------------------------------------------------------------------ telas
  var ETAPAS = [['1', 'UPLOAD'], ['2', 'PROCESSING'], ['3', 'DOWNLOAD']];

  function montarEtapas() {
    document.querySelectorAll('.tela[data-etapa]').forEach(function (tela) {
      var ativa = parseInt(tela.getAttribute('data-etapa'), 10);
      var nav = tela.querySelector('.etapas');
      nav.textContent = '';
      ETAPAS.forEach(function (etapa, i) {
        var idx = i + 1;
        if (idx > 1) {
          var linha = document.createElement('div');
          linha.className = 'etapa-linha' + (idx <= ativa ? ' acesa' : '');
          linha.setAttribute('aria-hidden', 'true');
          nav.appendChild(linha);
        }
        var item = document.createElement('div');
        item.className = 'etapa' + (idx <= ativa ? ' feita' : '') + (idx === ativa ? ' atual' : '');
        var num = document.createElement('span');
        num.className = 'etapa-num';
        if (idx < ativa) {
          num.innerHTML = '<svg class="ic"><use href="#i-check"/></svg>';
        } else {
          num.textContent = etapa[0];
        }
        var nome = document.createElement('span');
        nome.className = 'etapa-nome';
        nome.textContent = etapa[1];
        item.appendChild(num);
        item.appendChild(nome);
        if (idx === ativa) item.setAttribute('aria-current', 'step');
        nav.appendChild(item);
      });
    });
  }

  function mostrarTela(chave) {
    document.querySelectorAll('.nav-item').forEach(function (item) {
      var ativo = item.getAttribute('data-tela') === chave;
      item.classList.toggle('ativo', ativo);
      if (ativo) item.setAttribute('aria-current', 'page'); else item.removeAttribute('aria-current');
    });
    if (chave === 'catalogo') atualizarCatalogo();
    document.querySelectorAll('.tela').forEach(function (tela) {
      tela.hidden = tela.id !== 'tela-' + chave;
    });
    document.querySelector('.area').scrollTop = 0;
    // a galeria só existe no Download: lista rápida; miniaturas só das novas
    if (chave === 'download' && inicio) atualizarGaleria();
  }

  // ------------------------------------------------------------------ logo do cabeçalho (1; 2 com a janela larga)
  function ajustarLogo() {
    if (!inicio) return;
    var img = $('logo-cabecalho');
    var largo = window.innerWidth >= inicio.limite_logo;
    var fonte = largo ? (inicio.logos.largo || inicio.logos.normal) : (inicio.logos.normal || inicio.logos.largo);
    if (!fonte) {
      img.hidden = true;
      $('nome-app').hidden = false;
      return;
    }
    if (img.getAttribute('src') !== fonte) img.setAttribute('src', fonte);
    img.classList.toggle('largo', largo && !!inicio.logos.largo);
    img.hidden = false;
    $('nome-app').hidden = true;
  }

  // ------------------------------------------------------------------ Upload
  function preencherSelect(select, opcoes, selecionado) {
    select.textContent = '';
    opcoes.forEach(function (o) {
      var op = document.createElement('option');
      op.value = typeof o === 'string' ? o : o.valor;
      op.textContent = typeof o === 'string' ? o : o.rotulo;
      select.appendChild(op);
    });
    select.value = selecionado;
  }

  function mostrarResinas(dados) {
    preencherSelect($('sel-resina'), dados.opcoes, dados.selecionado);
  }

  var CLASSES_TIPO = { BASE: 't-base', MDF: 't-mdf', MDF_COSTAS: 't-mdf', ACRILICO: 't-acrilico',
                       ACRILICO_GRAVADO: 't-acrilico', ACRILICO_ESPELHADO: 't-acrilico' };

  function mostrarAnalise(resultado) {
    var dados = resultado.dados;
    $('analise-vazia').hidden = true;
    $('analise-erro').hidden = !!dados;
    $('analise-dados').hidden = !dados;
    if (!dados) {
      $('analise-erro').textContent = resultado.texto;
      return;
    }
    $('analise-arquivo').textContent = dados.nome_arquivo;
    var lista = $('analise-materiais');
    lista.textContent = '';
    dados.materiais.forEach(function (m) {
      var li = document.createElement('li');
      li.className = 'material';
      var esquerda = document.createElement('div');
      var chip = document.createElement('span');
      chip.className = 'chip-tipo ' + (CLASSES_TIPO[m.tipo] || '');
      chip.textContent = m.tipo;
      var nome = document.createElement('span');
      nome.className = 'mono-md material-nome';
      nome.textContent = m.nome;
      esquerda.appendChild(chip);
      esquerda.appendChild(nome);
      var qtd = document.createElement('span');
      qtd.className = 'mono-md material-qtd';
      qtd.textContent = m.qtd;
      li.appendChild(esquerda);
      li.appendChild(qtd);
      lista.appendChild(li);
    });
    if (!dados.materiais.length) {
      var vazio = document.createElement('li');
      vazio.className = 'mono-sm lista-vazia';
      vazio.textContent = 'Nenhuma peça com cor da tabela de materiais.';
      lista.appendChild(vazio);
    }
    $('medida-fundo').textContent = dados.nome_fundo;
    $('medida-largura').textContent = dados.largura_mm + ' mm';
    $('medida-largura-cm').textContent = '(' + dados.largura_cm + ' cm)';
    $('medida-altura').textContent = dados.altura_mm + ' mm';
    $('medida-altura-cm').textContent = '(' + dados.altura_cm + ' cm)';
    $('analise-descartadas').hidden = !dados.descartadas;
    $('analise-descartadas-qtd').textContent = dados.descartadas;
  }

  function selecionarSvg() {
    chamar('selecionar_svg').then(function (r) {
      if (!r || !r.ok) return;
      var nome = $('svg-nome');
      nome.textContent = r.nome;
      nome.classList.remove('suave');
      nome.classList.add('sucesso');
      $('svg-dica').hidden = false;
      mostrarAnalise(r);
      atualizarGaleria();                            // a galeria passa a ser a da pasta deste SVG
      if (r.aviso) mostrarAviso(r.aviso.titulo, r.aviso.mensagem, 'aviso');
    });
  }

  function opcoesUpload() {
    return {
      render_auto: $('chk-render-auto').checked,
      cam_principal: $('chk-cam-principal').checked,
      cam_esquerda: $('chk-cam-esquerda').checked,
      cam_direita: $('chk-cam-direita').checked,
      usar_textura: $('chk-textura').checked,
      usar_verniz: $('chk-verniz').checked,
      resina: $('sel-resina').value
    };
  }

  function avancar() {
    chamar('avancar', opcoesUpload()).then(function (r) {
      if (!r.ok) {
        mostrarAviso(r.aviso.titulo, r.aviso.mensagem, 'aviso');
        return;
      }
      $('proc-status').textContent = r.status;
      $('proc-samples').textContent = r.samples;
      iniciarProgresso();
      gal.camsProntas = 0;
      mostrarContagem(0, 0);
      mostrarTela('processing');
    });
  }

  // ------------------------------------------------------------------ Processing (eventos do Blender)
  // A barra mostra o progresso real calculado no Python (nucleo.ProgressoRender): nunca volta,
  // só chega a 100% quando o Blender termina com sucesso e, enquanto o Blender não manda
  // informação, fica no modo "trabalhando" (faixa que vai e volta) sem inventar progresso.
  // avanco: hora em que a porcentagem subiu pela última vez; ocupado: o Blender trabalha sem
  // progresso medido (preparação, shaders/BVH, denoise, gravação); fim: concluiu ou deu erro
  var prog = { real: false, base: null, recebido: 0, relogio: null, inicio: 0, pct: 0, avanco: 0, ocupado: true, fim: false };
  var ROTULO_ESTADO = { concluida: 'concluída', andamento: 'em andamento', pendente: 'pendente', pulada: 'pulada', erro: 'erro' };
  var MARCA_ESTADO = { concluida: '✓', erro: '!' };

  // ---- animações da barra e do logo (o visual fica no estilo.css)
  // Estados da barra: uma destas classes por vez no #proc-trilho.
  //   rodando = samples chegando; trabalhando = ocupado sem progresso medido (faixa vai e volta);
  //   concluido = terminou bem (efeito curto); erro = cor de erro, sem animação.
  var ESTADOS_BARRA = ['rodando', 'trabalhando', 'concluido', 'erro'];
  var DEMORA_MS = 4000;                 // sem avanço por mais que isto: mostra o logo animado
  var ESPERA_CONCLUSAO_MS = 900;        // tempo do efeito de conclusão antes de ir para o Download

  function movimentoReduzido() {
    return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  }

  function estadoBarra(nome) {
    var trilho = $('proc-trilho');
    ESTADOS_BARRA.forEach(function (e) { trilho.classList.toggle(e, e === nome); });
  }

  // estado da barra a partir de um evento 'progresso' (nucleo.ProgressoRender.estado())
  function estadoDoProgresso(d) {
    if (d.concluido) return d.sucesso === false ? 'erro' : 'concluido';
    if ((d.etapas || []).some(function (e) { return e.estado === 'erro'; })) return 'erro';
    return d.trabalhando ? 'trabalhando' : 'rodando';
  }

  // logo animado: enquanto o Blender está ocupado sem progresso medido ou a barra está parada há
  // mais de DEMORA_MS; some quando o progresso volta a andar ou o render termina
  function estaDemorando() {
    if (prog.fim) return false;
    return prog.ocupado || Date.now() - prog.avanco > DEMORA_MS;
  }

  function textoDaEtapa() {
    var etapas = (prog.base && prog.base.etapas) || [];
    for (var i = 0; i < etapas.length; i++) {
      if (etapas[i].estado === 'andamento') return etapas[i].titulo;
    }
    return $('proc-status').textContent;
  }

  function atualizarDemora() {
    var demorando = estaDemorando();
    $('proc-cartao').classList.toggle('demorando', demorando);
    if (demorando) {
      var txt = textoDaEtapa();
      if ($('proc-logo-texto').textContent !== txt) $('proc-logo-texto').textContent = txt;
    }
  }

  function terminarAnimacoes(estado) {
    if (prog.fim && $('proc-trilho').classList.contains('erro')) estado = 'erro';   // erro não vira sucesso
    prog.fim = true;
    estadoBarra(estado);
    atualizarDemora();
  }

  function porcentagem(valor) {
    valor = Math.max(prog.pct, Math.max(0, Math.min(100, valor)));
    if (valor > prog.pct) prog.avanco = Date.now();
    prog.pct = valor;
    $('proc-barra').style.width = valor + '%';
    $('proc-porcentagem').textContent = Math.floor(valor) + '%';
    $('proc-trilho').setAttribute('aria-valuenow', String(Math.floor(valor)));
  }

  function duracao(segundos) {
    var s = Math.max(0, Math.round(segundos));
    function dois(n) { return (n < 10 ? '0' : '') + n; }
    if (s < 60) return s + ' s';
    if (s < 3600) return Math.floor(s / 60) + ' min ' + dois(s % 60) + ' s';
    return Math.floor(s / 3600) + ' h ' + dois(Math.floor((s % 3600) / 60)) + ' min';
  }

  function mostrarTempos() {
    var passou = (Date.now() - prog.recebido) / 1000;
    var decorrido = prog.base ? prog.base.decorrido + passou : (Date.now() - prog.inicio) / 1000;
    var txt = 'Decorrido: ' + duracao(decorrido);
    if (prog.base && prog.base.restante !== null && prog.base.restante !== undefined) {
      var falta = prog.base.restante - passou;
      txt += '  ·  Restante: ' + (falta >= 1 ? '~' + duracao(falta) : 'quase lá');
    }
    $('proc-samples').textContent = txt;
  }

  function pararRelogio() {
    if (prog.relogio) clearInterval(prog.relogio);
    prog.relogio = null;
  }

  function iniciarProgresso() {
    pararRelogio();
    prog = { real: false, base: null, recebido: Date.now(), relogio: null, inicio: Date.now(), pct: 0,
             avanco: Date.now(), ocupado: true, fim: false };
    $('proc-barra').style.width = '0%';
    $('proc-porcentagem').textContent = '0%';
    $('proc-trilho').setAttribute('aria-valuenow', '0');
    estadoBarra('trabalhando');          // sem dados do Blender ainda: faixa indeterminada
    $('proc-etapas').textContent = '';
    etapasMostradas = null;
    atualizarDemora();
    prog.relogio = setInterval(function () {
      if (prog.real) mostrarTempos();
      atualizarDemora();
    }, 1000);
  }

  var etapasMostradas = null;

  function mostrarEtapas(etapas) {
    // o progresso chega várias vezes por segundo: a lista só é refeita quando uma etapa muda
    var assinatura = etapas.map(function (e) { return e.id + ':' + e.estado + ':' + e.titulo; }).join('|');
    if (assinatura === etapasMostradas) return;
    etapasMostradas = assinatura;
    var lista = $('proc-etapas');
    lista.textContent = '';
    etapas.forEach(function (e) {
      var li = document.createElement('li');
      li.className = 'body-md';
      li.setAttribute('data-estado', e.estado);
      var marca = document.createElement('span');
      marca.className = 'marca';
      marca.textContent = MARCA_ESTADO[e.estado] || '';
      var titulo = document.createElement('span');
      titulo.textContent = e.titulo;
      var situacao = document.createElement('span');
      situacao.className = 'situacao label-md suave';
      situacao.textContent = ROTULO_ESTADO[e.estado] || e.estado;
      li.appendChild(marca);
      li.appendChild(titulo);
      li.appendChild(situacao);
      lista.appendChild(li);
    });
  }

  function mostrarProgresso(d) {
    prog.real = true;
    prog.base = d;
    prog.recebido = Date.now();
    porcentagem(d.porcentagem);
    if (prog.ocupado && !d.trabalhando) prog.avanco = Date.now();   // as samples começaram: conta a demora daqui
    prog.ocupado = !!d.trabalhando;
    $('proc-status').textContent = d.atual;
    mostrarEtapas(d.etapas || []);
    mostrarTempos();
    var estado = estadoDoProgresso(d);
    if (estado === 'concluido' || estado === 'erro') terminarAnimacoes(estado);
    else if (!prog.fim) { estadoBarra(estado); atualizarDemora(); }
    if (d.concluido) pararRelogio();
    // na Processing só a contagem de imagens prontas (a galeria aparece no Download, no fim)
    gal.camsProntas = camerasProntas(d.etapas);
    mostrarContagem(gal.camsProntas, totalCameras(d.etapas));   // só mexe no DOM se o texto mudar
  }

  function mostrarContagem(prontas, total) {
    var el = $('proc-imagens');
    var txt = total ? 'Imagens prontas: ' + prontas + ' de ' + total : '';
    if (el.textContent !== txt) el.textContent = txt;
    el.hidden = !total;
  }

  window.ptm = {
    evento: function (d) {
      try {
        // com o progresso real chegando, os textos antigos (status/passo/amostras) não
        // sobrescrevem a etapa atual
        if (d.tipo === 'status') {
          if (!prog.real) $('proc-status').textContent = d.status;
        } else if (d.tipo === 'passo') {
          if (!prog.real) $('proc-status').textContent = d.status;
        } else if (d.tipo === 'amostras') {
          if (!prog.real) $('proc-status').textContent = d.status;
        } else if (d.tipo === 'progresso') {
          mostrarProgresso(d);
        } else if (d.tipo === 'concluido') {
          pararRelogio();
          var falhou = d.sucesso === false || prog.base && prog.base.sucesso === false;
          terminarAnimacoes(falhou ? 'erro' : 'concluido');
          $('proc-status').textContent = d.status;
          if (d.porcentagem !== null && d.porcentagem !== undefined) porcentagem(d.porcentagem);
          $('proc-samples').textContent = d.samples;
          if (falhou || movimentoReduzido()) {
            mostrarTela('download');                 // atualiza a galeria com as imagens novas
          } else {
            // deixa a barra chegar a 100% e mostrar o efeito de conclusão antes de trocar de tela
            setTimeout(function () { mostrarTela('download'); }, ESPERA_CONCLUSAO_MS);
          }
        } else if (d.tipo === 'erro') {
          pararRelogio();
          terminarAnimacoes('erro');
          mostrarAviso(d.titulo, d.mensagem, 'erro');
        }
      } catch (e) {
        registrarErro('erro ao mostrar evento do Blender', e);
      }
      return true;
    }
  };

  // ------------------------------------------------------------------ Galeria (imagens geradas)
  // A lista vem rápida do Python (sem ler as imagens); as miniaturas vêm depois, uma por vez, e
  // só com a galeria na tela. A galeria fica SÓ na tela de conclusão (Download); a Processing
  // mostra apenas a contagem de imagens prontas. A imagem ampliada abre num modal (anterior/próxima).
  // pedindo/listando: hora do pedido em andamento (0 = nenhum; depois de 30 s, libera de novo)
  var gal = { itens: [], assinatura: null, mini: {}, falhou: {}, pedindo: 0, imgs: {},
              camsProntas: 0, lista: [], atual: -1, pedidoGrande: 0, listando: 0, denovo: false };

  function galeriaVisivel() {
    return !$('tela-download').hidden;
  }

  function atualizarGaleria() {
    if (gal.listando && Date.now() - gal.listando < 30000) { gal.denovo = true; return; }
    gal.listando = Date.now();
    chamar('listar_galeria').then(function (r) {
      gal.listando = false;
      gal.itens = r.itens || [];
      desenharGalerias();
      pedirMiniaturas();
      if (gal.denovo) { gal.denovo = false; atualizarGaleria(); }
    });
  }

  function desenharGalerias() {
    var assinatura = gal.itens.map(function (i) { return i.chave; }).join('\n');
    if (assinatura === gal.assinatura) return;      // nada mudou: o DOM fica como está
    gal.assinatura = assinatura;
    gal.imgs = {};
    document.querySelectorAll('[data-galeria]').forEach(function (cartao) {
      var itens = gal.itens;
      var grade = cartao.querySelector('.galeria-grade');
      grade.textContent = '';
      itens.forEach(function (item, i) { grade.appendChild(montarItem(item, i, itens)); });
      var vazia = cartao.querySelector('.galeria-vazia');
      if (vazia) vazia.hidden = itens.length > 0;
    });
    $('tela-download').classList.toggle('com-imagens', gal.itens.length > 0);
  }

  function montarItem(item, indice, lista) {
    var li = document.createElement('li');
    var botao = document.createElement('button');
    botao.type = 'button';
    botao.className = 'galeria-item';
    botao.title = 'Ampliar ' + item.arquivo;
    var quadro = document.createElement('div');
    quadro.className = 'galeria-miniatura';
    var img = document.createElement('img');
    img.alt = item.camera;
    img.decoding = 'async';
    if (gal.mini[item.chave]) {
      img.src = gal.mini[item.chave];
    } else {
      img.hidden = true;
      quadro.innerHTML = '<svg class="ic"><use href="#i-imagem"/></svg>';
    }
    quadro.appendChild(img);
    (gal.imgs[item.chave] = gal.imgs[item.chave] || []).push(img);
    var nome = document.createElement('span');
    nome.className = 'galeria-nome';
    nome.textContent = item.camera;
    var dados = document.createElement('span');
    dados.className = 'galeria-dados';
    dados.textContent = [item.dimensoes, item.tamanho, item.data].filter(Boolean).join('  ·  ');
    botao.appendChild(quadro);
    botao.appendChild(nome);
    botao.appendChild(dados);
    botao.addEventListener('click', function () { abrirImagem(lista, indice); });
    li.appendChild(botao);
    return li;
  }

  function mostrarMiniatura(chave, src) {
    (gal.imgs[chave] || []).forEach(function (img) {
      img.src = src;
      img.hidden = false;
      var icone = img.parentNode && img.parentNode.querySelector('.ic');
      if (icone) icone.parentNode.removeChild(icone);
    });
  }

  function pedirMiniaturas() {
    if ((gal.pedindo && Date.now() - gal.pedindo < 30000) || !galeriaVisivel()) return;
    var falta = gal.itens.filter(function (i) { return !gal.mini[i.chave] && !gal.falhou[i.chave]; })[0];
    if (!falta) return;
    gal.pedindo = Date.now();
    chamar('miniatura', falta.chave).then(function (r) {
      gal.pedindo = false;
      if (r && r.ok) {
        gal.mini[falta.chave] = r.src;
        mostrarMiniatura(falta.chave, r.src);
      } else {
        gal.falhou[falta.chave] = true;
      }
      setTimeout(pedirMiniaturas, 0);              // a próxima, sem segurar a tela
    });
  }

  function abrirImagem(lista, indice) {
    gal.lista = lista;
    $('janela-imagem').hidden = false;
    mostrarImagem(indice);
    $('btn-imagem-fechar').focus();
  }

  function mostrarImagem(indice) {
    var item = gal.lista[indice];
    if (!item) return;
    gal.atual = indice;
    $('imagem-titulo').textContent = item.camera;
    $('imagem-info').textContent = [item.arquivo, item.dimensoes, item.tamanho, item.data].filter(Boolean).join('  ·  ');
    $('imagem-posicao').textContent = (indice + 1) + ' / ' + gal.lista.length;
    $('btn-imagem-anterior').disabled = indice <= 0;
    $('btn-imagem-proxima').disabled = indice >= gal.lista.length - 1;
    var img = $('imagem-grande');
    img.alt = item.camera;
    if (gal.mini[item.chave]) img.src = gal.mini[item.chave]; else img.removeAttribute('src');
    $('imagem-carregando').hidden = false;
    var pedido = ++gal.pedidoGrande;
    chamar('imagem', item.chave).then(function (r) {
      if (pedido !== gal.pedidoGrande) return;      // já foi para outra imagem
      $('imagem-carregando').hidden = true;
      if (r && r.ok) {
        img.src = r.src;
      } else {
        $('imagem-carregando').textContent = (r && r.erro) || 'Não deu para abrir a imagem.';
        $('imagem-carregando').hidden = false;
      }
    });
  }

  function navegarImagem(passo) {
    var novo = gal.atual + passo;
    if (novo >= 0 && novo < gal.lista.length) {
      $('imagem-carregando').textContent = 'Carregando...';
      mostrarImagem(novo);
    }
  }

  function fecharImagem() {
    gal.pedidoGrande++;
    $('janela-imagem').hidden = true;
    $('imagem-grande').removeAttribute('src');      // solta a memória da imagem grande
    $('imagem-carregando').textContent = 'Carregando...';
  }

  function camerasProntas(etapas) {
    return (etapas || []).filter(function (e) { return String(e.id).indexOf('camera:') === 0 && e.estado === 'concluida'; }).length;
  }

  function totalCameras(etapas) {
    return (etapas || []).filter(function (e) { return String(e.id).indexOf('camera:') === 0 && e.estado !== 'pulada'; }).length;
  }

  // ------------------------------------------------------------------ Catálogo
  var REALCES = [
    ['─', 'l-divisor'],
    ['📁', 'l-titulo'], ['📦', 'l-titulo'], ['📐', 'l-titulo'], ['📈', 'l-titulo'], ['📝', 'l-titulo'],
    ['⚠', 'l-aviso'], ['❌', 'l-erro'],
    ['Modalidade:', 'l-destaque'], ['Status: ✓', 'l-ok'], ['Status: ✗', 'l-apagado']
  ];

  function pintarRelatorio(pre, texto) {
    pre.textContent = '';
    texto.split('\n').forEach(function (linha, i, todas) {
      var span = document.createElement('span');
      var inicioLinha = linha.replace(/^\s+/, '');
      for (var j = 0; j < REALCES.length; j++) {
        if (inicioLinha.indexOf(REALCES[j][0]) === 0) { span.className = REALCES[j][1]; break; }
      }
      span.textContent = linha;
      pre.appendChild(span);
      if (i < todas.length - 1) pre.appendChild(document.createTextNode('\n'));
    });
  }

  var catalogo = { texto: null, pedindo: 0 };

  function atualizarCatalogo() {
    // a tela troca na hora (o relatório anterior continua lá); o novo chega quando o Python
    // terminar de mapear (às vezes numa unidade de rede) e só é repintado se mudou
    if (catalogo.pedindo && Date.now() - catalogo.pedindo < 30000) return;   // já tem um pedido andando
    catalogo.pedindo = Date.now();
    chamar('relatorio_catalogo').then(function (r) {
      catalogo.pedindo = false;
      if (r.texto === catalogo.texto) return;
      catalogo.texto = r.texto;
      pintarRelatorio($('catalogo-texto'), r.texto);
    });
  }

  // ------------------------------------------------------------------ Configurações
  function abrirConfiguracoes() {
    chamar('configuracoes').then(function (c) {
      $('cfg-blender').value = c.blender_path;
      $('cfg-catalogo').value = c.catalogo_dir;
      $('cfg-resina').value = c.resina_dir;
      $('cfg-blend-dir').value = c.blend_dir;
      $('cfg-samples').value = c.cycles_samples;
      configBlendAtual = c.blends.selecionado;
      preencherSelect($('cfg-blend'), c.blends.opcoes, c.blends.selecionado);
      $('janela-config').hidden = false;
      $('cfg-blender').focus();
    });
  }

  function fecharConfiguracoes() {
    $('janela-config').hidden = true;
  }

  function buscarPasta(campo, depois) {
    chamar('buscar_pasta').then(function (pasta) {
      if (!pasta) return;
      $(campo).value = pasta;
      if (depois) depois(pasta);
    });
  }

  function atualizarBlends(pasta) {
    chamar('listar_blends', pasta, $('cfg-blend').value || configBlendAtual).then(function (b) {
      preencherSelect($('cfg-blend'), b.opcoes, b.selecionado);
    });
  }

  function salvarConfiguracoes() {
    chamar('salvar_configuracoes', {
      blender_path: $('cfg-blender').value,
      catalogo_dir: $('cfg-catalogo').value,
      resina_dir: $('cfg-resina').value,
      blend_dir: $('cfg-blend-dir').value,
      selected_blend: $('cfg-blend').value,
      cycles_samples: $('cfg-samples').value
    }).then(function (r) {
      mostrarResinas(r.resina);
      fecharConfiguracoes();
      mostrarAviso(r.titulo, r.mensagem, 'info');
    });
  }

  // ------------------------------------------------------------------ começo
  function ligar(id, funcao) {
    $(id).addEventListener('click', function (ev) { ev.preventDefault(); funcao(); });
  }

  function iniciar() {
    if (inicio) return;
    chamar('estado_inicial').then(function (e) {
      inicio = e;
      document.title = e.nome_app;
      $('nome-app').textContent = e.nome_app;
      $('logo-cabecalho').alt = e.nome_app;
      var icone = e.icone || (e.logos && e.logos.normal);   // logo animado do cartão de progresso
      if (icone) { $('proc-logo-img').setAttribute('src', icone); $('proc-logo-img').hidden = false; }
      $('rodape-texto').textContent = '© 2026 ' + e.nome_app + '. All rights reserved.';
      $('analise-vazia').textContent = e.aguardando;
      $('proc-status').textContent = e.status_inicial;
      $('proc-samples').textContent = e.samples_inicial;
      mostrarResinas(e.resina);
      ajustarLogo();
      // galeria do último render: só a lista (rápida), depois que a tela já apareceu
      setTimeout(atualizarGaleria, 400);
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    montarEtapas();
    document.querySelectorAll('.nav-item').forEach(function (item) {
      item.addEventListener('click', function (ev) {
        ev.preventDefault();
        mostrarTela(item.getAttribute('data-tela'));
      });
    });
    ligar('btn-selecionar-svg', selecionarSvg);
    ligar('btn-avancar', avancar);
    ligar('btn-abrir-pasta', function () { chamar('abrir_pasta_saida'); });
    ligar('btn-galeria-pasta', function () { chamar('abrir_pasta_saida'); });
    ligar('btn-imagem-fechar', fecharImagem);
    ligar('btn-imagem-anterior', function () { navegarImagem(-1); });
    ligar('btn-imagem-proxima', function () { navegarImagem(1); });
    $('janela-imagem').addEventListener('click', function (ev) { if (ev.target === $('janela-imagem')) fecharImagem(); });
    ligar('btn-atualizar-catalogo', atualizarCatalogo);
    ligar('btn-configuracoes', abrirConfiguracoes);
    ligar('btn-config-fechar', fecharConfiguracoes);
    ligar('btn-config-salvar', salvarConfiguracoes);
    ligar('btn-buscar-blender', function () {
      chamar('buscar_blender').then(function (f) { if (f) $('cfg-blender').value = f; });
    });
    ligar('btn-buscar-catalogo', function () { buscarPasta('cfg-catalogo'); });
    ligar('btn-buscar-resina', function () { buscarPasta('cfg-resina'); });
    ligar('btn-buscar-blend-dir', function () { buscarPasta('cfg-blend-dir', atualizarBlends); });
    ligar('btn-aviso-ok', fecharAviso);
    document.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape') {
        if (!$('janela-aviso').hidden) fecharAviso();
        else if (!$('janela-imagem').hidden) fecharImagem();
        else if (!$('janela-config').hidden) fecharConfiguracoes();
      } else if (!$('janela-imagem').hidden && $('janela-aviso').hidden && (ev.key === 'ArrowLeft' || ev.key === 'ArrowRight')) {
        ev.preventDefault();
        navegarImagem(ev.key === 'ArrowLeft' ? -1 : 1);
      } else if (ev.key === 'Enter' && !$('janela-aviso').hidden) {
        ev.preventDefault();
        fecharAviso();
      }
    });
    window.addEventListener('resize', ajustarLogo);
    mostrarTela('upload');
    var ponte = api();
    if (ponte && typeof ponte.estado_inicial === 'function') iniciar();   // a ponte chegou antes
  });

  window.addEventListener('pywebviewready', iniciar);
})();
