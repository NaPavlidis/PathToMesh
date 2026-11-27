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
| `area_transferencia.py` | Copiar e arrastar as imagens da galeria para outros programas no Windows: área de transferência por ctypes (arquivo `CF_HDROP`, bitmap `CF_DIB`/`CF_BITMAP` e PNG) e arrastar de arquivo nativo (`DoDragDrop`) pelo WinForms da janela do pywebview |
| `galeria.py` | Galeria das imagens geradas (pasta `imagens 3d`): lista as imagens com câmera, tamanho, dimensões e data e prepara as miniaturas (reduzidas com o Pillow, se ele estiver instalado, com cache em `.cache_miniaturas/`; senão vai a imagem original, com o tamanho limitado na tela). Mostra só as imagens do render atual (`RenderAtual`: fotografa a pasta no começo e lista as novas ou regravadas). Guarda o último render (pasta, início e nomes das imagens) em `.ultimo_render.json` (no `.gitignore`), para a galeria mostrar só ele ao abrir o app |
| `requirements-base.txt` / `requirements.txt` / `requirements-opcional.txt` | Dependências do Python: o `requirements-base.txt` tem as essenciais (`svgpathtools`); o `requirements.txt` inclui o base e acrescenta o `pywebview` (a janela do app); o `requirements-opcional.txt` tem o `Pillow` (miniaturas leves da galeria), instalado por último e sem impedir o app se falhar |
| `nucleo.py` | A lógica do app, sem interface: análise do SVG e das cores (`MAPA_MATERIAIS`), configuração (`config.local.json`), mapa do catálogo e a chamada do Blender com o progresso. Usada pelas duas interfaces |
| `app_ui.py` | Interface Tkinter do app (a de reserva): escolhe o catálogo, a cena `.blend` e os modelos, e chama o Blender (pelo `nucleo.py`). Usa o `TEMA`/`ESPACO` do `tema_janela.py` e as fontes de `FONTES`, aplicados por `aplicar_estilo` |
| `tema_janela.py` | Visual compartilhado pelo app e pelo launcher: a paleta `TEMA` e os espaços `ESPACO` (tirados do `docs/modelo-layout.html`), a escolha das fontes, os ícones das janelas, o logo do cabeçalho (que muda com a largura da janela) e a barra de título do Windows pintada nas cores do tema (DWM; no Windows 10 fica só o modo escuro) |
| `assets/icones/` | Ícones e logos: `PathToMash-icon` é o ícone principal (janelas, atalhos e instalador); `1` é o logo do cabeçalho do app e do launcher, trocado pelo `2` quando a janela fica larga (veja o `README.md` da pasta) |
| `docs/modelo-layout.html` | Modelo de layout (HTML) que serviu de referência para o visual |
| `blender_engine.py` | Roda dentro do Blender (`bpy`): importa o SVG, aplica materiais e extrusão, configura câmeras e renderiza |
| `malha_logica.py` | Lógica pura (sem `bpy`) do tratamento de malha: opções, padrões, limites e quais arestas recebem bevel. Testável fora do Blender |
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
   - Para atualizar, clique em **Atualizar agora**. O seu `config.local.json` nunca é sobrescrito (veja **Configuração**). Se a atualização mudou arquivos do próprio launcher (`launcher.py`, `launcher_web.py`, `tema_janela.py`, `registro_erros.py`, `app.py`, as telas `ui_web/launcher.*`, `tema.css`/`estilo.css`, as fontes ou os ícones), ao terminar ele mostra **Atualizado, reiniciando…** por ~1 s, abre uma nova instância (o mesmo Python e os mesmos argumentos, sem janela de cmd) e fecha a atual; isso vale também na janela Tkinter de reserva. Se nada do launcher mudou, ele não reinicia. A nova instância recebe `--reiniciado=<commit>`, para não reiniciar de novo pela mesma atualização (no máximo 1 reinício por atualização). Na primeira atualização depois desta mudança, o launcher aberto ainda é o antigo: feche e abra uma vez.
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

## Malha 3D (limpeza, dissolve e bordas arredondadas)

As duas opções principais ficam **no cartão "Renderização" de ⚙ Configurações, logo abaixo da Qtd de Samples** (tela web e tela Tk), e vêm **DESLIGADAS por padrão** (também para configurações salvas antigas):

1. **Tratar a malha** (limpeza, dissolve limitado e normais por ângulo);
2. **Arredondar bordas da base** (bevel leve), com escolha das bordas (topo / base / ambos) e a largura em mm.

**As duas são independentes**: o arredondamento funciona sozinho (sem limpeza, dissolve nem normais) e o tratamento funciona sem o arredondamento. Os ajustes finos (merge, resolução das curvas, dissolve e ângulo, segmentos e peças do bevel, sombreamento suave) ficam em **Avançado**, recolhido por padrão. Tudo é salvo no `config.local.json` (chave `malha`) junto com as demais configurações. Com as duas desligadas, a geração segue o mesmo caminho de antes, sem nenhuma etapa nova. (A chave antiga `bevel` virou `arredondar`; um `bevel: true` salvo antes é ignorado, para não ligar o arredondamento sem o usuário pedir.)

Com o tratamento ligado, depois da conversão do SVG e da extrusão, cada peça passa por ele. Ordem: **limpeza → dissolve limitado → bevel → tampas → normais**.

- **Resolução das curvas** (padrão 24, nunca abaixo da do importador): com poucos pontos no SVG os trechos Bézier são longos e a curva sai facetada.
- **Limpeza**: merge by distance (padrão 0,01 mm, nunca mais que 10% da espessura da peça, para não colapsar peças finas como o PLOTTER), remove faces degeneradas, arestas e pontos soltos e recalcula as normais para fora.
- **Dissolve limitado** (padrão 5°): junta faces quase coplanares sem juntar materiais diferentes nem mexer nas bordas. O log mostra os vértices/faces antes e depois (`>>> Malha <peça>: ...`).
- **Bevel leve** (padrão 0,5 mm, 5 segmentos, limitado a 40% da espessura por lado; peças finas demais pulam): só nas arestas onde a tampa plana encontra a parede, no topo, na base ou nos dois (padrão ambos), por padrão só na peça de base (opção "todas"). Com clamp overlap.
- **Tampas**: n-gons viram triângulos pelo método beauty (sem faces finas e longas).
- **Normais**: sombreamento suave só nas partes curvas (arestas acima de 30° continuam vivas, as faces planas ficam retas), Weighted Normal com keep sharp e harden normals no bevel.
- Cada etapa que falhar avisa no log e a montagem continua. "Tratar a malha" desligado volta ao comportamento anterior (a resolução da curva também).
- O motor recebe as opções como o último argumento da linha de comando (`chave=valor;...`).

## Progresso da renderização

A barra da tela **Processing** mostra o trabalho real do Blender:

- O `blender_engine.py` imprime marcadores, com flush (`PTM_ETAPA <id> <i>/<n> <descrição>`, `PTM_PLANO`, `PTM_PASSADAS principal[,freestyle]`, `PTM_CAMERA <i>/<n> <nome>`, `PTM_SAMPLES <s> <m> <passada> [<restante>]`, `PTM_PASSADA freestyle`, `PTM_CAMERA_FIM`, `PTM_FIM`; e, para o log, `PTM_RENDER_INICIO`/`_POS`/`_FIM` e `PTM_STATS <texto do Cycles>`). As samples vêm dos handlers do render (`render_init`, `render_stats`, `render_post`, `render_complete`), não da saída do Cycles: o Blender 5.3 em `--background` não imprime mais as linhas `... | Sample 37/64`, e o que ele imprime pelo C chega atrasado, em bloco. O Blender roda com `PYTHONUNBUFFERED=1`.
- O que os logs reais (`render-*.log`) mostraram: o `render_stats` só chega com as samples 0, 1 (com o "Remaining" do Cycles) e a última de cada passada, nada no meio (~26 s em 64 samples), e cada câmera tem 2 passadas, a principal e a do **Freestyle** (os contornos, ~6,6 s). Por isso, entre uma sample real e a próxima, a barra anda pelo tempo estimado da passada, com base no ritmo medido (Blender que manda as samples uma a uma), na duração real da mesma passada na câmera anterior, na proporção Freestyle/principal (0,25) ou no "Remaining" do Cycles corrigido (×1,15 na principal, ×2,7 no Freestyle, que ele subestima). A estimativa anda em linha reta até 90% da passada e depois freia, e nunca chega ao fim da passada antes da sample real. Enquanto isso, o estado vai para a tela a cada 0,25 s. A etapa atual mostra as samples estimadas com "~" (ex.: "— ~37/64 samples" ou "— contornos (Freestyle), ~20/64 samples").
- A barra é composta, com pesos proporcionais aos tempos medidos nos logs (`SEG_*` no `nucleo.py`): preparação ~2 s, cada câmera ~0,9 s de preparo + 0,43 s/sample na principal + 0,10 s/sample no Freestyle + 0,3 s para gravar, e finalização ~0,25 s. Com 1 câmera de 64 samples com Freestyle, fica em ~5,4% / 93,9% / 0,7%; com 3 câmeras, ~1,9% / 97,9% / 0,2%. Ela nunca volta e só chega a 100% quando o Blender termina com sucesso. Enquanto o Blender trabalha sem mandar informação e sem estimativa (abrir, carregar os kernels, montar o BVH, gravar a imagem), a barra não avança e fica no modo "trabalhando".
- Animações da tela web (só CSS local, com `transform`/`opacity`): com as samples chegando, o preenchimento tem listras e um brilho passando e desliza até a porcentagem nova (sem pular); no modo "trabalhando", uma faixa vai e volta pelo trilho; ao concluir, a barra fica verde com um brilho curto, sem mudar de tamanho (a tela passa para o Download logo depois, em menos de 1 s); com erro, fica na cor de erro, parada. Quando a etapa demora (preparação, shaders/BVH, denoise, gravação ou mais de ~4 s sem avanço), o ícone principal aparece "respirando" no cartão, com uma bolinha orbitando em volta dele e o nome da etapa embaixo, e some quando o progresso volta a andar. A interface Tkinter não tem essas animações.
- Com **movimento reduzido** (`prefers-reduced-motion`: no Windows, **Configurações > Acessibilidade > Efeitos visuais > Efeitos de animação** desligado; o WebView2 segue essa opção), as animações de feedback continuam (listras da barra, faixa do "trabalhando", bolinha orbitando o logo e o ponto da etapa em andamento), só mais lentas; os enfeites (brilhos e o logo "respirando") ficam desligados. Antes elas eram todas desligadas nesse caso, e era por isso que a barra e o logo ficavam parados em PCs com essa opção desligada.
- A tela mostra a lista de etapas (concluída, em andamento ou pendente), a etapa atual (ex.: "Renderizando câmera 2 de 3 (Camera_Esquerda) — 37/64 samples"), o tempo decorrido e, quando já há dados suficientes, uma estimativa do tempo restante pelo ritmo real das câmeras. Na interface clássica (Tkinter) aparecem a etapa atual, os tempos e a barra.

## Pré-visualização das imagens

- A pré-visualização fica só na tela de conclusão (**Download**). Durante o render, a tela **Processing** mostra apenas a contagem de imagens prontas (ex.: "Imagens prontas: 2 de 3"). Na tela **Download** fica a galeria com **só as imagens geradas no render que acabou de rodar** (na pasta de saída `imagens 3d`, ao lado do SVG), com o nome da câmera, as dimensões, o tamanho e a data. As imagens que já estavam na pasta ficam de fora: quando o render começa, o app fotografa a pasta (nome, data e tamanho de cada imagem) e depois mostra só as novas ou regravadas, com data a partir do início do render. A lista é fechada quando o Blender termina (com sucesso ou com erro: as imagens que saíram antes do erro aparecem).
- O último render fica registrado em `.ultimo_render.json` (fora do git): a pasta, o horário de início e os nomes das imagens dele. Ao abrir o app, a galeria mostra só essas imagens; sem registro (ou com o registro antigo, que só tinha a pasta), ela fica vazia até o próximo render. Escolher outro SVG não muda a galeria (ela continua com o último render).
- Clique numa miniatura para ver a imagem ampliada, sem abrir o Explorer: ← e → (ou os botões) passam para a anterior ou a próxima, e Esc fecha. O botão **Abrir pasta** abre a pasta no Explorer.
- As miniaturas são reduzidas no Python (lado maior de 320 px) quando o **Pillow** está instalado (opcional: o launcher e o instalador instalam pelo `requirements-opcional.txt`). Elas ficam guardadas em `.cache_miniaturas/`, na pasta do programa (fora do git); quando a imagem é regravada (data ou tamanho novos), a miniatura é refeita. Sem o Pillow, a tela recebe a imagem original e limita o tamanho dela. A tela só pede imagens da lista da galeria, nunca de outro caminho.
- Na interface clássica (Tkinter), a tela **Download** mostra a lista com as miniaturas (PNG) e um botão **Abrir imagem** para cada uma.

### Levar as imagens para outros programas (WhatsApp Desktop, Explorer, e-mail)

Só na interface web, no Windows (`area_transferencia.py`):

- **Copiar imagem** (no canto da miniatura, ao passar o mouse, e na imagem ampliada): põe na área de transferência do Windows o **arquivo** real (`CF_HDROP`, com "Preferred DropEffect" = cópia), o **bitmap** (`CF_DIB` pelo Pillow; sem o Pillow, `CF_BITMAP` pelo GDI+ do próprio Windows) e o **PNG** original. Depois é só **Ctrl+V**: no WhatsApp Desktop e no e-mail vira imagem ou anexo; no Explorer, cola o arquivo (cópia; o original não sai do lugar). A transparência vira fundo branco no bitmap.
- **Copiar todas** (no cabeçalho da galeria): copia todas as imagens do render como **arquivos** (`CF_HDROP`). Cola no Explorer, no e-mail e no WhatsApp Desktop (como vários arquivos). Com várias imagens não vai bitmap (a área de transferência só guarda um).
- **Arrastar** a miniatura ou a imagem ampliada para outro programa: o arrasto do HTML é cancelado e o Python começa um arrastar de **arquivo** nativo do Windows (OLE `DoDragDrop` com `CF_HDROP` do arquivo real), pelo WinForms da janela do pywebview (o pythonnet já vem com o pywebview no Windows; nenhuma dependência nova). Se o PC não tiver isso, ou se o arrasto não começar, a tela mostra um aviso para usar **Copiar imagem**.
- A tela só pede essas ações pela chave de uma imagem listada na galeria, nunca por um caminho.

## Fundo translúcido (Windows 11)

Na janela web do app, o fundo da página e o cabeçalho (que têm a mesma cor) ficam levemente translúcidos sobre o efeito **Acrylic** do Windows 11 (o que está atrás da janela, desfocado e escurecido). A página fica com alfa 0.85, então a cor continua praticamente a mesma; cartões, campos e janelas continuam opacos e a legibilidade não muda. As áreas opacas maiores (cartões, menu lateral e janelas) usam a cor `--surface-opaca` / `TEMA['superficie_opaca']` (`#14181C`), o meio-termo (média RGB) entre a superfície (`#181C20`) e a cor do cabeçalho e da barra de título (`#101418`); o launcher e a interface Tk de reserva usam a mesma cor sólida. As janelas do app (configurações, imagem ampliada, avisos) desfocam de leve o app atrás delas (`backdrop-filter`).

- Como é feito (`tema_janela.fundo_translucido_pywebview`): `DwmSetWindowAttribute(DWMWA_SYSTEMBACKDROP_TYPE = 38, Acrylic = 3)` e `DwmExtendFrameIntoClientArea(-1)` no HWND; no WinForms do pywebview, o Form com fundo preto e o WebView2 com `DefaultBackgroundColor` transparente. O `transparent=True` do pywebview não é usado: no Windows ele recorta a janela por cor, sem desfoque.
- Só liga no Windows 11 22H2 (build 22621) ou mais novo e com **Efeitos de transparência** ligado (Personalização > Cores). No Windows 10, sem suporte ou se qualquer passo falhar, tudo é desfeito e fica a cor sólida de sempre. Para desligar à mão, defina a variável de ambiente `PTM_SEM_TRANSPARENCIA=1`.

## Desempenho

- O `svgpathtools` (que puxa o numpy) não é importado ao abrir o app: ele carrega em segundo plano logo depois que a janela aparece, antes de o primeiro SVG ser analisado.
- As telas são seções da mesma página, só mostradas ou escondidas. Ao trocar de tela, a nova entra com um fade e um leve deslize (~220 ms, só `opacity`/`transform`, sem refazer o layout); a anterior some na hora, então nada pisca nem fica por cima. Com movimento reduzido, só o fade. A lista de etapas do Processing só é refeita quando uma etapa muda, e o relatório do Catálogo só é repintado quando o texto muda (a troca de tela não espera o mapeamento do catálogo).
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
