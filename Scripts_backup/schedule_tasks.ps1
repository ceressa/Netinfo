# Fetch Statseeker Script: Günde bir kez saat 22:00'da çalıştır
schtasks /Create `
    /TN "Fetch_Statseeker" `
    /TR "cmd.exe /c python D:\INTRANET\Netinfo\Scripts\fetch_statseeker.py" `
    /SC DAILY `
    /ST 22:00 `
    /RU SYSTEM `
    /F

# Fetch NetDB Script: Sabah 08:20'den akşam 20:20'ye kadar her saat 20 geçe çalıştır
$scriptPath2 = "D:\INTRANET\Netinfo\Scripts\fetch_netdb.py"

# Saat döngüsü
for ($hour = 8; $hour -le 20; $hour++) {
    # Saat başı çalıştırılacak görev adı
    $taskName = "Fetch_NetDB_${hour}20"
    $startTime = "{0:D2}:20" -f $hour

    # Görevi oluştur
    schtasks /Create `
        /TN $taskName `
        /TR "cmd.exe /c python $scriptPath2" `
        /SC DAILY `
        /ST $startTime `
        /RU SYSTEM `
        /F

    Write-Output "Görev oluşturuldu: $taskName - Saat: $startTime"
}
