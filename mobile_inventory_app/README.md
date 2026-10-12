# EMBURN Inwentaryzacja — Android offline

Telefon pracuje bez serwera i internetu, a eksport CSV jest zgodny z modułem 15 w Streamlit.

1. Pobierz ze Streamlit „Katalog do telefonu” jako CSV.
2. W telefonie zaimportuj katalog, skanuj EAN, potem QR tacki (`TRAY|000145`) i wpisz ilość.
3. Udostępnij CSV do późniejszego importu w Streamlit.

## Budowanie APK

Na komputerze potrzebne są Flutter, Android SDK i JDK 17.

```powershell
flutter create .
flutter pub get
flutter build apk --release
```

Po `flutter create .` dodaj wpis z `android_manifest_additions.xml` do manifestu Androida.
Gotowy plik: `build/app/outputs/flutter-apk/app-release.apk`.
