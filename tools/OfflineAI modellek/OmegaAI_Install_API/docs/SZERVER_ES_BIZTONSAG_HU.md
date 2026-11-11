# OmegaAI szervertelepítés, üzemeltetés és biztonság

## Két külön számítógép

A fejlesztői számítógép `C:\OmegaAI` könyvtára és a Rackforest Windows szerver `C:\OmegaAI` könyvtára két **külön telepítés**. A `127.0.0.1` mindig **az adott gépre** mutat. Ha a későbbi .NET API és az OmegaAI ugyanazon a Rackforest szerveren fut, az API a szerver saját `http://127.0.0.1:8768` címét hívja. Ha külön gépen vannak, biztonságos belső hálózat/titkosított kapcsolat kell; a jelen csomag nem nyit ki nyilvános portot.

## Célfelépítés

```text
Internet -> HTTPS (443) -> IIS / ASP.NET Core API
                            | belső titkos X-Api-Key
                            v
                   127.0.0.1:8768 (OmegaAI REST)
                       |          |         |
                 Whisper      pyannote     Qwen
                 C:\OmegaAI\models\*     127.0.0.1:11434
                                          meglévő Ollama
                                          C:\OmegaAI\models\ollama
```

**Nem** kell semmilyen modellfájlt a `wwwroot` mappába tenni. A modellkönyvtárak és az eredeti hangfelvételek nem publikus állományok. Az IIS a saját .NET API-t szolgálja ki; az OmegaAI önálló Python-folyamat.

## Telepítés fejlesztői gépre és szerverre

1. Python 3.12 x64 és a Windows Ollama telepítése az adott gépen. Szerveren az Ollama modellek mappáját a **szolgáltatást indító Windows-fiók** `OLLAMA_MODELS=C:\OmegaAI\models\ollama` környezeti beállításával add meg, még a folyamat indítása előtt.
2. Ellenőrizd helyi PowerShellben: `Invoke-RestMethod http://127.0.0.1:11434/api/tags`. A modelllistában `qwen3:8b` legyen. Ha már megvan, **nem kell újra letölteni**. A `C:\OmegaAI\models\ollama` mappa önmagában nem bizonyítja, hogy a futó Ollama azt használja; a 11434-es API-t is ellenőrizd.
3. Kicsomagolás pl. `C:\OmegaAI_Csomag`, majd belépés a `C:\OmegaAI_Csomag\OmegaAI` almappába. `01_TELEPITES.bat CHECK` → `01_TELEPITES.bat INSTALL`. A telepítés **nem törli** a meglevő Qwen-modelltárat és API-kulcsot.
4. `02_ELLENORZES.bat DEEP`, `03_INDITAS.bat`, `04_TEST_QWEN.bat`, `05_TEST_MP3.bat "C:\Hangok\teszt.mp3"`.
5. Ha minden helyben sikeres, állítsd be az OmegaAI folyamat automatikus indítását dedikált, korlátozott jogosultságú szolgáltatásfiókkal a Windows Feladatütemezőben. A feladatnak a bejelentkezéstől függetlenül futnia kell, és nem indulhat több példányban. A Python-folyamat önálló, nem az IIS alkalmazáskészlet alatt fut.

## Biztonsági alapok

- `127.0.0.1:8768` és `127.0.0.1:11434` csak a helyi gépről elérhető; ne nyisd ki a publikus tűzfalon.
- Az `X-Api-Key` csak a szerveroldali .NET API-ban legyen, soha ne HTML-ben, MAUI-ban vagy Kotlin-kliensben.
- Korlátozd a `C:\OmegaAI\config\api-key.txt` és a `C:\OmegaAI\data\jobs` NTFS-jogosultságait; felvételek adatvédelmét, megőrzését és a résztvevők tájékoztatását szabályozd.
- Futtatófióknak olvasási jog kell az `app`, `tools`, `models` könyvtárakhoz, írási jog a `data`, `logs` mappákhoz.
- A `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1` és az Ollama `OLLAMA_NO_CLOUD=1` beállításokat a megfelelő folyamatok környezetében alkalmazd. A localhost HTTP önmagában nem igazolja, hogy egy másik Ollama-folyamat nem használ felhős képességet; a konkrét `qwen3:8b` helyi modell ellenőrzése szükséges.

## Gyakori hibák

| Hiba | Ellenőrzés |
|---|---|
| `Connection refused` 11434-en | A meglévő Ollama elindult-e? `ollama list` és `/api/tags` |
| `qwen3:8b` nem látszik | A futó Ollama **melyik** `OLLAMA_MODELS` könyvtárat használja? |
| `No module named fastapi` | `C:\OmegaAI\.venv\Scripts\python.exe -m pip check` |
| Hiányzó FFmpeg | `C:\OmegaAI\tools\ffmpeg.exe -version` |
| Hiányzó Whisper | `C:\OmegaAI\models\whisper-large-v3\model.bin` |
| Hiányzó pyannote | `C:\OmegaAI\models\pyannote-community-1\config.yaml` |
| `401 Unauthorized` | `C:\OmegaAI\config\api-key.txt` és `X-Api-Key` fejléc |
| Swagger működik, AI nem | `02_ELLENORZES.bat DEEP` + valódi MP3-teszt |

## Korlát

Ez a csomag az önálló OmegaAI-szolgáltatást adja. A hitelesítő, internetre kivezetett ASP.NET Core 10 API és a web/mobil kliensek külön projektként kapcsolódnak majd hozzá.


## v1.5: lassú szerver, sor és megszakítás

Az alapbeállítás egy Uvicorn API-példány és egyetlen hangfeldolgozó worker. A három egyidejű feltöltés azonnal 3 azonosítót kap, a max. 8 futó/várakozó munka közül csak 1 fut ténylegesen. Több API-példányt ugyanarra a C:\OmegaAI\data könyvtárra ne indíts; az in-process sor nem elosztott. A várakozó feladatok `job.json` alapján újraindításkor folytathatók, az éppen futó nem automatikusan folytatódik. A C:\OmegaAI\config\settings.json `device`, `audio_chunk_seconds`, `audio_overlap_seconds`, `*_timeout_sec`, `stall_warning_sec` értékei állíthatók. A GPU-vizsgálatot /v1/hardware, a tényleges végrehajtót a job.device jelzi. Modellfájlok, X-Api-Key és audio nem kerülhet IIS wwwroot alá.
