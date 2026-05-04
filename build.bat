@echo off
cd /d "%~dp0"

echo ================================
echo   Build - BOT Gestao
echo ================================
echo.

:: Verifica se Python esta instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo ERRO: Python nao encontrado. Instale em https://python.org
    pause
    exit /b 1
)

:: Cria venv Windows se nao existir (ou se for do WSL/Linux)
if not exist "venv_win\Scripts\activate.bat" (
    echo Criando ambiente virtual Windows...
    python -m venv venv_win
    if errorlevel 1 (
        echo ERRO: Falha ao criar venv.
        pause
        exit /b 1
    )
)

:: Ativa o venv Windows
call venv_win\Scripts\activate.bat

:: Instala dependencias
echo Instalando dependencias...
pip install -r requirements.txt --quiet
pip install pyinstaller --quiet

:: Remove build anterior
if exist "dist\BOT_Gestao.exe" del /f "dist\BOT_Gestao.exe"

:: Gera o executavel
echo.
echo Gerando executavel (pode demorar alguns minutos)...
echo.
pyinstaller --onefile ^
    --name "BOT_Gestao" ^
    --collect-all asyncpg ^
    --collect-all telegram ^
    --hidden-import dotenv ^
    main_bot.py

echo.
if exist "dist\BOT_Gestao.exe" (
    echo ================================
    echo  BUILD CONCLUIDO COM SUCESSO!
    echo ================================
    echo.
    echo Arquivo: dist\BOT_Gestao.exe
    echo.
    echo Entregar ao cliente uma pasta com:
    echo   - BOT_Gestao.exe
    echo   - .env
    echo ================================
) else (
    echo ERRO: build falhou. Veja as mensagens acima.
)

pause
