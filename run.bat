@echo off
cd /d "%~dp0"
if not exist .venv (
    echo Creating virtual environment...
    python -m venv .venv || goto :error
)
call .venv\Scripts\activate.bat
python -m pip install -q -r requirements.txt || goto :error
if not exist .env copy .env.example .env >nul && echo Created .env - add your ANTHROPIC_API_KEY to it.
python app.py
goto :eof

:error
echo Setup failed. Make sure Python 3.11+ is installed and on PATH.
pause
