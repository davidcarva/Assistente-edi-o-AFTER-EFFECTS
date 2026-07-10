@echo off
cd /d "%~dp0"
echo Rodando o Assistente em modo diagnostico (console visivel).
echo Use o app normalmente ate ele travar. O erro vai aparecer aqui embaixo.
echo ============================================================
".venv\Scripts\python.exe" app.py
echo ============================================================
echo O app fechou. Se travou, copie as ultimas linhas acima.
pause
