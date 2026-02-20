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
        private readonly DataPathsConfig _paths;
        private List<TokenInfo> _tokens = new();

        public TokenService(Serilog.ILogger logger, DataPathsConfig paths)  // Serilog.ILogger parametre
        {
            _logger = logger;
            _paths = paths;
            _tokenFilePath = Path.Combine(_paths.DataDir, _paths.ToolTokens);
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

        public TokenInfo? GetTokenInfo(string tokenValue)
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
            // Cryptographically secure URL-safe Base64 token
            var tokenBytes = RandomNumberGenerator.GetBytes(32);
            var base64Token = Convert.ToBase64String(tokenBytes)
                .Replace("+", "-")
                .Replace("/", "_")
                .TrimEnd('=');
            return base64Token;
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
                if (directory != null && !Directory.Exists(directory))
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
        public string Id { get; set; } = string.Empty;
        public string TokenValue { get; set; } = string.Empty;
        public DateTime CreatedAt { get; set; }
        public DateTime ExpiresAt { get; set; }
        public string Description { get; set; } = string.Empty;
        public bool IsActive { get; set; }
    }
}
