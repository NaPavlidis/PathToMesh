# Resumo do projeto Phy-2d-by-3d

Este documento explica, do começo ao fim, o que o projeto faz: o que entra, como as cores do desenho viram materiais, o que o Blender faz e o que sai no final.

## Visão geral em uma frase

Você escolhe o **SVG de um troféu** (desenhado no CorelDRAW, com cada peça contornada por uma cor-código). O app **lê as cores**, entrega o arquivo ao **Blender**, e o Blender monta o troféu em 3D (peças com espessura, de pé sobre a base, com materiais realistas) e **renderiza fotos PNG** de até 3 ângulos.

```
SVG do catálogo ──► app_ui.py (janela) ──► blender.exe --python blender_engine.py ──► PNGs em "imagens 3d"
                     │                        │
                     └ análise rápida         └ importa, extruda, empilha, ergue,
                       (materiais e medidas)    aplica materiais, câmeras, render
```

## 1. Entrada: os SVGs do catálogo

O catálogo fica numa pasta do Windows (`catalogo_dir` no `config.json`) com esta estrutura:

```
CATALOGO/
  KART/                 ← modalidade
    KAR25001/           ← modelo (código)
      SVG/
        KAR25001.svg    ← o desenho do troféu
        KAR25001_Images/  (opcional: imagens dos adesivos)
```

- A tela **📊 Catálogo** do app (e o script `mapear_catalogo.py`) varre essa estrutura e mostra, por modalidade, quais modelos estão "prontos". Um modelo conta como pronto quando tem pelo menos um `.svg` na subpasta `SVG`. É só um relatório: o render não sai daí.
- Para renderizar, o SVG é escolhido **um de cada vez** na tela **Upload** ("Selecionar Arquivo SVG").
- Imagens de adesivo: se o SVG tiver imagens (`<image>`), o motor procura os arquivos na pasta `<nome do svg>__Images` ou `<nome do svg>_Images`, ao lado do SVG.

## 2. Como as cores viram materiais

Cada peça do desenho é identificada pela **cor do contorno (stroke)**. A cor de **preenchimento (fill)** define a cor que a peça vai ter no render.

| Cor do contorno | Tipo | Material | Espessura no 3D |
| --- | --- | --- | --- |
| `#ed3237` | ACRILICO | acrilico_padrão | 1 mm |
| `#fff212` | ACRILICO | Acrilico_transparente | 1 mm |
| `#d2ae6d` | ACRILICO | Acrilico_Dourado | 1 mm |
| `#9d98ca` | ACRILICO_GRAVADO | Acrilico_Gravado | 0,1 mm (fosco, imita a gravação a laser) |
| `#fefefe` | MDF | MDF_3mm | 3 mm |
| `#e6e7e8` | MDF | MDF_6mm | 6 mm |
| `#d2d3d5` | MDF | MDF_9mm | 9 mm |
| `#00afef` | MDF_COSTAS | MDF_Costas_3mm | 3 mm (placa de trás) |
| `#f58634` | BASE | Base_3MM | 3 mm |
| `#3e4095` | BASE | Base_6MM | 9 mm |
| `#f7adaf` | BASE | Base_9MM | 15 mm |
| `#84716b` | BASE | Base_12MM | 25 mm |
| `#373435` | PLOTTER | PLOTTER | 0,1 mm |
| `#ec268f` | ADESIVO | Adesivo_Padrao | 0,5 mm (recebe a imagem do adesivo) |
| `#00a859` | RESINA (no app) / RESINA_AREA (no motor) | Área da resina 3D | sem espessura: só marca o lugar da peça de resina |

> As espessuras das bases no 3D (9, 15 e 25 mm) não batem com os nomes (6, 9 e 12 mm). É assim que está no `blender_engine.py` (`REGRAS_MATERIAIS`), provavelmente para a base parecer mais robusta no render.

Onde essa tabela mora no código:
- `app_ui.py` e `infos_svg.py` → `MAPA_MATERIAIS` (só nome e tipo, para a análise na tela).
- `blender_engine.py` → `REGRAS_MATERIAIS` (nome, tipo, espessura, rugosidade, transmissão e IOR, que é o que vale no render).

As duas tabelas precisam ter as mesmas cores. **Para criar um material novo, é preciso acrescentar a cor nos dois lugares.**

Diferenças entre a análise (app) e o render (Blender):
- **Na análise do app**, vale o stroke e, sem stroke, o fill, inclusive vindo de classes CSS do CorelDRAW. Se a cor não for exata, o app aceita a cor da tabela mais próxima (distância RGB menor que 45). Se nenhuma estiver perto, a peça aparece como `OUTRO`.
- **No render**, vale só o **stroke**, e a cor tem que ser **exata**. Peça sem contorno, ou com uma cor de contorno fora da tabela, **é descartada** e não aparece no 3D.
- Fill vazio ou branco: MDF, costas e base ficam com cor de madeira crua (`#5c4033`); as outras peças ficam pretas.

## 3. O que o Blender faz

O app roda o Blender assim (em segundo plano, se "Renderizar automaticamente" estiver marcado):

```
blender.exe --background --python blender_engine.py -- <svg> <pasta de saída> <cena .blend> <renderizar> <textura> <samples> <verniz> <modelo resina> <câmeras>
```

Passo a passo dentro do `blender_engine.py`:

1. **Abre a cena base** (`.blend` escolhido nas configurações: estúdio, luz, HDRI) e ajusta o mapeamento do HDRI.
2. **Prepara o SVG**: lê as cores de cada peça, descarta o que não tem contorno conhecido, remove imagens e máscaras e grava um `temp_import.svg` provisório na pasta do SVG (apagado depois).
3. **Importa** o SVG como curvas e converte tudo em malhas.
4. **Ordena** as peças: primeiro as bases, depois o resto, na ordem do desenho.
5. **Empilha e extruda**: cada peça "cai" sobre a que está embaixo (por raio) e ganha a espessura do material.
6. **Aplica os materiais**:
   - MDF, costas e base: textura procedural de madeira, se "Aplicar texturas" estiver marcado. Com "Aplicar Verniz", a madeira fica brilhante.
   - Acrílico: material brilhante (Glossy) com a cor do preenchimento.
   - Acrílico gravado: fosco, esbranquiçado, com micro-relevo.
   - Adesivo: recebe as imagens da pasta `_Images`, escurecidas, ou a cor do preenchimento.
7. **Ergue o troféu**: o corpo (MDF e acrílicos que não estão apoiados na base) gira 90° e fica de pé sobre a base, que continua deitada.
8. **Posiciona as costas** (`MDF_COSTAS`) atrás do corpo.
9. **Encaixa a resina 3D** (opcional): se você escolheu um modelo `.obj`, `.fbx`, `.stl` ou `.blend` da pasta de resina e o SVG tem a área verde `#00a859`, o modelo é importado, redimensionado e colocado nessa área (deitado, se estiver sobre a base, ou de pé, se não estiver).
10. **Cria 3 câmeras** enquadrando o troféu: `Camera_Principal` (de frente), `Camera_Esquerda` e `Camera_Direita` (35° para cada lado).
11. **Renderiza** no Cycles (CPU, com denoise), em 1080×1350, com o número de samples do `config.json`, só nas câmeras marcadas.

Durante o processo, o motor imprime mensagens (`>>> Aplicando materiais...`, `[SAMPLE_PROGRESS] ...`) que o app lê para atualizar a barra de progresso.

## 4. O que sai no final

- Uma imagem **PNG por câmera** marcada: `Camera_Principal.png`, `Camera_Esquerda.png`, `Camera_Direita.png`.
- As imagens ficam em **`<pasta do SVG>\imagens 3d\`**, criada automaticamente. Um novo render sobrescreve os PNGs anteriores.
- Na tela final, o botão "Abrir Pasta de Imagens / Arquivos" abre essa pasta.
- O motor **não salva um `.blend`** do troféu montado. Para mexer na montagem, desmarque "Renderizar automaticamente": o Blender abre com a janela normal e o troféu montado fica na tela, sem render.

## 5. O que precisa estar instalado e configurado

Instalado no PC (Windows):
- **Blender 5.2**, com o importador de SVG (`import_curve.svg`) disponível. O `config.json` aponta para `C:/Program Files/Blender Foundation/Blender 5.2/blender.exe`.
- **Python 3** com Tkinter (já vem no instalador oficial do python.org).
- Opcional: `pip install -r requirements.txt` (instala o `svgpathtools`, que melhora a medição de largura e altura na análise do app). O render não depende dele.

Configurado no `config.json`, ou pela engrenagem ⚙ do app, que grava no mesmo arquivo:

| Chave | Para que serve |
| --- | --- |
| `blender_path` | Caminho do `blender.exe` |
| `catalogo_dir` | Pasta raiz do catálogo (para a tela 📊 Catálogo) |
| `blend_dir` | Pasta com as cenas de estúdio `.blend` |
| `selected_blend` | Qual cena `.blend` usar |
| `resina_dir` | Pasta com os modelos 3D de resina (`.obj`, `.fbx`, `.stl`, `.blend`) |
| `cycles_samples` | Qualidade do render (mais samples = mais lento e mais limpo) |

Cuidados:
- Rode o app **de dentro da pasta do projeto** (`python app_ui.py`). O `config.json` é lido e gravado na pasta atual, e o app procura o `blender_engine.py` ao lado do `app_ui.py`.
- O render é forçado em **CPU**, então pode demorar com muitos samples.
- No SVG, cada peça precisa ter **contorno com uma das cores da tabela**, senão não aparece no 3D.

## 6. Outros arquivos

- `infos_svg.py`: versão de terminal da análise do app (materiais, quantidades e medidas da maior peça). O caminho do SVG está fixo no topo do arquivo (`CAMINHO_TROFÉUS`).
- `mapear_catalogo.py`: versão de terminal do relatório do catálogo.
- `legado/blender_engine_antigo.py`: motor antigo, guardado só como referência (o app não usa).
