@echo off
rem Instalador do PathToMesh: de dois cliques neste arquivo.
rem Ele roda o instalar.ps1 (da mesma pasta ou, se nao tiver, baixado do GitHub).
setlocal
title Instalador do PathToMesh
set "PS1=%~dp0instalar.ps1"
set "PS1_TEMP=%TEMP%\pathtomesh-instalar.ps1"
if not exist "%PS1%" set "PS1=%PS1_TEMP%"
if "%PS1%"=="%PS1_TEMP%" (
    echo Baixando o instalador do GitHub...
    if exist "%PS1_TEMP%" del /q "%PS1_TEMP%"
    powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -UseBasicParsing -Uri 'https://raw.githubusercontent.com/NaPavlidis/PathToMesh/main/instalar.ps1' -OutFile $env:PS1_TEMP"
)
if not exist "%PS1%" (
    echo.
    echo Nao deu para baixar o instalador. Confira a internet e tente de novo.
    pause
    exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%"
rem Codigo 0 ou 1: o instalar.ps1 ja mostrou o resumo ou o erro e esperou o Enter.
rem Outro codigo: o PowerShell nem rodou o instalador; segura a janela para ler a mensagem.
if errorlevel 2 pause
endlocal
