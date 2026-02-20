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
                _logger.Warning("Empty or invalid password validation attempt.");
                return false;
            }

            try
            {
                bool isValid = BCrypt.Net.BCrypt.Verify(password, _adminPasswordHash);

                if (isValid)
                    _logger.Information("Password validation successful.");
                else
                    _logger.Warning("Password validation failed.");

                return isValid;
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "Password validation error.");
                return false;
            }
        }
    }
}
