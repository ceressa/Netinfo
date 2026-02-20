const translations = {
    "tr": {
        "Cihaz Listesi": "Cihaz Listesi",
        "Search Device...": "Cihaz Ara...",
        "Model": "Model",
        "Durum": "Durum",
        "Aktif": "Aktif",
        "Pasif": "Pasif",
        "Bilinmeyen": "Bilinmeyen",
        "Cihaz Durumları": "Cihaz Durumları",
        "Aktif Cihazlar": "Aktif Cihazlar",
        "Pasif Cihazlar": "Pasif Cihazlar",
        "Bilinmeyen Cihazlar": "Bilinmeyen Cihazlar",
        "Son 24 Saatte Durum Değiştiren Cihazlar": "Son 24 Saatte Durum Değiştiren Cihazlar",
        "Cihaz Adı": "Cihaz Adı",
        "Seri Numarası": "Seri Numarası",
        "Durum Değişiklik Zamanı": "Durum Değişiklik Zamanı",
        "Durum Değişikliği": "Durum Değişikliği",
        "En Çok Data Kullanan Cihazlar": "En Çok Data Kullanan Cihazlar",
        "Giriş Trafiği (Mbps)": "Giriş Trafiği (Mbps)",
        "Çıkış Trafiği (Mbps)": "Çıkış Trafiği (Mbps)",
        "En Fazla Trafik Olan Port": "En Fazla Trafik Olan Port",
        "Kritik Cihazlar": "Kritik Cihazlar",
        "IP Adresi": "IP Adresi",
        "İşlem": "İşlem",
        "Kaldır": "Kaldır",
        "UP → DOWN": "UP → DOWN",
        "DOWN → UP": "DOWN → UP"
    },
    "en": {
        "Cihaz Listesi": "Device List",
        "Search Device...": "Search Device...",
        "Model": "Model",
        "Durum": "Status",
        "Aktif": "Active",
        "Pasif": "Inactive",
        "Bilinmeyen": "Unknown",
        "Cihaz Durumları": "Device Status",
        "Aktif Cihazlar": "Active Devices",
        "Pasif Cihazlar": "Inactive Devices",
        "Bilinmeyen Cihazlar": "Unknown Devices",
        "Son 24 Saatte Durum Değiştiren Cihazlar": "Devices Changed Status in Last 24 Hours",
        "Cihaz Adı": "Device Name",
        "Seri Numarası": "Serial Number",
        "Durum Değişiklik Zamanı": "Status Change Time",
        "Durum Değişikliği": "Status Change",
        "En Çok Data Kullanan Cihazlar": "Top Data Consuming Devices",
        "Giriş Trafiği (Mbps)": "Inbound Traffic (Mbps)",
        "Çıkış Trafiği (Mbps)": "Outbound Traffic (Mbps)",
        "En Fazla Trafik Olan Port": "Highest Traffic Port",
        "Kritik Cihazlar": "Critical Devices",
        "IP Adresi": "IP Address",
        "İşlem": "Action",
        "Kaldır": "Remove",
        "UP → DOWN": "UP → DOWN",
        "DOWN → UP": "DOWN → UP"
    },
    "pt": {
        "Cihaz Listesi": "Lista de Dispositivos",
        "Search Device...": "Pesquisar Dispositivo...",
        "Model": "Modelo",
        "Durum": "Status",
        "Aktif": "Ativo",
        "Pasif": "Inativo",
        "Bilinmeyen": "Desconhecido",
        "Cihaz Durumları": "Status dos Dispositivos",
        "Aktif Cihazlar": "Dispositivos Ativos",
        "Pasif Cihazlar": "Dispositivos Inativos",
        "Bilinmeyen Cihazlar": "Dispositivos Desconhecidos",
        "Son 24 Saatte Durum Değiştiren Cihazlar": "Dispositivos que Mudaram de Status nas Últimas 24 Horas",
        "Cihaz Adı": "Nome do Dispositivo",
        "Seri Numarası": "Número de Série",
        "Durum Değişiklik Zamanı": "Hora da Mudança de Status",
        "Durum Değişikliği": "Mudança de Status",
        "En Çok Data Kullanan Cihazlar": "Dispositivos com Maior Consumo de Dados",
        "Giriş Trafiği (Mbps)": "Tráfego de Entrada (Mbps)",
        "Çıkış Trafiği (Mbps)": "Tráfego de Saída (Mbps)",
        "En Fazla Trafik Olan Port": "Porta com Maior Tráfego",
        "Kritik Cihazlar": "Dispositivos Críticos",
        "IP Adresi": "Endereço IP",
        "İşlem": "Ação",
        "Kaldır": "Remover",
        "UP → DOWN": "UP → DOWN",
        "DOWN → UP": "DOWN → UP"
    }
};

// Varsayılan dil
let currentLanguage = localStorage.getItem("selectedLanguage") || "tr";

// Sayfadaki metinleri çevirme fonksiyonu
function translatePage() {
    document.querySelectorAll('*').forEach(element => {
        if (element.childNodes.length === 1 && element.childNodes[0].nodeType === 3) {
            let text = element.innerText.trim();
            if (translations[currentLanguage][text]) {
                element.innerText = translations[currentLanguage][text];
            }
        }
    });
}

// Dil değiştirme fonksiyonu
function changeLanguage(lang) {
    currentLanguage = lang;
    localStorage.setItem("selectedLanguage", lang);
    translatePage();
}

// Dinamik içerikleri gözlemleme
const observer = new MutationObserver(() => {
    translatePage();
});

// Sayfa yüklendiğinde çalıştır
document.addEventListener("DOMContentLoaded", () => {
    translatePage();
    observer.observe(document.body, { childList: true, subtree: true });
});

// HTML içine dil seçim menüsü ekle
document.addEventListener("DOMContentLoaded", () => {
    const langSwitcher = document.createElement("div");
    langSwitcher.innerHTML = `
        <select id="languageSelector">
            <option value="tr">Türkçe</option>
            <option value="en">English</option>
            <option value="pt">Português</option>
        </select>
    `;
    langSwitcher.style.position = "absolute";
    langSwitcher.style.top = "40px"; // Tarihin hemen altı
    langSwitcher.style.left = "10px"; // Sol üst köşe
    langSwitcher.style.zIndex = "1000";

    document.body.appendChild(langSwitcher);

    // Varsayılan dil ayarla
    document.getElementById("languageSelector").value = currentLanguage;
    document.getElementById("languageSelector").addEventListener("change", (e) => {
        changeLanguage(e.target.value);
    });
});
