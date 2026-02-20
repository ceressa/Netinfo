// Statseeker'dan raporu almak için fetch fonksiyonu
async function getStatseekerReport(hostname) {
    const username = 'tr-api';
    const password = 'F3xpres!';
    const deviceName = hostname;  // Bu parametre Excel'den çekilecek hostname olacak

    // Temel kimlik doğrulama için base64 encoding
    const auth = btoa(`${username}:${password}`);
    const url = `https://statseeker.emea.fedex.com/cgi/nimc02?rid=54366&sort=Ntxutil&tfc_fav=range+%3D+start_of_today+to+now%3B&year=&month=&day=&hour=&minute=&duration=&wday_from=&wday_to=&time_from=&time_to=&tz=Europe%2FIstanbul&tfc=range+%3D+start_of_today+to+now%3B&regex=&top_n=&group_selector=geto&report=37&device=${deviceName}&has_refreshed=1`;

    try {
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'Authorization': `Basic ${auth}`,
                'Content-Type': 'text/html',  // HTML döneceği için bunu belirtiyoruz
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        const html = await response.text(); // Raporun HTML olarak döneceğini kabul ediyoruz

        // HTML içeriği parse etmek için bir DOM parser kullanıyoruz
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');

        // HTML içerisinden gerekli bilgileri çekiyoruz
        const rows = doc.querySelectorAll('table tbody tr');  // Statseeker'ın HTML tablosunun gövdesinden tüm satırları seçiyoruz
        const reportData = [];

        rows.forEach(row => {
            const device = row.cells[0]?.textContent.trim(); // Birinci hücre: cihaz adı
            const interfaceName = row.cells[1]?.textContent.trim(); // İkinci hücre: interface adı
            const title = row.cells[22]?.textContent.trim(); // 23. hücre: title

            if (device && interfaceName && title) {
                reportData.push({ device, interface: interfaceName, title });
            }
        });

        return reportData; // Geriye rapor verisini döndürün
    } catch (error) {
        console.error('Fetch error:', error);
        return [];
    }
}

// Excel'deki hostname ile eşleştirip raporu admin ekranına yansıtma
async function updateAdminScreen(hostname) {
    const reportData = await getStatseekerReport(hostname);
    if (reportData && reportData.length > 0) {
        const tableBody = document.getElementById('statseekerTableBody');
        tableBody.innerHTML = ''; // Önce tabloyu temizleyin

        reportData.forEach((port) => {
            const row = document.createElement("tr");
            row.innerHTML = `
                <td>${port.device}</td>
                <td>${port.interface}</td>
                <td>${port.title}</td>
            `;
            tableBody.appendChild(row);
        });

        document.getElementById("statseekerReportContainer").style.display = "block";
    } else {
        alert('Rapor alınırken bir hata oluştu veya veri mevcut değil.');
    }
}

// Raporu Getir butonuna basarak tetikleme
async function fetchStatseekerReport() {
    if (deviceData && deviceData.hostname) {
        await updateAdminScreen(deviceData.hostname);
    } else {
        alert('Cihaz bilgileri henüz yüklenmedi.');
    }
}
