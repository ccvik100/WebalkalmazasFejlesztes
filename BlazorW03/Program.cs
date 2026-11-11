using BlazorW03.Components;
using BlazorW03.Services;

var builder = WebApplication.CreateBuilder(args);
builder.WebHost.UseUrls(builder.Configuration["urls"] ?? "http://127.0.0.1:3000");
builder.WebHost.UseStaticWebAssets();
builder.Configuration["AllowedHosts"] = "127.0.0.1;localhost";

builder.Services.AddRazorComponents().AddInteractiveServerComponents();
builder.Services.AddHttpClient<MeetingService>(client =>
{
    client.Timeout = TimeSpan.FromSeconds(10);
}).ConfigurePrimaryHttpMessageHandler(() => new HttpClientHandler
{
    AllowAutoRedirect = false
});

var app = builder.Build();
app.UseAntiforgery();
app.MapStaticAssets();
app.MapRazorComponents<App>().AddInteractiveServerRenderMode();
app.Run();
