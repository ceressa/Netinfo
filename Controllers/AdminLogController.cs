using Microsoft.AspNetCore.Mvc;
using Serilog;

namespace Netinfo.Controllers
{
    [ApiController]
    [Route("api/log")]
    public class AdminLogController : ControllerBase
    {
        private readonly Serilog.ILogger _logger;

        public AdminLogController(Serilog.ILogger logger)
        {
            _logger = logger;
        }

        [HttpPost("admin_activity")]
public IActionResult LogAdminActivity([FromBody] AdminActivityLogModel model)
{
    if (model == null || string.IsNullOrEmpty(model.Activity))
    {
        _logger.Warning("Log isteği eksik veri ile yapıldı. IP: {IP}", HttpContext.Connection.RemoteIpAddress);
        return BadRequest(new { success = false, message = "Eksik veya geçersiz veri." });
    }

    string clientIp = HttpContext.Connection.RemoteIpAddress?.ToString() ?? "Unknown IP";

    _logger.Information("Admin aktivitesi loglandı. Aktivite: {Activity}, Tarih: {Timestamp}, IP: {IP}", model.Activity, model.Timestamp, clientIp);

    return Ok(new { success = true, message = "Log kaydedildi." });
}

}

    public class AdminActivityLogModel
{
    public string? Activity { get; set; }
    public DateTime Timestamp { get; set; } = DateTime.UtcNow; // Varsayılan değer
    public string? Username { get; set; } // Aktiviteyi gerçekleştiren kullanıcı
}

}
