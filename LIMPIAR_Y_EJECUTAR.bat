@echo off
cd /d "%~dp0"

echo ========================================
echo  LIMPIANDO CACHE DE PYTHON...
echo ========================================
if exist "__pycache__" rmdir /s /q "__pycache__"
if exist "app\__pycache__" rmdir /s /q "app\__pycache__"

echo Buscando y eliminando archivos .pyc...
for /r %%i in (*.pyc) do del /f /q "%%i" 2>nul
for /r %%i in (*.pyo) do del /f /q "%%i" 2>nul

echo.
echo ========================================
echo  EJECUTANDO APLICACION (sin bytecode)...
echo ========================================
python -B main.py

pause
