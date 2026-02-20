using Microsoft.AspNetCore.Mvc;
using Serilog;
using System.Text.RegularExpressions;

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
                return BadRequest(new { success = false, error = "Eksik veya gecersiz veri." });
            }

            // Sanitize activity string to prevent log injection
            string sanitizedActivity = Regex.Replace(model.Activity, @"[\r\n]", " ");
            string clientIp = HttpContext.Connection.RemoteIpAddress?.ToString() ?? "Unknown IP";

            _logger.Information("Admin aktivitesi. Aktivite: {Activity}, Tarih: {Timestamp}, IP: {IP}",
                sanitizedActivity, model.Timestamp, clientIp);

            return Ok(new { success = true, message = "Log kaydedildi." });
        }
    }

    public class AdminActivityLogModel
    {
        public string? Activity { get; set; }
        public DateTime Timestamp { get; set; } = DateTime.UtcNow;
        public string? Username { get; set; }
    }
}
