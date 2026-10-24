@echo off
REM ===========================================================================
REM  Blonde Majestic Salon - start the website locally + public Cloudflare URL
REM  Double-click this file, or run it from VS Code's terminal / cmd:
REM      start-public.bat
REM
REM  What it does:
REM    1) Starts the salon server on port 8000 (skips it if already running)
REM    2) Verifies http://127.0.0.1:8000 answers before going further
REM    3) Starts a Cloudflare quick tunnel and prints your public URL below
REM
REM  Keep this window open while you want the site public. Close it to stop
REM  the tunnel. Re-run this file to bring the site back (quick-tunnel URLs
REM  change every restart - see README section "Public URL" or ask for a
REM  stable named-tunnel setup).
REM ===========================================================================
setlocal
cd /d "%~dp0"
set "CF=%LOCALAPPDATA%\cloudflared\cloudflared.exe"

REM --- 1/2: local server on port 8000 -------------------------------------
netstat -ano | findstr "LISTENING" | findstr /c:":8000 " >nul
if errorlevel 1 (
    echo [1/2] Starting salon server on http://localhost:8000 ...
    where uv >nul 2>nul
    if errorlevel 1 (
        start "Salon server :8000" cmd /k "start.bat"
    ) else (
        start "Salon server :8000" cmd /k "uv run --no-project python server.py"
    )
) else (
    echo [1/2] Salon server already running on port 8000.
)

REM wait until the server answers (max ~20 seconds)
set /a _t=0
:wait_local
curl -s -o nul --max-time 2 http://127.0.0.1:8000/ && goto local_ok
set /a _t+=1
if %_t% lss 20 (timeout /t 1 /nobreak >nul & goto wait_local)
echo.
echo      ERROR: the server is not answering on http://127.0.0.1:8000
echo      Fix the server window above first, then run start-public.bat again.
pause
exit /b 1
:local_ok
echo      OK - local website responds on http://localhost:8000

REM --- 2/2: Cloudflare quick tunnel ---------------------------------------
if not exist "%CF%" (
    echo.
    echo      cloudflared is not installed. Install it once with:
    echo      curl -L -o "%LOCALAPPDATA%\cloudflared\cloudflared.exe" https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe
    pause
    exit /b 1
)
echo [2/2] Starting Cloudflare tunnel...
echo.
echo      Your public website address is the https://.....trycloudflare.com
echo      line printed below. Copy it into a browser to verify.
echo.
"%CF%" tunnel --url http://127.0.0.1:8000 --no-autoupdate
echo.
echo Tunnel stopped. Run start-public.bat again to get a fresh public URL.
pause
