// Statseeker raporu icin backend proxy uzerinden fetch fonksiyonu
// Credentials artik backend tarafinda yonetiliyor
async function getStatseekerReport(hostname) {
    const deviceName = hostname;

    try {
        const response = await fetch(`/Netinfo/api/get_report?deviceid=${encodeURIComponent(deviceName)}`);

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        const reportData = await response.json();
        return reportData;
    } catch (error) {
        console.error('Fetch error:', error);
        return [];
    }
}

// Excel'deki hostname ile eslestirip raporu admin ekranina yansitma
async function updateAdminScreen(hostname) {
    const reportData = await getStatseekerReport(hostname);
    if (reportData && reportData.length > 0) {
        const tableBody = document.getElementById('statseekerTableBody');
        tableBody.textContent = ''; // Guvenli temizleme

        reportData.forEach((port) => {
            const row = document.createElement("tr");

            const deviceCell = document.createElement("td");
            deviceCell.textContent = port.device || port["Device ID"] || "";

            const interfaceCell = document.createElement("td");
            interfaceCell.textContent = port.interface || port["Interface"] || "";

            const titleCell = document.createElement("td");
            titleCell.textContent = port.title || port["Tanim"] || "";

            row.appendChild(deviceCell);
            row.appendChild(interfaceCell);
            row.appendChild(titleCell);
            tableBody.appendChild(row);
        });

        document.getElementById("statseekerReportContainer").style.display = "block";
    } else {
        console.warn('Rapor alinamadi veya veri mevcut degil.');
    }
}

// Raporu Getir butonuna basarak tetikleme
async function fetchStatseekerReport() {
    if (deviceData && deviceData.hostname) {
        await updateAdminScreen(deviceData.hostname);
    } else {
        console.warn('Cihaz bilgileri henuz yuklenmedi.');
    }
}
