# =============================================================
# OKTATÓI MAGYARÁZAT – TestApi.ps1
# A megjegyzések bemutatják a PowerShell parancsok célját.
# Az eredeti futtatási utasítások nincsenek megváltoztatva.
# =============================================================
# TANANYAG – A teszt a helyi 5200-as API-t vizsgálja, opcionális MP3 fájllal és korlátozott állapotlekérdezéssel.
param([string]$BaseUrl='http://localhost:5200', [string]$AudioPath='', [int]$MaxChecks=360)
# TANANYAG – A legkisebb hiba is megszakítja a tesztet, hogy ne írjunk ki hamis OK eredményt.
$ErrorActionPreference='Stop'
# TANANYAG – A projektmappát a scripts gyökérből számolja.
$root=Split-Path -Parent $PSScriptRoot
# TANANYAG – A tesztcél kulcsot a nem publikált private konfigurációból olvassa ki.
$cfg=(Get-Content (Join-Path $root 'private\meetingnotes.secrets.json') -Raw | ConvertFrom-Json).MeetingNotes
# TANANYAG – Az első regisztrált kliens külön X-Meeting-Key kulcsát használja.
$key=[string]$cfg.Clients[0].ClientKey
# TANANYAG – Elkészíti a védett endpointokhoz kötelező HTTP-fejlécet.
$headers=@{'X-Meeting-Key'=$key}
# TANANYAG – A báziscím végéről levágja a felesleges / karaktert, hogy jó URL-ek keletkezzenek.
$base=$BaseUrl.TrimEnd('/')
# TANANYAG – A fejléc jelzi, melyik szervercímet teszteljük.
Write-Host "=== MeetingNotesAPI teszt: $base ===" -ForegroundColor Cyan
# TANANYAG – Nyilvános életjel: nem igényel hozzáférést az OmegaAI-hoz.
$live=Invoke-RestMethod -Uri "$base/api/health/live" -TimeoutSec 15
# TANANYAG – A saját .NET API válaszát megjeleníti.
Write-Host "[OK] Saját API: $($live.status)"
# TANANYAG – Külön lekérdezi, hogy az API eléri-e az OmegaAI háttérszolgáltatást.
$ready=Invoke-RestMethod -Uri "$base/api/health/omegaai" -Headers $headers -TimeoutSec 20
# TANANYAG – Az omegaAiOnline és ready két külön jelző; utóbbi nem jelent tényleges modellinferencia tesztet.
Write-Host "[OK] OmegaAI kapcsolat: $($ready.omegaAiOnline) / ready: $($ready.ready)"
# TANANYAG – A munkasor aktuális terhelését ellenőrzi.
$queue=Invoke-RestMethod -Uri "$base/api/queue" -Headers $headers -TimeoutSec 20
# TANANYAG – Megjeleníti, hány feldolgozás fut és várakozik a központi AI-ban.
Write-Host "[OK] Futo: $($queue.activeJobs), varakozo: $($queue.waitingJobs)"
# TANANYAG – Egyszerű magyar Qwen kérdést állít össze JSON formában.
$body=@{prompt='Egy mondatban magyarázd el, mi az API.'}|ConvertTo-Json
# TANANYAG – POST kérés UTF-8 bájtokkal; hosszabb Qwen válaszra akár 300 másodpercet is enged.
$chat=Invoke-RestMethod -Method Post -Uri "$base/api/ai/chat" -Headers $headers -ContentType 'application/json' -Body ([Text.Encoding]::UTF8.GetBytes($body)) -TimeoutSec 300
# TANANYAG – A válasz első 120 karakterét írja ki, hogy a konzol áttekinthető maradjon.
Write-Host "[OK] Qwen valasz: $([string]$chat.answer).Substring(0,[Math]::Min(120,([string]$chat.answer).Length))"
# TANANYAG – Ha nincs MP3-útvonal, a szöveges teszttel sikeresen végez a szkript.
if (-not $AudioPath) { Write-Host '[OK] Szoveges tesztek lefutottak. MP3 feltoltes opcionális.'; exit 0 }
# TANANYAG – Nem létező fájlnál azonnal hibát dobunk, nem indítunk üres hangmunkát.
if (-not (Test-Path -LiteralPath $AudioPath)) { throw "Nincs hangfájl: $AudioPath" }
# A Windows PowerShell 5.1 curl.exe hivasaval biztosan multipart/form-data kuldheto.
# TANANYAG – A curl.exe -F kapcsolói Windows PowerShell 5.1 alatt is megbízható multipart adatküldést adnak.
$raw=& curl.exe --silent --show-error --fail -X POST "$base/api/meetings" -H "X-Meeting-Key: $key" `
    # TANANYAG – A formázott dátumot startedAt néven küldi, az Audio fájlt és a címet feltöltéskor.
    -F "Audio=@$AudioPath" -F 'Title=MeetingNotesAPI teszt' -F "StartedAt=$(Get-Date -Format 'yyyy-MM-ddTHH:mm:sszzz')" `
    # TANANYAG – A diarizációt és az összesítést is bekapcsolja, így a teljes feldolgozási utat teszteljük.
    -F 'Diarize=true' -F 'Summarize=true'
# TANANYAG – A curl külső program kilépési kódját ellenőrzi, és hibánál nem próbál tovább állapotot olvasni.
if ($LASTEXITCODE -ne 0) { throw "A hangfeltoltes elbukott: $raw" }
# TANANYAG – A JSON feltöltési választ PowerShell-objektummá alakítja.
$upload=$raw | ConvertFrom-Json
# TANANYAG – A külön feladathoz tartozó ID-t kéri ki a válaszból.
$id=[string]$upload.id
# TANANYAG – Azonosító hiányában a feldolgozást nem lehet követni; jelezzük a hibát.
if (-not $id) { throw "Nem jött feladathoz id: $raw" }
# TANANYAG – A jobs_ahead a feladat előtt még várakozó/futó munkák száma.
Write-Host "[OK] Feldolgozas sorba allitva: id=$id, elotte=$($upload.jobs_ahead)"
# TANANYAG – Legfeljebb MaxChecks alkalommal kérdezünk rá a feldolgozásra.
for ($i=0;$i -lt $MaxChecks;$i++) {
    # TANANYAG – A jobId szerinti HTTP GET a teljes, aktuális állapotot olvassa.
    $job=Invoke-RestMethod -Uri "$base/api/meetings/$id" -Headers $headers -TimeoutSec 30
    # TANANYAG – Konzolon a státusz, munkasor, szakasz és részletes százalék látszik.
    Write-Host "[$($job.status)] elotte=$($job.jobs_ahead); $($job.stage): $($job.progress)% | $($job.stage_detail)"
    # TANANYAG – Completed állapotban kilépünk a várakozási ciklusból.
    if ($job.status -eq 'completed') { break }
    # TANANYAG – Failed/canceled állapotnál a részletes hibaüzenetet adjuk tovább.
    if ($job.status -in @('failed','canceled')) { throw "Feldolgozas leallt: $($job.message)" }
    # TANANYAG – Öt másodperces várakozással elkerüljük a túl sűrű lekérdezések miatti terhelést.
    Start-Sleep -Seconds 5
}
# TANANYAG – Ha túl sok lekérdezés után sem kész, megszakítjuk a tesztfigyelést; az AI-munka ettől még futhat.
if ($job.status -ne 'completed') { throw 'A maximális állapotellenőrzési idő lejárt; a job ettől még futhat.' }
# TANANYAG – Az adott feladat saját teszteredmény-könyvtárát nevezi el.
$out=Join-Path $root "teszteredmeny_$id"
# TANANYAG – Létrehozza a mappát, ha nincs meg.
New-Item -ItemType Directory -Force $out | Out-Null
# TANANYAG – A teljes átiratot a helyi atirat.txt fájlba menti.
Invoke-WebRequest -Uri "$base/api/meetings/$id/transcript" -Headers $headers -OutFile (Join-Path $out 'atirat.txt') -UseBasicParsing
# TANANYAG – A kész összesítőt külön osszesito.txt fájlba menti.
Invoke-WebRequest -Uri "$base/api/meetings/$id/summary" -Headers $headers -OutFile (Join-Path $out 'osszesito.txt') -UseBasicParsing
# TANANYAG – Az eredmények pontos mappáját megjeleníti, hogy a tesztelő megtalálja őket.
Write-Host "[OK] Teljes MP3 teszt kesz: $out" -ForegroundColor Green
