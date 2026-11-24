# Instalador do PathToMesh para Windows (PowerShell 5.1 ou mais novo).
# Normalmente é aberto pelo instalar.bat (dois cliques). Este arquivo fica em UTF-8 com BOM,
# para o PowerShell 5.1 ler os acentos certo.
#
# O que faz:
#   1. confere o Python 3 (py ou python) e o Git; se faltar, instala com o winget;
#   2. pergunta a pasta (padrão %LOCALAPPDATA%\PathToMesh; se o programa já estiver instalado na
#      pasta do nome antigo, %LOCALAPPDATA%\Phy-2d-by-3d, o padrão é ela) e clona o repositório
#      público, ou só atualiza se a pasta já existir (o config.local.json nunca é apagado);
#   3. instala as dependências (pip install -r requirements.txt: svgpathtools e pywebview, a
#      janela do app; sem o pywebview ou o WebView2, o app abre na interface Tkinter de reserva);
#   4. cria o config.local.json a partir do config.exemplo.json, se faltar, e procura o Blender;
#   5. cria os atalhos do launcher na Área de Trabalho e no Menu Iniciar (com o ícone do
#      PathToMesh; os atalhos com o nome antigo que apontam para a mesma pasta são trocados)
#      e mostra um resumo.

$ErrorActionPreference = 'Continue'     # os erros dos programas (git, pip) são vistos pelo código de saída
# O repositório se chamava Phy-2d-by-3d: o GitHub redireciona o endereço antigo para o novo
$RepoUrl = 'https://github.com/NaPavlidis/PathToMesh.git'
$NomeApp = 'PathToMesh'
$NomeAntigo = 'Phy-2d-by-3d'
$IconeAtalho = 'assets\icones\3.ico'     # ícone principal do PathToMesh

try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'

$Resumo = New-Object System.Collections.Generic.List[string]
$Avisos = New-Object System.Collections.Generic.List[string]

function Titulo($texto) {
    Write-Host ''
    Write-Host "== $texto ==" -ForegroundColor Cyan
}

function Certo($texto) {
    Write-Host "   [OK] $texto" -ForegroundColor Green
}

function Avisar($texto) {
    Write-Host "   [!] $texto" -ForegroundColor Yellow
    $script:Avisos.Add($texto)
}

function Fechar($codigo) {
    Write-Host ''
    Read-Host 'Aperte Enter para fechar esta janela' | Out-Null
    exit $codigo
}

function Parar($texto) {
    Write-Host ''
    Write-Host "ERRO: $texto" -ForegroundColor Red
    Write-Host 'A instalação não terminou. Corrija o problema acima e rode o instalador de novo.' -ForegroundColor Red
    Fechar 1
}

function Atualizar-Path {
    # Depois do winget, o PATH novo só vale para janelas novas: lê de novo do registro
    $maquina = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $usuario = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = (@($maquina, $usuario) | Where-Object { $_ }) -join ';'
}

function Instalar-ComWinget($id, $nome, $site) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Parar "O $nome não está instalado e este Windows não tem o winget para instalar sozinho. Instale o $nome pelo site $site e rode o instalador de novo."
    }
    Write-Host "   O $nome não foi encontrado. Vou instalar agora com o winget." -ForegroundColor Yellow
    Write-Host '   Isso pode demorar alguns minutos, e o Windows pode pedir permissão (clique em Sim).' -ForegroundColor Yellow
    & winget install --id $id -e --source winget --accept-package-agreements --accept-source-agreements
    $codigo = $LASTEXITCODE
    Atualizar-Path
    if ($codigo -ne 0) {
        Write-Host "   O winget terminou com o código $codigo. Vou conferir se o $nome ficou instalado mesmo assim..." -ForegroundColor Yellow
    }
}

# ---------------------------------------------------------------- Python

function Testar-Python($exe, $extras) {
    try {
        $saida = & $exe @extras -c 'import sys; print(sys.version_info[0])' 2>$null
        return ($LASTEXITCODE -eq 0 -and ("$saida").Trim() -eq '3')
    } catch {
        return $false
    }
}

function Achar-Python {
    # Devolve @{Exe=...; Extras=@(...)} ou $null. O "python" da Microsoft Store (atalho vazio) não conta.
    $candidatos = @()
    if (Get-Command py -ErrorAction SilentlyContinue) { $candidatos += , @('py', @('-3')) }
    if (Get-Command python -ErrorAction SilentlyContinue) { $candidatos += , @('python', @()) }
    $locais = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Launcher\py.exe'),
        (Join-Path $env:SystemRoot 'py.exe')
    )
    foreach ($l in $locais) { if (Test-Path -LiteralPath $l) { $candidatos += , @($l, @('-3')) } }
    $pastas = @(Get-ChildItem -Path (Join-Path $env:LOCALAPPDATA 'Programs\Python') -Directory -Filter 'Python3*' -ErrorAction SilentlyContinue) +
              @(Get-ChildItem -Path $env:ProgramFiles -Directory -Filter 'Python3*' -ErrorAction SilentlyContinue)
    foreach ($p in ($pastas | Where-Object { $_ } | Sort-Object Name -Descending)) {
        $exe = Join-Path $p.FullName 'python.exe'
        if (Test-Path -LiteralPath $exe) { $candidatos += , @($exe, @()) }
    }
    foreach ($c in $candidatos) {
        if (Testar-Python $c[0] $c[1]) { return @{ Exe = $c[0]; Extras = $c[1] } }
    }
    return $null
}

# ---------------------------------------------------------------- Git

function Achar-Git {
    if (Get-Command git -ErrorAction SilentlyContinue) { return 'git' }
    foreach ($l in @((Join-Path $env:ProgramFiles 'Git\cmd\git.exe'), (Join-Path $env:LOCALAPPDATA 'Programs\Git\cmd\git.exe'))) {
        if (Test-Path -LiteralPath $l) {
            $env:Path = (Split-Path $l -Parent) + ';' + $env:Path
            return $l
        }
    }
    return $null
}

# ---------------------------------------------------------------- configuração antes do git pull

function Proteger-Config($pasta) {
    # Mesma proteção do launcher: os valores do usuário no config.json antigo nunca se perdem,
    # e o git pull não trava por causa dele (nem quando o GitHub apagou o config.json).
    $base = Join-Path $pasta 'config.json'
    $local = Join-Path $pasta 'config.local.json'
    if ((Test-Path -LiteralPath $base) -and -not (Test-Path -LiteralPath $local)) {
        Copy-Item -LiteralPath $base -Destination $local
        Certo 'Os seus valores do config.json foram copiados para o config.local.json.'
    }
    & git -C $pasta ls-files --error-unmatch -- config.json *> $null
    if ($LASTEXITCODE -ne 0) { return }          # config.json não é versionado: nada a fazer
    & git -C $pasta diff --quiet HEAD -- config.json *> $null
    if ($LASTEXITCODE -eq 0) { return }          # sem mudanças locais
    if ((Test-Path -LiteralPath $base) -and (Test-Path -LiteralPath $local)) {
        if ((Get-FileHash -LiteralPath $base).Hash -ne (Get-FileHash -LiteralPath $local).Hash) {
            Copy-Item -LiteralPath $base -Destination (Join-Path $pasta 'config.json.bak') -Force
            Certo 'O config.json alterado foi guardado em config.json.bak.'
        }
    }
    & git -C $pasta checkout HEAD -- config.json *> $null
}

function Parece-OPrograma($pasta) {
    return ((Test-Path -LiteralPath (Join-Path $pasta 'app_ui.py')) -and (Test-Path -LiteralPath (Join-Path $pasta 'launcher.py')))
}

function Pasta-Vazia($pasta) {
    return (-not (Get-ChildItem -LiteralPath $pasta -Force -ErrorAction SilentlyContinue | Select-Object -First 1))
}

function Clonar-OuAtualizar($pasta) {
    if (Test-Path -LiteralPath (Join-Path $pasta '.git')) {
        Write-Host "   A pasta já tem o programa. Vou só atualizar (a sua configuração não é apagada)."
        $ramo = (& git -C $pasta rev-parse --abbrev-ref HEAD 2>$null | Out-String).Trim()
        if ($ramo -ne 'main') {
            Avisar "A pasta está na branch '$ramo', não na main. Não atualizei o programa."
            $script:Resumo.Add("Programa: não atualizado (branch '$ramo')")
            return
        }
        Proteger-Config $pasta
        & git -C $pasta pull --ff-only origin main
        if ($LASTEXITCODE -ne 0) {
            Avisar 'O git não conseguiu atualizar o programa (veja a mensagem acima). Continuei com a versão que já estava na pasta.'
            $script:Resumo.Add('Programa: já estava instalado (não deu para atualizar)')
        } else {
            Certo 'Programa atualizado.'
            $script:Resumo.Add('Programa: atualizado')
        }
        return
    }
    if ((Test-Path -LiteralPath $pasta) -and -not (Pasta-Vazia $pasta)) {
        # Instalado antes sem git (zip): vira um clone, mantendo config.local.json, logs etc.
        if (-not (Parece-OPrograma $pasta)) {
            Parar "A pasta '$pasta' já existe e tem outros arquivos. Rode o instalador de novo e escolha outra pasta."
        }
        Write-Host '   A pasta já tem o programa (sem git). Vou ligá-la ao GitHub e atualizar.'
        Proteger-Config $pasta
        & git -C $pasta init -q
        & git -C $pasta remote remove origin *> $null
        & git -C $pasta remote add origin $RepoUrl
        & git -C $pasta fetch origin main
        if ($LASTEXITCODE -ne 0) { Parar 'Não deu para baixar o programa do GitHub. Confira a internet e tente de novo.' }
        & git -C $pasta checkout -f -B main origin/main
        if ($LASTEXITCODE -ne 0) { Parar 'Não deu para atualizar os arquivos do programa na pasta.' }
        & git -C $pasta branch --set-upstream-to=origin/main main *> $null
        Certo 'Programa atualizado.'
        $script:Resumo.Add('Programa: atualizado (a pasta agora é atualizada pelo git)')
        return
    }
    Write-Host "   Baixando o programa do GitHub para $pasta ..."
    & git clone $RepoUrl $pasta
    if ($LASTEXITCODE -ne 0) { Parar 'Não deu para baixar o programa do GitHub. Confira a internet e tente de novo.' }
    Certo 'Programa baixado.'
    $script:Resumo.Add('Programa: instalado agora')
}

# ---------------------------------------------------------------- atalhos

function Criar-Atalho($arquivo, $alvo, $argumentos, $pasta) {
    $shell = New-Object -ComObject WScript.Shell
    $atalho = $shell.CreateShortcut($arquivo)
    $atalho.TargetPath = $alvo
    $atalho.Arguments = $argumentos
    $atalho.WorkingDirectory = $pasta
    $atalho.Description = 'Abre o launcher do PathToMesh'
    $icone = Join-Path $pasta $IconeAtalho
    if (Test-Path -LiteralPath $icone) { $atalho.IconLocation = "$icone,0" }
    $atalho.Save()
}

function Remover-AtalhoAntigo($arquivo, $pasta) {
    # Atalho com o nome antigo (Phy-2d-by-3d.lnk): só é apagado se abrir esta mesma pasta,
    # para não ficarem dois atalhos do mesmo programa. Devolve $true se apagou.
    if (-not (Test-Path -LiteralPath $arquivo)) { return $false }
    try {
        $shell = New-Object -ComObject WScript.Shell
        $antigo = $shell.CreateShortcut($arquivo)
        $pastaAtalho = ("" + $antigo.WorkingDirectory).TrimEnd('\')
        if ($pastaAtalho -and ($pastaAtalho -ieq $pasta.TrimEnd('\'))) {
            Remove-Item -LiteralPath $arquivo -Force
            return $true
        }
    } catch { }
    return $false
}

# ================================================================ início

try {
    Clear-Host
    Write-Host '=============================================' -ForegroundColor Cyan
    Write-Host '   Instalador do PathToMesh' -ForegroundColor Cyan
    Write-Host '=============================================' -ForegroundColor Cyan

    # 1. Python
    Titulo '1/6  Python 3'
    $py = Achar-Python
    if (-not $py) {
        Instalar-ComWinget 'Python.Python.3.14' 'Python 3' 'https://www.python.org/downloads/'
        $py = Achar-Python
        if (-not $py) { Parar 'O Python 3 ainda não foi encontrado. Feche esta janela, abra o instalador de novo e, se continuar, instale o Python pelo site https://www.python.org/downloads/.' }
    }
    $pyArgs = @($py.Extras)              # ex.: -3 para o py; nada para o python
    $versaoPy = (& $py.Exe @pyArgs -c 'import platform; print(platform.python_version())' 2>$null | Out-String).Trim()
    Certo "Python $versaoPy ($($py.Exe))"
    $Resumo.Add("Python: $versaoPy")

    # 2. Git
    Titulo '2/6  Git'
    $git = Achar-Git
    if (-not $git) {
        Instalar-ComWinget 'Git.Git' 'Git' 'https://git-scm.com/download/win'
        $git = Achar-Git
        if (-not $git) { Parar 'O Git ainda não foi encontrado. Feche esta janela, abra o instalador de novo e, se continuar, instale o Git pelo site https://git-scm.com/download/win.' }
    }
    $versaoGit = (& git --version 2>$null | Out-String).Trim()
    Certo $versaoGit
    $Resumo.Add("Git: $versaoGit")

    # 3. Pasta e programa
    Titulo '3/6  Pasta de instalação'
    $padrao = Join-Path $env:LOCALAPPDATA $NomeApp
    $padraoAntigo = Join-Path $env:LOCALAPPDATA $NomeAntigo
    if (-not (Test-Path -LiteralPath $padrao) -and (Parece-OPrograma $padraoAntigo)) {
        # Instalado antes da troca de nome: continua na mesma pasta (só atualiza)
        $padrao = $padraoAntigo
        Write-Host "   O programa já está instalado na pasta do nome antigo ($NomeAntigo). Ela continua sendo usada."
    }
    Write-Host '   Onde instalar o programa?'
    Write-Host "   Aperte Enter para usar a pasta padrão: $padrao"
    $resposta = Read-Host '   Pasta'
    if ([string]::IsNullOrWhiteSpace($resposta)) {
        $pasta = $padrao
    } else {
        $pasta = [Environment]::ExpandEnvironmentVariables($resposta.Trim().Trim('"'))
    }
    try {
        $pasta = [System.IO.Path]::GetFullPath($pasta)
    } catch {
        Parar "A pasta '$pasta' não é válida."
    }
    if ((Test-Path -LiteralPath $pasta) -and -not (Test-Path -LiteralPath (Join-Path $pasta '.git')) -and -not (Pasta-Vazia $pasta) -and -not (Parece-OPrograma $pasta)) {
        # Pasta com outras coisas (ex.: Documentos): instala numa subpasta, sem mexer no resto
        $pasta = Join-Path $pasta $NomeApp
        Write-Host "   Essa pasta já tem outros arquivos. Vou instalar em: $pasta"
    }
    Clonar-OuAtualizar $pasta
    $Resumo.Insert(0, "Pasta: $pasta")

    # 4. Dependências
    Titulo '4/6  Dependências (pip)'
    $requisitos = Join-Path $pasta 'requirements.txt'
    if (Test-Path -LiteralPath $requisitos) {
        & $py.Exe @pyArgs -m pip install --disable-pip-version-check -r $requisitos
        if ($LASTEXITCODE -ne 0) {
            Avisar 'O pip não conseguiu instalar as dependências (veja a mensagem acima). O launcher tenta de novo quando abrir.'
            $Resumo.Add('Dependências: com problema (o launcher tenta de novo)')
        } else {
            Certo 'Dependências instaladas.'
            $Resumo.Add('Dependências: instaladas')
        }
    } else {
        Certo 'Sem requirements.txt: nada para instalar.'
    }

    # 5. Configuração e Blender
    Titulo '5/6  Configuração e Blender'
    $pythonw = ''
    $linhas = & $py.Exe @pyArgs (Join-Path $pasta 'launcher.py') --preparar-config 2>$null
    $json = @($linhas) | Where-Object { "$_".Trim().StartsWith('{') } | Select-Object -Last 1
    if (-not $json) {
        Avisar 'Não deu para preparar a configuração. Abra o app e ajuste nas configurações (botão da engrenagem).'
        $Resumo.Add('Configuração: com problema (ajuste nas configurações do app)')
    } else {
        $cfg = $json | ConvertFrom-Json
        $pythonw = $cfg.pythonw
        if ($cfg.erro) {
            Avisar $cfg.erro
            $Resumo.Add('Configuração: com problema (ajuste nas configurações do app)')
        } else {
            if ($cfg.criado) { Certo 'config.local.json criado.' } else { Certo 'config.local.json já existia (mantido).' }
            $Resumo.Add('Configuração: ' + $(if ($cfg.criado) { 'config.local.json criado' } else { 'config.local.json mantido' }))
        }
        if ($cfg.blender_ok) {
            if ($cfg.blender_achado) { Certo "Blender encontrado: $($cfg.blender)" } else { Certo "Blender: $($cfg.blender)" }
            $Resumo.Add("Blender: $($cfg.blender)")
        } elseif (-not $cfg.erro) {
            Avisar 'Não achei o Blender em C:\Program Files\Blender Foundation. Instale o Blender (https://www.blender.org/) ou escolha o blender.exe nas configurações do app (botão da engrenagem).'
            $Resumo.Add('Blender: não encontrado (escolha nas configurações do app)')
        }
    }

    # 6. Atalhos
    Titulo '6/6  Atalhos'
    $pyw = Join-Path $pasta 'launcher.pyw'
    if ($pythonw -and (Test-Path -LiteralPath $pythonw)) {
        $alvo = $pythonw
        $argumentos = '"' + $pyw + '"'
    } else {
        $alvo = $pyw                     # o Windows abre o .pyw com o Python
        $argumentos = ''
    }
    $atalhos = @()
    $antigosTrocados = 0
    foreach ($destino in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {
        if (-not $destino) { continue }
        $arquivo = Join-Path $destino "$NomeApp.lnk"
        try {
            Criar-Atalho $arquivo $alvo $argumentos $pasta
            $atalhos += $arquivo
            if (Remover-AtalhoAntigo (Join-Path $destino "$NomeAntigo.lnk") $pasta) { $antigosTrocados++ }
        } catch {
            Avisar "Não deu para criar o atalho em $destino."
        }
    }
    if ($atalhos.Count -gt 0) {
        Certo 'Atalhos criados na Área de Trabalho e no Menu Iniciar.'
        if ($antigosTrocados -gt 0) { Certo "Os atalhos com o nome antigo ($NomeAntigo) foram trocados pelos novos." }
        $Resumo.Add('Atalhos: Área de Trabalho e Menu Iniciar (' + $NomeApp + ')')
    }

    # Resumo
    Write-Host ''
    Write-Host '=============================================' -ForegroundColor Cyan
    if ($Avisos.Count -eq 0) {
        Write-Host '   Pronto! O PathToMesh foi instalado.' -ForegroundColor Green
    } else {
        Write-Host '   Instalação terminada, com avisos.' -ForegroundColor Yellow
    }
    Write-Host '=============================================' -ForegroundColor Cyan
    foreach ($linha in $Resumo) { Write-Host "   - $linha" }
    if ($Avisos.Count -gt 0) {
        Write-Host ''
        Write-Host '   Avisos:' -ForegroundColor Yellow
        foreach ($a in $Avisos) { Write-Host "   - $a" -ForegroundColor Yellow }
    }
    Write-Host ''
    Write-Host "   Para abrir o programa, dê dois cliques no atalho '$NomeApp' na Área de Trabalho."
    Write-Host '   Para atualizar no futuro, use o botão "Atualizar agora" do launcher (ou rode este instalador de novo).'
    Fechar 0
} catch {
    Write-Host ''
    Write-Host "ERRO inesperado: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'A instalação não terminou. Rode o instalador de novo; se o erro continuar, avise.' -ForegroundColor Red
    Fechar 1
}
