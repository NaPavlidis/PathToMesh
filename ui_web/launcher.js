/* PathToMesh — launcher no visual do app.
   Os botões chamam a ApiLauncher do launcher_web.py (window.pywebview.api.<método>) pela função
   chamar('<método>'). As tarefas rodam no Python numa thread; o resultado chega por
   window.ptmLauncher.evento({...}) (evaluate_js). */
(function () {
  'use strict';

  var $ = function (id) { return document.getElementById(id); };
  var inicio = null;
  var fila = [];                  // avisos esperando a vez (um modal por vez)

  function api() {
    return window.pywebview && window.pywebview.api;
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
        if (p && p.catch) p.catch(function () {});
      }
    } catch (e) { /* sem ponte: nada a fazer */ }
  }

  function chamar(metodo) {
    var ponte = api();
    if (!ponte || typeof ponte[metodo] !== 'function') {
      return Promise.reject(new Error('a ponte com o Python não tem o método ' + metodo));
    }
    return ponte[metodo]().catch(function (erro) {
      registrarErro('erro ao chamar ' + metodo, erro);
      mensagem('Erro ao chamar ' + metodo + ': ' + textoErro(erro));
      return new Promise(function () {});
    });
  }

  window.addEventListener('error', function (ev) { registrarErro('erro de JavaScript', ev.error || ev.message); });
  window.addEventListener('unhandledrejection', function (ev) { registrarErro('promessa sem tratamento', ev.reason); });

  // ------------------------------------------------------------------ modal (confirmação e erro)
  function modal(titulo, texto, tipo, aoSim) {
    fila.push({ titulo: titulo, texto: texto, tipo: tipo || 'aviso', aoSim: aoSim || null });
    if (fila.length === 1) abrirModal();
  }

  function abrirModal() {
    var a = fila[0];
    if (!a) return;
    var caixa = document.querySelector('.modal-aviso');
    caixa.classList.remove('tipo-aviso', 'tipo-erro', 'tipo-info');
    caixa.classList.add('tipo-' + a.tipo);
    var icone = $('aviso-icone');
    icone.querySelector('use').setAttribute('href', a.tipo === 'erro' ? '#i-erro' : '#i-aviso');
    icone.setAttribute('class', 'ic ic-titulo ' + (a.tipo === 'erro' ? 'erro' : 'aviso'));
    $('aviso-titulo').textContent = a.titulo;
    $('aviso-mensagem').textContent = a.texto;
    $('btn-aviso-nao').hidden = !a.aoSim;
    $('btn-aviso-ok').textContent = a.aoSim ? 'Sim' : 'OK';
    $('janela-aviso').hidden = false;
    $('btn-aviso-ok').focus();
  }

  function fecharModal(sim) {
    var a = fila.shift();
    $('janela-aviso').hidden = true;
    if (a && sim && a.aoSim) a.aoSim();
    if (fila.length) abrirModal();
  }

  // ------------------------------------------------------------------ tela
  var ROTULOS = { atualizacao: 'st-atualizacao', dependencias: 'st-dependencias', blender: 'st-blender', logs: 'st-logs' };
  var BOTOES = { atualizar: 'btn-atualizar', abrir: 'btn-abrir' };

  function status(cartao, texto, ok) {
    var el = $(ROTULOS[cartao]);
    if (!el) return;
    var icone = ok === null || ok === undefined ? '' : (ok ? '✅ ' : '⚠ ');
    el.textContent = icone + texto;
    el.classList.remove('suave', 'sucesso', 'aviso');
    el.classList.add(ok === null || ok === undefined ? 'suave' : (ok ? 'sucesso' : 'aviso'));
  }

  function mensagem(texto) {
    var pre = $('txt-mensagens');
    pre.textContent += String(texto).replace(/\s+$/, '') + '\n';
    pre.scrollTop = pre.scrollHeight;
  }

  function ajustarLogo() {
    if (!inicio || !inicio.logos) return;
    var img = $('logo-cabecalho');
    var largo = window.innerWidth >= inicio.limite_logo;
    var fonte = largo ? (inicio.logos.largo || inicio.logos.normal) : (inicio.logos.normal || inicio.logos.largo);
    if (!fonte) { img.hidden = true; $('nome-app').hidden = false; return; }
    if (img.getAttribute('src') !== fonte) img.setAttribute('src', fonte);
    img.classList.toggle('largo', largo && !!inicio.logos.largo);
    img.hidden = false;
    $('nome-app').hidden = true;
  }

  window.ptmLauncher = {
    evento: function (d) {
      try {
        if (d.tipo === 'status') {
          status(d.cartao, d.texto, d.ok);
        } else if (d.tipo === 'versao') {
          $('txt-versao').textContent = d.texto;
        } else if (d.tipo === 'botao') {
          var b = $(BOTOES[d.botao]);
          if (b) {
            b.disabled = !d.ativo;
            if (d.texto) b.textContent = d.texto;
          }
        } else if (d.tipo === 'mensagem') {
          mensagem(d.texto);
        } else if (d.tipo === 'erro') {
          modal(d.titulo, d.mensagem, 'erro');
        }
      } catch (e) {
        registrarErro('erro ao mostrar evento do launcher', e);
      }
      return true;
    }
  };

  function clicarAtualizar() {
    chamar('pode_atualizar').then(function (r) {
      if (!r.ok) return;
      modal('Atualizar', inicio ? inicio.pergunta_atualizar : 'Baixar a versão nova do GitHub agora?', 'aviso',
            function () { chamar('atualizar'); });
    });
  }

  function ligar(id, funcao) {
    $(id).addEventListener('click', function (ev) { ev.preventDefault(); funcao(); });
  }

  function iniciar() {
    if (inicio) return;
    inicio = {};
    chamar('estado_inicial').then(function (e) {
      inicio = e;
      document.title = e.nome_app + ' - Launcher';
      $('nome-app').textContent = e.nome_app;
      $('logo-cabecalho').alt = e.nome_app;
      $('btn-abrir').textContent = e.texto_abrir;
      ajustarLogo();
      chamar('verificar_tudo');
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    ligar('btn-atualizar', clicarAtualizar);
    ligar('btn-procurar', function () { chamar('procurar_atualizacao'); });
    ligar('btn-instalar', function () { chamar('instalar_dependencias'); });
    ligar('btn-blender', function () { chamar('conferir_blender'); });
    ligar('btn-pasta-logs', function () { chamar('abrir_pasta_logs'); });
    ligar('btn-enviar-logs', function () { chamar('enviar_logs'); });
    ligar('btn-abrir', function () { $('btn-abrir').disabled = true; chamar('abrir_app'); });
    ligar('btn-aviso-ok', function () { fecharModal(true); });
    ligar('btn-aviso-nao', function () { fecharModal(false); });
    document.addEventListener('keydown', function (ev) {
      if ($('janela-aviso').hidden) return;
      if (ev.key === 'Escape') fecharModal(false);
      else if (ev.key === 'Enter') { ev.preventDefault(); fecharModal(true); }
    });
    window.addEventListener('resize', ajustarLogo);
    var ponte = api();
    if (ponte && typeof ponte.estado_inicial === 'function') iniciar();
  });

  window.addEventListener('pywebviewready', iniciar);
})();
