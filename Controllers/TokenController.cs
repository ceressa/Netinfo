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
        private readonly Serilog.ILogger _logger;  // Microsoft.Extensions.Logging değil, Serilog.ILogger

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
            token = token.TokenValue,
            expires = token.ExpiresAt
        });
    }
    catch (Exception ex)
    {
        _logger.Error(ex, "Error creating token");
        return StatusCode(500, new { error = ex.Message });
    }
}


        [HttpGet("validate/{tokenValue}")]
        public IActionResult ValidateToken(string tokenValue)
        {
            try
            {
                var isValid = _tokenService.ValidateToken(tokenValue);
                var tokenInfo = _tokenService.GetTokenInfo(tokenValue);

                if (isValid && tokenInfo != null)
                {
                    _logger.Information("Token validated successfully: {TokenId}", tokenInfo.Id);
                    return Ok(new { 
                        valid = true, 
                        expires = tokenInfo.ExpiresAt,
                        description = tokenInfo.Description 
                    });
                }

                _logger.Warning("Invalid token validation attempt: {Token}", tokenValue);
                return Ok(new { valid = false });
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "Error validating token");
                return StatusCode(500, new { error = ex.Message });
            }
        }

        [HttpGet("list")]
        public IActionResult GetActiveTokens()
        {
            try
            {
                var tokens = _tokenService.GetActiveTokens();
                return Ok(tokens);
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "Error listing tokens");
                return StatusCode(500, new { error = ex.Message });
            }
        }

        [HttpDelete("revoke/{tokenValue}")]
        public IActionResult RevokeToken(string tokenValue)
        {
            try
            {
                var revoked = _tokenService.RevokeToken(tokenValue);
                if (revoked)
                {
                    _logger.Information("Token revoked: {Token}", tokenValue);
                    return Ok(new { message = "Token revoked successfully" });
                }
                return NotFound(new { error = "Token not found" });
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "Error revoking token");
                return StatusCode(500, new { error = ex.Message });
            }
        }
    }

    public class CreateTokenRequest
    {
        public string Description { get; set; } = "";
    }
}