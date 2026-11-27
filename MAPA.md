# MAPA do PathToMesh

| Arquivo | O que tem | Onde mexer |
|---|---|---|
| `blender_engine.py` | Roda no Blender (`bpy`). `importar_e_converter_svg` (curva -> malha), `aplicar_materiais_e_empilhar` (extrusão, **`tratar_malha_objeto`**, materiais), montagem, câmeras, render | Regras de material: `REGRAS_MATERIAIS`. Tratamento da malha: `_limpar_bm`, `_marcar_arestas_bevel`, `_suavizar_so_curvas`, `tratar_malha_objeto` |
| `malha_logica.py` | Pura (sem bpy): `PADROES`, `LIMITES`, `normalizar`, `para_texto/de_texto`, `limitar_merge_m`, `largura_bevel_m`, `classificar_aresta` | Padrões e limites das opções de malha |
| `nucleo.py` | `EstadoApp` (config; `opcoes_malha`, chave `malha` no config), `montar_comando_blender` (último argumento = opções da malha) | Argumentos do Blender, config |
| `app_ui.py` | Janela Tk; cartão "Malha 3D" em `SettingsWindow` | Campos de opções |
| `app_web.py` | API da interface web (`configuracoes`/`salvar_configuracoes` levam `malha`) | A tela web ainda não tem campos de malha |

Testes (fora do repo): `python3 -I /root/co/testes/pathtomesh/rodar_todos.py` e `testar_malha.py`. Só no Blender dá para conferir: contagens no log `>>> Malha ...`, bevel nas arestas certas, sombreamento, normais para fora.
