namespace Netinfo.Services
{
    public class DataPathsConfig
    {
        public string DataDir { get; set; } = "Data";
        public string LogDir { get; set; } = "logs";
        public string ArchiveLogDir { get; set; } = "logs/Archived_Logs";
        public string SyslogDir { get; set; } = "logs/Syslog_AI";
        public string PingLogPath { get; set; } = "logs/PingStateChanges.log";
        public string DeviceInventory { get; set; } = "network_device_inventory.json";
        public string PreviousDeviceInventory { get; set; } = "network_device_inventory_previous.json";
        public string MainData { get; set; } = "main_data.json";
        public string RouterData { get; set; } = "main_router_data.json";
        public string UUIDPool { get; set; } = "UUID_Pool.json";
        public string StationInfo { get; set; } = "station-info.json";
        public string SyslogSummary { get; set; } = "syslog_summary.json";
        public string InsightSummary { get; set; } = "insight_summary.json";
        public string TokenList { get; set; } = "token_list.json";
        public string ToolTokens { get; set; } = "tool_tokens.json";
        public string DeviceConfigHistory { get; set; } = "device_config_history.json";
        public string APInventory { get; set; } = "access_point_inventory.json";
        public string EnhancedWirelessData { get; set; } = "enhanced_wireless_data.json";
        public string HourlyClientStats { get; set; } = "hourly_client_stats.json";
        public string StatusChangesLog { get; set; } = "device_status_changes.json";

        public string GetFullDataPath(string fileName) => Path.Combine(DataDir, fileName);
        public string GetFullLogPath(string fileName) => Path.Combine(LogDir, fileName);
    }
}
