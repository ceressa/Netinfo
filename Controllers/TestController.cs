using Microsoft.AspNetCore.Mvc;

namespace Netinfo.Controllers
{
    [ApiController]
[Route("api/test")]
public class TestController : ControllerBase
{
    [HttpGet("ping")]
    public IActionResult Ping()
    {
        return Ok("pong");
    }
}

}