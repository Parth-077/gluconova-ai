@echo off
echo ========================================
echo GlucoNova AI - Complete System Startup V2
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python 3.8+ from python.org
    pause
    exit /b 1
)

echo [1/6] Checking Python installation...
python --version
echo.

REM Check if model exists
if not exist "diabetes_model.pkl" (
    echo [2/6] Model not found. Training model...
    python train_model.py
    if errorlevel 1 (
        echo [ERROR] Model training failed
        pause
        exit /b 1
    )
) else (
    echo [2/6] Model found: diabetes_model.pkl
)
echo.

REM Check if dependencies are installed
echo [3/6] Checking dependencies...
python -c "import flask, flask_cors, numpy, sklearn, pickle, pytesseract, fitz" >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Some dependencies missing. Installing...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Dependency installation failed
        pause
        exit /b 1
    )
) else (
    echo [OK] All dependencies installed
)
echo.

REM Check Tesseract
echo [4/6] Checking Tesseract OCR...
if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
    echo [OK] Tesseract found
) else (
    echo [WARNING] Tesseract not found at default location
    echo OCR features may not work
    echo Install from: https://github.com/UB-Mannheim/tesseract/wiki
)
echo.

echo [5/6] Starting Backend Server (Flask)...
echo.
start "GlucoNova Backend" cmd /k "python app.py"
timeout /t 3 >nul

echo [6/6] Starting Frontend Server (HTTP)...
echo.
start "GlucoNova Frontend" cmd /k "python serve_frontend.py"
timeout /t 2 >nul

echo.
echo ========================================
echo ✅ SYSTEM STARTED SUCCESSFULLY!
echo ========================================
echo.
echo 🔹 Backend Server: http://localhost:5000
echo 🔹 Frontend Server: http://localhost:8080
echo.
echo 🌐 Your browser should open automatically
echo    If not, open: http://localhost:8080
echo.
echo ⚠️  Keep both server windows open
echo 🛑 Close the server windows to stop
echo ========================================
echo.
pause
