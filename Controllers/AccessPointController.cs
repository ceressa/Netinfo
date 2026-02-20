using Microsoft.AspNetCore.Mvc;
using Netinfo.Services;

namespace Netinfo.Controllers
{
    [ApiController]
    [Route("api/device")]
    public class AccessPointController : ControllerBase
    {
        private readonly AccessPointService _accessPointService;
        private readonly Serilog.ILogger _logger;

        public AccessPointController(AccessPointService accessPointService, Serilog.ILogger logger)
        {
            _accessPointService = accessPointService;
            _logger = logger.ForContext<AccessPointController>();
        }

        /// <summary>
        /// Get complete Access Point inventory with summary statistics
        /// </summary>
        [HttpGet("ap-inventory")]
        public async Task<IActionResult> GetAccessPointInventory()
        {
            try
            {
                _logger.Information("AP inventory requested");
                var result = await _accessPointService.GetAccessPointInventory();
                return Ok(result);
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "Error retrieving AP inventory");
                return StatusCode(500, new { success = false, error = "Failed to retrieve AP inventory" });
            }
        }

        /// <summary>
        /// Get all wireless clients across all APs with detailed information
        /// </summary>
        [HttpGet("ap-clients")]
        public async Task<IActionResult> GetWirelessClients()
        {
            try
            {
                _logger.Information("Wireless clients data requested");
                var result = await _accessPointService.GetWirelessClients();
                return Ok(result);
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "Error retrieving wireless clients");
                return StatusCode(500, new { success = false, error = "Failed to retrieve wireless clients" });
            }
        }
		
		

        /// <summary>
        /// Get comprehensive AP statistics including top APs, uptime leaders, and signal analysis
        /// </summary>
        [HttpGet("ap-statistics")]
        public async Task<IActionResult> GetAPStatistics()
        {
            try
            {
                _logger.Information("AP statistics requested");
                var result = await _accessPointService.GetAPStatistics();
                return Ok(result);
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "Error retrieving AP statistics");
                return StatusCode(500, new { success = false, error = "Failed to retrieve AP statistics" });
            }
        }

        /// <summary>
        /// Combined endpoint - All AP dashboard data in single response
        /// </summary>
        [HttpGet("ap-dashboard")]
public async Task<IActionResult> GetAPDashboardData()
{
    try
    {
        _logger.Information("Complete AP dashboard data requested");
        
        var inventory = await _accessPointService.GetAccessPointInventory();
        var clients = await _accessPointService.GetWirelessClients();
        var statistics = await _accessPointService.GetAPStatistics();
        var hourlyStats = await _accessPointService.GetHourlyClientStats(); // BUNU EKLE

        var combinedResult = new
        {
            success = true,
            inventory,
            clients,
            statistics,
            hourly_stats = hourlyStats, // BUNU EKLE
            last_updated = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"),
            refresh_interval = 30 // seconds
        };

        return Ok(combinedResult);
    }
    catch (Exception ex)
    {
        _logger.Error(ex, "Error retrieving complete AP dashboard data");
        return StatusCode(500, new { success = false, error = "Failed to retrieve AP dashboard data" });
    }
}

        /// <summary>
        /// Force reload AP data from files
        /// </summary>
        [HttpPost("ap-reload")]
        public async Task<IActionResult> ReloadAPData()
        {
            try
            {
                _logger.Information("AP data reload requested");
                await Task.Run(() => _accessPointService.LoadAllAPData());
                
                return Ok(new 
                { 
                    success = true, 
                    message = "AP data reloaded successfully",
                    timestamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss")
                });
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "Error reloading AP data");
                return StatusCode(500, new { success = false, error = "Failed to reload AP data" });
            }
        }
    }
}