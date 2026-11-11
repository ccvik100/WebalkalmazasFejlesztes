# =============================================================
# OKTATÓI MAGYARÁZAT – Check.ps1
# A megjegyzések bemutatják a PowerShell parancsok célját.
# Az eredeti futtatási utasítások nincsenek megváltoztatva.
# =============================================================
# TANANYAG – A környezetellenőrző nem áll le minden kisebb konzolhibánál; a kritikus állapotokat saját feltételekkel jelzi.
$ErrorActionPreference = 'Continue'
# TANANYAG – A $PSScriptRoot a scripts mappa; a szülőkönyvtárban található a MeetingNotesAPI projekt.
$Root = Split-Path -Parent $PSScriptRoot
# TANANYAG – A titkos konfigurációt nem a wwwroot, hanem a private könyvtár tartalmazza.
$Secrets = Join-Path $Root 'private\meetingnotes.secrets.json'
# TANANYAG – A fejléc jelzi, hogy most előfeltételeket ellenőrzünk, nem hangot írunk át.
Write-Host '=== MeetingNotesAPI - ellenorzes ===' -ForegroundColor Cyan
# TANANYAG – A dotnet parancs meglétét keresi, még a verzió lekérdezése előtt.
$dotnet = Get-Command dotnet -ErrorAction SilentlyContinue
# TANANYAG – Hiányzó CLI esetén saját hibaüzenettel és 2-es kilépési kóddal állunk meg.
if (-not $dotnet) { Write-Host '[HIBA] .NET SDK nem talalhato.'; exit 2 }
# TANANYAG – A gépen telepített .NET SDK-k listáját kérjük le.
$sdks = & dotnet --list-sdks
# TANANYAG – A teljes SDK-listát megmutatjuk, hogy a hallgató lássa a verziókat.
$sdks | ForEach-Object { Write-Host $_ }
# TANANYAG – A projekt .NET 10-et céloz; régebbi SDK-val nem fordítható megfelelően.
if (-not ($sdks | Where-Object { $_ -match '^10\.' })) { Write-Host '[HIBA] .NET 10 SDK hianyzik.'; exit 2 }
# TANANYAG – A kulcsfájl megléte szükséges; a Configure.ps1 készíti el.
if (-not (Test-Path $Secrets)) { Write-Host '[HIBA] Elobb futtasd: 01_KONFIGURALAS.bat'; exit 3 }
# TANANYAG – A hálózati teszt hibái try/catch blokkba kerülnek.
try {
 # TANANYAG – A titkos JSON MeetingNotes szakaszát PowerShell-objektummá olvassa.
 $cfg = (Get-Content $Secrets -Raw | ConvertFrom-Json).MeetingNotes
 # TANANYAG – Ellenőrzi a klienslista és a fő OmegaAI-kulcs meglétét, de az értékeiket nem írja ki.
 if (-not $cfg.Clients -or -not $cfg.OmegaAi.ApiKey) { throw 'Kliens- vagy OmegaAI kulcs hianyzik.' }
 # TANANYAG – A helyi OmegaAI egyszerű életjelét tíz másodperces határidővel kéri le.
 $live = Invoke-RestMethod -Uri "$($cfg.OmegaAi.BaseUrl.TrimEnd('/'))/health/live" -TimeoutSec 10
 # TANANYAG – Pozitív visszajelzést ad a háttérszolgáltatás HTTP-eléréséről.
 Write-Host "[OK] OmegaAI elerheto: $($live.status)"
 # TANANYAG – A belső API-kulcsot és az első tenantkulcsot fejlécekbe helyezi; ezek titkosak.
 $headers = @{ 'X-Api-Key'=$cfg.OmegaAi.ApiKey; 'X-Tenant-Key'=$cfg.Clients[0].TenantKey }
 # TANANYAG – A ready végponttal megnézi, hogy a modellek/fájlok rendelkezésre állnak-e.
 $ready = Invoke-RestMethod -Uri "$($cfg.OmegaAi.BaseUrl.TrimEnd('/'))/v1/health/ready" -Headers $headers -TimeoutSec 15
 # TANANYAG – A Whisper, pyannote és Qwen állapotát megjeleníti anélkül, hogy inferenciát futtatna.
 Write-Host "[OK] Whisper-fajlok: $($ready.whisper_files); pyannote-fajlok: $($ready.pyannote_files); Qwen: $($ready.qwen_available)"
# TANANYAG – Hálózati, jogosultsági vagy JSON-hibánál ebbe az ágba jut a program.
} catch {
 # TANANYAG – Az első hiba rövid üzenetét jeleníti meg – nincs kulcsérték a naplóban.
 Write-Host "[HIBA] OmegaAI elofeltetel / hitelesites: $($_.Exception.Message)" -ForegroundColor Red
 # TANANYAG – A 4-es exit kódot a hívó BAT is látja, így megállapítható a sikertelen ellenőrzés.
 exit 4
}
# TANANYAG – Megkülönbözteti a sikeres alapellenőrzést a valós MP3 átiratkészítéstől.
Write-Host '[OK] Konfiguracio es OmegaAI alapallapot megfelelo. Nem teljes AI-feldolgozasi teszt.' -ForegroundColor Green
