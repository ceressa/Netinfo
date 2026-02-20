using System;
using System.Collections.Generic;
using System.Data;
using System.IO;
using System.Linq;
using OfficeOpenXml;
using Serilog;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using System.Text.RegularExpressions;
using System.Globalization;

namespace Netinfo.Services
{
    public class DeviceDataService
    {
        private readonly Serilog.ILogger _logger;
        private readonly DataPathsConfig _paths;
        private readonly TimeZoneInfo _timeZone;
        private List<Dictionary<string, object>> _deviceData;
        private List<Dictionary<string, object>> _portData;
        private List<Dictionary<string, object>> _routerPortData;
        private List<Dictionary<string, object>> _locationData;
        private readonly Dictionary<string, int> _lastPingStates;
        private Dictionary<string, DeviceModel> _previousDeviceData = new();
        private List<Dictionary<string, object>> _uuidPoolData = new();
        private DateTime _lastUuidPoolLoadTime;
        private List<Dictionary<string, object>> _logAnalysisData = new();
        private Dictionary<int, (double input, double output)> _hourlyTrafficData = new();

        public DeviceDataService(Serilog.ILogger logger, DataPathsConfig paths)
        {
            _logger = logger ?? throw new ArgumentNullException(nameof(logger));
            _paths = paths ?? throw new ArgumentNullException(nameof(paths));
            _timeZone = TimeZoneInfo.FindSystemTimeZoneById(paths.TimeZoneId);
            _deviceData = new List<Dictionary<string, object>>();
            _portData = new List<Dictionary<string, object>>();
            _routerPortData = new List<Dictionary<string, object>>();
            _locationData = new List<Dictionary<string, object>>();
            _lastPingStates = new Dictionary<string, int>();
        }

        public void InitializeData()
        {
            var stopwatch = System.Diagnostics.Stopwatch.StartNew();
            try
            {
                // JSON'dan cihaz verilerini yukle
                LoadDeviceData(Path.Combine(_paths.DataDir, _paths.DeviceInventory));

                // Onceki donguden kalan cihaz verilerini yukle
                LoadPreviousDeviceData(Path.Combine(_paths.DataDir, _paths.PreviousDeviceInventory));

                // Diger verileri yukle
                LoadPortData(Path.Combine(_paths.DataDir, _paths.MainData));
                LoadRouterPortData(Path.Combine(_paths.DataDir, _paths.RouterData));

                LoadLocationData(Path.Combine(_paths.DataDir, _paths.StationInfo));

                stopwatch.Stop();
                _logger.Information("All data initialized successfully in {ElapsedMilliseconds} ms", stopwatch.ElapsedMilliseconds);
            }
            catch (Exception ex)
            {
                stopwatch.Stop();
                _logger.Error(ex, "Error during data initialization. Elapsed time: {ElapsedMilliseconds} ms", stopwatch.ElapsedMilliseconds);
                throw;
            }
        }

        public class DeviceModel
        {
            public int DeviceId { get; set; }
            public string Serial { get; set; } = string.Empty;
            public string Hostname { get; set; } = string.Empty;
            public string IpAddress { get; set; } = string.Empty;
            public string Model { get; set; } = string.Empty;
            public string DeviceType { get; set; } = string.Empty;
            public string Location { get; set; } = string.Empty;
            public int PingStateNumeric { get; set; }
        }

        public List<Dictionary<string, object>> GetLatestDeviceStatusChanges()
        {
            var statusLogFile = Path.Combine(_paths.LogDir, _paths.StatusChangesLog);
            if (!File.Exists(statusLogFile))
                return new List<Dictionary<string, object>>();

            var jsonContent = File.ReadAllText(statusLogFile);
            return JsonConvert.DeserializeObject<List<Dictionary<string, object>>>(jsonContent) ?? new List<Dictionary<string, object>>();
        }

        public List<Dictionary<string, object>> GetLatestArchivedStatusLog()
        {
            if (!Directory.Exists(_paths.ArchiveLogDir))
                return new List<Dictionary<string, object>>();

            var archiveFiles = Directory.GetFiles(_paths.ArchiveLogDir, "device_status_archive_*.json")
                                        .OrderByDescending(f => f)
                                        .ToList();

            if (!archiveFiles.Any())
                return new List<Dictionary<string, object>>();

            var latestArchiveFile = archiveFiles.First();
            var jsonContent = File.ReadAllText(latestArchiveFile);
            return JsonConvert.DeserializeObject<List<Dictionary<string, object>>>(jsonContent) ?? new List<Dictionary<string, object>>();
        }

        public void LoadPreviousDeviceData(string filePath)
        {
            try
            {
                if (!File.Exists(filePath))
                {
                    _logger.Error("Previous device data file not found: {FilePath}", filePath);
                    return;
                }

                var json = File.ReadAllText(filePath);
                var deviceList = JsonConvert.DeserializeObject<List<DeviceModel>>(json) ?? new List<DeviceModel>();

                _previousDeviceData = deviceList
                    .GroupBy(d => new { d.DeviceId, d.Serial })
                    .Select(g => g.First())
                    .ToDictionary(d => $"{d.DeviceId}-{d.Serial}", d => d);

                _logger.Information("Previous device data loaded successfully from {FilePath}", filePath);
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "Error loading previous device data.");
            }
        }

        public void LoadDeviceData(string filePath)
        {
            _logger.Information("Loading device data from {FilePath}", filePath);

            if (!File.Exists(filePath))
            {
                _logger.Error("Device JSON file not found at {FilePath}", filePath);
                throw new FileNotFoundException("Device JSON file not found", filePath);
            }

            try
            {
                var jsonContent = File.ReadAllText(filePath);
                _deviceData = JsonConvert.DeserializeObject<List<Dictionary<string, object>>>(jsonContent) ?? new List<Dictionary<string, object>>();

                if (_deviceData.Count == 0)
                {
                    _logger.Warning("No device data found in JSON file at {FilePath}", filePath);
                }
                else
                {
                    _logger.Information("Device Data loaded from JSON. Total Records: {Count}", _deviceData.Count);
                }
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "Error reading device data from JSON file at {FilePath}", filePath);
                throw;
            }
        }

        public void LoadPortData(string filePath)
        {
            try
            {
                _logger.Information("Loading Port Data from JSON file: {FilePath}", filePath);

                if (!File.Exists(filePath))
                {
                    _logger.Error("Port data file not found at {FilePath}", filePath);
                    throw new FileNotFoundException("Port data file not found", filePath);
                }

                var jsonContent = File.ReadAllText(filePath);
                var jsonData = JsonConvert.DeserializeObject<Dictionary<string, object>>(jsonContent);

                if (jsonData == null || jsonData.Count == 0)
                {
                    _logger.Warning("Port data JSON is empty or invalid.");
                    return;
                }

                _portData = new List<Dictionary<string, object>>();

                if (!jsonData.TryGetValue("data", out var dataObj) || !(dataObj is JObject data))
                {
                    _logger.Error("Missing 'data' field in JSON. Cannot load port data.");
                    throw new InvalidOperationException("Port data JSON format is incorrect.");
                }

                foreach (var deviceEntry in data)
                {
                    string hostname = deviceEntry.Key;
                    if (deviceEntry.Value is JObject deviceData && deviceData.TryGetValue("ports", out var portsObj) && portsObj is JArray portsArray)
                    {
                        var portsList = portsArray.ToObject<List<Dictionary<string, object>>>();
                        if (portsList != null)
                        {
                            foreach (var port in portsList)
                            {
                                port["hostname"] = hostname;
                                _portData.Add(port);
                            }
                        }
                    }
                    else
                    {
                        _logger.Warning("No ports found for device: {Device}", hostname);
                    }
                }

                if (_portData.Count == 0)
                {
                    _logger.Error("Port data could not be loaded from JSON. Check the format.");
                    throw new InvalidOperationException("Port data not loaded.");
                }

                _logger.Information("Port Data successfully loaded. Total records: {Count}", _portData.Count);
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "Error reading Port Data from JSON file at {FilePath}", filePath);
                throw;
            }
        }

        public void LoadRouterPortData(string filePath)
        {
            _routerPortData = LoadJsonFile(filePath, "Router Port Data");
        }

        private List<Dictionary<string, object>> LoadJsonFile(string filePath, string dataType)
        {
            _logger.Information("Loading {DataType} from JSON file: {FilePath}", dataType, filePath);

            if (!File.Exists(filePath))
            {
                _logger.Error("{DataType} JSON file not found at {FilePath}", dataType, filePath);
                return new List<Dictionary<string, object>>();
            }

            try
            {
                var jsonContent = File.ReadAllText(filePath);
                var data = JsonConvert.DeserializeObject<List<Dictionary<string, object>>>(jsonContent);

                if (data == null || data.Count == 0)
                {
                    _logger.Warning("{DataType} JSON file is empty: {FilePath}", dataType, filePath);
                    return new List<Dictionary<string, object>>();
                }

                _logger.Information("{DataType} loaded with {Count} records from JSON", dataType, data.Count);
                return data;
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "Error reading {DataType} from JSON file: {FilePath}", dataType, filePath);
                return new List<Dictionary<string, object>>();
            }
        }

        public Dictionary<string, object>? GetDeviceById(string deviceId)
        {
            if (_deviceData == null || !_deviceData.Any())
            {
                _logger.Error("Device data not loaded.");
                throw new InvalidOperationException("Device data not loaded.");
            }

            return _deviceData.FirstOrDefault(d =>
                d.TryGetValue("deviceid", out var idValue) && idValue.ToString() == deviceId);
        }

        public List<Dictionary<string, object>> GetPortsByDeviceId(string deviceId)
        {
            if (_portData == null || !_portData.Any())
            {
                _logger.Warning("Port data is empty. Reloading from JSON...");
                LoadPortData(Path.Combine(_paths.DataDir, _paths.MainData));

                if (_portData == null || !_portData.Any())
                {
                    _logger.Error("Port data could not be loaded from JSON.");
                    throw new InvalidOperationException("Port data not loaded.");
                }
            }

            return _portData.Where(p =>
                p.TryGetValue("deviceid", out var idValue) && idValue.ToString() == deviceId).ToList();
        }

        public Dictionary<string, double>? GetMainDataMetrics()
        {
            string filePath = Path.Combine(_paths.DataDir, _paths.MainData);

            if (!File.Exists(filePath))
            {
                _logger.Warning("main_data.json file not found at {FilePath}", filePath);
                return null;
            }

            try
            {
                string jsonContent = File.ReadAllText(filePath);
                var jsonData = JsonConvert.DeserializeObject<Dictionary<string, object>>(jsonContent);

                if (jsonData == null || !jsonData.ContainsKey("cumulated_input_mbps") || !jsonData.ContainsKey("cumulated_output_mbps"))
                {
                    _logger.Warning("main_data.json is missing required fields.");
                    return null;
                }

                return new Dictionary<string, double>
                {
                    { "cumulated_input_mbps", Convert.ToDouble(jsonData["cumulated_input_mbps"]) },
                    { "cumulated_output_mbps", Convert.ToDouble(jsonData["cumulated_output_mbps"]) }
                };
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "Error reading main_data.json");
                return null;
            }
        }

        public void LogPingStateChanges()
        {
            string logFilePath = _paths.PingLogPath;

            if (_deviceData == null || _deviceData.Count == 0)
            {
                _logger.Warning("No device data available for ping state logging.");
                return;
            }

            foreach (var device in _deviceData)
            {
                if (!device.TryGetValue("deviceid", out var deviceId) || !device.TryGetValue("ping_state_numeric", out var currentPingState))
                {
                    _logger.Warning("Device data missing required fields.");
                    continue;
                }

                string? deviceKey = deviceId?.ToString();
                if (deviceKey == null) continue;
                int currentState = Convert.ToInt32(currentPingState);
                int previousState = currentState;

                if (_previousDeviceData.ContainsKey(deviceKey))
                {
                    var previousDevice = _previousDeviceData[deviceKey];

                    if (previousDevice != null)
                    {
                        previousState = previousDevice.PingStateNumeric;
                    }
                }

                if (previousState != currentState)
                {
                    string logEntry = $"{DateTime.UtcNow:yyyy-MM-dd HH:mm:ss} - Device ID: {deviceKey}, Old State: {previousState}, New State: {currentState}";
                    File.AppendAllLines(logFilePath, new[] { logEntry });
                    _logger.Information("Ping state change logged: {LogEntry}", logEntry);
                }

                device["ping_state_numeric"] = currentState;
                device["ping_state"] = currentState == 1 ? "up" : "down";
                device["previous_is_up"] = previousState;

                _lastPingStates[deviceKey] = currentState;
            }

            // Guncellenmis JSON dosyasini tekrar kaydet
            string jsonFile = Path.Combine(_paths.DataDir, _paths.DeviceInventory);
            File.WriteAllText(jsonFile, JsonConvert.SerializeObject(_deviceData, Formatting.Indented));

            string previousJsonFile = Path.Combine(_paths.DataDir, _paths.PreviousDeviceInventory);
            File.WriteAllText(previousJsonFile, JsonConvert.SerializeObject(_deviceData, Formatting.Indented));
        }

        public List<Dictionary<string, object>> GetRouterPortsByDeviceId(string deviceId)
        {
            _logger.Information("GetRouterPortsByDeviceId called with Device ID: {DeviceId}", deviceId);

            if (_routerPortData == null || !_routerPortData.Any())
            {
                _logger.Error("Router port data not loaded or empty.");
                throw new InvalidOperationException("Router port data not loaded.");
            }

            _logger.Information("Total Router Port Records Loaded: {Count}", _routerPortData.Count);

            try
            {
                var filteredData = _routerPortData
                    .Where(p =>
                        p.TryGetValue("deviceid", out var idValue) && idValue.ToString() == deviceId)
                    .ToList();

                if (!filteredData.Any())
                {
                    _logger.Warning("No router ports found for Device ID: {DeviceId}.", deviceId);
                }
                else
                {
                    _logger.Information("Router Ports Found: {Count} for Device ID: {DeviceId}.", filteredData.Count, deviceId);
                    _logger.Debug("Filtered Router Ports: {@FilteredData}", filteredData);
                }

                return filteredData;
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "An error occurred while fetching router ports for Device ID: {DeviceId}.", deviceId);
                throw;
            }
        }

        public List<Dictionary<string, object>> GetAllDevices()
        {
            if (_deviceData == null || !_deviceData.Any())
            {
                _logger.Warning("Device data is empty or not loaded. Reloading...");
                LoadDeviceData(Path.Combine(_paths.DataDir, _paths.DeviceInventory));
            }

            return _deviceData ?? new List<Dictionary<string, object>>();
        }

        public void LoadLocationData(string filePath)
        {
            try
            {
                if (!File.Exists(filePath))
                {
                    _logger.Error("Location JSON file not found at {FilePath}", filePath);
                    throw new FileNotFoundException("Location JSON file not found", filePath);
                }

                var jsonContent = File.ReadAllText(filePath);
                _locationData = JsonConvert.DeserializeObject<List<Dictionary<string, object>>>(jsonContent) ?? new List<Dictionary<string, object>>();

                if (!_locationData.Any())
                {
                    _logger.Warning("No location data found in JSON file at {FilePath}", filePath);
                }
                else
                {
                    _logger.Information("Location Data loaded from JSON. Total Records: {Count}", _locationData.Count);
                }
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "Error reading location data from JSON file at {FilePath}", filePath);
                throw;
            }
        }

        public Dictionary<string, object>? GetLocationInfoByCode(string locationCode)
        {
            if (_locationData == null || !_locationData.Any())
            {
                _logger.Error("Location data not loaded.");
                throw new InvalidOperationException("Location data not loaded.");
            }

            return _locationData.FirstOrDefault(d =>
                d.TryGetValue("code", out var codeValue) &&
                (codeValue?.ToString()?.Equals(locationCode, StringComparison.OrdinalIgnoreCase) ?? false));
        }

        public List<Dictionary<string, object>> GetDevicesByLocationCode(string locationCode)
        {
            if (_deviceData == null || !_deviceData.Any())
            {
                _logger.Error("Device data not loaded.");
                throw new InvalidOperationException("Device data not loaded.");
            }

            var filteredDevices = _deviceData.Where(device =>
                device.TryGetValue("location", out var codeValue) &&
                string.Equals(codeValue?.ToString(), locationCode, StringComparison.OrdinalIgnoreCase)).ToList();

            if (!filteredDevices.Any())
            {
                _logger.Warning("No devices found for Location Code: {LocationCode}", locationCode);
            }
            else
            {
                _logger.Information("Devices found for Location Code: {LocationCode}. Count: {Count}", locationCode, filteredDevices.Count);
            }

            return filteredDevices;
        }

        public string? GetDeviceIdByUUID(string uuid)
        {
            if (string.IsNullOrEmpty(uuid))
            {
                _logger.Warning("UUID is null or empty.");
                return null;
            }

            CheckAndReloadUUIDPool();

            var match = _uuidPoolData?.FirstOrDefault(d =>
                d.TryGetValue("uuid", out var uuidValue) && uuidValue?.ToString() == uuid);

            if (match != null && match.TryGetValue("deviceid", out var deviceId))
            {
                _logger.Information("Found Device ID: {DeviceId} for UUID: {UUID}", deviceId, uuid);
                return deviceId?.ToString();
            }

            _logger.Warning("No matching Device ID found for UUID: {UUID}", uuid);
            return null;
        }

        public Dictionary<string, object>? GetDeviceByUUID(string uuid)
        {
            if (string.IsNullOrEmpty(uuid))
            {
                _logger.Error("UUID cannot be null or empty.");
                throw new ArgumentException("UUID is required.", nameof(uuid));
            }

            var match = _uuidPoolData?.FirstOrDefault(d =>
                d.TryGetValue("uuid", out var uuidValue) && uuidValue?.ToString() == uuid);

            if (match != null && match.TryGetValue("deviceid", out var deviceId))
            {
                var deviceIdStr = deviceId?.ToString();
                if (deviceIdStr != null)
                {
                    _logger.Information("Device found for UUID {UUID}: {DeviceId}", uuid, deviceId);
                    return GetDeviceById(deviceIdStr);
                }
            }

            _logger.Warning("No device found for UUID: {UUID}", uuid);
            return null;
        }

        public void CheckAndReloadUUIDPool()
        {
            var uuidPoolFilePath = Path.Combine(_paths.DataDir, _paths.UUIDPool);
            var lastModifiedTime = File.GetLastWriteTime(uuidPoolFilePath);

            if (_uuidPoolData == null || lastModifiedTime > _lastUuidPoolLoadTime)
            {
                _logger.Information("UUID Pool file has changed. Reloading...");
                LoadUUIDPool(uuidPoolFilePath);
                _lastUuidPoolLoadTime = lastModifiedTime;
            }
        }

        public void LoadUUIDPool(string filePath)
        {
            _logger.Information("Loading UUID Pool from JSON: {FilePath}", filePath);

            if (!File.Exists(filePath))
            {
                _logger.Error("UUID JSON file not found at {FilePath}", filePath);
                throw new FileNotFoundException("UUID JSON file not found", filePath);
            }

            try
            {
                var jsonContent = File.ReadAllText(filePath);
                var jsonData = JsonConvert.DeserializeObject<Dictionary<string, object>>(jsonContent);

                if (jsonData == null || !jsonData.ContainsKey("deviceid_uuid_mapping"))
                {
                    _logger.Warning("Invalid UUID JSON format. Missing 'deviceid_uuid_mapping' key.");
                    return;
                }

                var uuidMappingRaw = jsonData["deviceid_uuid_mapping"] as JObject;
                if (uuidMappingRaw == null)
                {
                    _logger.Warning("deviceid_uuid_mapping is not a valid JSON object.");
                    return;
                }

                var uuidMapping = uuidMappingRaw.ToObject<Dictionary<string, string>>() ?? new Dictionary<string, string>();

                _uuidPoolData = uuidMapping
                    .Select(kvp => new Dictionary<string, object>
                    {
                        { "deviceid", kvp.Key },
                        { "uuid", string.IsNullOrEmpty(kvp.Value) ? "UNKNOWN" : kvp.Value }
                    })
                    .ToList();

                _logger.Information("UUID Pool loaded with {Count} entries.", _uuidPoolData.Count);
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "Error reading UUID Pool from JSON file at {FilePath}", filePath);
                throw;
            }
        }

        public List<Dictionary<string, object>> GetVlanData()
        {
            string filePath = Path.Combine(_paths.DataDir, _paths.DeviceConfigHistory);

            try
            {
                if (!File.Exists(filePath))
                {
                    _logger.Warning("VLAN data file not found at {FilePath}", filePath);
                    return new List<Dictionary<string, object>>();
                }

                var jsonContent = File.ReadAllText(filePath);
                var vlanData = JsonConvert.DeserializeObject<Dictionary<string, Dictionary<string, object>>>(jsonContent);

                if (vlanData == null || vlanData.Count == 0)
                {
                    _logger.Warning("VLAN data file is empty.");
                    return new List<Dictionary<string, object>>();
                }

                var vlanList = new List<Dictionary<string, object>>();
                foreach (var device in vlanData.Values)
                {
                    if (device.TryGetValue("vlans", out var vlanObj) && vlanObj is JObject vlanDict)
                    {
                        foreach (var vlanProp in vlanDict.Properties())
                        {
                            var vlanInfo = vlanProp.Value.ToObject<Dictionary<string, object>>();
                            if (vlanInfo != null)
                            {
                                vlanInfo["hostname"] = device["hostname"];
                                vlanList.Add(vlanInfo);
                            }
                        }
                    }
                }

                _logger.Information("VLAN data successfully loaded. Total VLANs: {Count}", vlanList.Count);
                return vlanList;
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "Error while reading VLAN data from file.");
                return new List<Dictionary<string, object>>();
            }
        }

        public List<Dictionary<string, object>> GetNetworkRushHour(string date)
        {
            try
            {
                string filePath = Path.Combine(_paths.DataDir, $"network_rush_hour_{date}.json");
                List<Dictionary<string, object>> rushHourData = new List<Dictionary<string, object>>();

                if (File.Exists(filePath))
                {
                    var jsonContent = File.ReadAllText(filePath);
                    rushHourData = JsonConvert.DeserializeObject<List<Dictionary<string, object>>>(jsonContent) ?? new List<Dictionary<string, object>>();
                }

                DateTime nowUtc = DateTime.UtcNow;
                DateTime nowTR = TimeZoneInfo.ConvertTimeFromUtc(nowUtc, _timeZone);

                int currentHour = nowTR.Hour;
                string currentHourRange = $"{currentHour:00}:00 - {currentHour + 1:00}:00";

                bool dataExistsForCurrentHour = rushHourData.Any(r => r["hour_range"].ToString() == currentHourRange);
                if (!dataExistsForCurrentHour)
                {
                    _logger.Warning("No rush hour data found for {HourRange} (TR Time). Generating new data...", currentHourRange);

                    double totalInputTraffic = _portData.Sum(p => Convert.ToDouble(p.GetValueOrDefault("input_rate_mbps", 0)));
                    double totalOutputTraffic = _portData.Sum(p => Convert.ToDouble(p.GetValueOrDefault("output_rate_mbps", 0)));

                    var newEntry = new Dictionary<string, object>
                    {
                        { "hour_range", currentHourRange },
                        { "input_traffic_mbps", totalInputTraffic },
                        { "output_traffic_mbps", totalOutputTraffic }
                    };

                    rushHourData.Add(newEntry);
                    SaveNetworkRushHourData(date, rushHourData);
                }

                return rushHourData;
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "Error fetching network rush hour data for {Date}", date);
                return new List<Dictionary<string, object>>();
            }
        }

        public string? GetLastAvailableRushHourData()
        {
            var files = Directory.GetFiles(_paths.DataDir, "network_rush_hour_*.json")
                                 .OrderByDescending(f => f)
                                 .ToList();

            if (!files.Any())
            {
                _logger.Warning("No available rush hour data files found.");
                return null;
            }

            string latestFile = Path.GetFileNameWithoutExtension(files.First());
            string lastAvailableDate = latestFile.Replace("network_rush_hour_", "");

            _logger.Information("Last available rush hour data found for {Date}", lastAvailableDate);
            return lastAvailableDate;
        }

        private void SaveNetworkRushHourData(string date, List<Dictionary<string, object>> rushHourData)
        {
            try
            {
                string filePath = Path.Combine(_paths.DataDir, $"network_rush_hour_{date}.json");

                List<Dictionary<string, object>> existingData = new List<Dictionary<string, object>>();
                if (File.Exists(filePath))
                {
                    var existingContent = File.ReadAllText(filePath);
                    existingData = JsonConvert.DeserializeObject<List<Dictionary<string, object>>>(existingContent) ?? new List<Dictionary<string, object>>();
                }

                DateTime nowTR = TimeZoneInfo.ConvertTimeFromUtc(DateTime.UtcNow, _timeZone);
                int currentHour = nowTR.Hour;
                string currentHourRange = $"{currentHour:00}:00 - {currentHour + 1:00}:00";

                var existingEntry = existingData.FirstOrDefault(e => e["hour_range"].ToString() == currentHourRange);
                if (existingEntry != null)
                {
                    existingData.Remove(existingEntry);
                }

                double totalInputTraffic = _portData.Sum(p => Convert.ToDouble(p.GetValueOrDefault("input_rate_mbps", 0)));
                double totalOutputTraffic = _portData.Sum(p => Convert.ToDouble(p.GetValueOrDefault("output_rate_mbps", 0)));

                var newEntry = new Dictionary<string, object>
                {
                    { "hour_range", currentHourRange },
                    { "input_traffic_mbps", totalInputTraffic },
                    { "output_traffic_mbps", totalOutputTraffic }
                };

                existingData.Add(newEntry);

                File.WriteAllText(filePath, JsonConvert.SerializeObject(existingData, Formatting.Indented));
                _logger.Information("Network rush hour data updated for {Date}. Last updated hour: {Hour}", date, currentHour);
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "Error saving network rush hour data for {Date}", date);
            }
        }

        public void UpdateMainDataMetrics()
        {
            try
            {
                string filePath = Path.Combine(_paths.DataDir, _paths.MainData);

                Dictionary<string, object> mainData = new Dictionary<string, object>();
                if (File.Exists(filePath))
                {
                    string jsonContent = File.ReadAllText(filePath);
                    mainData = JsonConvert.DeserializeObject<Dictionary<string, object>>(jsonContent) ?? new Dictionary<string, object>();
                }

                double totalInputTraffic = _portData.Sum(p => Convert.ToDouble(p.GetValueOrDefault("input_rate_mbps", 0)));
                double totalOutputTraffic = _portData.Sum(p => Convert.ToDouble(p.GetValueOrDefault("output_rate_mbps", 0)));

                mainData["cumulated_input_mbps"] = totalInputTraffic;
                mainData["cumulated_output_mbps"] = totalOutputTraffic;
                mainData["last_whole_data_updated"] = TimeZoneInfo.ConvertTimeFromUtc(DateTime.UtcNow, _timeZone).ToString("dd.MM.yyyy HH:mm");

                File.WriteAllText(filePath, JsonConvert.SerializeObject(mainData, Formatting.Indented));
                _logger.Information("main_data.json updated. Input: {Input}, Output: {Output}", totalInputTraffic, totalOutputTraffic);
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "Error updating main_data.json");
            }
        }

        public string GetLastWholeDataUpdated()
        {
            string filePath = Path.Combine(_paths.DataDir, _paths.MainData);

            if (!File.Exists(filePath))
            {
                _logger.Warning("main_data.json file not found.");
                return "Bilinmiyor";
            }

            try
            {
                string jsonContent = File.ReadAllText(filePath);
                var jsonData = JsonConvert.DeserializeObject<Dictionary<string, object>>(jsonContent);

                if (jsonData != null && jsonData.ContainsKey("last_whole_data_updated") && jsonData["last_whole_data_updated"] is string lastUpdated)
                {
                    DateTime parsedDate;
                    if (DateTime.TryParseExact(lastUpdated, "dd.MM.yyyy HH:mm", CultureInfo.InvariantCulture, DateTimeStyles.None, out parsedDate))
                    {
                        return parsedDate.ToString("dd.MM.yyyy HH:mm");
                    }
                    return "Bilinmiyor";
                }
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "Error reading 'last_whole_data_updated' from JSON.");
            }

            return "Bilinmiyor";
        }

        public void LoadLogAnalysisData(string filePath)
        {
            _logger.Information("Loading log analysis data from {FilePath}", filePath);

            if (!File.Exists(filePath))
            {
                _logger.Warning("Log analysis file not found: {FilePath}", filePath);
                _logAnalysisData = new List<Dictionary<string, object>>();
                return;
            }

            try
            {
                var jsonContent = File.ReadAllText(filePath);
                var jsonData = JsonConvert.DeserializeObject<Dictionary<string, Dictionary<string, object>>>(jsonContent);

                if (jsonData == null || jsonData.Count == 0)
                {
                    _logger.Warning("Log analysis JSON is empty.");
                    _logAnalysisData = new List<Dictionary<string, object>>();
                    return;
                }

                _logAnalysisData = jsonData.Select(kv =>
                {
                    var entry = kv.Value;
                    entry["device_id"] = kv.Key;

                    string? mostProblematicPortRaw = entry.ContainsKey("most_problematic_port")
                        ? entry["most_problematic_port"]?.ToString()
                        : null;

                    string? mostProblematicPort = mostProblematicPortRaw?.Split(':')[0].Trim();

                    string solution = "Cozum belirtilmemis";

                    if (!string.IsNullOrEmpty(mostProblematicPort) &&
                        entry.ContainsKey("logs") &&
                        entry["logs"] is JObject logsDict)
                    {
                        foreach (var log in logsDict.Properties())
                        {
                            var logEntry = log.Value as JObject;
                            if (logEntry != null && logEntry.ContainsKey("port"))
                            {
                                string logPort = logEntry["port"]?.ToString()?.Trim() ?? "";
                                if (logPort == mostProblematicPort && logEntry.ContainsKey("latest_log"))
                                {
                                    var latestLog = logEntry["latest_log"] as JObject;
                                    if (latestLog != null && latestLog.ContainsKey("solution"))
                                    {
                                        solution = latestLog["solution"]?.ToString() ?? "Cozum belirtilmemis";
                                        break;
                                    }
                                }
                            }
                        }
                    }

                    _logger.Information("Device: {Device}, Most Problematic Port: {Port}, Solution: {Solution}",
                                        kv.Key, mostProblematicPort, solution);

                    entry["most_problematic_port_solution"] = solution;
                    return entry;
                }).ToList();

                _logger.Information("Log analysis loaded successfully. Total logs: {Count}", _logAnalysisData.Count);
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "Error loading log analysis data.");
                _logAnalysisData = new List<Dictionary<string, object>>();
            }
        }

        public List<Dictionary<string, object>> GetLogAnalysis()
        {
            if (_logAnalysisData == null || _logAnalysisData.Count == 0)
            {
                _logger.Warning("Log analysis data is empty. Reloading...");
                LoadLogAnalysisData(Path.Combine(_paths.SyslogDir, _paths.SyslogSummary));
            }

            var enrichedLogs = _logAnalysisData.Select(entry =>
            {
                string mostProblematicPortSolution = "Cozum belirtilmemis";
                int mostProblematicPortOccurrences = 0;
                string mostProblematicPort = "N/A";

                if (entry.ContainsKey("most_problematic_port") && entry.ContainsKey("logs") && entry["logs"] is JObject logsDict)
                {
                    string? mostProblematicPortRaw = entry["most_problematic_port"]?.ToString();
                    var match = Regex.Match(mostProblematicPortRaw ?? "", @"(.*):\s*\((\d+)\s*occurrences\)");
                    if (match.Success)
                    {
                        mostProblematicPort = match.Groups[1].Value.Trim();
                        mostProblematicPortOccurrences = int.Parse(match.Groups[2].Value);
                    }
                    else
                    {
                        mostProblematicPort = mostProblematicPortRaw?.Trim() ?? "N/A";
                    }

                    if (mostProblematicPortOccurrences == 0)
                    {
                        foreach (var logEntry in logsDict.Properties())
                        {
                            if (logEntry.Value is JObject logObject &&
                                logObject.ContainsKey("port") &&
                                (logObject["port"]?.ToString()?.Trim() ?? "") == mostProblematicPort &&
                                logObject.ContainsKey("occurrences"))
                            {
                                mostProblematicPortOccurrences = Convert.ToInt32(logObject["occurrences"]);
                                break;
                            }
                        }
                    }

                    foreach (var logEntry in logsDict.Properties())
                    {
                        if (logEntry.Value is JObject logObject &&
                            logObject.ContainsKey("port") &&
                            (logObject["port"]?.ToString()?.Trim() ?? "") == mostProblematicPort &&
                            logObject.ContainsKey("latest_log") &&
                            logObject["latest_log"] is JObject latestLog &&
                            latestLog.ContainsKey("solution"))
                        {
                            mostProblematicPortSolution = latestLog["solution"]?.ToString() ?? "Cozum belirtilmemis";
                            break;
                        }
                    }
                }

                entry["most_problematic_port"] = mostProblematicPort;
                entry["most_problematic_port_occurrences"] = mostProblematicPortOccurrences;
                entry["most_problematic_port_solution"] = mostProblematicPortSolution;
                return entry;
            }).ToList();

            _logger.Information("Log analysis enriched with most problematic port solutions. Total logs: {Count}", enrichedLogs.Count);
            return enrichedLogs;
        }

        public void LoadInsightSummary(string filePath)
        {
            _logger.Information("Loading Insight Summary from {FilePath}", filePath);

            if (!File.Exists(filePath))
            {
                _logger.Warning("Insight summary file not found: {FilePath}", filePath);
                return;
            }

            try
            {
                var jsonContent = File.ReadAllText(filePath);
                var list = JsonConvert.DeserializeObject<List<InsightSummary>>(jsonContent);

                if (list == null || list.Count == 0)
                {
                    _logger.Warning("Insight summary JSON list is empty or invalid.");
                    return;
                }

                var latest = list.LastOrDefault();
                if (latest == null)
                {
                    _logger.Warning("Insight summary file contains no valid entries.");
                    return;
                }

                _logger.Information("Insight summary loaded. Latest timestamp: {Timestamp}", latest.Timestamp);
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "Error loading insight summary from file.");
            }
        }

        public List<InsightSummary> GetInsightSummary()
        {
            try
            {
                var insightSummaryFilePath = Path.Combine(_paths.DataDir, _paths.InsightSummary);
                if (!File.Exists(insightSummaryFilePath))
                {
                    _logger.Warning("Insight summary file not found at {FilePath}", insightSummaryFilePath);
                    return new List<InsightSummary>();
                }

                var jsonContent = File.ReadAllText(insightSummaryFilePath);
                var list = JsonConvert.DeserializeObject<List<InsightSummary>>(jsonContent);

                if (list == null || list.Count == 0)
                {
                    _logger.Warning("Insight summary JSON list is empty.");
                    return new List<InsightSummary>();
                }

                _logger.Information("Insight summary loaded. Count: {Count}", list.Count);
                return list;
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "Error reading insight summary JSON.");
                return new List<InsightSummary>();
            }
        }

        public InsightSummary? GetLatestInsightSummary()
        {
            try
            {
                var allSummaries = GetInsightSummary();
                return allSummaries.LastOrDefault();
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "Error getting latest insight summary.");
                return null;
            }
        }

        public class InsightSummary
        {
            [JsonProperty("timestamp")]
            public DateTime Timestamp { get; set; }

            [JsonProperty("total_devices")]
            public int TotalDevices { get; set; }

            [JsonProperty("online_devices")]
            public int OnlineDevices { get; set; }

            [JsonProperty("offline_devices")]
            public int OfflineDevices { get; set; }

            [JsonProperty("top_usage_devices")]
            public List<string> TopUsageDevices { get; set; } = new List<string>();

            [JsonProperty("recent_status_changes")]
            public List<StatusChange> RecentStatusChanges { get; set; } = new List<StatusChange>();

            [JsonProperty("rush_hour")]
            public RushHourData? RushHour { get; set; }

            [JsonProperty("insights")]
            public List<string> Insights { get; set; } = new List<string>();
        }

        public class StatusChange
        {
            [JsonProperty("hostname")]
            public string Hostname { get; set; } = string.Empty;

            [JsonProperty("serial")]
            public string Serial { get; set; } = string.Empty;

            [JsonProperty("timestamp")]
            public DateTime Timestamp { get; set; }

            [JsonProperty("status_change")]
            public string StatusChangeDescription { get; set; } = string.Empty;
        }

        public class RushHourData
        {
            [JsonProperty("min")]
            public HourRangeData? Min { get; set; }

            [JsonProperty("max")]
            public HourRangeData? Max { get; set; }
        }

        public class HourRangeData
        {
            [JsonProperty("hour_range")]
            public string HourRange { get; set; } = string.Empty;

            [JsonProperty("input")]
            public double Input { get; set; }

            [JsonProperty("output")]
            public double Output { get; set; }
        }

        public List<Dictionary<string, object>> GetAllPorts()
        {
            if (_portData == null || !_portData.Any())
            {
                _logger.Warning("Port data is empty. Reloading from JSON...");
                LoadPortData(Path.Combine(_paths.DataDir, _paths.MainData));

                if (_portData == null || !_portData.Any())
                {
                    _logger.Error("Port data could not be loaded from JSON.");
                    throw new InvalidOperationException("Port data not loaded.");
                }
            }

            _logger.Information("Successfully retrieved all device ports. Total: {Count}", _portData.Count);
            return _portData;
        }
    }
}
