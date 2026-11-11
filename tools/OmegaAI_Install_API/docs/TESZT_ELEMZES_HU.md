# Tesztelési jelentés – OmegaAI útvonalhoz igazított kiadás

A csomag konfigurációja `C:\OmegaAI` gyökérrel, a **meglévő** `http://127.0.0.1:11434` Ollamával és `qwen3:8b` modellel készült. A `C:\OmegaAI\models\ollama` adatállományait a telepítő nem írja felül és nem törli.

## Helyben futtatható tesztek

1. `08_MEGLEVO_OLLAMA_ELLENORZES.bat` – 11434 modelllista, fájlok helye, nincs inferencia.
2. `01_TELEPITES.bat CHECK` – Python 3.12 és forrásfájlok, nincs telepítés.
3. `01_TELEPITES.bat INSTALL` – Python-csomagok, FFmpeg, hiányzó Whisper/pyannote modellfájlok, meglévő Qwen ellenőrzése.
4. `02_ELLENORZES.bat DEEP` – tényleges helyi Whisper és pyannote modellbetöltés.
5. `03_INDITAS.bat` és `04_TEST_QWEN.bat` – tényleges HTTP és Qwen szövegválasz.
6. `05_TEST_MP3.bat "C:\Hangok\teszt.mp3"` – tényleges fájl, átirat, összesítő.
7. `06_TEST_BESZELOK.bat "C:\Hangok\teszt.mp3"` – tényleges diarizáció.

## Mit bizonyítanak az automatizált tesztek?

Az `app` API egységtesztjei valódi HTTP-szerződés-szinten, helyettesített AI-függvényekkel futnak. Ellenőrzik a hitelesítést, a feladatsor állapotait, a beszélőnevek kézi hozzárendelését, az átirat és az összesítő elérését. Ezek nem helyettesítik a Windowsos modellbetöltést.

A kiegészítő statikus regressziós tesztek kizárólag az alapértelmezett OmegaAI-útvonalat, a meglévő Ollama 11434-es használatát, a BAT-ok BOM nélküli kódolását és az újratelepítés modellkímélő szándékát ellenőrzik. **Windowsos PowerShell végrehajtást nem bizonyítanak.**
