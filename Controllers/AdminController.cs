using Microsoft.AspNetCore.Mvc;
using Netinfo.Services;
using Serilog;
using System.Globalization;

namespace Netinfo.Controllers
{
    [ApiController]
    [Route("api/environment")]
    public class AdminController : ControllerBase
    {
        private readonly IAdminAuthService _authService;
        private readonly Serilog.ILogger _logger;

        private static int _failedAttempts = 0;
        private static DateTime? _lockoutEndTime;
        private static DateTime? _lastActivityTime;

        // Admin session tracking - used by other controllers to verify admin access
        private static readonly HashSet<string> _activeAdminSessions = new();
        private static readonly object _sessionLock = new();

        public static bool IsAdminSession(string? clientIp)
        {
            if (string.IsNullOrEmpty(clientIp)) return false;
            lock (_sessionLock)
            {
                return _activeAdminSessions.Contains(clientIp);
            }
        }

        private static void GrantAdminSession(string? clientIp)
        {
            if (string.IsNullOrEmpty(clientIp)) return;
            lock (_sessionLock)
            {
                _activeAdminSessions.Add(clientIp);
            }
        }

        private static void RevokeAdminSession(string? clientIp)
        {
            if (string.IsNullOrEmpty(clientIp)) return;
            lock (_sessionLock)
            {
                _activeAdminSessions.Remove(clientIp);
            }
        }

        public AdminController(IAdminAuthService authService, Serilog.ILogger logger)
        {
            _authService = authService ?? throw new ArgumentNullException(nameof(authService));
            _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        }

        [HttpPost("validate_admin_password")]
        public IActionResult ValidateAdminPassword([FromBody] PasswordModel model)
        {
            if (model == null || string.IsNullOrWhiteSpace(model.Password))
            {
                _logger.Warning("Şifre doğrulama isteği boş veya geçersiz bir şifre ile yapıldı.");
                return BadRequest(new { success = false, message = "Şifre eksik." });
            }

            // 10 dakika kilit kontrolü
            if (_lockoutEndTime.HasValue && DateTime.UtcNow < _lockoutEndTime.Value)
            {
                TimeSpan remainingLockout = _lockoutEndTime.Value - DateTime.UtcNow;
                string formattedTime = remainingLockout.ToString(@"mm\:ss");
                return Unauthorized(new
                {
                    success = false,
                    message = $"3 kez başarısız giriş denemesi yaptığınız için 10 dakika boyunca sisteme giriş yapamayacaksınız. Kalan süre: {formattedTime}"
                });
            }

            bool isValid = _authService.ValidatePassword(model.Password);
            string logTime = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss", new CultureInfo("tr-TR"));

            if (isValid)
            {
                _failedAttempts = 0;
                _lastActivityTime = DateTime.UtcNow;
                GrantAdminSession(HttpContext.Connection.RemoteIpAddress?.ToString());
                _logger.Information("Basarili admin girisi. Zaman: {Time}", logTime);
                return Ok(new { success = true, message = "Admin giris basarili." });
            }

            // Başarısız giriş işlemleri
            _failedAttempts++;
            _logger.Warning(
                "Basarisiz admin giris denemesi. IP: {IP}, Zaman: {Time}",
                HttpContext.Connection.RemoteIpAddress?.ToString(),
                logTime
            );

            if (_failedAttempts >= 3)
            {
                _lockoutEndTime = DateTime.UtcNow.AddMinutes(10); // 10 dakikalık kilit
                _logger.Warning("3 kez yanlış giriş denemesi. 10 dakika boyunca giriş yapılamayacak.");
                return Unauthorized(new { success = false, message = "3 kez başarısız giriş denemesi yaptığınız için 10 dakika boyunca sisteme giriş yapamayacaksınız." });
            }

            return Unauthorized(new { success = false, message = "Hatalı şifre." });
        }

        [HttpPost("check_activity")]
        public IActionResult CheckActivity()
        {
            try
            {
                var clientIp = HttpContext.Connection.RemoteIpAddress?.ToString();
                if (_lastActivityTime.HasValue && DateTime.UtcNow - _lastActivityTime.Value > TimeSpan.FromMinutes(5))
                {
                    _logger.Information("Inaktif oturum kapatildi. Son aktivite: {LastActivity}", _lastActivityTime);
                    _lastActivityTime = null;
                    RevokeAdminSession(clientIp);
                    return Unauthorized(new { success = false, message = "Inaktif oturum kapatildi." });
                }

                _lastActivityTime = DateTime.UtcNow;
                return Ok(new { success = true });
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "CheckActivity hatasi.");
                return StatusCode(500, new { success = false, message = "Internal server error." });
            }
        }
    }

    public class PasswordModel
    {
        public string Password { get; set; } = string.Empty;
    }
}
