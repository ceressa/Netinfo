using System.Text.Json;
using Serilog;


namespace Netinfo.Services
{
    public class AccessPointService
    {
        private readonly Serilog.ILogger _logger; // Explicit Serilog reference
        private readonly DataPathsConfig _paths;
        private List<object> _apInventory = new List<object>();
        private List<object> _enhancedWirelessData = new List<object>();
        private DateTime _lastDataLoad = DateTime.MinValue;

        public AccessPointService(Serilog.ILogger logger, DataPathsConfig paths) // Explicit Serilog
        {
            _logger = logger.ForContext<AccessPointService>();
            _paths = paths;
            LoadAllAPData();
        }

        public void LoadAllAPData()
        {
            try
            {
                LoadAPInventory();
                LoadEnhancedWirelessData();
                _lastDataLoad = DateTime.Now;
                _logger.Information($"AP data loaded successfully at {_lastDataLoad}");
            }
            catch (Exception ex)
            {
                _logger.Error(ex, "Failed to load AP data");
            }
        }

        private void LoadAPInventory()
        {
            string apInventoryPath = Path.Combine(_paths.DataDir, _paths.APInventory);

            if (File.Exists(apInventoryPath))
            {
                string jsonContent = File.ReadAllText(apInventoryPath);
                _apInventory = JsonSerializer.Deserialize<List<dynamic>>(jsonContent) ?? new List<dynamic>();
                _logger.Information($"Loaded {_apInventory.Count} APs from inventory");
            }
            else
            {
                _logger.Warning($"AP inventory file not found: {apInventoryPath}");
                _apInventory = new List<dynamic>(); // Empty list if file doesn't exist
            }
        }

        private void LoadEnhancedWirelessData()
        {
            string enhancedDataPath = Path.Combine(_paths.DataDir, _paths.EnhancedWirelessData);

            if (File.Exists(enhancedDataPath))
            {
                try
                {
                    string jsonContent = File.ReadAllText(enhancedDataPath);
                    var data = JsonSerializer.Deserialize<JsonElement>(jsonContent);

                    if (data.TryGetProperty("enhanced_wireless_data", out var enhancedData))
                    {
                        _enhancedWirelessData = JsonSerializer.Deserialize<List<dynamic>>(enhancedData.GetRawText()) ?? new List<dynamic>();
                    }

                    _logger.Information($"Loaded enhanced wireless data for {_enhancedWirelessData.Count} APs");
                }
                catch (Exception ex)
                {
                    _logger.Warning(ex, "Failed to load enhanced wireless data");
                    _enhancedWirelessData = new List<dynamic>();
                }
            }
            else
            {
                _logger.Information("Enhanced wireless data file not found, skipping");
                _enhancedWirelessData = new List<dynamic>();
            }
        }

        public async Task<object> GetAccessPointInventory()
        {
            // Refresh data if older than 5 minutes
            if (DateTime.Now - _lastDataLoad > TimeSpan.FromMinutes(5))
            {
                await Task.Run(LoadAllAPData);
            }

            var activeAPs = _apInventory.Where(ap =>
            {
                var element = (JsonElement)ap;
                return element.TryGetProperty("is_up", out var isUp) && isUp.GetBoolean();
            }).ToList();

            var totalClients = _apInventory.Sum(ap =>
            {
                var element = (JsonElement)ap;
                return element.TryGetProperty("wireless_clients_numbers", out var count) ? count.GetInt32() : 0;
            });

            return new
            {
                success = true,
                data = _apInventory,
                summary = new
                {
                    total_aps = _apInventory.Count,
                    active_aps = activeAPs.Count,
                    total_clients = totalClients,
                    last_updated = _lastDataLoad.ToString("yyyy-MM-dd HH:mm:ss")
                }
            };
        }

		public async Task<object> GetHourlyClientStats()
{
    try
    {
        var hourlyStatsPath = Path.Combine(_paths.DataDir, _paths.HourlyClientStats);

        if (!File.Exists(hourlyStatsPath))
        {
            return new Dictionary<string, object>();
        }

        var json = await File.ReadAllTextAsync(hourlyStatsPath);

        // Mixed format için JsonElement kullan
        var hourlyStats = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(json);

        // JsonElement'leri object'e dönüştür
        var result = new Dictionary<string, object>();

        foreach (var kvp in hourlyStats)
        {
            if (kvp.Value.ValueKind == JsonValueKind.Number)
            {
                // Eski format - sadece sayı
                result[kvp.Key] = kvp.Value.GetInt32();
            }
            else if (kvp.Value.ValueKind == JsonValueKind.Object)
            {
                // Yeni format - object
                var objStr = kvp.Value.GetRawText();
                var obj = JsonSerializer.Deserialize<Dictionary<string, object>>(objStr);
                result[kvp.Key] = obj;
            }
        }

        return result;
    }
    catch (Exception ex)
    {
        _logger.Error(ex, "Error loading hourly client stats");
        return new Dictionary<string, object>();
    }
}

        public async Task<object> GetWirelessClients()
        {
            var allClients = new List<object>();

            foreach (var ap in _apInventory)
            {
                var element = (JsonElement)ap;

                if (element.TryGetProperty("wireless_clients", out var clientsProperty) &&
                    clientsProperty.ValueKind == JsonValueKind.Array)
                {
                    foreach (var client in clientsProperty.EnumerateArray())
                    {
                        var clientData = new
                        {
                            hostname = client.TryGetProperty("hostname", out var h) ? h.GetString() : "Unknown",
                            ip_address = client.TryGetProperty("ip_address", out var ip) ? ip.GetString() : "N/A",
                            mac_address = client.TryGetProperty("mac_address", out var mac) ? mac.GetString() : "N/A",
                            username = client.TryGetProperty("username", out var user) ? user.GetString() : "N/A",
                            wlan = client.TryGetProperty("wlan", out var wlan) ? wlan.GetString() : "N/A",
                            ap_hostname = element.TryGetProperty("hostname", out var apHost) ? apHost.GetString() : "Unknown",
                            ap_ip = element.TryGetProperty("ipaddress", out var apIp) ? apIp.GetString() : "N/A",
                            connection_time = GetRandomConnectionTime(),
                            signal_strength = GetRandomSignalStrength(),
                            last_seen = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss")
                        };

                        allClients.Add(clientData);
                    }
                }
            }

            return new
            {
                success = true,
                data = allClients,
                total_clients = allClients.Count,
                last_updated = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss")
            };
        }

        public async Task<object> GetAPStatistics()
        {
            // Top 10 busiest APs
            var topAPs = _apInventory
                .Where(ap =>
                {
                    var element = (JsonElement)ap;
                    return element.TryGetProperty("wireless_clients_numbers", out var count) && count.GetInt32() > 0;
                })
                .OrderByDescending(ap =>
                {
                    var element = (JsonElement)ap;
                    return element.TryGetProperty("wireless_clients_numbers", out var count) ? count.GetInt32() : 0;
                })
                .Take(10)
                .ToList();

            // Uptime analysis
            var uptimeStats = _apInventory
                .Where(ap =>
                {
                    var element = (JsonElement)ap;
                    return element.TryGetProperty("uptime", out var uptime) && !string.IsNullOrEmpty(uptime.GetString());
                })
                .Select(ap =>
                {
                    var element = (JsonElement)ap;
                    var uptimeStr = element.GetProperty("uptime").GetString();
                    var hostname = element.TryGetProperty("hostname", out var h) ? h.GetString() : "Unknown";

                    return new
                    {
                        hostname,
                        uptime = uptimeStr,
                        uptime_hours = ParseUptimeToHours(uptimeStr ?? ""),
                        is_up = element.TryGetProperty("is_up", out var isUp) && isUp.GetBoolean()
                    };
                })
                .OrderByDescending(x => x.uptime_hours)
                .Take(10)
                .ToList();

            // Signal analysis
            var signalAnalysis = new List<object>();
            foreach (var ap in _apInventory)
            {
                var element = (JsonElement)ap;
                if (element.TryGetProperty("enhanced_wireless", out var enhanced) &&
                    enhanced.TryGetProperty("radio_info", out var radioInfo) &&
                    radioInfo.ValueKind == JsonValueKind.Array)
                {
                    var activeRadios = radioInfo.EnumerateArray()
                        .Where(radio => radio.TryGetProperty("is_active", out var active) && active.GetBoolean())
                        .ToList();

                    if (activeRadios.Any())
                    {
                        var avgPower = activeRadios.Average(radio =>
                            radio.TryGetProperty("power_dbm", out var power) ? power.GetDouble() : 0);

                        signalAnalysis.Add(new
                        {
                            hostname = element.TryGetProperty("hostname", out var h) ? h.GetString() : "Unknown",
                            active_radios = activeRadios.Count(),
                            total_radios = radioInfo.GetArrayLength(),
                            avg_power_dbm = Math.Round(avgPower, 1),
                            client_count = element.TryGetProperty("wireless_clients_numbers", out var count) ? count.GetInt32() : 0,
                            clients_per_radio = activeRadios.Count() > 0 ?
                                Math.Round((double)(element.TryGetProperty("wireless_clients_numbers", out var c) ? c.GetInt32() : 0) / activeRadios.Count(), 1) : 0
                        });
                    }
                }
            }

            return new
            {
                success = true,
                data = new
                {
                    top_aps = topAPs,
                    uptime_leaders = uptimeStats,
                    signal_analysis = signalAnalysis.Take(10).ToList(),
                    summary = new
                    {
                        total_aps = _apInventory.Count,
                        active_aps = _apInventory.Count(ap =>
                        {
                            var element = (JsonElement)ap;
                            return element.TryGetProperty("is_up", out var isUp) && isUp.GetBoolean();
                        }),
                        avg_uptime_percentage = CalculateAverageUptimePercentage(),
                        total_clients = _apInventory.Sum(ap =>
                        {
                            var element = (JsonElement)ap;
                            return element.TryGetProperty("wireless_clients_numbers", out var count) ? count.GetInt32() : 0;
                        })
                    }
                },
                last_updated = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss")
            };
        }

        private double ParseUptimeToHours(string uptime)
        {
            if (string.IsNullOrEmpty(uptime)) return 0;

            var regex = new System.Text.RegularExpressions.Regex(@"(\d+)\s*days?,?\s*(\d+)\s*hours?",
                System.Text.RegularExpressions.RegexOptions.IgnoreCase);
            var match = regex.Match(uptime);

            if (match.Success)
            {
                var days = int.Parse(match.Groups[1].Value);
                var hours = int.Parse(match.Groups[2].Value);
                return days * 24 + hours;
            }

            return 0;
        }

        private double CalculateAverageUptimePercentage()
        {
            var apsWithUptime = _apInventory.Where(ap =>
            {
                var element = (JsonElement)ap;
                return element.TryGetProperty("uptime", out var uptime) && !string.IsNullOrEmpty(uptime.GetString());
            }).ToList();

            if (!apsWithUptime.Any()) return 0;

            var totalHours = apsWithUptime.Sum(ap =>
            {
                var element = (JsonElement)ap;
                var uptimeStr = element.GetProperty("uptime").GetString();
                return ParseUptimeToHours(uptimeStr ?? "");
            });

            var avgHours = totalHours / apsWithUptime.Count;
            return Math.Min((avgHours / (24 * 30)) * 100, 100); // 30 day reference
        }

        private string GetRandomConnectionTime()
        {
            var times = new[] { "2h 15m", "45m", "1h 30m", "3h 22m", "25m", "1h 05m", "4h 10m" };
            return times[new Random().Next(times.Length)];
        }

        private int GetRandomSignalStrength()
        {
            return new Random().Next(-70, -30); // -70 to -30 dBm
        }
    }
}
