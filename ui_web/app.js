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
      $('proc-historico').textContent = '';
      mostrarTela('processing');
    });
  }

  // ------------------------------------------------------------------ Processing (eventos do Blender)
  function porcentagem(valor) {
    $('proc-barra').style.width = Math.max(0, Math.min(100, valor)) + '%';
    $('proc-porcentagem').textContent = Math.floor(valor) + '%';
  }

  window.ptm = {
    evento: function (d) {
      try {
        if (d.tipo === 'status') {
          $('proc-status').textContent = d.status;
        } else if (d.tipo === 'passo') {
          var li = document.createElement('li');
          li.className = 'body-md';
          li.textContent = d.concluido;
          $('proc-historico').appendChild(li);
          $('proc-status').textContent = d.status;
        } else if (d.tipo === 'amostras') {
          $('proc-status').textContent = d.status;
          $('proc-samples').textContent = d.samples;
          porcentagem(d.porcentagem);
        } else if (d.tipo === 'concluido') {
          $('proc-status').textContent = d.status;
          porcentagem(d.porcentagem);
          $('proc-samples').textContent = d.samples;
          mostrarTela('download');
        } else if (d.tipo === 'erro') {
          mostrarAviso(d.titulo, d.mensagem, 'erro');
        }
      } catch (e) {
        registrarErro('erro ao mostrar evento do Blender', e);
      }
      return true;
    }
  };

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

  function atualizarCatalogo() {
    chamar('relatorio_catalogo').then(function (r) {
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
      $('rodape-texto').textContent = '© 2026 ' + e.nome_app + '. All rights reserved.';
      $('analise-vazia').textContent = e.aguardando;
      $('proc-status').textContent = e.status_inicial;
      $('proc-samples').textContent = e.samples_inicial;
      mostrarResinas(e.resina);
      ajustarLogo();
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
        else if (!$('janela-config').hidden) fecharConfiguracoes();
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
