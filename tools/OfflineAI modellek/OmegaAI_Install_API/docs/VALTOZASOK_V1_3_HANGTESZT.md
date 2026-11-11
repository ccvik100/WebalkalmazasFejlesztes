# Valos hangfeldolgozas javitasa – v1.3

Korabbi felhasznaloi teszt: `05_TEST_MP3.bat` a 25%-os Whisper allapotnal `open() got an unexpected keyword argument 'metadata_errors'` hibaval leallt. Ez `faster-whisper==1.2.1` es `PyAV 19` ismert kompatibilitasi hiba.

Az uj `09_JAVITAS_HANGDEKODER.bat` egyszeri javito futtatasa elott allitsd le a REST API-t. A javito csak a PyAV verziot es negy programfajlt erinti, modell vagy hangadat nem torlodik. A javito a forrasfajlokrol biztonsagi masolatot tesz a `C:\OmegaAI\logs` ala.

```powershell
.\09_JAVITAS_HANGDEKODER.bat
.\02_ELLENORZES.bat DEEP
.\03_INDITAS.bat
```

Masodik terminal:

```powershell
.\05_TEST_MP3.bat "C:\Hangok\teszt.mp3"
.\06_TEST_BESZELOK.bat "C:\Hangok\teszt.mp3"
```

A `DEEP` csak modell-betoltes, nem teljes inferencia. A hibajelzes megszunese onmagaban nem bizonyitja a Qwen osszesites sikeret; a `completed` allapotot, az atiratot, osszesitot es beszelo-szegmenseket ellenorizd.

Ez a fejezet a v1.3 hibajavitasanak torteneti hatteret tartalmazza. Az aktualis, egységes dokumentáció a csomag gyökerében lévő v1.5.1 Word-kézikönyv.
