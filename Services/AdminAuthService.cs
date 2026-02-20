using System.Security.Cryptography;
using System.Text;
using Serilog;

namespace Netinfo.Services
{
    public class AdminAuthService : IAdminAuthService
    {
        private readonly string _adminPasswordHash;
        private readonly Serilog.ILogger _logger;

        public AdminAuthService(string adminPasswordHash, Serilog.ILogger logger)
        {
            _adminPasswordHash = adminPasswordHash ?? throw new ArgumentNullException(nameof(adminPasswordHash));
            _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        }

        public bool ValidatePassword(string password)
{
    if (string.IsNullOrWhiteSpace(password))
    {
        _logger.Warning("Şifre doğrulama boş veya geçersiz bir şifre ile denendi.");
        return false;
    }
    
    string hashedPassword = ComputeSha256Hash(password);
    
    // DEBUG: Hash değerlerini loglayın
    _logger.Information($"Girilen şifre: {password}");
    _logger.Information($"Girilen şifrenin hash'i: {hashedPassword}");
    _logger.Information($"Beklenen hash: {_adminPasswordHash}");
    
    bool isValid = hashedPassword == _adminPasswordHash;
    
    if (isValid)
    {
        _logger.Information("Şifre doğrulama başarılı.");
    }
    else
    {
        _logger.Warning("Şifre doğrulama başarısız.");
    }
    
    return isValid;
}

        private static string ComputeSha256Hash(string rawData)
        {
            using var sha256 = SHA256.Create();
            byte[] bytes = sha256.ComputeHash(Encoding.UTF8.GetBytes(rawData));
            return BitConverter.ToString(bytes).Replace("-", "").ToLowerInvariant();
        }
    }
}