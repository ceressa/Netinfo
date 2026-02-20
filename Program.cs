using Serilog;
using Microsoft.Extensions.FileProviders;
using DotNetEnv;
using Netinfo.Services;

var builder = WebApplication.CreateBuilder(args);

// .env dosyasını yükle
DotNetEnv.Env.Load();
string adminPasswordHash = Environment.GetEnvironmentVariable("ADMIN_PASSWORD_HASH") 
    ?? throw new InvalidOperationException("ADMIN_PASSWORD_HASH bulunamadı.");

// Log klasörü ve dosya yolu
string logDirectory = @"D:\INTRANET\Netinfo\logs\Latest_Logs";
string logPath = Path.Combine(logDirectory, $"All_activities_{DateTime.UtcNow:yyyy-MM-dd}.log");

if (!Directory.Exists(logDirectory))
    Directory.CreateDirectory(logDirectory);

// Serilog yapılandırması
builder.Host.UseSerilog((context, services, configuration) =>
{
    configuration
        .ReadFrom.Configuration(context.Configuration)
        .ReadFrom.Services(services)
        .Enrich.FromLogContext()
        .Enrich.WithProperty("Application", "Netinfo")
        .WriteTo.Console()
        .WriteTo.File(
            path: logPath,
            rollingInterval: RollingInterval.Day,
            retainedFileCountLimit: 7,
            outputTemplate: "{Timestamp:yyyy-MM-dd HH:mm:ss} [{Level:u3}] {Message:lj} {Properties}{NewLine}{Exception}"
        );
});

// CORS yapılandırması
builder.Services.AddCors(options =>
{
    options.AddDefaultPolicy(policy =>
    {
        policy.AllowAnyOrigin()
              .AllowAnyMethod()
              .AllowAnyHeader();
    });
});

// Servis kayıtları
builder.Services.AddSingleton<Serilog.ILogger>(Log.Logger);

builder.Services.AddSingleton<TokenService>(provider =>
{
    var logger = Log.ForContext<TokenService>();
    return new TokenService(logger);  // tool_tokens.json burada yüklenir
});

builder.Services.AddSingleton<IAdminAuthService>(provider =>
{
    string envPasswordHash = Environment.GetEnvironmentVariable("ADMIN_PASSWORD_HASH")
        ?? throw new InvalidOperationException("ADMIN_PASSWORD_HASH bulunamadı.");
    return new AdminAuthService(envPasswordHash, Log.Logger);
});

builder.Services.AddSingleton<DeviceDataService>(provider =>
{
    var logger = Log.ForContext<DeviceDataService>();
    var deviceService = new DeviceDataService(logger);

    deviceService.LoadDeviceData(@"D:\INTRANET\Netinfo\Data\network_device_inventory.json");
    deviceService.LoadPreviousDeviceData(@"D:\INTRANET\Netinfo\Data\network_device_inventory_previous.json");
    deviceService.LoadPortData(@"D:\INTRANET\Netinfo\Data\main_data.json");
    deviceService.LoadRouterPortData(@"D:\INTRANET\Netinfo\Data\main_router_data.json");
    deviceService.LoadUUIDPool(@"D:\INTRANET\Netinfo\Data\UUID_Pool.json");
    deviceService.LoadLocationData(@"D:\INTRANET\Netinfo\Data\station-info.json");
    deviceService.LoadLogAnalysisData(@"D:\INTRANET\Netinfo\Logs\Syslog_AI\syslog_summary.json");
    deviceService.LoadInsightSummary(@"D:\INTRANET\Netinfo\Data\insight_summary.json");

    return deviceService;
});

// 🚀 AP Dashboard Service Registration
builder.Services.AddSingleton<AccessPointService>(provider =>
{
    var logger = Log.ForContext<AccessPointService>();
    return new AccessPointService(logger);
});

builder.Services.AddControllers();

var app = builder.Build();

app.UsePathBase("/Netinfo");

app.UseRouting();
app.UseCors();

app.UseStaticFiles(new StaticFileOptions
{
    FileProvider = new PhysicalFileProvider(
        Path.Combine(Directory.GetCurrentDirectory(), "wwwroot")),
    RequestPath = ""
});

app.UseDefaultFiles(new DefaultFilesOptions
{
    DefaultFileNames = new List<string> { "index.html" }
});

app.UseEndpoints(endpoints =>
{
    endpoints.MapControllers(); // 👈 tüm controller'ları aktif eder
});

app.Run();