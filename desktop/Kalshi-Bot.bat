@echo off
REM ==========================================================================
REM  KALSHI BOT -- double-click to START trading, close this window to STOP.
REM  Windows. First run does a one-time setup; after that it just trades.
REM ==========================================================================
setlocal
set REPO=https://github.com/dgkenn/Codex-playground-.git
set BRANCH=claude/polymarket-bot-live-ready-vw7ut5
set DIR=%USERPROFILE%\kalshi-bot
set KDIR=%USERPROFILE%\.kalshi

echo ==========================================
echo    KALSHI MAKER-BOX BOT
echo ==========================================

REM 1) one-time credentials
if not exist "%KDIR%\key.pem" goto setup
if not exist "%KDIR%\env.bat" goto setup
goto haveCreds
:setup
if not exist "%KDIR%" mkdir "%KDIR%"
echo.
echo FIRST-TIME SETUP (do this once):
echo   1. Put your Kalshi RSA private key here:   %KDIR%\key.pem
echo   2. Create this file:                       %KDIR%\env.bat
echo        set KALSHI_API_KEY_ID=YOUR_KEY_ID
echo        set KALSHI_PRIVATE_KEY_PATH=%KDIR%\key.pem
echo   (optional phone alerts: set TELEGRAM_BOT_TOKEN=... and set TELEGRAM_CHAT_ID=...)
echo.
explorer "%KDIR%"
echo Then double-click this file again.
pause
exit /b 1
:haveCreds

REM 2) get / update the code
echo Updating bot code...
if exist "%DIR%\.git" (
  git -C "%DIR%" fetch -q origin %BRANCH%
  git -C "%DIR%" checkout -q %BRANCH%
  git -C "%DIR%" reset -q --hard origin/%BRANCH%
) else (
  git clone -q -b %BRANCH% %REPO% "%DIR%" || ( echo git clone failed -- is git installed? & pause & exit /b 1 )
)
cd /d "%DIR%"

REM 3) python + deps
where python >nul 2>nul || ( echo Install Python 3 from python.org, then retry. & pause & exit /b 1 )
python -m pip install --quiet --user numpy scipy requests cryptography websockets

REM 4) creds + preflight
call "%KDIR%\env.bat"
echo Running safety preflight...
python kalshi_preflight.py --asset btc | findstr /C:"VERDICT: GO" >nul || ( echo PREFLIGHT NO-GO -- see above. A sticky kill sentinel may need deleting: del "%DIR%\.kalshi_killed_btc15m" & pause & exit /b 1 )

echo.
echo ==========================================
echo    BOT IS LIVE.  CLOSE THIS WINDOW TO STOP.
echo ==========================================
echo.
REM Closing the window terminates python; the bot's atexit/dead-man cancels orders on SIGTERM.
set I_UNDERSTAND_REAL_MONEY=yes
python -u kalshi_trader.py --asset btc --live --size-mode flat --post 1 --max-notional 5 --loss-limit 6 --max-rungs 1 --duration 31536000
pause
