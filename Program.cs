using Serilog;
using Microsoft.Extensions.FileProviders;
using DotNetEnv;
using Netinfo.Services;

var builder = WebApplication.CreateBuilder(args);

// .env dosyasini yukle
DotNetEnv.Env.Load();
string adminPasswordHash = Environment.GetEnvironmentVariable("ADMIN_PASSWORD_HASH")
    ?? throw new InvalidOperationException("ADMIN_PASSWORD_HASH bulunamadi.");

// Konfigurasyondan path'leri oku
var config = builder.Configuration;
string dataDir = Environment.GetEnvironmentVariable("DATA_DIR")
    ?? config["DataPaths:DataDir"]
    ?? "Data";
string logDir = Environment.GetEnvironmentVariable("LOG_DIR")
    ?? config["DataPaths:LogDir"]
    ?? "logs";
string archiveLogDir = Environment.GetEnvironmentVariable("ARCHIVE_LOG_DIR")
    ?? config["DataPaths:ArchiveLogDir"]
    ?? "logs/Archived_Logs";
string syslogDir = Environment.GetEnvironmentVariable("SYSLOG_DIR")
    ?? config["DataPaths:SyslogDir"]
    ?? "logs/Syslog_AI";
string pingLogPath = Environment.GetEnvironmentVariable("PING_LOG_PATH")
    ?? config["DataPaths:PingLogPath"]
    ?? "logs/PingStateChanges.log";

// Log klasoru ve dosya yolu
if (!Directory.Exists(logDir))
    Directory.CreateDirectory(logDir);

string logPath = Path.Combine(logDir, $"All_activities_{DateTime.UtcNow:yyyy-MM-dd}.log");

// Serilog yapilandirmasi
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

// CORS yapilandirmasi - kisitli
var corsOrigins = Environment.GetEnvironmentVariable("CORS_ALLOWED_ORIGINS");
var allowedOrigins = config.GetSection("Cors:AllowedOrigins").Get<string[]>() ?? Array.Empty<string>();

if (!string.IsNullOrEmpty(corsOrigins))
{
    allowedOrigins = corsOrigins.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
}

builder.Services.AddCors(options =>
{
    options.AddDefaultPolicy(policy =>
    {
        if (allowedOrigins.Length > 0)
        {
            policy.WithOrigins(allowedOrigins)
                  .WithMethods("GET", "POST", "DELETE")
                  .WithHeaders("Content-Type", "Authorization");
        }
        else
        {
            // Fallback: sadece same-origin izin ver
            policy.SetIsOriginAllowed(origin => new Uri(origin).Host == "localhost")
                  .WithMethods("GET", "POST", "DELETE")
                  .WithHeaders("Content-Type", "Authorization");
        }
    });
});

// DataPaths konfigurasyonunu singleton olarak kaydet
var dataPaths = new DataPathsConfig
{
    DataDir = dataDir,
    LogDir = logDir,
    ArchiveLogDir = archiveLogDir,
    SyslogDir = syslogDir,
    PingLogPath = pingLogPath,
    DeviceInventory = config["DataPaths:DeviceInventory"] ?? "network_device_inventory.json",
    PreviousDeviceInventory = config["DataPaths:PreviousDeviceInventory"] ?? "network_device_inventory_previous.json",
    MainData = config["DataPaths:MainData"] ?? "main_data.json",
    RouterData = config["DataPaths:RouterData"] ?? "main_router_data.json",
    UUIDPool = config["DataPaths:UUIDPool"] ?? "UUID_Pool.json",
    StationInfo = config["DataPaths:StationInfo"] ?? "station-info.json",
    SyslogSummary = config["DataPaths:SyslogSummary"] ?? "syslog_summary.json",
    InsightSummary = config["DataPaths:InsightSummary"] ?? "insight_summary.json",
    TokenList = config["DataPaths:TokenList"] ?? "token_list.json",
    ToolTokens = config["DataPaths:ToolTokens"] ?? "tool_tokens.json",
    DeviceConfigHistory = config["DataPaths:DeviceConfigHistory"] ?? "device_config_history.json",
    APInventory = config["DataPaths:APInventory"] ?? "access_point_inventory.json",
    EnhancedWirelessData = config["DataPaths:EnhancedWirelessData"] ?? "enhanced_wireless_data.json",
    HourlyClientStats = config["DataPaths:HourlyClientStats"] ?? "hourly_client_stats.json",
    StatusChangesLog = config["DataPaths:StatusChangesLog"] ?? "device_status_changes.json",
    TimeZoneId = config["DataPaths:TimeZoneId"] ?? "Turkey Standard Time"
};
builder.Services.AddSingleton(dataPaths);

// Servis kayitlari
builder.Services.AddSingleton<Serilog.ILogger>(Log.Logger);

builder.Services.AddSingleton<TokenService>(provider =>
{
    var logger = Log.ForContext<TokenService>();
    var paths = provider.GetRequiredService<DataPathsConfig>();
    return new TokenService(logger, paths);
});

builder.Services.AddSingleton<IAdminAuthService>(provider =>
{
    string envPasswordHash = Environment.GetEnvironmentVariable("ADMIN_PASSWORD_HASH")
        ?? throw new InvalidOperationException("ADMIN_PASSWORD_HASH bulunamadi.");
    return new AdminAuthService(envPasswordHash, Log.Logger);
});

builder.Services.AddSingleton<DeviceDataService>(provider =>
{
    var logger = Log.ForContext<DeviceDataService>();
    var paths = provider.GetRequiredService<DataPathsConfig>();
    var deviceService = new DeviceDataService(logger, paths);

    // Each load is wrapped individually so one missing file doesn't crash the entire service
    void SafeLoad(string label, Action action)
    {
        try { action(); }
        catch (Exception ex) { logger.Warning(ex, "{Label} could not be loaded on startup.", label); }
    }

    SafeLoad("DeviceData", () => deviceService.LoadDeviceData(Path.Combine(paths.DataDir, paths.DeviceInventory)));
    SafeLoad("PreviousDeviceData", () => deviceService.LoadPreviousDeviceData(Path.Combine(paths.DataDir, paths.PreviousDeviceInventory)));
    SafeLoad("PortData", () => deviceService.LoadPortData(Path.Combine(paths.DataDir, paths.MainData)));
    SafeLoad("RouterPortData", () => deviceService.LoadRouterPortData(Path.Combine(paths.DataDir, paths.RouterData)));
    SafeLoad("UUIDPool", () => deviceService.LoadUUIDPool(Path.Combine(paths.DataDir, paths.UUIDPool)));
    SafeLoad("LocationData", () => deviceService.LoadLocationData(Path.Combine(paths.DataDir, paths.StationInfo)));
    SafeLoad("LogAnalysisData", () => deviceService.LoadLogAnalysisData(Path.Combine(paths.SyslogDir, paths.SyslogSummary)));
    SafeLoad("InsightSummary", () => deviceService.LoadInsightSummary(Path.Combine(paths.DataDir, paths.InsightSummary)));

    logger.Information("DeviceDataService initialized. DataDir={DataDir}, SyslogDir={SyslogDir}", paths.DataDir, paths.SyslogDir);
    return deviceService;
});

// AP Dashboard Service Registration
builder.Services.AddSingleton<AccessPointService>(provider =>
{
    var logger = Log.ForContext<AccessPointService>();
    var paths = provider.GetRequiredService<DataPathsConfig>();
    return new AccessPointService(logger, paths);
});

builder.Services.AddControllers();

var app = builder.Build();

app.UsePathBase("/Netinfo");

// Security headers middleware
app.Use(async (context, next) =>
{
    var headers = context.Response.Headers;
    headers["X-Content-Type-Options"] = "nosniff";
    headers["X-Frame-Options"] = "DENY";
    headers["X-XSS-Protection"] = "1; mode=block";
    headers["Referrer-Policy"] = "strict-origin-when-cross-origin";
    headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()";
    headers["Content-Security-Policy"] =
        "default-src 'self'; " +
        "connect-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://stackpath.bootstrapcdn.com; " +
        "script-src 'self' 'unsafe-inline' https://code.jquery.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://stackpath.bootstrapcdn.com; " +
        "style-src 'self' 'unsafe-inline' https://stackpath.bootstrapcdn.com https://cdnjs.cloudflare.com; " +
        "img-src 'self' https://tr.eu.fedex.com data:; " +
        "font-src 'self' https://cdnjs.cloudflare.com;";
    await next();
});

// API rate limiting middleware - per IP, per endpoint category
var _rateLimitStore = new System.Collections.Concurrent.ConcurrentDictionary<string, (int count, DateTime windowStart)>();
app.Use(async (context, next) =>
{
    if (context.Request.Path.StartsWithSegments("/api"))
    {
        var clientIp = context.Connection.RemoteIpAddress?.ToString() ?? "unknown";
        var path = context.Request.Path.Value ?? "";
        var now = DateTime.UtcNow;
        var window = TimeSpan.FromMinutes(1);

        // Sensitive endpoints get stricter limits
        int maxRequests;
        if (path.Contains("/validate_admin_password") || path.Contains("/token/create"))
            maxRequests = 10;
        else if (path.Contains("/token/") || path.Contains("/reload") || path.Contains("/ap-reload"))
            maxRequests = 20;
        else
            maxRequests = 100;

        var rateLimitKey = $"{clientIp}:{(maxRequests <= 20 ? path : "general")}";
        var entry = _rateLimitStore.AddOrUpdate(rateLimitKey,
            _ => (1, now),
            (_, existing) =>
            {
                if (now - existing.windowStart > window)
                    return (1, now);
                return (existing.count + 1, existing.windowStart);
            });

        if (entry.count > maxRequests)
        {
            context.Response.StatusCode = 429;
            context.Response.Headers["Retry-After"] = "60";
            await context.Response.WriteAsJsonAsync(new { success = false, error = "Too many requests. Please try again later." });
            return;
        }
    }
    await next();
});

// API cache control middleware
app.Use(async (context, next) =>
{
    if (context.Request.Path.StartsWithSegments("/api"))
    {
        context.Response.OnStarting(() =>
        {
            if (!context.Response.Headers.ContainsKey("Cache-Control"))
            {
                context.Response.Headers["Cache-Control"] = "no-store, no-cache, must-revalidate";
                context.Response.Headers["Pragma"] = "no-cache";
            }
            return Task.CompletedTask;
        });
    }
    await next();
});

app.UseRouting();
app.UseCors();

app.UseDefaultFiles(new DefaultFilesOptions
{
    DefaultFileNames = new List<string> { "index.html" }
});

app.UseStaticFiles(new StaticFileOptions
{
    FileProvider = new PhysicalFileProvider(
        Path.Combine(Directory.GetCurrentDirectory(), "wwwroot")),
    RequestPath = ""
});

app.UseEndpoints(endpoints =>
{
    endpoints.MapControllers();
});

// Diagnostic health check - no DI dependencies, always works if app is running
app.MapGet("/api/health", (IServiceProvider sp) =>
{
    var result = new Dictionary<string, object> { ["status"] = "running", ["time"] = DateTime.UtcNow.ToString("o") };
    try
    {
        var paths = sp.GetRequiredService<DataPathsConfig>();
        result["dataDir"] = paths.DataDir;
        result["dataDirExists"] = Directory.Exists(paths.DataDir);
        result["syslogDir"] = paths.SyslogDir;

        var files = new Dictionary<string, object>
        {
            ["DeviceInventory"] = File.Exists(Path.Combine(paths.DataDir, paths.DeviceInventory)),
            ["UUIDPool"] = File.Exists(Path.Combine(paths.DataDir, paths.UUIDPool)),
            ["MainData"] = File.Exists(Path.Combine(paths.DataDir, paths.MainData)),
            ["StationInfo"] = File.Exists(Path.Combine(paths.DataDir, paths.StationInfo)),
            ["SyslogSummary"] = File.Exists(Path.Combine(paths.SyslogDir, paths.SyslogSummary)),
        };
        result["files"] = files;

        // Test if DeviceDataService can be resolved
        try { sp.GetRequiredService<DeviceDataService>(); result["deviceDataService"] = "OK"; }
        catch { result["deviceDataService"] = "FAILED"; }
    }
    catch { result["error"] = "Health check error"; }
    return Results.Json(result);
});

app.Run();
