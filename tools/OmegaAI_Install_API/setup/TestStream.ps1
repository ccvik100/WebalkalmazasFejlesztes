$ErrorActionPreference='Stop'
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
$Base=if($env:OFFLINEAI_HOME){$env:OFFLINEAI_HOME}else{'C:\OmegaAI'}
$key=([IO.File]::ReadAllText((Join-Path $Base 'config\api-key.txt'))).Trim()
Add-Type -AssemblyName System.Net.Http
$client=[System.Net.Http.HttpClient]::new()
$client.Timeout=[TimeSpan]::FromMinutes(20)
$client.DefaultRequestHeaders.Add('X-Api-Key',$key)
try {
    $body=@{prompt='Magyarul, 6 kulon mondatban magyarazd el a Whisper, a pyannote es a Qwen szerepet egy megbeszeles feldolgozasaban.'}|ConvertTo-Json
    $request=[System.Net.Http.HttpRequestMessage]::new([System.Net.Http.HttpMethod]::Post,'http://127.0.0.1:8768/v1/chat/stream')
    $request.Content=[System.Net.Http.StringContent]::new($body,[Text.Encoding]::UTF8,'application/json')
    $response=$client.SendAsync($request,[System.Net.Http.HttpCompletionOption]::ResponseHeadersRead).GetAwaiter().GetResult()
    if(-not $response.IsSuccessStatusCode){throw ('SSE HTTP: '+$response.StatusCode+' '+$response.Content.ReadAsStringAsync().GetAwaiter().GetResult())}
    $stream=$response.Content.ReadAsStreamAsync().GetAwaiter().GetResult()
    $reader=[IO.StreamReader]::new($stream,[Text.Encoding]::UTF8)
    Write-Host '[SSE] Azonnal erkezo Qwen szoveg:'
    $seenDone=$false
    try {
        while(-not $reader.EndOfStream){
            $line=$reader.ReadLine()
            if($line.StartsWith('event: done')){$seenDone=$true}
            if($line.StartsWith('event: error')){Write-Host "`n[SSE HIBA event]" -ForegroundColor Red}
            if($line.StartsWith('data: ')){
                $obj=$line.Substring(6)|ConvertFrom-Json
                if($null -ne $obj.delta){[Console]::Write($obj.delta)}
                if($null -ne $obj.message){Write-Host (' [HIBA] '+$obj.message)}
            }
        }
    } finally {$reader.Dispose();$stream.Dispose()}
    Write-Host ''
    if(-not $seenDone){throw 'Az SSE stream vege hianyzik; a valasz nem ellenorzotten kesz.'}
    Write-Host '[OK] SSE done esemeny beerkezett.'
} finally {$client.Dispose()}
