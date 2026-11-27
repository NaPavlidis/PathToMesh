# MAPA do PathToMesh

| Arquivo | O que tem | Onde mexer |
|---|---|---|
| `blender_engine.py` | Roda no Blender (`bpy`). `importar_e_converter_svg` (curva -> malha), `aplicar_materiais_e_empilhar` (extrusão, **`tratar_malha_objeto`**, materiais), montagem, câmeras, render | Regras de material: `REGRAS_MATERIAIS`. Tratamento da malha: `_limpar_bm`, `_marcar_arestas_bevel`, `_suavizar_so_curvas`, `tratar_malha_objeto` |
| `malha_logica.py` | Pura (sem bpy): `PADROES`, `LIMITES`, `normalizar`, `para_texto/de_texto`, `limitar_merge_m`, `largura_bevel_m`, `classificar_aresta`, `espessura_efetiva`, `selecionar_arestas_bevel` | Padrões e limites das opções de malha. `tratar` e `arredondar` vêm **desligados por padrão** (único ponto onde o padrão é definido: `PADROES`) |
| `nucleo.py` | `EstadoApp` (config; `opcoes_malha`, chave `malha` no config), `montar_comando_blender` (último argumento = opções da malha) | Argumentos do Blender, config |
| `app_ui.py` | Janela Tk; `SettingsWindow._build_ui`: opções de malha dentro do cartão "Renderização", abaixo das samples (Tratar, Arredondar, bordas, largura) + botão "Avançado" recolhível | Campos de opções |
| `app_web.py` | API da interface web (`configuracoes`/`salvar_configuracoes` levam `malha`) | — |
| `ui_web/index.html`, `app.js` | Mesmas opções no cartão "Renderização" (ids `cfg-malha-*`, `<details class="avancado">`); `CAMPOS_MALHA`, `preencherMalha`, `lerMalha` | Campos da malha na tela web |

`tratar` e `arredondar` (bevel) são independentes e ambos desligados por padrão; só-bevel não faz limpeza/dissolve/normais.

Testes (fora do repo): `python3 -I /root/co/testes/pathtomesh/rodar_todos.py`, `testar_malha.py` e `testar_opcoes_malha.py`. Só no Blender dá para conferir: contagens no log `>>> Malha ...`, bevel nas arestas certas, sombreamento, normais para fora.
