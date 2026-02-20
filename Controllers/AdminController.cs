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
                _failedAttempts = 0; // Başarılı girişte sayaç sıfırlanır
                _lastActivityTime = DateTime.UtcNow; // Son aktivite zamanını güncelle
                _logger.Information("Başarılı admin girişi. Zaman: {Time}", logTime);
                return Ok(new { success = true, message = "Admin giriş başarılı." });
            }

            // Başarısız giriş işlemleri
            _failedAttempts++;
            _logger.Warning(
                "Başarısız admin giriş denemesi. Girilen şifre: {Password}, IP: {IP}, Zaman: {Time}",
                model.Password,
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
        if (_lastActivityTime.HasValue && DateTime.UtcNow - _lastActivityTime.Value > TimeSpan.FromMinutes(5))
        {
            _logger.Information("Kullanıcı inaktif olduğu için oturumu kapatıldı. Son aktivite: {LastActivity}", _lastActivityTime);
            _lastActivityTime = null;
            return Unauthorized(new { success = false, message = "5 dakikadan fazla inaktif olduğunuz için oturum kapatıldı." });
        }

        _lastActivityTime = DateTime.UtcNow; // Aktiviteyi güncelle
        return Ok(new { success = true });
    }
    catch (Exception ex)
    {
        _logger.Error(ex, "CheckActivity sırasında bir hata oluştu.");
        return StatusCode(500, new { success = false, message = "Bir iç sunucu hatası oluştu." });
    }
}
    }

    public class PasswordModel
    {
        public string Password { get; set; }
    }
}
