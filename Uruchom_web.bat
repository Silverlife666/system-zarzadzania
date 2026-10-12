@echo off
chcp 65001 >nul

echo ==========================================
echo Instalacja/Sprawdzanie wymaganych pakietow...
echo ==========================================
py -3 -m pip install --upgrade pip
py -3 -m pip install streamlit pandas numpy matplotlib plotly reportlab odfpy openpyxl opencv-python pypdf

echo.
echo ==========================================
echo Uruchamianie aplikacji Streamlit...
echo ==========================================
wscript.exe "%~dp0start.vbs"
