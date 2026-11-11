# OmegaAI v1.3: `metadata_errors` hangdekodolo hiba

## Ok
A korabbi projektben rogzített `faster-whisper==1.2.1` a `PyAV 19` alatt `TypeError: open() got an unexpected keyword argument 'metadata_errors'` hibara fut. A `DEEP` csak modellbetoltest vegzett; nem probalt tenyleges hangatiratot.

## Azonnali gyogyszer (meglevo telepites)
**Leallitott 8768-as REST szolgaltatas mellett**, az uj projektcsomag `OmegaAI` mappajaban PowerShellbol:

```powershell
.\09_JAVITAS_HANGDEKODER.bat
```

A hotfix menti a felulirando Python fajlokat, frissiti a hangfeldolgozot es a PyAV kompatibilis valtozatat. Nem torli a modelleket, felveteleket, API-kulcsot.

## Kezi gyorskezelés kulon hotfix nelkul
```powershell
& 'C:\OmegaAI\.venv\Scripts\python.exe' -m pip install --no-deps --force-reinstall 'av==18.1.0'
```
Ez utan `03_INDITAS.bat` ujrainditas es a `05_TEST_MP3.bat` ujra futtatasa; a regi *failed* job nem folytatodik.

## Kodoldali fix
`app/offlineai/engines.py`: az FFmpeg altal konvertalt 16kHz/mono/PCM16 WAV-ot Python `wave` + NumPy olvassa, es a `WhisperModel.transcribe` mar nem fajlutvonalat, hanem `float32` hangmintakat kap. Ez elkeruli a PyAV `av.open` kompatibilitasi reszet, de az `av==18.1.0` pin is rogzitett.

## Ellenorzesi lepesek
1. `02_ELLENORZES.bat DEEP` (modellbetoltes, nem hangfeldolgozas)
2. `03_INDITAS.bat` (egyik ablakban, hagyd nyitva)
3. `04_TEST_QWEN.bat` (masodik ablakban)
4. `05_TEST_MP3.bat "C:\Hangok\teszt.mp3"`
5. `06_TEST_BESZELOK.bat "C:\Hangok\teszt.mp3"`

Csak akkor igazolt a teljes folyamat, ha a valodi WAV-atirat, Qwen osszesito es a beszelo-szegmensek is keszen vannak.

**Biztonsag**: a kulcsot ne tedd bele kliensappba; a 8768-as port maradjon localhost.
