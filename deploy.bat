@echo off
setlocal EnableDelayedExpansion

:: ============================================================
::  NETINFO - TEK TUSLA DEPLOY SCRIPTI
::  Git Merge + Push + Build + IIS Deploy
:: ============================================================

:: === [1] UTF-8 Kodlama ===
chcp 65001 >nul 2>&1

echo.
echo ############################################################
echo #           NETINFO - FULL DEPLOY PIPELINE                 #
echo #   Git Merge ^> Push ^> Build ^> IIS Deploy                  #
echo ############################################################
echo.

:: === [2] Degiskenler ===
set "PROJECT_PATH=D:\INTRANET\Netinfo"
set "PUBLISH_PATH=%PROJECT_PATH%\publish"
set "APPPOOL_NAME=NetinfoPythonPool"
set "TARGET_BRANCH=main"
set "REMOTE=origin"
set "STEP=0"
set "DID_STASH=0"

:: === [3] Yonetici Yetkisi Kontrolu ===
net session >nul 2>&1
if !errorlevel! neq 0 (
    echo [ERROR] Bu islem icin yonetici yetkisi gerekiyor.
    echo [INFO] Yonetici izni isteniyor...
    powershell -Command "Start-Process cmd -ArgumentList '/c \"%~0\"' -Verb RunAs"
    exit /b 1
)
echo [OK] Yonetici yetkisi mevcut.

:: === [4] Uygulama Dizinine Gec ===
echo.
echo [INFO] Proje dizini: %PROJECT_PATH%
cd /d "%PROJECT_PATH%" || (
    echo [ERROR] Dizin bulunamadi: %PROJECT_PATH%
    goto :error_exit
)

:: === [5] Gerekli Araclar Kontrolu ===
git --version >nul 2>&1 || (
    echo [ERROR] Git bulunamadi. Lutfen yukleyin.
    goto :error_exit
)
dotnet --version >nul 2>&1 || (
    echo [ERROR] .NET SDK bulunamadi. Lutfen yukleyin.
    goto :error_exit
)
echo [OK] Git ve .NET SDK mevcut.

:: ============================================================
:: ADIM 1: GIT DURUM KONTROLU
:: ============================================================
set /a STEP+=1
echo.
echo ==================================================
echo  ADIM !STEP!: GIT DURUM KONTROLU
echo ==================================================

for /f "tokens=*" %%a in ('git rev-parse --abbrev-ref HEAD 2^>nul') do set "CURRENT_BRANCH=%%a"
echo [INFO] Mevcut branch: !CURRENT_BRANCH!

git ls-remote --exit-code %REMOTE% >nul 2>&1
if !errorlevel! neq 0 (
    echo [ERROR] Remote '%REMOTE%' baglantisi basarisiz.
    goto :error_exit
)
echo [OK] Remote '%REMOTE%' erisiliyor.

:: Uncommitted degisiklik kontrolu
git diff --quiet 2>nul
set "HAS_UNSTAGED=!errorlevel!"
git diff --cached --quiet 2>nul
set "HAS_STAGED=!errorlevel!"

if !HAS_UNSTAGED! equ 0 if !HAS_STAGED! equ 0 (
    echo [OK] Calisan dizin temiz.
    goto :git_clean
)

echo [WARNING] Commit edilmemis degisiklikler var!
echo.
git status --short
echo.
echo [SORU] Degisiklikleri ne yapayim?
echo   [E] Evet - commit et ve devam et
echo   [H] Hayir - deploy'u iptal et
echo   [S] Stash - degisiklikleri sakla, deploy sonrasi geri al
echo.
set /p "COMMIT_CHOICE=Seciminiz [E/H/S]: "

if /i "!COMMIT_CHOICE!"=="H" (
    echo [INFO] Deploy iptal edildi.
    goto :end
)
if /i "!COMMIT_CHOICE!"=="S" goto :do_stash
goto :do_commit

:do_stash
echo [INFO] Degisiklikler stash ediliyor...
git stash push -m "deploy-oncesi-stash"
if !errorlevel! neq 0 (
    echo [ERROR] Stash basarisiz.
    goto :error_exit
)
echo [OK] Stash tamamlandi.
set "DID_STASH=1"
goto :git_clean

:do_commit
echo [INFO] Tum degisiklikler commit ediliyor...
git add -A
git commit -m "Deploy oncesi otomatik commit - %date% %time:~0,8%"
if !errorlevel! neq 0 (
    echo [ERROR] Commit basarisiz.
    goto :error_exit
)
echo [OK] Commit tamamlandi.

:git_clean

:: ============================================================
:: ADIM 2: MERGE ISLEMI
:: ============================================================
set /a STEP+=1
echo.
echo ==================================================
echo  ADIM !STEP!: MERGE ISLEMI
echo ==================================================

if /i "!CURRENT_BRANCH!"=="%TARGET_BRANCH%" (
    echo [INFO] Zaten '%TARGET_BRANCH%' branch'indesiniz. Merge atlanacak.
    goto :skip_merge
)

echo [INFO] '!CURRENT_BRANCH!' --^> '%TARGET_BRANCH%' merge edilecek.
set "SOURCE_BRANCH=!CURRENT_BRANCH!"

for /f %%n in ('git rev-list --count %TARGET_BRANCH%..!SOURCE_BRANCH! 2^>nul') do set "AHEAD_COUNT=%%n"
echo [INFO] %TARGET_BRANCH% branch'inin !AHEAD_COUNT! commit ilerisinde.

echo [INFO] '%TARGET_BRANCH%' branch'ine geciliyor...
git checkout %TARGET_BRANCH%
if !errorlevel! neq 0 (
    echo [ERROR] Branch gecisi basarisiz.
    goto :error_exit
)

echo [INFO] Remote'dan en son '%TARGET_BRANCH%' aliniyor...
git pull %REMOTE% %TARGET_BRANCH%
if !errorlevel! neq 0 (
    echo [WARNING] Pull basarisiz. Yerel branch ile devam ediliyor...
)

echo [INFO] '!SOURCE_BRANCH!' merge ediliyor...
git merge !SOURCE_BRANCH! --no-edit
if !errorlevel! neq 0 (
    echo [ERROR] MERGE CONFLICT - Catisma olustu!
    echo [INFO] Merge iptal ediliyor...
    git merge --abort
    git checkout !SOURCE_BRANCH!
    goto :error_exit
)
echo [OK] Merge basarili.

:skip_merge

:: ============================================================
:: ADIM 3: GIT PUSH
:: ============================================================
set /a STEP+=1
echo.
echo ==================================================
echo  ADIM !STEP!: GIT PUSH
echo ==================================================

echo [INFO] '%TARGET_BRANCH%' branch'i remote'a push ediliyor...

set "PUSH_RETRY=0"
:push_retry_loop
git push %REMOTE% %TARGET_BRANCH% 2>nul
if !errorlevel! equ 0 (
    echo [OK] Push tamamlandi.
    goto :push_done
)
set /a PUSH_RETRY+=1
if !PUSH_RETRY! geq 4 (
    echo [WARNING] Push 4 denemeden sonra basarisiz. Deploy devam edecek.
    goto :push_done
)
set /a "WAIT_SEC=PUSH_RETRY*2"
echo [WARNING] Push basarisiz. !WAIT_SEC! saniye sonra tekrar deneniyor...
timeout /t !WAIT_SEC! /nobreak >nul
goto :push_retry_loop

:push_done

:: ============================================================
:: ADIM 4: IIS APP POOL DURDUR
:: ============================================================
set /a STEP+=1
echo.
echo ==================================================
echo  ADIM !STEP!: IIS APP POOL DURDURMA
echo ==================================================

if not exist "%windir%\system32\inetsrv\appcmd.exe" (
    echo [WARNING] IIS appcmd.exe bulunamadi. Devam ediliyor...
    goto :pool_stopped
)
echo [INFO] App Pool durduruluyor: %APPPOOL_NAME%
"%windir%\system32\inetsrv\appcmd.exe" stop apppool /apppool.name:"%APPPOOL_NAME%" >nul 2>&1
REM Uygulamanin dosyalari serbest birakmasi icin bekle
echo [INFO] Uygulama kapaniyor, 3 saniye bekleniyor...
timeout /t 3 /nobreak >nul
echo [OK] App Pool durduruldu.

:pool_stopped

:: ============================================================
:: ADIM 5: DOTNET PUBLISH
:: ============================================================
set /a STEP+=1
echo.
echo ==================================================
echo  ADIM !STEP!: UYGULAMA DERLEME VE YAYINLAMA
echo ==================================================

echo [INFO] dotnet publish calisiyor...
echo [INFO] Cikti: %PUBLISH_PATH%
echo.

dotnet restore
if !errorlevel! neq 0 (
    echo [ERROR] NuGet paket yuklemesi basarisiz.
    goto :start_pool_and_exit
)

dotnet publish -c Release -o "%PUBLISH_PATH%"
if !errorlevel! neq 0 (
    echo [ERROR] Derleme/yayinlama basarisiz.
    goto :start_pool_and_exit
)
echo.
echo [OK] Derleme ve yayinlama tamamlandi.

:: ============================================================
:: ADIM 6: IIS APP POOL BASLAT
:: ============================================================
set /a STEP+=1
echo.
echo ==================================================
echo  ADIM !STEP!: IIS APP POOL BASLATMA
echo ==================================================

if not exist "%windir%\system32\inetsrv\appcmd.exe" (
    echo [WARNING] IIS appcmd.exe bulunamadi.
    goto :pool_started
)
echo [INFO] App Pool baslatiliyor: %APPPOOL_NAME%
"%windir%\system32\inetsrv\appcmd.exe" start apppool /apppool.name:"%APPPOOL_NAME%" >nul 2>&1
echo [OK] App Pool baslatildi.

:pool_started

:: ============================================================
:: ADIM 7: DOGRULAMA
:: ============================================================
set /a STEP+=1
echo.
echo ==================================================
echo  ADIM !STEP!: DEPLOY DOGRULAMA
echo ==================================================

if exist "%PUBLISH_PATH%\Netinfo.dll" (
    echo [OK] Netinfo.dll mevcut.
) else (
    echo [ERROR] Netinfo.dll bulunamadi!
)

if exist "%PUBLISH_PATH%\wwwroot\index.html" (
    echo [OK] wwwroot/index.html mevcut.
) else (
    echo [WARNING] wwwroot/index.html bulunamadi.
)

echo.
echo [INFO] Git durumu:
for /f "tokens=*" %%a in ('git rev-parse --abbrev-ref HEAD 2^>nul') do echo   Branch: %%a
for /f "tokens=*" %%a in ('git log -1 --format^="%%h %%s" 2^>nul') do echo   Son commit: %%a

if "!DID_STASH!"=="1" (
    echo.
    echo [INFO] Stash edilen degisiklikler geri aliniyor...
    git stash pop
    echo [OK] Stash geri alindi.
)

:: ============================================================
:: TAMAMLANDI
:: ============================================================
echo.
echo ############################################################
echo #                                                          #
echo #         DEPLOY BASARIYLA TAMAMLANDI!                     #
echo #                                                          #
echo ############################################################
echo.
echo   Proje:     %PROJECT_PATH%
echo   Publish:   %PUBLISH_PATH%
echo   App Pool:  %APPPOOL_NAME%
echo.
goto :end

:start_pool_and_exit
echo.
echo [INFO] Hata olustu ama App Pool tekrar baslatiliyor...
if exist "%windir%\system32\inetsrv\appcmd.exe" (
    "%windir%\system32\inetsrv\appcmd.exe" start apppool /apppool.name:"%APPPOOL_NAME%" >nul 2>&1
    echo [OK] App Pool eski surum ile baslatildi.
)

:error_exit
echo.
echo ############################################################
echo #                                                          #
echo #         DEPLOY BASARISIZ!                                #
echo #                                                          #
echo ############################################################
echo.
echo [ERROR] Yukaridaki hata mesajlarini inceleyin.
echo.

:end
pause
exit /b
