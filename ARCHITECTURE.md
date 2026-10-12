# Architektura kalkulatora produkcyjnego

`app.py` jest punktem uruchomienia Streamlit. Odpowiada za wybór modułu,
sesję użytkownika i przekazanie zależności do ekranów. Nie powinien zawierać
nowej logiki obliczeniowej, generowania dokumentów ani bezpośrednio testowanej
reguły biznesowej.

## Warstwy

- `core/` — obliczenia i walidacje bez Streamlit oraz trwałego zapisu.
- `services/` — trwały stan, dokumenty, wersjonowanie, e-mail i PDF-y.
- `modules/` — ekrany Streamlit. Ekran otrzymuje zależności od routera;
  nigdy nie importuje `app.py`.
- `tests/` — testy regresji usług, dokumentów i kluczowych przepływów danych.
- `dane_aplikacji/` — trwałe dane użytkowe: rejestr zleceń, konteksty
  robocze, dokumenty, archiwa, plan produkcji i sesje inwentaryzacji.

## Router widoków

`app.py` zawiera jeden rejestr `MODULE_RENDERERS`. Po wyborze pozycji w menu
identyfikator modułu jest używany do pobrania funkcji renderującej, a następnie
wywoływany tylko ten jeden widok. Nie ma równoległych bloków
`if selected_module == ...` ani pozostawionych bloków `if False`.

| ID | Widok |
| --- | --- |
| 1 | Baza produktów i import |
| 2 | Paletyzacja |
| 3 | E-mail |
| 4 | Optymalizacja palety |
| 5 | Transport |
| 6 | Packing List |
| 7 | Box Rightsizing |
| 8 | Analiza BCT kartonu |
| 9 | Zlecenie produkcyjne / TDS, E-Order i Karta Pracy |
| 10 | Mass Specification PPWR |
| 11 | Walidacja zamówień z drukarni / QA |
| 12 | Centrum zlecenia |
| 13 | Planowanie produkcji |
| 14 | Panel użytkowników |
| 15 | Inwentaryzacja |

Każdy renderer przekazuje do ekranu tylko potrzebne funkcje i dane. Dzięki temu
logika ekranów pozostaje odseparowana od punktu uruchomienia, a router jest
jedynym miejscem koordynującym zależności interfejsu.

## Kontekst zlecenia i użytkownika

`order_id` jest kontekstem wspólnym ekranów operacyjnych. Dane robocze są
zapisywane w `konteksty_zlecen.json` i przy przełączeniu zlecenia są najpierw
utrwalane, a następnie odtwarzane dla wybranego `order_id`.

Ostatnio wybrane zlecenie użytkownika jest przechowywane w
`ustawienia_przestrzeni_uzytkownikow.json`. Po poprawnym zalogowaniu aplikacja
wraca do tego zlecenia, jeśli nadal istnieje w rejestrze. Dane logowania nie są
zapisywane w tym pliku ani przekazywane w adresie strony.

## Zasady dla dokumentów

Generator PDF zwraca wyłącznie bajty. `app.py` zapisuje dokument funkcją
`store_order_pdf()`, aby zachować `order_id`, wersję, historię i bezpieczną
ścieżkę pliku. Ta zasada dotyczy TDS, E-Order, Karty Pracy, Packing List,
zlecenia transportowego, BCT, PPWR, deklaracji i QA.

## Zasady dla ekranów

Nowy ekran należy utworzyć w `modules/` jako funkcję `render_…`. Parametry
takie jak zapis archiwum, bieżące `order_id` czy generator PDF są przekazywane
przez router. Dzięki temu ekran pozostaje możliwy do importu i kontroli bez
uruchamiania całej aplikacji.

## Kontrola przed uruchomieniem

W katalogu projektu uruchom:

```powershell
python -m compileall -q app.py core services modules tests
python -m unittest discover -s tests -p "test_regression_core.py"
```

Testy obejmują 90 przypadków regresyjnych i integracyjnych: zapis/odczyt
kontekstu, generowanie PDF, wersjonowanie, komplet ZIP, historię e-maila,
usuwanie zlecenia oraz dane modułu inwentaryzacji.

Po zmianie ekranu sprawdź ręcznie: przełączenie modułu, zapis i przywrócenie
`order_id`, pobranie PDF oraz wpis w Centrum zlecenia. W przypadku PDF należy
sprawdzić pierwszą stronę przez `pdftoppm` lub podgląd w module 12.
