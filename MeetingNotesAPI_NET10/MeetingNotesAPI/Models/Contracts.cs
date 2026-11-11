// ================================================================
// OKTATÓI FORRÁSKÓD – A HTTP-kérések DTO-adatszerződései
// A magyarázó kommentek a kód értelmét és biztonsági szerepét írják le.
// A működő programutasításokat az eredeti kiadáshoz képest nem módosítjuk.
// ================================================================
// TANANYAG – A [Required], [Range], [MaxLength] stb. szerződéses adatellenőrző attribútumok.
using System.ComponentModel.DataAnnotations;
// TANANYAG – JSON-szerializációhoz tartozó típusok névtere; most a modellkódban közvetlenül nem használjuk.
using System.Text.Json.Serialization;

// TANANYAG – A kérések bemeneti DTO-it a Models névtér tartalmazza.
namespace MeetingNotesAPI.Models;

// TANANYAG – Qwen-szöveges kérdés bemenetét leíró típus.
public sealed class ChatRequest
{
    // TANANYAG – A Prompt kötelező, legalább egy karakter, és legfeljebb 20 000 karakter lehet.
    [Required, MinLength(1), MaxLength(20000)] public string Prompt { get; set; } = "";
}
// TANANYAG – Kész átiratból, új hangfeldolgozás nélkül készülő összesítő bemeneti modellje.
public sealed class SummaryRequest
{
    // TANANYAG – A Transcript a Qwen alapanyaga, és nem lehet üres vagy 90 000 karakternél hosszabb.
    [Required, MinLength(1), MaxLength(90000)] public string Transcript { get; set; } = "";
    // TANANYAG – A Title a megbeszélés címének felhasználó által megadott megjelenítése.
    [MaxLength(150)] public string Title { get; set; } = "Megbeszélés";
    // TANANYAG – A StartedAt kezdeti időpontját szövegként kapja az OmegaAI; célszerű ISO 8601 alakban megadni.
    [MaxLength(80)] public string StartedAt { get; set; } = "Nincs megadva";
}
// TANANYAG – Fájl és metaadatok összefogása egy multipart/form-data kéréshez.
public sealed class UploadMeetingRequest
{
    // TANANYAG – Az IFormFile a ténylegesen feltöltött audioállományt képviseli, még nem feldolgozott szöveg.
    [Required] public IFormFile Audio { get; set; } = default!;
    // TANANYAG – A cím kötelező és legfeljebb 150 karakteres; hibás adatnál a modellkötés 400-at adhat.
    [Required, MaxLength(150)] public string Title { get; set; } = "Megbeszélés";
    // TANANYAG – A kezdet időpontja szövegként kerül továbbításra; a szerver külön ellenőrzi a hosszát.
    public string StartedAt { get; set; } = "Nincs megadva";
    // TANANYAG – Ha true, pyannote beszélőszétválasztást kérünk a Whisper-átirat mellé.
    public bool Diarize { get; set; } = true;
    // TANANYAG – Ha true, a végén Qwen-összesítő is készül a feldolgozott átirat alapján.
    public bool Summarize { get; set; } = true;
}
// TANANYAG – A SPEAKER_XX címkéket felhasználói nevekkel összekötő kéréstípus.
public sealed class SpeakerNamesRequest
{
    // TANANYAG – A szótár kulcsa a beszélőcímke, az értéke a név; például SPEAKER_00 → Kovács Anna.
    [Required] public Dictionary<string, string> Names { get; set; } = new();
}
// TANANYAG – Személy felvételének/frissítésének adatmodellje, nem azonos a hangmintával.
public sealed class PersonRequest
{
    // TANANYAG – A külső ügyviteli rendszer saját személy-ID-ja, amelyet az OmegaAI személyével összeköthetünk.
    public string? ExternalPersonId { get; set; }
    // TANANYAG – A személy megjelenítendő neve kötelező, hossza legfeljebb 200 karakter.
    [Required, MaxLength(200)] public string Name { get; set; } = "";
    // TANANYAG – A szervezet megnevezése; például önkormányzat vagy cég.
    public string Organization { get; set; } = "";
    // TANANYAG – A betöltött munkakör vagy pozíció, például fejlesztő.
    public string Position { get; set; } = "";
    // TANANYAG – A választott tisztség külön mező, például bizottsági elnök.
    public string ElectedPosition { get; set; } = "";
}
// TANANYAG – Hangmintafelvétel beérkező adatai.
public sealed class VoiceSampleRequest
{
    // TANANYAG – A hangfelvétel bináris fájlként jön, nem JSON szövegként.
    [Required] public IFormFile Audio { get; set; } = default!;
    // TANANYAG – A hozzájárulás megerősítése kötelező az Enroll vezérlőben; ez önmagában nem helyettesíti a jogszerű adatkezelést.
    public bool ConsentConfirmed { get; set; }
    // TANANYAG – A ConsentNote dokumentálja, milyen jogszerű hozzájárulás alapján vettük fel a hangmintát.
    [Required, MinLength(3)] public string ConsentNote { get; set; } = "";
}
// TANANYAG – Az automatikus beszélőazonosítás paraméterei.
public sealed class MatchRequest
{
    // TANANYAG – A hasonlósági küszöb; 0,88 alapérték, a találat NEM a személyazonosság 88%-os valószínűsége.
    [Range(0.8, 1.0)] public double Threshold { get; set; } = 0.88;
    // TANANYAG – A második legjobb találathoz képest elvárt különbség; a bizonytalan találat ismeretlen maradhat.
    [Range(0, 0.3)] public double Margin { get; set; } = 0.04;
}
// TANANYAG – A kézzel jóváhagyott személyhozzárendelés bemenete.
public sealed class ApproveRequest
{
    // TANANYAG – A jóváhagyott SPEAKER_XX → personId párok; az automatikus javaslat nem írja felül a döntést.
    [Required] public Dictionary<string, string> Approved { get; set; } = new();
}
