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
        private List<Dictionary<string, object>> _deviceData;
        private List<Dictionary<string, object>> _portData;
        private List<Dictionary<string, object>> _routerPortData;
		private List<Dictionary<string, object>> _locationData;
		private readonly Dictionary<string, int> _lastPingStates;
		private Dictionary<string, DeviceModel> _previousDeviceData;
		private readonly string _statusLogFile = "D:/INTRANET/Netinfo/Logs/Latest_Logs/device_status_changes.json";
        private readonly string _archiveFolder = "D:/INTRANET/Netinfo/Logs/Archived_Logs";
		private List<Dictionary<string, object>> _uuidPoolData;
		private DateTime _lastUuidPoolLoadTime;
		private readonly string _uuidPoolFilePath = "D:/INTRANET/Netinfo/Data/UUID_Pool.json";
		private List<Dictionary<string, object>> _logAnalysisData;
		private readonly string _logAnalysisFilePath = "D:/INTRANET/Netinfo/Logs/Syslog_AI/syslog_summary.json";
		private Dictionary<int, (double input, double output)> _hourlyTrafficData = new();
		private int _lastProcessedHour = -1;  // En son işlenen saat
		private readonly string _insightSummaryFilePath = "D:/INTRANET/Netinfo/Data/insight_summary.json";

		public void InitializeData()
{
    var stopwatch = System.Diagnostics.Stopwatch.StartNew();
    try
    {
        // JSON'dan cihaz verilerini yükle
        LoadDeviceData("D:\\INTRANET\\Netinfo\\Data\\network_device_inventory.json");

        // Önceki döngüden kalan cihaz verilerini yükle
        LoadPreviousDeviceData("D:\\INTRANET\\Netinfo\\Data\\network_device_inventory_previous.json");

        // Diğer verileri yükle
        LoadPortData("D:\\INTRANET\\Netinfo\\Data\\main_data.json");
LoadRouterPortData("D:\\INTRANET\\Netinfo\\Data\\main_router_data.json");

        LoadLocationData("D:\\INTRANET\\Netinfo\\Data\\station-info.json");

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
    public string Serial { get; set; }
    public string Hostname { get; set; }
    public string IpAddress { get; set; }
    public string Model { get; set; }
    public string DeviceType { get; set; }
    public string Location { get; set; }
    public int PingStateNumeric { get; set; }
}

public List<Dictionary<string, object>> GetLatestDeviceStatusChanges()
        {
            if (!File.Exists(_statusLogFile))
                return new List<Dictionary<string, object>>(); // Eğer log dosyası yoksa boş liste döndür

            var jsonContent = File.ReadAllText(_statusLogFile);
            return JsonConvert.DeserializeObject<List<Dictionary<string, object>>>(jsonContent);
        }


        public List<Dictionary<string, object>> GetLatestArchivedStatusLog()
        {
            if (!Directory.Exists(_archiveFolder))
                return new List<Dictionary<string, object>>(); // Eğer arşiv klasörü yoksa boş liste döndür

            var archiveFiles = Directory.GetFiles(_archiveFolder, "device_status_archive_*.json")
                                        .OrderByDescending(f => f) // En yeni dosyayı bul
                                        .ToList();

            if (!archiveFiles.Any())
                return new List<Dictionary<string, object>>(); // Arşivde kayıt yoksa boş liste döndür

            var latestArchiveFile = archiveFiles.First();
            var jsonContent = File.ReadAllText(latestArchiveFile);
            return JsonConvert.DeserializeObject<List<Dictionary<string, object>>>(jsonContent);
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
                var deviceList = JsonConvert.DeserializeObject<List<DeviceModel>>(json); // 🛠 `JsonConvert` artık tanınıyor

                // **Hem deviceid hem de serial'e göre grupla**
                _previousDeviceData = deviceList
    .GroupBy(d => new { d.DeviceId, d.Serial }) // Aynı Device ID ve Serial olanları grupla
    .Select(g => g.First())   // İlk kaydı al, diğerlerini yok say
    .ToDictionary(d => $"{d.DeviceId}-{d.Serial}", d => d); // Dictionary için anahtar: DeviceId + Serial


                _logger.Information("Previous device data loaded successfully from {FilePath}", filePath);
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "Error loading previous device data.");
            }
        }

		

		
        public DeviceDataService(Serilog.ILogger logger)
        {
            _logger = logger ?? throw new ArgumentNullException(nameof(logger));
            _deviceData = new List<Dictionary<string, object>>();
            _portData = new List<Dictionary<string, object>>();
            _routerPortData = new List<Dictionary<string, object>>();
			_locationData = new List<Dictionary<string, object>>();
			_lastPingStates = new Dictionary<string, int>();
			
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
        _deviceData = Newtonsoft.Json.JsonConvert.DeserializeObject<List<Dictionary<string, object>>>(jsonContent);

        if (_deviceData == null || _deviceData.Count == 0)
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

        // ✅ "last_whole_data_updated" alanını atlıyoruz
        if (!jsonData.TryGetValue("data", out var dataObj) || !(dataObj is JObject data))
        {
            _logger.Error("❌ Missing 'data' field in JSON. Cannot load port data.");
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
                        port["hostname"] = hostname; // Hostname'i ekleyelim
                        _portData.Add(port);
                    }
                }
            }
            else
            {
                _logger.Warning("❌ No ports found for device: {Device}", hostname);
            }
        }

        if (_portData.Count == 0)
        {
            _logger.Error("❌ Port data could not be loaded from JSON. Check the format.");
            throw new InvalidOperationException("Port data not loaded.");
        }

        _logger.Information("✅ Port Data successfully loaded. Total records: {Count}", _portData.Count);
    }
    catch (Exception ex)
    {
        _logger.Error(ex, "❌ Error reading Port Data from JSON file at {FilePath}", filePath);
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
        return new List<Dictionary<string, object>>(); // Boş liste döndür
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
        return new List<Dictionary<string, object>>(); // Hata durumunda boş liste döndür
    }
}

		
		

        public Dictionary<string, object> GetDeviceById(string deviceId)
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
        LoadPortData("D:\\INTRANET\\Netinfo\\Data\\main_data.json"); // JSON'dan yükle

        if (_portData == null || !_portData.Any())
        {
            _logger.Error("Port data could not be loaded from JSON.");
            throw new InvalidOperationException("Port data not loaded.");
        }
    }

    return _portData.Where(p =>
        p.TryGetValue("deviceid", out var idValue) && idValue.ToString() == deviceId).ToList();
}

public Dictionary<string, double> GetMainDataMetrics()
{
    string filePath = "D:/INTRANET/Netinfo/Data/main_data.json";

    if (!File.Exists(filePath))
    {
        _logger.Warning("❌ main_data.json file not found at {FilePath}", filePath);
        return null;
    }

    try
    {
        string jsonContent = File.ReadAllText(filePath);
        var jsonData = JsonConvert.DeserializeObject<Dictionary<string, object>>(jsonContent);

        if (jsonData == null || !jsonData.ContainsKey("cumulated_input_mbps") || !jsonData.ContainsKey("cumulated_output_mbps"))
        {
            _logger.Warning("⚠ main_data.json is missing required fields.");
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
        _logger.Error(ex, "❌ Error reading main_data.json");
        return null;
    }
}



public void LogPingStateChanges()
{
    string logFilePath = @"D:\INTRANET\Netinfo\Logs\PingStateChanges.log";

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

        string deviceKey = deviceId.ToString();
        int currentState = Convert.ToInt32(currentPingState);
        int previousState = currentState; // ✅ Varsayılan olarak mevcut durumu atıyoruz

        // **Önceki cihaz verisini kontrol et**
        if (_previousDeviceData.ContainsKey(deviceKey))
        {
            var previousDevice = _previousDeviceData[deviceKey]; // DeviceModel nesnesini al
            
            // Eğer PingStateNumeric varsa ve integer'a çevrilebiliyorsa kullan
            if (previousDevice != null)
            {
                previousState = previousDevice.PingStateNumeric;
            }
        }

        // Eğer önceki ve mevcut durum farklıysa logla
        if (previousState != currentState)
        {
            string logEntry = $"{DateTime.UtcNow:yyyy-MM-dd HH:mm:ss} - Device ID: {deviceKey}, Old State: {previousState}, New State: {currentState}";
            File.AppendAllLines(logFilePath, new[] { logEntry });
            _logger.Information("Ping state change logged: {LogEntry}", logEntry);
        }

        // **Cihazın JSON içindeki `ping_state`, `ping_state_numeric` ve `previous_is_up` değerlerini güncelle**
        device["ping_state_numeric"] = currentState;
        device["ping_state"] = currentState == 1 ? "up" : "down";
        device["previous_is_up"] = previousState;

        _lastPingStates[deviceKey] = currentState;
    }

    // **Güncellenmiş JSON dosyasını tekrar kaydet**
    string jsonFile = @"D:\INTRANET\Netinfo\Data\network_device_inventory.json";
    File.WriteAllText(jsonFile, Newtonsoft.Json.JsonConvert.SerializeObject(_deviceData, Newtonsoft.Json.Formatting.Indented));


    string previousJsonFile = @"D:\INTRANET\Netinfo\Data\network_device_inventory_previous.json";
    File.WriteAllText(previousJsonFile, Newtonsoft.Json.JsonConvert.SerializeObject(_deviceData, Newtonsoft.Json.Formatting.Indented));
}





       public List<Dictionary<string, object>> GetRouterPortsByDeviceId(string deviceId)
{
    // Log: Metot çağrısı
    _logger.Information("GetRouterPortsByDeviceId called with Device ID: {DeviceId}", deviceId);

    // Log: Router port verisinin yüklü olup olmadığını kontrol et
    if (_routerPortData == null || !_routerPortData.Any())
    {
        _logger.Error("Router port data not loaded or empty.");
        throw new InvalidOperationException("Router port data not loaded.");
    }

    // Log: Router port veri sayısını kontrol et
    _logger.Information("Total Router Port Records Loaded: {Count}", _routerPortData.Count);

    try
    {
        // Filtreleme işlemi
        var filteredData = _routerPortData
            .Where(p => 
                p.TryGetValue("deviceid", out var idValue) && idValue.ToString() == deviceId)
            .ToList();

        // Log: Filtreleme sonrası sonuç
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
        // Log: Hata mesajı
        _logger.Error(ex, "An error occurred while fetching router ports for Device ID: {DeviceId}.", deviceId);
        throw;
    }
}

        public List<Dictionary<string, object>> GetAllDevices()
{
    if (_deviceData == null || !_deviceData.Any())
    {
        _logger.Warning("Device data is empty or not loaded. Reloading...");
        LoadDeviceData("D:\\INTRANET\\Netinfo\\Data\\network_device_inventory.json");
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

        var jsonContent = File.ReadAllText(filePath); // JSON dosyasını oku
        _locationData = Newtonsoft.Json.JsonConvert.DeserializeObject<List<Dictionary<string, object>>>(jsonContent); // JSON'u deserialize et

        if (_locationData == null || !_locationData.Any())
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


		
		public Dictionary<string, object> GetLocationInfoByCode(string locationCode)
{
    if (_locationData == null || !_locationData.Any())
    {
        _logger.Error("Location data not loaded.");
        throw new InvalidOperationException("Location data not loaded.");
    }

    return _locationData.FirstOrDefault(d =>
        d.TryGetValue("code", out var codeValue) && 
        codeValue.ToString().Equals(locationCode, StringComparison.OrdinalIgnoreCase));
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



public string GetDeviceIdByUUID(string uuid)
{
    if (string.IsNullOrEmpty(uuid))
    {
        _logger.Warning("UUID is null or empty.");
        return null;
    }

    // \u2705 \u00d6nce UUID havuzunun g\u00fcncelli\u011fini kontrol et
    CheckAndReloadUUIDPool();

    var match = _uuidPoolData?.FirstOrDefault(d =>
        d.TryGetValue("uuid", out var uuidValue) && uuidValue?.ToString() == uuid);

    if (match != null && match.TryGetValue("deviceid", out var deviceId))
    {
        _logger.Information("\u2705 Found Device ID: {DeviceId} for UUID: {UUID}", deviceId, uuid);
        return deviceId.ToString();
    }

    _logger.Warning("\u26a0\ufe0f No matching Device ID found for UUID: {UUID}", uuid);
    return null;
}


public Dictionary<string, object> GetDeviceByUUID(string uuid)
{
    if (string.IsNullOrEmpty(uuid))
    {
        _logger.Error("UUID cannot be null or empty.");
        throw new ArgumentException("UUID is required.", nameof(uuid));
    }

    // **UUID eşleşmesini JSON'dan çek**
    var match = _uuidPoolData?.FirstOrDefault(d =>
        d.TryGetValue("uuid", out var uuidValue) && uuidValue?.ToString() == uuid);

    if (match != null && match.TryGetValue("deviceid", out var deviceId))
    {
        _logger.Information("Device found for UUID {UUID}: {DeviceId}", uuid, deviceId);
        return GetDeviceById(deviceId.ToString());
    }

    _logger.Warning("No device found for UUID: {UUID}", uuid);
    return null;
}


public void CheckAndReloadUUIDPool()
{
    var lastModifiedTime = File.GetLastWriteTime(_uuidPoolFilePath);

    // E\u011fer dosya de\u011fi\u015fmi\u015fse veya daha \u00f6nce y\u00fcklenmemi\u015fse, tekrar y\u00fckle
    if (_uuidPoolData == null || lastModifiedTime > _lastUuidPoolLoadTime)
    {
        _logger.Information("UUID Pool file has changed. Reloading...");
        LoadUUIDPool(_uuidPoolFilePath);
;
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

        var uuidMapping = uuidMappingRaw.ToObject<Dictionary<string, string>>();

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
    string filePath = "D:/INTRANET/Netinfo/Data/device_config_history.json"; // VLAN JSON dosyası

    try
    {
        if (!File.Exists(filePath))
        {
            _logger.Warning("❌ VLAN data file not found at {FilePath}", filePath);
            return new List<Dictionary<string, object>>();
        }

        var jsonContent = File.ReadAllText(filePath);
        var vlanData = JsonConvert.DeserializeObject<Dictionary<string, Dictionary<string, object>>>(jsonContent);

        if (vlanData == null || vlanData.Count == 0)
        {
            _logger.Warning("⚠ VLAN data file is empty.");
            return new List<Dictionary<string, object>>();
        }

        // 🔍 VLAN bilgilerini işleyerek liste haline getir
        var vlanList = new List<Dictionary<string, object>>();
        foreach (var device in vlanData.Values) // Cihazların JSON objesini oku
        {
            if (device.TryGetValue("vlans", out var vlanObj) && vlanObj is JObject vlanDict)
            {
                foreach (var vlanProp in vlanDict.Properties()) // ❗ Burada JSON nesnesini düzgün okuyoruz
                {
                    var vlanInfo = vlanProp.Value.ToObject<Dictionary<string, object>>();
                    vlanInfo["hostname"] = device["hostname"]; // VLAN'a cihaz ismini ekleyelim
                    vlanList.Add(vlanInfo);
                }
            }
        }

        _logger.Information("✅ VLAN data successfully loaded. Total VLANs: {Count}", vlanList.Count);
        return vlanList;
    }
    catch (Exception ex)
    {
        _logger.Error(ex, "❌ Error while reading VLAN data from file.");
        return new List<Dictionary<string, object>>();
    }
}

public List<Dictionary<string, object>> GetNetworkRushHour(string date)
{
    try
    {
        string filePath = $"D:/INTRANET/Netinfo/Data/network_rush_hour_{date}.json";
        List<Dictionary<string, object>> rushHourData = new List<Dictionary<string, object>>();

        // **Eğer dosya varsa, mevcut veriyi oku**
        if (File.Exists(filePath))
        {
            var jsonContent = File.ReadAllText(filePath);
            rushHourData = JsonConvert.DeserializeObject<List<Dictionary<string, object>>>(jsonContent) ?? new List<Dictionary<string, object>>();
        }

        // **📌 Şu anki saat TR saatine göre alınıyor (UTC+3)**
        DateTime nowUtc = DateTime.UtcNow;
        DateTime nowTR = nowUtc.AddHours(3);  // UTC + 3 saat ekleyerek Türkiye saatine çevir

        int currentHour = nowTR.Hour;
        string currentHourRange = $"{currentHour:00}:00 - {currentHour + 1:00}:00";

        // **Eğer bu saat için veri yoksa, yeni veri oluştur ve kaydet**
        bool dataExistsForCurrentHour = rushHourData.Any(r => r["hour_range"].ToString() == currentHourRange);
        if (!dataExistsForCurrentHour)
        {
            _logger.Warning($"⚠ No rush hour data found for {currentHourRange} (TR Time). Generating new data...");

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
        _logger.Error(ex, $"❌ Error fetching network rush hour data for {date}");
        return new List<Dictionary<string, object>>();
    }
}



public string GetLastAvailableRushHourData()
{
    string directory = "D:/INTRANET/Netinfo/Data/";
    var files = Directory.GetFiles(directory, "network_rush_hour_*.json")
                         .OrderByDescending(f => f)  // En yeni tarihli dosyayı bul
                         .ToList();

    if (!files.Any())
    {
        _logger.Warning("❌ No available rush hour data files found.");
        return null; // Eğer hiç dosya yoksa null döndür
    }

    string latestFile = Path.GetFileNameWithoutExtension(files.First());
    string lastAvailableDate = latestFile.Replace("network_rush_hour_", ""); // Tarih kısmını ayıkla

    _logger.Information("📅 Last available rush hour data found for {Date}", lastAvailableDate);
    return lastAvailableDate;
}


private void SaveNetworkRushHourData(string date, List<Dictionary<string, object>> rushHourData)
{
    try
    {
        string filePath = $"D:/INTRANET/Netinfo/Data/network_rush_hour_{date}.json";

        List<Dictionary<string, object>> existingData = new List<Dictionary<string, object>>();
        if (File.Exists(filePath))
        {
            var existingContent = File.ReadAllText(filePath);
            existingData = JsonConvert.DeserializeObject<List<Dictionary<string, object>>>(existingContent) ?? new List<Dictionary<string, object>>();
        }

        // 📌 **Şu anki saat TR saatine göre hesapla**
        DateTime nowTR = DateTime.UtcNow.AddHours(3);
        int currentHour = nowTR.Hour;
        string currentHourRange = $"{currentHour:00}:00 - {currentHour + 1:00}:00";

        // ✅ **Eğer bu saate ait veri varsa, eski veriyi sil**
        var existingEntry = existingData.FirstOrDefault(e => e["hour_range"].ToString() == currentHourRange);
        if (existingEntry != null)
        {
            existingData.Remove(existingEntry);
        }

        // 🔥 **Gerçek zamanlı veriyi oku**
        double totalInputTraffic = _portData.Sum(p => Convert.ToDouble(p.GetValueOrDefault("input_rate_mbps", 0)));
        double totalOutputTraffic = _portData.Sum(p => Convert.ToDouble(p.GetValueOrDefault("output_rate_mbps", 0)));

        // ✅ **Yeni veri ekle**
        var newEntry = new Dictionary<string, object>
        {
            { "hour_range", currentHourRange },
            { "input_traffic_mbps", totalInputTraffic },
            { "output_traffic_mbps", totalOutputTraffic }
        };

        existingData.Add(newEntry);

        File.WriteAllText(filePath, JsonConvert.SerializeObject(existingData, Formatting.Indented));
        _logger.Information("✅ Network rush hour data updated for {Date}. Last updated hour: {Hour}", date, currentHour);
    }
    catch (Exception ex)
    {
        _logger.Error(ex, "❌ Error saving network rush hour data for {Date}", date);
    }
}



public void UpdateMainDataMetrics()
{
    try
    {
        string filePath = "D:/INTRANET/Netinfo/Data/main_data.json";

        Dictionary<string, object> mainData = new Dictionary<string, object>();
        if (File.Exists(filePath))
        {
            string jsonContent = File.ReadAllText(filePath);
            mainData = JsonConvert.DeserializeObject<Dictionary<string, object>>(jsonContent) ?? new Dictionary<string, object>();
        }

        // 📌 **Gerçek zamanlı olarak input/output verisini hesapla**
        double totalInputTraffic = _portData.Sum(p => Convert.ToDouble(p.GetValueOrDefault("input_rate_mbps", 0)));
        double totalOutputTraffic = _portData.Sum(p => Convert.ToDouble(p.GetValueOrDefault("output_rate_mbps", 0)));

        // 📌 **main_data.json dosyasını güncelle**
        mainData["cumulated_input_mbps"] = totalInputTraffic;
        mainData["cumulated_output_mbps"] = totalOutputTraffic;
        mainData["last_whole_data_updated"] = DateTime.UtcNow.AddHours(3).ToString("dd.MM.yyyy HH:mm");

        File.WriteAllText(filePath, JsonConvert.SerializeObject(mainData, Formatting.Indented));
        _logger.Information("✅ main_data.json updated. Input: {Input}, Output: {Output}", totalInputTraffic, totalOutputTraffic);
    }
    catch (Exception ex)
    {
        _logger.Error(ex, "❌ Error updating main_data.json");
    }
}






public string GetLastWholeDataUpdated()
{
    string filePath = "D:\\INTRANET\\Netinfo\\Data\\main_data.json";

    if (!File.Exists(filePath))
    {
        _logger.Warning("⚠ main_data.json file not found.");
        return "Bilinmiyor";
    }

    try
    {
        string jsonContent = File.ReadAllText(filePath);
        var jsonData = JsonConvert.DeserializeObject<Dictionary<string, object>>(jsonContent);

        if (jsonData != null && jsonData.ContainsKey("last_whole_data_updated") && jsonData["last_whole_data_updated"] is string lastUpdated)
        {
            // 📌 Güncellenmiş tarih formatı
            DateTime parsedDate;
            if (DateTime.TryParseExact(lastUpdated, "dd.MM.yyyy HH:mm", CultureInfo.InvariantCulture, DateTimeStyles.None, out parsedDate))
            {
                return parsedDate.ToString("dd.MM.yyyy HH:mm"); // 📌 Formatı koru
            }
            return "Bilinmiyor"; // 📌 Format hatalıysa
        }
    }
    catch (Exception ex)
    {
        _logger.Error(ex, "❌ Error reading 'last_whole_data_updated' from JSON.");
    }

    return "Bilinmiyor";
}



public void LoadLogAnalysisData(string filePath)
{
    _logger.Information("📂 Loading log analysis data from {FilePath}", filePath);

    if (!File.Exists(filePath))
    {
        _logger.Warning("❌ Log analysis file not found: {FilePath}", filePath);
        _logAnalysisData = new List<Dictionary<string, object>>();
        return;
    }

    try
    {
        var jsonContent = File.ReadAllText(filePath);
        var jsonData = JsonConvert.DeserializeObject<Dictionary<string, Dictionary<string, object>>>(jsonContent);

        if (jsonData == null || jsonData.Count == 0)
        {
            _logger.Warning("⚠ Log analysis JSON is empty.");
            _logAnalysisData = new List<Dictionary<string, object>>();
            return;
        }

        _logAnalysisData = jsonData.Select(kv =>
        {
            var entry = kv.Value;
            entry["device_id"] = kv.Key;

            // ✅ **En çok hata veren portu al**
            string mostProblematicPortRaw = entry.ContainsKey("most_problematic_port") 
                ? entry["most_problematic_port"].ToString() 
                : null;

            string mostProblematicPort = mostProblematicPortRaw?.Split(':')[0].Trim(); 
            // "Gi1/0/2: (25962 occurrences)" → "Gi1/0/2"

            string solution = "Çözüm belirtilmemiş"; 

            // ✅ **Eğer logs varsa, ilgili portun `solution` değerini al**
            if (!string.IsNullOrEmpty(mostProblematicPort) && 
                entry.ContainsKey("logs") && 
                entry["logs"] is JObject logsDict)
            {
                foreach (var log in logsDict.Properties())
                {
                    var logEntry = log.Value as JObject;
                    if (logEntry != null && logEntry.ContainsKey("port"))
                    {
                        string logPort = logEntry["port"].ToString().Trim();
                        if (logPort == mostProblematicPort && logEntry.ContainsKey("latest_log"))
                        {
                            var latestLog = logEntry["latest_log"] as JObject;
                            if (latestLog != null && latestLog.ContainsKey("solution"))
                            {
                                solution = latestLog["solution"].ToString();
                                break; // İlk eşleşmeyi bulunca çık
                            }
                        }
                    }
                }
            }

            // 🔥 **Doğru çözüme sahip olduğumuzu doğrulamak için log basalım**
            _logger.Information("🔎 Device: {Device}, Most Problematic Port: {Port}, Solution: {Solution}", 
                                kv.Key, mostProblematicPort, solution);

            entry["most_problematic_port_solution"] = solution;
            return entry;
        }).ToList();

        _logger.Information("✅ Log analysis loaded successfully. Total logs: {Count}", _logAnalysisData.Count);
    }
    catch (Exception ex)
    {
        _logger.Error(ex, "❌ Error loading log analysis data.");
        _logAnalysisData = new List<Dictionary<string, object>>();
    }
}


public List<Dictionary<string, object>> GetLogAnalysis()
{
    if (_logAnalysisData == null || _logAnalysisData.Count == 0)
    {
        _logger.Warning("⚠ Log analysis data is empty. Reloading...");
        LoadLogAnalysisData(_logAnalysisFilePath);
    }

    var enrichedLogs = _logAnalysisData.Select(entry =>
    {
        string mostProblematicPortSolution = "Çözüm belirtilmemiş";
        int mostProblematicPortOccurrences = 0;
        string mostProblematicPort = "N/A";

        if (entry.ContainsKey("most_problematic_port") && entry.ContainsKey("logs") && entry["logs"] is JObject logsDict)
        {
            // ✅ **En fazla hata veren portu düzgün ayıkla**
            string mostProblematicPortRaw = entry["most_problematic_port"].ToString();
            var match = Regex.Match(mostProblematicPortRaw, @"(.*):\s*\((\d+)\s*occurrences\)");
            if (match.Success)
            {
                mostProblematicPort = match.Groups[1].Value.Trim();
                mostProblematicPortOccurrences = int.Parse(match.Groups[2].Value); // 🔥 Hata düzeltildi
            }
            else
            {
                mostProblematicPort = mostProblematicPortRaw.Trim();
            }

            // ✅ **Alternatif olarak JSON içinde occurrences alanını kontrol et**
            if (mostProblematicPortOccurrences == 0)
            {
                foreach (var logEntry in logsDict.Properties())
                {
                    if (logEntry.Value is JObject logObject &&
                        logObject.ContainsKey("port") &&
                        logObject["port"].ToString().Trim() == mostProblematicPort &&
                        logObject.ContainsKey("occurrences"))
                    {
                        mostProblematicPortOccurrences = Convert.ToInt32(logObject["occurrences"]);
                        break;
                    }
                }
            }

            // ✅ **Çözümü al**
            foreach (var logEntry in logsDict.Properties())
            {
                if (logEntry.Value is JObject logObject &&
                    logObject.ContainsKey("port") &&
                    logObject["port"].ToString().Trim() == mostProblematicPort &&
                    logObject.ContainsKey("latest_log") &&
                    logObject["latest_log"] is JObject latestLog &&
                    latestLog.ContainsKey("solution"))
                {
                    mostProblematicPortSolution = latestLog["solution"].ToString();
                    break; // **İlk eşleşmeyi bulduktan sonra döngüyü bitir**
                }
            }
        }

        entry["most_problematic_port"] = mostProblematicPort;
        entry["most_problematic_port_occurrences"] = mostProblematicPortOccurrences;
        entry["most_problematic_port_solution"] = mostProblematicPortSolution;
        return entry;
    }).ToList();

    _logger.Information("✅ Log analysis enriched with most problematic port solutions. Total logs: {Count}", enrichedLogs.Count);
    return enrichedLogs;
}

public void LoadInsightSummary(string filePath)
{
    _logger.Information("📂 Loading Insight Summary from {FilePath}", filePath);

    if (!File.Exists(filePath))
    {
        _logger.Warning("❌ Insight summary file not found: {FilePath}", filePath);
        return;
    }

    try
    {
        var jsonContent = File.ReadAllText(filePath);
        var list = JsonConvert.DeserializeObject<List<InsightSummary>>(jsonContent); // Değişiklik burada

        if (list == null || list.Count == 0)
        {
            _logger.Warning("⚠ Insight summary JSON list is empty or invalid.");
            return;
        }

        var latest = list.LastOrDefault();
        if (latest == null)
        {
            _logger.Warning("⚠ Insight summary file contains no valid entries.");
            return;
        }

        _logger.Information("✅ Insight summary loaded. Latest timestamp: {Timestamp}", latest.Timestamp);
    }
    catch (Exception ex)
    {
        _logger.Error(ex, "❌ Error loading insight summary from file.");
    }
}

public List<InsightSummary> GetInsightSummary()
{
    try
    {
        if (!File.Exists(_insightSummaryFilePath))
        {
            _logger.Warning("❌ Insight summary file not found at {FilePath}", _insightSummaryFilePath);
            return new List<InsightSummary>();
        }

        var jsonContent = File.ReadAllText(_insightSummaryFilePath);
        var list = JsonConvert.DeserializeObject<List<InsightSummary>>(jsonContent); // Değişiklik burada

        if (list == null || list.Count == 0)
        {
            _logger.Warning("⚠ Insight summary JSON list is empty.");
            return new List<InsightSummary>();
        }

        _logger.Information("✅ Insight summary loaded. Count: {Count}", list.Count);
        return list;
    }
    catch (Exception ex)
    {
        _logger.Error(ex, "❌ Error reading insight summary JSON.");
        return new List<InsightSummary>();
    }
}

public InsightSummary GetLatestInsightSummary()
{
    try
    {
        var allSummaries = GetInsightSummary(); // Yukarıdaki metodu kullanıyoruz
        return allSummaries.LastOrDefault();
    }
    catch (Exception ex)
    {
        _logger.Error(ex, "❌ Error getting latest insight summary.");
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
    public RushHourData RushHour { get; set; }

    [JsonProperty("insights")]
    public List<string> Insights { get; set; } = new List<string>();
}

public class StatusChange
{
    [JsonProperty("hostname")]
    public string Hostname { get; set; }

    [JsonProperty("serial")]
    public string Serial { get; set; }

    [JsonProperty("timestamp")]
    public DateTime Timestamp { get; set; }

    [JsonProperty("status_change")]
    public string StatusChangeDescription { get; set; }
}

public class RushHourData
{
    [JsonProperty("min")]
    public HourRangeData Min { get; set; }

    [JsonProperty("max")]
    public HourRangeData Max { get; set; }
}

public class HourRangeData
{
    [JsonProperty("hour_range")]
    public string HourRange { get; set; }

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
        LoadPortData("D:\\INTRANET\\Netinfo\\Data\\main_data.json");

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
