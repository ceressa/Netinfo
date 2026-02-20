@echo off
setlocal EnableDelayedExpansion
:: === [1] UTF-8 Kodlama Ayari ===
chcp 65001 >nul 2>&1
echo.
echo ==================================================
echo [INFO] Kodlama UTF-8 olarak ayarlandi.
echo ==================================================
:: === [2] Yonetici Yetkisi Kontrolu ===
net session >nul 2>&1
if !errorlevel! neq 0 (
    echo [ERROR] Bu islem icin yonetici yetkisi gerekiyor.
    echo [INFO] Yonetici izni isteniyor...
    powershell -Command "Start-Process cmd -ArgumentList '/c \"%~0\"' -Verb RunAs"
    exit /b 1
)
:: === [3] Uygulama Dizini ve Degiskenler ===
set "PROJECT_PATH=D:\INTRANET\Netinfo"
set "PUBLISH_PATH=%PROJECT_PATH%\publish"
set "APPPOOL_NAME=NetinfoPythonPool"
echo.
echo [INFO] Uygulama dizinine geciliyor: %PROJECT_PATH%
cd /d "%PROJECT_PATH%" || (
    echo [ERROR] Dizin gecisi basarisiz: %PROJECT_PATH%
    goto :error_exit
)
:: === [4] .NET SDK Kontrolu ===
dotnet --version >nul 2>&1 || (
    echo [ERROR] .NET SDK bulunamadi. Lutfen yuklu oldugundan emin olun.
    goto :error_exit
)
:: === [5] IIS App Pool Durdurma ===
echo.
echo [INFO] IIS App Pool kontrol ediliyor...
if exist "%windir%\system32\inetsrv\appcmd.exe" (
    echo [INFO] App Pool durduruluyor: %APPPOOL_NAME%
    "%windir%\system32\inetsrv\appcmd.exe" stop apppool /apppool.name:"%APPPOOL_NAME%" >nul 2>&1
    echo [OK] App Pool durduruldu.
) else (
    echo [WARNING] IIS yuklu degil veya appcmd.exe bulunamadi. Devam ediliyor...
)
:: === [6] Yayinlama (Deploy) Islemi ===
echo.
echo [INFO] Uygulama yayinlaniyor...
dotnet publish -c Release -o "%PUBLISH_PATH%" --no-restore
if !errorlevel! neq 0 (
    echo [WARNING] Ilk publish denemesi basarisiz. Tekrar deneniyor...
    dotnet publish -c Release -o "%PUBLISH_PATH%"
    if !errorlevel! neq 0 (
        echo [ERROR] Uygulama yayinlanamadi.
        goto :error_exit
    )
)
echo [OK] Yayinlama tamamlandi: %PUBLISH_PATH%
:: === [7] IIS App Pool Baslatma ===
echo.
if exist "%windir%\system32\inetsrv\appcmd.exe" (
    echo [INFO] App Pool baslatiliyor: %APPPOOL_NAME%
    "%windir%\system32\inetsrv\appcmd.exe" start apppool /apppool.name:"%APPPOOL_NAME%" >nul 2>&1
    echo [OK] App Pool baslatildi.
)
:: === [8] Tamamlandi ===
echo.
echo ==================================================
echo [OK] Uygulama basariyla deploy edildi!
echo ==================================================
echo [INFO] Yayinlanan dizin: %PUBLISH_PATH%
echo [INFO] Uygulama dosyasi: %PUBLISH_PATH%\Netinfo.dll
echo.
goto :end
:error_exit
echo.
echo ==================================================
echo [ERROR] HATA OLUSTU!
echo ==================================================
echo [ERROR] Islem tamamlanamadi. Lutfen yukaridaki hata mesajlarini inceleyin.
echo.
goto :end
:end
pause
exit /b
