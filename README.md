# Phy-2d-by-3d

Conversão de SVG para 3D.

O app lê os arquivos SVG do catálogo de troféus e identifica o material de cada peça pela cor de contorno (acrílico, MDF, base, resina, plotter, adesivo...). Depois o Blender monta e renderiza o modelo 3D.

Só vale a cor de contorno **exata** da tabela de materiais (sem diferença entre maiúsculas e minúsculas; `#abc` equivale a `#aabbcc`). Peças com outra cor, ou sem contorno, não são convertidas e somem do 3D. Por isso, ao carregar um SVG, o app mostra um aviso com a quantidade dessas peças e as suas cores/ids.

## Arquivos

| Arquivo | O que faz |
| --- | --- |
| `app_ui.py` | Janela do app (Tkinter): escolhe o catálogo, a cena `.blend` e os modelos, e chama o Blender. As cores, fontes e espaçamentos da janela ficam todos no dicionário `TEMA` (e em `FONTES`/`ESPACO`), aplicados por `aplicar_estilo` |
| `blender_engine.py` | Roda dentro do Blender (`bpy`): importa o SVG, aplica materiais e extrusão, configura câmeras e renderiza |
| `mapear_catalogo.py` | Mapeia o catálogo (`CATALOGO/<MODALIDADE>/<MODELO>/SVG/*.svg`) e mostra quais modelos estão prontos |
| `infos_svg.py` | Analisa um SVG e lista as peças e os materiais encontrados |
| `launcher.py` | Launcher (Tkinter): procura atualização, instala as dependências, confere o Blender, envia os logs de erro e abre o app |
| `launcher.bat` / `launcher.pyw` | Atalhos para abrir o launcher no Windows (com console / sem console) |
| `registro_erros.py` | Grava os logs de erro em `logs/` (sem dados do PC) e envia para a branch `logs` |
| `config.json` | Configuração de partida (caminhos do Blender, das pastas e da cena, e o número de amostras do Cycles). Só serve para criar o `config.local.json` |
| `config.local.json` | A **sua** configuração, a que o app e o launcher usam. Fica só no seu PC (está no `.gitignore` e nunca vai para o GitHub) |
| `legado/` | Versão antiga do motor, guardada como referência |

## Como rodar (Windows)

1. Instale o [Blender](https://www.blender.org/) (o `config.json` aponta para a versão 5.2) e o Python 3.
2. Instale a dependência opcional, que melhora a leitura dos caminhos do SVG: `pip install -r requirements.txt`
3. Ajuste os caminhos nas configurações do app (⚙) ou direto no `config.local.json` (veja abaixo).
4. Abra o **launcher** (veja abaixo) e clique em **Abrir o app**. Também dá para abrir direto com `python app_ui.py`, na pasta do projeto.

## Launcher

Dê dois cliques em `launcher.pyw` (abre sem a janela preta) ou em `launcher.bat` (abre com o console, bom para ver mensagens de erro). Ao abrir, o launcher faz sozinho:

1. **Atualização**: mostra a versão atual (o commit) e se há uma versão nova na `main` do GitHub.
   - Se o git estiver instalado e a pasta for um clone, usa `git fetch`/`git pull`. Só atualiza na branch `main`; em outra branch, ele só avisa.
   - Sem git, compara com o último commit pela API pública do GitHub e baixa o zip da `main`. A versão instalada fica guardada no arquivo `.versao`.
   - Para atualizar, clique em **Atualizar agora**. O seu `config.local.json` nunca é sobrescrito (veja **Configuração**). Depois de atualizar, feche e abra o launcher de novo.
2. **Dependências**: roda `pip install -r requirements.txt`.
3. **Blender**: confere se o `blender_path` do `config.local.json` existe. Se não existir, ajuste nas configurações do app (⚙).
4. **Logs de erro**: envia os logs novos para o GitHub (veja abaixo).

Ao clicar em **Abrir o app**, o app abre como um programa independente e o launcher se fecha sozinho (se ainda estiver terminando uma tarefa, como o pip, ele espera ela acabar). Se o app não abrir, o launcher fica aberto, mostra o erro e grava o log de erro.

## Configuração

A configuração que o app e o launcher usam fica em **`config.local.json`**, na pasta do projeto. Ele está no `.gitignore`: fica só no seu PC e nunca vai para o GitHub (o repositório é público).

- Se o `config.local.json` não existir, o app e o launcher o criam copiando o `config.json`. A partir daí, as configurações do app (⚙) são gravadas só no `config.local.json`, e o `config.json` não é mais mudado.
- Antes de atualizar pelo git, o launcher protege a sua configuração: se o `config.json` tiver mudanças suas e o `config.local.json` ainda não existir, copia o `config.json` para o `config.local.json`, descarta a mudança local do `config.json` (`git checkout`) e só então faz o `git pull`. Se o `config.local.json` já existir e o `config.json` tiver outro conteúdo, este é guardado em `config.json.bak` antes de ser descartado.
- Na atualização pelo zip, o `config.local.json` nunca é sobrescrito.

## Logs de erro

O app e o launcher gravam os erros (exceções, falhas do Blender e do pip) em `logs/erro-AAAAMMDD-HHMMSS.log`, com a versão (commit), o sistema e o traceback.

Como o repositório é público, os logs são higienizados antes de serem gravados: os caminhos do PC (`C:\...`, `F:\...`, a pasta do usuário) viram `<CAMINHO>/<nome-do-arquivo>`, o nome do usuário e do PC vira `<USUARIO>`, e os valores do `config.local.json` (e do `config.json`) viram `<CONFIG>`.

- Com git e uma credencial do GitHub salva no PC, o launcher envia os logs novos para a branch **`logs`** (pasta `logs/` nela). A `main` e a branch em que você está trabalhando não mudam. Os logs já enviados ficam listados em `logs/.enviados`.
- Sem git (ou sem credencial), os logs ficam só no PC. O launcher mostra onde eles estão e tem o botão **Abrir pasta de logs**.

A pasta `logs/` está no `.gitignore` e não entra na `main`.
