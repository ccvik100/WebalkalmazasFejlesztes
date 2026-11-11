# OmegaAI v1.6 – teljes ZIP, Windows magyar UTF-8 hibajavítással

## Miért volt szükséges a javítás?

Korábbi teljes MP3-feldolgozásnál, a Whisper-átirat befejezése után,
a Qwen-összesítés indításakor `UnicodeEncodeError: 'charmap' codec can't encode character '\u0151'`
hiba keletkezhetett. A JSONL státuszsor a Windows konzol nem UTF-8
kódolásán próbálta az `ő` karaktert továbbítani.

Ez a teljes kiadás már tartalmazza a javított fájlokat:

- `app/offlineai/worker.py` – JSONL állapotesemények ASCII-safe escape-ként
- `app/offlineai/main.py` – UTF-8 Python alfolyamat-környezet
- `setup/Start.ps1` – REST-folyamat UTF-8 konfigurációja
- `03_INDITAS.bat` – Python UTF-8 környezet és konzol kódolás
- `tests/test_utf8_worker.py` – regressziós teszt

## Biztonságos frissítés a jelenlegi `C:\OmegaAI` telepítésen

1. Várd meg a futó AI-feldolgozásokat, majd állítsd le a REST API-t Ctrl+C-vel.
2. Készíts mentést legalább a `C:\OmegaAI\app`, `C:\OmegaAI\setup`,
   `C:\OmegaAI\config` és `C:\OmegaAI\data` mappákról.
3. A teljes ZIP-et külön mappába bontsd ki, például `C:\OmegaAI_Csomag_UTF8` alá.
4. PowerShellből lépj a kicsomagolt `OmegaAI` mappába és futtasd:

```powershell
.\01_TELEPITES.bat CHECK
.\01_TELEPITES.bat INSTALL
.\02_ELLENORZES.bat DEEP
.\03_INDITAS.bat
```

5. A futó API mellett **új** PowerShell ablakból, ugyanabból a csomagmappából:

```powershell
.\04_TEST_QWEN.bat
.\05_TEST_MP3.bat "C:\Hangok\teszt.mp3"
.\06_TEST_BESZELOK.bat "C:\Hangok\teszt.mp3"
```

A régi `failed` állapotú job nem folytatódik automatikusan, új feltöltés kell.
Az `INSTALL` a korábbi Qwen-modelltárat, a Whisper- és pyannote-modelleket,
a `config/settings.json` fájlt, a titkos API-kulcsot és a `data` adatokat megőrzi.
**Fontos:** a teljes `INSTALL` ellenőrzi/telepítheti a Python-csomagokat,
valamint hiányzó modellek esetén internetkapcsolatra lehet szüksége.

## Mit teszteltünk?

A Python-tesztkészlet modellhelyettesítéssel, köztük szándékosan
`cp1252` kódolásra kényszerített gyermekfolyamattal ellenőrzi a javítást.
A teszt nem bizonyítja, hogy Windows alatt a teljes, valódi modell-
inferencia hibamentes. Ezt a `05_TEST_MP3.bat` és `06_TEST_BESZELOK.bat`
kimenete, valamint a kapott átirat/összesítő ellenőrzése igazolja.

## Címek és adatok

- OmegaAI API: `http://127.0.0.1:8768/docs`
- Meglévő Ollama: `http://127.0.0.1:11434`
- Python és modellek: `C:\OmegaAI`
- Titkos API-kulcs: `C:\OmegaAI\config\api-key.txt` (csak szerveren)
- Hangprofilok: tenantonként külön SQLite a `C:\OmegaAI\data\tenants` alatt

A fenti könyvtárak nem részei a publikusan kiszolgált webes `wwwroot` tartalomnak.
