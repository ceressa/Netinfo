// Statseeker raporu icin backend proxy uzerinden fetch fonksiyonu
// Credentials artik backend tarafinda yonetiliyor
async function getStatseekerReport(hostname) {
    const deviceName = hostname;
    const url = `/Netinfo/api/get_report?deviceid=${encodeURIComponent(deviceName)}`;
    const maxRetries = 3;
    const timeoutMs = 15000;

    for (let attempt = 0; attempt < maxRetries; attempt++) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

        try {
            const response = await fetch(url, { signal: controller.signal });
            clearTimeout(timeoutId);

            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            clearTimeout(timeoutId);
            if (attempt === maxRetries - 1) {
                console.error('Fetch error after retries:', error);
                return [];
            }
            const delay = Math.pow(2, attempt) * 1000;
            await new Promise(resolve => setTimeout(resolve, delay));
        }
    }
    return [];
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
