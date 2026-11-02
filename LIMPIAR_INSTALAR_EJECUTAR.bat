@echo off
cd /d "%~dp0"

echo ========================================
echo  1. INSTALANDO DEPENDENCIAS...
echo ========================================
python -m pip install -r requirements.txt

echo.
echo ========================================
echo  2. LIMPIANDO CACHE DE PYTHON (.pyc)...
echo ========================================
if exist "__pycache__" rmdir /s /q "__pycache__"
if exist "app\__pycache__" rmdir /s /q "app\__pycache__"
for /r %%i in (*.pyc) do del /f /q "%%i" 2>nul
for /r %%i in (*.pyo) do del /f /q "%%i" 2>nul

echo.
echo ========================================
echo  3. EJECUTANDO APLICACION (sin bytecode)...
echo ========================================
python -B main.py

pause
