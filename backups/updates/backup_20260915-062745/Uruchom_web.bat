@echo off
chcp 65001 >nul

echo ==========================================
echo Instalacja/Sprawdzanie wymaganych pakietow...
echo ==========================================
python -m pip install --upgrade pip
python -m pip install streamlit pandas numpy matplotlib plotly reportlab odfpy openpyxl opencv-python

echo.
echo ==========================================
echo Uruchamianie aplikacji Streamlit...
echo ==========================================
wscript.exe "%~dp0start.vbs"