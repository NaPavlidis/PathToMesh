# PathToMesh

Conversão de SVG para 3D. (Antes, o programa e o repositório se chamavam **Phy-2d-by-3d**; o GitHub redireciona os endereços antigos e as instalações antigas continuam funcionando.)

O app lê os arquivos SVG do catálogo de troféus e identifica o material de cada peça pela cor de contorno (acrílico, MDF, base, resina, plotter, adesivo...). Depois o Blender monta e renderiza o modelo 3D.

Só vale a cor de contorno **exata** da tabela de materiais (sem diferença entre maiúsculas e minúsculas; `#abc` equivale a `#aabbcc`). Peças com outra cor, ou sem contorno, não são convertidas e somem do 3D. Por isso, ao carregar um SVG, o app mostra um aviso com a quantidade dessas peças e as suas cores/ids.

## Arquivos

| Arquivo | O que faz |
| --- | --- |
| `app.py` | **Entrada do app** (é o que o launcher abre). Abre a janela web (`app_web.py`); se o pywebview ou o WebView2 não funcionarem, grava um log de erro e abre a interface Tkinter (`app_ui.py`). Com `python app.py --tk`, abre direto a Tkinter |
| `app_web.py` | Janela do app com **pywebview** (WebView2 do Windows): mostra a tela de `ui_web/` e liga os botões à lógica pela classe `Api` (`js_api`). Diálogos de arquivo e pasta nativos; o Blender roda numa thread e as etapas e o progresso chegam à tela por `evaluate_js`; avisos e erros aparecem em janelas (modais) na própria tela |
| `ui_web/` | A tela do app: `index.html`, `estilo.css` e `app.js`, feitos a partir do `docs/modelo-layout.html`. O `tema.css` (cores, fontes, botões e cabeçalho) é carregado pelas duas telas, a do app e a do launcher, para o visual não divergir; as cores são as mesmas do `tema_janela.TEMA` (Tkinter e barra de título do Windows). Funciona offline: sem CDN, ícones em SVG dentro da página e fontes do modelo em `ui_web/fontes/` (Instrument Sans, Red Hat Text e Red Hat Mono, `.ttf` variáveis com a licença SIL OFL nos `*-OFL.txt`; se faltarem, usa a Segoe UI) |
| `galeria.py` | Galeria das imagens geradas (pasta `imagens 3d`): lista as imagens com câmera, tamanho, dimensões e data e prepara as miniaturas (reduzidas com o Pillow, se ele estiver instalado, com cache em `.cache_miniaturas/`; senão vai a imagem original, com o tamanho limitado na tela). Mostra só as imagens do render atual (`RenderAtual`: fotografa a pasta no começo e lista as novas ou regravadas). Guarda o último render (pasta, início e nomes das imagens) em `.ultimo_render.json` (no `.gitignore`), para a galeria mostrar só ele ao abrir o app |
| `requirements-base.txt` / `requirements.txt` / `requirements-opcional.txt` | Dependências do Python: o `requirements-base.txt` tem as essenciais (`svgpathtools`); o `requirements.txt` inclui o base e acrescenta o `pywebview` (a janela do app); o `requirements-opcional.txt` tem o `Pillow` (miniaturas leves da galeria), instalado por último e sem impedir o app se falhar |
| `nucleo.py` | A lógica do app, sem interface: análise do SVG e das cores (`MAPA_MATERIAIS`), configuração (`config.local.json`), mapa do catálogo e a chamada do Blender com o progresso. Usada pelas duas interfaces |
| `app_ui.py` | Interface Tkinter do app (a de reserva): escolhe o catálogo, a cena `.blend` e os modelos, e chama o Blender (pelo `nucleo.py`). Usa o `TEMA`/`ESPACO` do `tema_janela.py` e as fontes de `FONTES`, aplicados por `aplicar_estilo` |
| `tema_janela.py` | Visual compartilhado pelo app e pelo launcher: a paleta `TEMA` e os espaços `ESPACO` (tirados do `docs/modelo-layout.html`), a escolha das fontes, os ícones das janelas, o logo do cabeçalho (que muda com a largura da janela) e a barra de título do Windows pintada nas cores do tema (DWM; no Windows 10 fica só o modo escuro) |
| `assets/icones/` | Ícones e logos: `PathToMash-icon` é o ícone principal (janelas, atalhos e instalador); `1` é o logo do cabeçalho do app e do launcher, trocado pelo `2` quando a janela fica larga (veja o `README.md` da pasta) |
| `docs/modelo-layout.html` | Modelo de layout (HTML) que serviu de referência para o visual |
| `blender_engine.py` | Roda dentro do Blender (`bpy`): importa o SVG, aplica materiais e extrusão, configura câmeras e renderiza |
| `mapear_catalogo.py` | Mapeia o catálogo (`CATALOGO/<MODALIDADE>/<MODELO>/SVG/*.svg`) e mostra quais modelos estão prontos |
| `infos_svg.py` | Analisa um SVG e lista as peças e os materiais encontrados |
| `launcher.py` | Launcher: procura atualização, instala as dependências, confere o Blender, envia os logs de erro e abre o app. Abre no visual novo (`launcher_web.py`); se o `pywebview` ainda não estiver instalado (é o próprio launcher que o instala) ou a janela web falhar, abre a janela Tkinter, com as mesmas funções. `python launcher.py --tk` abre direto a Tkinter |
| `launcher_web.py` | Janela do launcher no visual do app (pywebview): a tela fica em `ui_web/launcher.html`, `ui_web/launcher.js` e `ui_web/launcher.css` (o layout compacto), com o mesmo `tema.css` e `estilo.css` do app, o ícone principal e o logo 1/2 |
| `launcher.bat` / `launcher.pyw` | Atalhos para abrir o launcher no Windows (com console / sem console) |
| `instalar.bat` / `instalar.ps1` | Instalador para Windows (veja **Instalação**). O `.bat` é o que você baixa e roda; ele chama o `.ps1` |
| `registro_erros.py` | Grava os logs de erro em `logs/` (sem dados do PC) e envia para a branch `logs` |
| `config.exemplo.json` | Modelo da configuração, com valores genéricos (caminho do Blender, pastas `C:/Caminho/...`, cena e número de amostras do Cycles). Só serve para criar o `config.local.json` |
| `config.local.json` | A **sua** configuração, a que o app e o launcher usam. Fica só no seu PC (está no `.gitignore` e nunca vai para o GitHub) |
| `legado/` | Versão antiga do motor, guardada como referência |

## Instalação

1. Baixe o instalador: **[instalar.bat](https://github.com/NaPavlidis/PathToMesh/raw/main/instalar.bat)**. Se o navegador mostrar o texto em vez de baixar, clique com o botão direito no link e escolha **Salvar link como...**, ou abra a [página do arquivo](https://github.com/NaPavlidis/PathToMesh/blob/main/instalar.bat) e clique no botão de download (**Download raw file**).
2. Dê dois cliques no `instalar.bat`. Se o Windows mostrar "O Windows protegeu o computador", clique em **Mais informações** e depois em **Executar assim mesmo**.
3. Responda o que ele perguntar (a pasta de instalação; aperte Enter para usar a padrão) e espere o resumo no fim.

O instalador (`instalar.bat`, que roda o `instalar.ps1`) faz sozinho:

- confere se há o **Python 3** (comando `py` ou `python`) e o **Git**. Se faltar algum, instala com o `winget` (`Python.Python.3.14` e `Git.Git`), avisando antes;
- pergunta a pasta de instalação (padrão: `%LOCALAPPDATA%\PathToMesh`) e baixa o programa do GitHub (`git clone`). Se o programa já estiver nessa pasta, só atualiza, sem apagar o seu `config.local.json`. Quem instalou antes da troca de nome tem o programa em `%LOCALAPPDATA%\Phy-2d-by-3d`: nesse caso, o padrão continua sendo essa pasta (só atualiza);
- instala as dependências em duas partes: primeiro as essenciais (`py -m pip install -r requirements-base.txt`: o `svgpathtools`) e depois o `requirements.txt` (acrescenta o `pywebview`, a janela do app). Se só o `pywebview` falhar (por exemplo, o `pythonnet`, de que ele depende no Windows, ainda sem pacote para a versão do Python), avisa que a interface nova não pôde ser instalada e segue: o app abre na versão clássica (Tkinter). Por fim, instala o opcional (`requirements-opcional.txt`: o `Pillow`, que deixa as miniaturas da galeria leves); se ele falhar, só avisa e segue (a galeria usa as imagens originais);
- cria o `config.local.json` a partir do `config.exemplo.json`, se ele ainda não existir, e procura o Blender instalado (em `C:\Program Files\Blender Foundation\Blender *\blender.exe`, usando a versão mais nova). Um `blender_path` que já existe nunca é trocado;
- cria o atalho **PathToMesh** (abre o launcher, com o ícone do programa) na Área de Trabalho e no Menu Iniciar. Os atalhos antigos **Phy-2d-by-3d** que abrem a mesma pasta são trocados pelo novo;
- mostra um resumo do que fez e dos avisos (por exemplo, se não achou o Blender).

Depois é só abrir o atalho **PathToMesh** na Área de Trabalho. Para atualizar, use o botão **Atualizar agora** do launcher (ou rode o instalador de novo).

## Como rodar sem o instalador (Windows)

1. Instale o [Blender](https://www.blender.org/) e o Python 3.
2. Instale as dependências: `pip install -r requirements.txt` (o `pywebview`, para a janela do app, e o `svgpathtools`, que melhora a leitura dos caminhos do SVG). A janela usa o **WebView2**, que já vem no Windows 10 e 11; sem ele (ou sem o `pywebview`), o app abre na interface Tkinter de reserva. Se o `pywebview` não instalar, rode `pip install -r requirements-base.txt` para ter ao menos as essenciais. Opcional: `pip install -r requirements-opcional.txt` (o `Pillow`, para as miniaturas leves da galeria).
3. Ajuste os caminhos nas configurações do app (⚙) ou direto no `config.local.json` (veja abaixo).
4. Abra o **launcher** (veja abaixo) e clique em **Abrir o app**. Também dá para abrir direto com `python app.py`, na pasta do projeto (ou `python app.py --tk` para a interface Tkinter).

## Launcher

Dê dois cliques em `launcher.pyw` (abre sem a janela preta) ou em `launcher.bat` (abre com o console, bom para ver mensagens de erro). O launcher abre no mesmo visual do app (pywebview). Na primeira vez, antes de o `pywebview` ser instalado, ou se a janela web não abrir, ele abre na janela clássica (Tkinter), que faz exatamente as mesmas coisas. Ao abrir, o launcher faz sozinho:

1. **Atualização**: mostra a versão atual (o commit) e se há uma versão nova na `main` do GitHub.
   - Se o git estiver instalado e a pasta for um clone, usa `git fetch`/`git pull`. Só atualiza na branch `main`; em outra branch, ele só avisa.
   - Sem git, compara com o último commit pela API pública do GitHub e baixa o zip da `main`. A versão instalada fica guardada no arquivo `.versao`.
   - Para atualizar, clique em **Atualizar agora**. O seu `config.local.json` nunca é sobrescrito (veja **Configuração**). Depois de atualizar, feche e abra o launcher de novo.
2. **Dependências**: roda o `pip install` em duas partes, como o instalador: primeiro o `requirements-base.txt` (essenciais) e depois o `requirements.txt` (o `pywebview`). Se só o `pywebview` falhar, mostra "A interface nova não pôde ser instalada; o app abre na versão clássica", grava o log de erro e segue; o app abre na interface Tkinter. Depois instala o opcional (`requirements-opcional.txt`, o `Pillow`); se ele falhar, só grava o log e segue, sem mostrar erro: a galeria usa as imagens originais.
3. **Blender**: confere se o `blender_path` do `config.local.json` existe. Se não existir, ajuste nas configurações do app (⚙).
4. **Logs de erro**: envia os logs novos para o GitHub (veja abaixo).

A janela do launcher é pequena, do tamanho do conteúdo (os 4 cartões e o botão **Abrir o app**, que acompanha a largura da janela), e se ajusta ao redimensionar. Os detalhes (o log da atualização e do pip) aparecem num bloco embaixo só enquanto ele trabalha; se a tarefa escreveu alguma mensagem (resultado ou erro), o bloco fica até você clicar em **Ocultar**.

Ao clicar em **Abrir o app**, o launcher roda o `app.py` (na falta dele, o `app_ui.py`) e o app abre como um programa independente e o launcher se fecha sozinho (se ainda estiver terminando uma tarefa, como o pip, ele espera ela acabar). Se o app não abrir, o launcher fica aberto, mostra o erro e grava o log de erro.

## Configuração

A configuração que o app e o launcher usam fica em **`config.local.json`**, na pasta do projeto. Ele está no `.gitignore`: fica só no seu PC e nunca vai para o GitHub (o repositório é público).

- Se o `config.local.json` não existir, o app, o launcher e o instalador o criam copiando o **`config.exemplo.json`** (o modelo, com valores genéricos). As configurações do app (⚙) são gravadas só no `config.local.json`.
- **Quem ainda tem o `config.json` antigo** (de antes do `config.local.json`): se o `config.local.json` não existir, ele nasce do `config.json`, com os seus valores. O `config.json` não é mais usado nem versionado (está no `.gitignore`).
- Antes de atualizar pelo git, o launcher (e o instalador) protegem a sua configuração: se o `config.json` antigo tiver mudanças suas, os valores vão para o `config.local.json` (se ele ainda não existir) ou, se o `config.local.json` já existir e o conteúdo for outro, para o `config.json.bak`. Depois a mudança local do `config.json` é descartada (`git checkout`) e só então é feito o `git pull`. Assim o `git pull` funciona também na atualização que tira o `config.json` do GitHub.
- Na atualização pelo zip, o `config.local.json` (e um `config.json` antigo) nunca são sobrescritos.

## Progresso da renderização

A barra da tela **Processing** mostra o trabalho real do Blender:

- O `blender_engine.py` imprime marcadores (`PTM_ETAPA <id> <i>/<n> <descrição>`, `PTM_PLANO`, `PTM_CAMERA <i>/<n> <nome>`, `PTM_CAMERA_FIM`, `PTM_FIM`, `PTM_STATS <texto do Cycles>`). As samples de cada câmera vêm do próprio Cycles: o Blender 5.3 em `--background` não imprime mais as linhas `... | Sample 37/64`, então o motor registra um handler `render_stats` durante o render e repassa esse texto como `PTM_STATS` (com flush; o que o Blender imprime pelo C chega atrasado, em bloco).
- A barra é composta (pesos no `nucleo.py`, calibrados com os logs `render-*.log`): preparação 10% (inclui abrir o Blender), render das câmeras 89% (dividido entre as câmeras, que usam as mesmas samples) e finalização 1%. Ela nunca volta e só chega a 100% quando o Blender termina com sucesso. Enquanto o Blender trabalha sem mandar informação (carregar os kernels, montar o BVH, denoise, gravar a imagem), a barra não avança e fica no modo "trabalhando".
- Animações da tela web (só CSS local, com `transform`/`opacity`): com as samples chegando, o preenchimento tem listras e um brilho passando e desliza até a porcentagem nova (sem pular); no modo "trabalhando", uma faixa vai e volta pelo trilho; ao concluir, a barra fica verde com um brilho curto, sem mudar de tamanho (a tela passa para o Download logo depois, em menos de 1 s); com erro, fica na cor de erro, parada. Quando a etapa demora (preparação, shaders/BVH, denoise, gravação ou mais de ~4 s sem avanço), o ícone principal aparece "respirando" no cartão, com uma bolinha orbitando em volta dele e o nome da etapa embaixo, e some quando o progresso volta a andar. A interface Tkinter não tem essas animações.
- Com **movimento reduzido** (`prefers-reduced-motion`: no Windows, **Configurações > Acessibilidade > Efeitos visuais > Efeitos de animação** desligado; o WebView2 segue essa opção), as animações de feedback continuam (listras da barra, faixa do "trabalhando", bolinha orbitando o logo e o ponto da etapa em andamento), só mais lentas; os enfeites (brilhos e o logo "respirando") ficam desligados. Antes elas eram todas desligadas nesse caso, e era por isso que a barra e o logo ficavam parados em PCs com essa opção desligada.
- A tela mostra a lista de etapas (concluída, em andamento ou pendente), a etapa atual (ex.: "Renderizando câmera 2 de 3 (Camera_Esquerda) — 37/64 samples"), o tempo decorrido e, quando já há dados suficientes, uma estimativa do tempo restante pelo ritmo real das câmeras. Na interface clássica (Tkinter) aparecem a etapa atual, os tempos e a barra.

## Pré-visualização das imagens

- A pré-visualização fica só na tela de conclusão (**Download**). Durante o render, a tela **Processing** mostra apenas a contagem de imagens prontas (ex.: "Imagens prontas: 2 de 3"). Na tela **Download** fica a galeria com **só as imagens geradas no render que acabou de rodar** (na pasta de saída `imagens 3d`, ao lado do SVG), com o nome da câmera, as dimensões, o tamanho e a data. As imagens que já estavam na pasta ficam de fora: quando o render começa, o app fotografa a pasta (nome, data e tamanho de cada imagem) e depois mostra só as novas ou regravadas, com data a partir do início do render. A lista é fechada quando o Blender termina (com sucesso ou com erro: as imagens que saíram antes do erro aparecem).
- O último render fica registrado em `.ultimo_render.json` (fora do git): a pasta, o horário de início e os nomes das imagens dele. Ao abrir o app, a galeria mostra só essas imagens; sem registro (ou com o registro antigo, que só tinha a pasta), ela fica vazia até o próximo render. Escolher outro SVG não muda a galeria (ela continua com o último render).
- Clique numa miniatura para ver a imagem ampliada, sem abrir o Explorer: ← e → (ou os botões) passam para a anterior ou a próxima, e Esc fecha. O botão **Abrir pasta** abre a pasta no Explorer.
- As miniaturas são reduzidas no Python (lado maior de 320 px) quando o **Pillow** está instalado (opcional: o launcher e o instalador instalam pelo `requirements-opcional.txt`). Elas ficam guardadas em `.cache_miniaturas/`, na pasta do programa (fora do git); quando a imagem é regravada (data ou tamanho novos), a miniatura é refeita. Sem o Pillow, a tela recebe a imagem original e limita o tamanho dela. A tela só pede imagens da lista da galeria, nunca de outro caminho.
- Na interface clássica (Tkinter), a tela **Download** mostra a lista com as miniaturas (PNG) e um botão **Abrir imagem** para cada uma.

## Desempenho

- O `svgpathtools` (que puxa o numpy) não é importado ao abrir o app: ele carrega em segundo plano logo depois que a janela aparece, antes de o primeiro SVG ser analisado.
- As telas são seções da mesma página, só mostradas ou escondidas. A lista de etapas do Processing só é refeita quando uma etapa muda, e o relatório do Catálogo só é repintado quando o texto muda (a troca de tela não espera o mapeamento do catálogo).
- Os eventos de progresso do Blender que chegam juntos viram um só (cada um já traz o estado inteiro), para a tela não ficar para trás quando o Cycles manda muitas linhas por segundo.
- O logo do cabeçalho é lido do disco uma vez só.

## Sem janelas de cmd

O Blender, o `pip` (no launcher) e o `git` rodam sem abrir a janela preta do cmd no Windows (`CREATE_NO_WINDOW` e, quando o programa não tem janela própria, `startupinfo` com `SW_HIDE`; veja `registro_erros.opcoes_sem_janela`). A saída deles continua capturada para o progresso e os logs. O render automático usa o Blender em `--background`; no modo interativo (sem **Renderizar automaticamente**) a janela do próprio Blender continua abrindo.

## Logs de erro

O app e o launcher gravam os erros (exceções, falhas do Blender e do pip) em `logs/erro-AAAAMMDD-HHMMSS.log`, com a versão (commit), o sistema e o traceback.

A cada renderização, o app grava também `logs/render-AAAAMMDD-HHMMSS.log`: a saída do Blender com o horário de cada linha e o tempo de cada etapa. Ele é higienizado e enviado do mesmo jeito que os logs de erro e serve para ajustar os pesos da barra de progresso com dados reais.

Como o repositório é público, os logs são higienizados antes de serem gravados: os caminhos do PC (`C:\...`, `F:\...`, a pasta do usuário) viram `<CAMINHO>/<nome-do-arquivo>`, o nome do usuário e do PC vira `<USUARIO>`, e os valores do `config.local.json` (e do `config.json` antigo, se ainda existir) viram `<CONFIG>`.

- Com git e uma credencial do GitHub salva no PC, o launcher envia os logs novos para a branch **`logs`** (pasta `logs/` nela). A `main` e a branch em que você está trabalhando não mudam. Os logs já enviados ficam listados em `logs/.enviados`.
- Sem git (ou sem credencial), os logs ficam só no PC. O launcher mostra onde eles estão e tem o botão **Abrir pasta de logs**.

A pasta `logs/` está no `.gitignore` e não entra na `main`.
