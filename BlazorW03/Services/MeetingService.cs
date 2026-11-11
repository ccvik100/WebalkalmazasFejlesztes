using System.Net;
using System.Text.Json.Serialization;

namespace BlazorW03.Services;

public record TranscriptExport(string Id, string Title, string StartedAt, string Transcript);

public class MeetingService(HttpClient client, IConfiguration configuration)
{
    public const string DemoId = "11111111111111111111111111111111";
    private const string PendingId = "22222222222222222222222222222222";

    public bool DemoMode => configuration.GetValue<bool>("Demo");

    public async Task<(string Status, TranscriptExport? Export)> LoadAsync(string id)
    {
        if (DemoMode)
        {
            if (id == PendingId)
                return ("queued", null);

            if (id != DemoId)
                throw new HttpRequestException("Ismeretlen demóazonosító.", null, HttpStatusCode.NotFound);

            return ("completed", new TranscriptExport(id, "Őszi gyűlés", "2026-11-10T10:00:00+01:00",
                "Anna: A következő gyűlés témája az őszi beszámoló.\nBence: A jegyzőkönyvet csütörtökig küldöm."));
        }

        var key = configuration["MEETING_API_KEY"];
        var address = configuration["MEETING_API_URL"] ?? "http://localhost:5200";
        if (string.IsNullOrWhiteSpace(key) || !Uri.TryCreate(address, UriKind.Absolute, out var apiUrl)
            || (apiUrl.Scheme != "http" && apiUrl.Scheme != "https"))
        {
            throw new InvalidOperationException("Ellenőrizd a szerveren a MeetingNotesAPI címét és kulcsát.");
        }

        using var statusResponse = await GetAsync(apiUrl, $"/api/meetings/{id}", key);
        var meeting = await statusResponse.Content.ReadFromJsonAsync<MeetingStatus>()
            ?? throw new InvalidDataException("Az API üres státuszválaszt küldött.");

        if (meeting.Status != "completed")
            return (meeting.Status, null);

        using var transcriptResponse = await GetAsync(apiUrl, $"/api/meetings/{id}/transcript", key);
        var transcript = await transcriptResponse.Content.ReadAsStringAsync();
        return (meeting.Status, new TranscriptExport(id, meeting.Title, meeting.StartedAt, transcript));
    }

    private async Task<HttpResponseMessage> GetAsync(Uri apiUrl, string path, string key)
    {
        using var request = new HttpRequestMessage(HttpMethod.Get, new Uri(apiUrl, path));
        request.Headers.Add("X-Meeting-Key", key);

        var response = await client.SendAsync(request);
        if (response.IsSuccessStatusCode)
            return response;

        var status = response.StatusCode;
        response.Dispose();
        throw new HttpRequestException("Sikertelen MeetingNotesAPI-kérés.", null, status);
    }

    private record MeetingStatus(string Status, string Title,
        [property: JsonPropertyName("started_at")] string StartedAt);
}
