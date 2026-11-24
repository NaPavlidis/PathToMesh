@echo off
rem Abre o launcher do Phy-2d-by-3d (com console, para ver mensagens de erro).
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 launcher.py
) else (
    python launcher.py
)
if errorlevel 1 pause
