using System;
using Microsoft.AspNetCore.Mvc;
using Serilog;
using Netinfo.Services;

namespace Netinfo.Controllers
{
    [ApiController]
    [Route("api/token")]
    public class TokenController : ControllerBase
    {
        private readonly TokenService _tokenService;
        private readonly Serilog.ILogger _logger;

        public TokenController(TokenService tokenService, Serilog.ILogger logger)
        {
            _tokenService = tokenService ?? throw new ArgumentNullException(nameof(tokenService));
            _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        }

        [HttpPost("create")]
        public IActionResult CreateToken()
        {
            try
            {
                var token = _tokenService.CreateToken();
                _logger.Information("Token created: {TokenId}", token.Id);

                return Ok(new
                {
                    success = true,
                    token = token.TokenValue,
                    expires = token.ExpiresAt
                });
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "Error creating token");
                return StatusCode(500, new { success = false, error = "Token olusturulamadi." });
            }
        }

        [HttpGet("validate/{tokenValue}")]
        public IActionResult ValidateToken(string tokenValue)
        {
            try
            {
                if (string.IsNullOrWhiteSpace(tokenValue))
                    return BadRequest(new { success = false, error = "Token degeri gerekli." });

                var isValid = _tokenService.ValidateToken(tokenValue);
                var tokenInfo = _tokenService.GetTokenInfo(tokenValue);

                if (isValid && tokenInfo != null)
                {
                    _logger.Information("Token validated successfully: {TokenId}", tokenInfo.Id);
                    return Ok(new
                    {
                        success = true,
                        valid = true,
                        expires = tokenInfo.ExpiresAt,
                        description = tokenInfo.Description
                    });
                }

                _logger.Warning("Invalid token validation attempt");
                return Ok(new { success = true, valid = false });
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "Error validating token");
                return StatusCode(500, new { success = false, error = "Token dogrulanamadi." });
            }
        }

        [HttpGet("list")]
        public IActionResult GetActiveTokens()
        {
            try
            {
                var tokens = _tokenService.GetActiveTokens();
                return Ok(new { success = true, data = tokens, total = tokens.Count });
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "Error listing tokens");
                return StatusCode(500, new { success = false, error = "Token listesi alinamadi." });
            }
        }

        [HttpDelete("revoke/{tokenValue}")]
        public IActionResult RevokeToken(string tokenValue)
        {
            try
            {
                if (string.IsNullOrWhiteSpace(tokenValue))
                    return BadRequest(new { success = false, error = "Token degeri gerekli." });

                var revoked = _tokenService.RevokeToken(tokenValue);
                if (revoked)
                {
                    _logger.Information("Token revoked successfully");
                    return Ok(new { success = true, message = "Token iptal edildi." });
                }
                return NotFound(new { success = false, error = "Token bulunamadi." });
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "Error revoking token");
                return StatusCode(500, new { success = false, error = "Token iptal edilemedi." });
            }
        }
    }
}
