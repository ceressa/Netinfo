using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Microsoft.AspNetCore.Mvc;
using Serilog;
using Netinfo.Services;
using Newtonsoft.Json;

namespace Netinfo.Controllers
{
    [ApiController]
    [Route("api/device")]
    public class DeviceController : ControllerBase
    {
        private readonly DeviceDataService _deviceDataService;
        private readonly DataPathsConfig _dataPaths;
        private readonly Serilog.ILogger _logger;

        public DeviceController(DeviceDataService deviceDataService, DataPathsConfig dataPaths, Serilog.ILogger logger)
        {
            _deviceDataService = deviceDataService ?? throw new ArgumentNullException(nameof(deviceDataService));
            _dataPaths = dataPaths ?? throw new ArgumentNullException(nameof(dataPaths));
            _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        }

        [HttpGet("token_list")]
        public IActionResult GetTokenList()
        {
            try
            {
                var filePath = Path.Combine(_dataPaths.DataDir, _dataPaths.TokenList);
                if (!System.IO.File.Exists(filePath))
                    return NotFound(new { success = false, error = "Token list not found." });

                var json = System.IO.File.ReadAllText(filePath);
                var tokenList = JsonConvert.DeserializeObject<object>(json);
                return Ok(tokenList);
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "Error loading token_list.json");
                return StatusCode(500, new { success = false, error = ex.Message });
            }
        }

        [HttpGet("get_device_info")]
        public IActionResult GetDeviceInfo(string id)
        {
            try
            {
                if (string.IsNullOrEmpty(id))
                {
                    _logger.Warning("Device ID is null or empty.");
                    return BadRequest(new { success = false, error = "Device ID is required." });
                }

                var device = _deviceDataService.GetDeviceById(id);
                if (device == null)
                {
                    _logger.Warning("Device with ID {Id} not found.", id);
                    return NotFound(new { success = false, error = $"Device with ID '{id}' not found." });
                }

                _logger.Information("Device with ID {Id} retrieved successfully.", id);
                return Ok(device);
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "An error occurred while retrieving device info for ID {Id}.", id);
                return StatusCode(500, new { success = false, error = ex.Message });
            }
        }

        [HttpGet("insight_summary")]
        public IActionResult GetInsightSummary()
        {
            try
            {
                var latest = _deviceDataService.GetLatestInsightSummary();
                return latest != null ? Ok(latest) : NotFound(new { success = false, error = "No insight summary available." });
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "Error fetching insight summary.");
                return StatusCode(500, new { success = false, error = "Internal server error" });
            }
        }

        [HttpGet("get_device_ports")]
        public IActionResult GetDevicePorts([FromQuery] string id)
        {
            try
            {
                if (string.IsNullOrEmpty(id))
                {
                    _logger.Warning("Device ID is null or empty.");
                    return BadRequest(new { success = false, error = "Device ID is required" });
                }

                var ports = _deviceDataService.GetPortsByDeviceId(id);
                if (ports == null || !ports.Any())
                {
                    _logger.Warning("No ports found for Device ID {Id}.", id);
                    return NotFound(new { success = false, error = "No ports found for the specified device." });
                }

                _logger.Information("Ports for Device ID {Id} retrieved successfully.", id);
                return Ok(ports);
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "An error occurred while retrieving ports for Device ID {Id}.", id);
                return StatusCode(500, new { success = false, error = ex.Message });
            }
        }

        [HttpGet("get_router_ports")]
        public IActionResult GetRouterPorts([FromQuery] string id)
        {
            if (string.IsNullOrEmpty(id))
                return BadRequest(new { success = false, error = "ID is required" });

            var routerPorts = _deviceDataService.GetRouterPortsByDeviceId(id);
            if (routerPorts == null)
                return NotFound(new { success = false, error = "Router ports not found." });

            return Ok(routerPorts);
        }

        [HttpGet("get_all_devices")]
        public IActionResult GetAllDevices([FromQuery] int page = 1, [FromQuery] int pageSize = 50)
        {
            try
            {
                _logger.Information("GetAllDevices API called. Page: {Page}, PageSize: {PageSize}", page, pageSize);

                var devices = _deviceDataService.GetAllDevices();
                if (devices == null || !devices.Any())
                {
                    _logger.Warning("No devices found.");
                    return NotFound(new { success = false, error = "No devices found." });
                }

                var pagedItems = devices.Skip((page - 1) * pageSize).Take(pageSize).ToList();

                _logger.Information("Total devices: {Total}, returning page {Page} with {Count} items.", devices.Count, page, pagedItems.Count);
                return Ok(new { data = pagedItems, total = devices.Count, page, pageSize });
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "An error occurred while retrieving all devices.");
                return StatusCode(500, new { success = false, error = ex.Message });
            }
        }

        [HttpGet("device-status-changes")]
        public IActionResult GetDeviceStatusChanges()
        {
            try
            {
                var statusLogFile = Path.Combine(_dataPaths.LogDir, "Latest_Logs", _dataPaths.StatusChangesLog);

                if (!System.IO.File.Exists(statusLogFile))
                    return NotFound(new { success = false, error = "Status change log not found." });

                var jsonContent = System.IO.File.ReadAllText(statusLogFile);
                return Ok(jsonContent);
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "Error reading device status changes log.");
                return StatusCode(500, new { success = false, error = ex.Message });
            }
        }

        [HttpGet("device-status-archives")]
        public IActionResult GetArchivedStatusLogs()
        {
            try
            {
                var archiveFolder = _dataPaths.ArchiveLogDir;

                if (!Directory.Exists(archiveFolder))
                    return NotFound(new { success = false, error = "Archive folder not found." });

                var archiveFiles = Directory.GetFiles(archiveFolder, "device_status_archive_*.json")
                                            .OrderByDescending(f => f)
                                            .ToList();

                if (archiveFiles.Count == 0)
                    return NotFound(new { success = false, error = "No archived log files found." });

                var latestArchiveFile = archiveFiles.First();
                var jsonContent = System.IO.File.ReadAllText(latestArchiveFile);

                return Ok(jsonContent);
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "Error reading archived status logs.");
                return StatusCode(500, new { success = false, error = ex.Message });
            }
        }

        [HttpGet("reload_device_data")]
        public IActionResult ReloadDeviceData()
        {
            try
            {
                _logger.Information("Reloading device data from JSON...");

                _deviceDataService.LoadDeviceData(Path.Combine(_dataPaths.DataDir, _dataPaths.DeviceInventory));
                _deviceDataService.LoadPreviousDeviceData(Path.Combine(_dataPaths.DataDir, _dataPaths.PreviousDeviceInventory));
                _deviceDataService.LoadPortData(Path.Combine(_dataPaths.DataDir, _dataPaths.MainData));

                _logger.Information("Device data reloaded successfully.");
                return Ok(new { message = "Device data reloaded successfully." });
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "An error occurred while reloading device data.");
                return StatusCode(500, new { success = false, error = ex.Message });
            }
        }

        [HttpGet("get_ping_log")]
        public IActionResult GetPingLog(string id)
        {
            try
            {
                var logFilePath = _dataPaths.PingLogPath;

                if (!System.IO.File.Exists(logFilePath))
                {
                    return NotFound(new { success = false, error = "Ping state log not found." });
                }

                var logLines = System.IO.File.ReadAllLines(logFilePath)
                    .Where(line => line.Contains($"Device ID: {id}"))
                    .ToList();

                if (logLines.Count == 0)
                {
                    return NotFound(new { success = false, error = "No logs found for the specified device." });
                }

                return Ok(logLines);
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "Error while fetching ping log for device ID: {Id}", id);
                return StatusCode(500, new { success = false, error = ex.Message });
            }
        }

        [HttpGet("uuid_to_deviceid")]
        public IActionResult GetDeviceIdByUUID([FromQuery] string uuid)
        {
            try
            {
                if (string.IsNullOrEmpty(uuid))
                {
                    _logger.Warning("UUID is null or empty.");
                    return BadRequest(new { success = false, error = "UUID is required." });
                }

                var deviceId = _deviceDataService.GetDeviceIdByUUID(uuid);
                if (deviceId == null)
                {
                    _logger.Warning("No device found for UUID: {UUID}", uuid);
                    return NotFound(new { success = false, error = $"No device found for UUID '{uuid}'." });
                }

                _logger.Information("Device ID {DeviceId} retrieved for UUID {UUID}", deviceId, uuid);
                return Ok(new { uuid = uuid, device_id = deviceId });
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "An error occurred while fetching Device ID for UUID: {UUID}.", uuid);
                return StatusCode(500, new { success = false, error = ex.Message });
            }
        }

        [HttpPost("get_location_info")]
        public IActionResult GetLocationInfo([FromBody] LocationRequest request)
        {
            try
            {
                if (string.IsNullOrEmpty(request.LocationCode))
                    return BadRequest(new { success = false, error = "Location code is required." });

                var locationInfo = _deviceDataService.GetLocationInfoByCode(request.LocationCode);
                if (locationInfo == null)
                    return NotFound(new { success = false, error = "Location information not found." });

                var deviceSummary = _deviceDataService.GetDevicesByLocationCode(request.LocationCode);
                var mapUrl = locationInfo.TryGetValue("maps url", out var url) ? url.ToString() : string.Empty;

                return Ok(new
                {
                    success = true,
                    locationDetails = locationInfo,
                    deviceSummary,
                    mapUrl
                });
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "Error fetching location info for code: {LocationCode}", request.LocationCode);
                return StatusCode(500, new { success = false, error = ex.Message });
            }
        }

        [HttpGet("get_devices_by_location")]
        public IActionResult GetDevicesByLocation([FromQuery] string locationCode)
        {
            try
            {
                if (string.IsNullOrEmpty(locationCode))
                {
                    _logger.Warning("Location code is null or empty.");
                    return BadRequest(new { success = false, error = "Location code is required." });
                }

                _logger.Information("Fetching devices for location code: {LocationCode}", locationCode);

                var devices = _deviceDataService.GetDevicesByLocationCode(locationCode);
                if (devices == null || !devices.Any())
                {
                    _logger.Warning("No devices found for Location Code: {LocationCode}", locationCode);
                    return NotFound(new { success = false, error = $"No devices found for the location code '{locationCode}'." });
                }

                _logger.Information("Devices found: {Count} for Location Code: {LocationCode}", devices.Count, locationCode);
                return Ok(new { devices });
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "Error fetching devices for Location Code: {LocationCode}", locationCode);
                return StatusCode(500, new { success = false, error = "An internal server error occurred.", details = ex.Message });
            }
        }

        [HttpGet("get_vlans")]
        public IActionResult GetVlanData()
        {
            try
            {
                _logger.Information("Fetching VLAN data from JSON...");
                var vlanData = _deviceDataService.GetVlanData();

                if (vlanData == null || !vlanData.Any())
                {
                    _logger.Warning("No VLAN data available.");
                    return NotFound(new { success = false, error = "No VLAN data found." });
                }

                return Ok(vlanData);
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "An error occurred while retrieving VLAN data.");
                return StatusCode(500, new { success = false, error = "An error occurred while fetching VLAN data.", details = ex.Message });
            }
        }

        [HttpGet("get_all_device_ports")]
        public IActionResult GetAllDevicePorts([FromQuery] int page = 1, [FromQuery] int pageSize = 50)
        {
            try
            {
                _logger.Information("Fetching all device ports data. Page: {Page}, PageSize: {PageSize}", page, pageSize);

                var allPorts = _deviceDataService.GetAllPorts();
                if (allPorts == null || !allPorts.Any())
                {
                    _logger.Warning("No port data found.");
                    return NotFound(new { success = false, error = "No port data found." });
                }

                var pagedItems = allPorts.Skip((page - 1) * pageSize).Take(pageSize).ToList();

                _logger.Information("Total ports: {Total}, returning page {Page} with {Count} items.", allPorts.Count, page, pagedItems.Count);
                return Ok(new { data = pagedItems, total = allPorts.Count, page, pageSize });
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "An error occurred while retrieving all device ports.");
                return StatusCode(500, new { success = false, error = ex.Message });
            }
        }

        [HttpGet("network_rush_hour")]
        public IActionResult GetNetworkRushHour([FromQuery] string date)
        {
            try
            {
                if (string.IsNullOrEmpty(date))
                {
                    DateTime nowTR = TimeZoneInfo.ConvertTimeFromUtc(DateTime.UtcNow,
                                       TimeZoneInfo.FindSystemTimeZoneById("Turkey Standard Time"));
                    date = nowTR.ToString("yyyy-MM-dd");
                }

                _logger.Information("Fetching Network Rush Hour data for date: {Date}", date);

                var rushHourData = _deviceDataService.GetNetworkRushHour(date);
                string lastUpdated = _deviceDataService.GetLastWholeDataUpdated();

                if (rushHourData == null || !rushHourData.Any())
                {
                    string lastAvailableDate = _deviceDataService.GetLastAvailableRushHourData();
                    if (!string.IsNullOrEmpty(lastAvailableDate) && lastAvailableDate != date)
                    {
                        _logger.Warning("No data for {Date}, using latest available date {LastAvailableDate}", date, lastAvailableDate);
                        rushHourData = _deviceDataService.GetNetworkRushHour(lastAvailableDate);
                        date = lastAvailableDate;
                    }
                    else
                    {
                        return NotFound(new { success = false, error = $"No rush hour data available for {date}." });
                    }
                }

                var mainData = _deviceDataService.GetMainDataMetrics();
                if (mainData == null)
                {
                    return StatusCode(500, new { success = false, error = "Failed to load main data metrics." });
                }

                return Ok(new
                {
                    last_updated = lastUpdated,
                    date_used = date,
                    rush_hours = rushHourData,
                    cumulated_input_mbps = mainData["cumulated_input_mbps"],
                    cumulated_output_mbps = mainData["cumulated_output_mbps"]
                });
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "Error occurred while fetching Network Rush Hour.");
                return StatusCode(500, new { success = false, error = ex.Message });
            }
        }

        [HttpGet("available_rush_hour_dates")]
        public IActionResult GetAvailableRushHourDates()
        {
            try
            {
                var directory = _dataPaths.DataDir;
                var files = Directory.GetFiles(directory, "network_rush_hour_*.json")
                                     .Select(f => Path.GetFileNameWithoutExtension(f).Replace("network_rush_hour_", ""))
                                     .ToList();

                if (!files.Any())
                {
                    return NotFound(new { success = false, error = "No available rush hour data dates found." });
                }

                return Ok(new { available_dates = files });
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "Error retrieving available rush hour data dates.");
                return StatusCode(500, new { success = false, error = ex.Message });
            }
        }

        [HttpGet("log_analysis")]
        public IActionResult GetLogAnalysis()
        {
            try
            {
                _logger.Information("API Request: Fetching Log Analysis Data...");

                var logData = _deviceDataService.GetLogAnalysis();
                if (logData == null || !logData.Any())
                {
                    _logger.Warning("Log analysis data is empty!");
                    return Ok(new { message = "No log data found.", data = new List<object>() });
                }

                _logger.Information("Successfully retrieved log analysis data. Entries: {Count}", logData.Count);
                return Ok(logData);
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "Error retrieving log analysis data.");
                return StatusCode(500, new { success = false, error = "Internal Server Error", details = ex.Message });
            }
        }

        public class LocationRequest
        {
            public string LocationCode { get; set; } = string.Empty;
        }
    }
}
