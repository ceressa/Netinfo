using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using Newtonsoft.Json;
using Serilog;

namespace Netinfo.Services
{
    public class TokenService
    {
        private readonly string _tokenFilePath;
        private readonly Serilog.ILogger _logger;  // Serilog.ILogger kullan
        private List<TokenInfo> _tokens;

        public TokenService(Serilog.ILogger logger)  // Serilog.ILogger parametre
        {
            _logger = logger;
            _tokenFilePath = Path.Combine("D:", "INTRANET", "Netinfo", "Data", "tool_tokens.json");
            LoadTokens();
        }

        public TokenInfo CreateToken()
{
    var token = new TokenInfo
    {
        Id = Guid.NewGuid().ToString("N")[..8],
        TokenValue = GenerateToken(),
        CreatedAt = DateTime.UtcNow,
        ExpiresAt = DateTime.UtcNow.AddHours(1),
        Description = "",
        IsActive = true
    };

    _tokens.Add(token);
    SaveTokens();
    return token;
}



        public bool ValidateToken(string tokenValue)
        {
            CleanExpiredTokens();
            var token = _tokens.FirstOrDefault(t => t.TokenValue == tokenValue && t.IsActive);
            return token != null && token.ExpiresAt > DateTime.UtcNow;
        }

        public TokenInfo GetTokenInfo(string tokenValue)
        {
            return _tokens.FirstOrDefault(t => t.TokenValue == tokenValue && t.IsActive);
        }

        public List<TokenInfo> GetActiveTokens()
{
    CleanExpiredTokens(); // otomatik siler
    return _tokens.Where(t => t.IsActive && t.ExpiresAt > DateTime.UtcNow).ToList();
}


        public bool RevokeToken(string tokenValue)
        {
            var token = _tokens.FirstOrDefault(t => t.TokenValue == tokenValue);
            if (token != null)
            {
                token.IsActive = false;
                SaveTokens();
                return true;
            }
            return false;
        }

       private string GenerateToken()
{
    // Komik token formatı: AQ-TR-[ADJECTIVE][NUMBER]
    var adjective = GetFunnyPrefix();     // Örn: "NOOB", "FATAL", "WEIRD"
    var number = GenerateRandomString(5); // Örn: "X7P3Q"
    return $"WTF-{adjective}{number}";
}

private string GenerateRandomString(int length)
{
    const string chars = "123456789";
    using var rng = RandomNumberGenerator.Create();
    var bytes = new byte[length];
    rng.GetBytes(bytes);
    return new string(bytes.Select(b => chars[b % chars.Length]).ToArray());
}

private string GetFunnyPrefix()
{
    // Bu listeye istediğin kadar mizahi veya yerel terim ekleyebilirsin
    string[] prefixes = new[]
    {
        "UFUK-", "MEHMETCAN-", "KADRIYECAN-", "NIHATOZ-", "KORLAELCI-"
    };

    using var rng = RandomNumberGenerator.Create();
    byte[] buffer = new byte[1];
    rng.GetBytes(buffer);
    int index = buffer[0] % prefixes.Length;
    return prefixes[index];
}


        private void LoadTokens()
{
    try
    {
        _logger.Information("Loading tokens from: {FilePath}", _tokenFilePath);
        
        if (File.Exists(_tokenFilePath))
        {
            var json = File.ReadAllText(_tokenFilePath);
            _tokens = JsonConvert.DeserializeObject<List<TokenInfo>>(json) ?? new List<TokenInfo>();
            _logger.Information("Loaded {Count} tokens from storage", _tokens.Count);
        }
        else
        {
            _tokens = new List<TokenInfo>();
            _logger.Warning("Token file not found, creating empty list: {FilePath}", _tokenFilePath);
            
            // Dosyayı oluştur
            SaveTokens();
        }
    }
    catch (Exception ex)
    {
        _logger.Error(ex, "Error loading tokens from {FilePath}", _tokenFilePath);
        _tokens = new List<TokenInfo>();
    }
}

        private void SaveTokens()
        {
            try
            {
                var directory = Path.GetDirectoryName(_tokenFilePath);
                if (!Directory.Exists(directory))
                    Directory.CreateDirectory(directory);

                var json = JsonConvert.SerializeObject(_tokens, Formatting.Indented);
                File.WriteAllText(_tokenFilePath, json);
                _logger.Information("Saved {Count} tokens to storage", _tokens.Count);
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "Error saving tokens to {FilePath}", _tokenFilePath);
            }
        }

        private void CleanExpiredTokens()
        {
            var expiredCount = _tokens.RemoveAll(t => t.ExpiresAt < DateTime.UtcNow);
            if (expiredCount > 0)
            {
                SaveTokens();
                _logger.Information("Cleaned {Count} expired tokens", expiredCount);
            }
        }
    }

    public class TokenInfo
    {
        public string Id { get; set; }
        public string TokenValue { get; set; }
        public DateTime CreatedAt { get; set; }
        public DateTime ExpiresAt { get; set; }
        public string Description { get; set; }
        public bool IsActive { get; set; }
    }
}