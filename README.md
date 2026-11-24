# Phy-2d-by-3d

Conversão de SVG para 3D.

O app lê os arquivos SVG do catálogo de troféus e identifica o material de cada peça pela cor (acrílico, MDF, base, resina, plotter, adesivo...). Depois o Blender monta e renderiza o modelo 3D.

Para o fluxo completo (entrada, cores e materiais, o que o Blender faz, saída e configuração), veja [docs/RESUMO.md](docs/RESUMO.md).

## Arquivos

| Arquivo | O que faz |
| --- | --- |
| `app_ui.py` | Janela do app (Tkinter): escolhe o catálogo, a cena `.blend` e os modelos, e chama o Blender |
| `blender_engine.py` | Roda dentro do Blender (`bpy`): importa o SVG, aplica materiais e extrusão, configura câmeras e renderiza |
| `mapear_catalogo.py` | Mapeia o catálogo (`CATALOGO/<MODALIDADE>/<MODELO>/SVG/*.svg`) e mostra quais modelos estão prontos |
| `infos_svg.py` | Analisa um SVG e lista as peças e os materiais encontrados |
| `config.json` | Caminhos do Blender, das pastas e da cena, e o número de amostras do Cycles |
| `legado/` | Versão antiga do motor, guardada como referência |

## Como rodar (Windows)

1. Instale o [Blender](https://www.blender.org/) (o `config.json` aponta para a versão 5.2) e o Python 3.
2. Instale a dependência opcional, que melhora a leitura dos caminhos do SVG: `pip install -r requirements.txt`
3. Ajuste os caminhos no `config.json`.
4. Na pasta do projeto, rode `python app_ui.py`.
