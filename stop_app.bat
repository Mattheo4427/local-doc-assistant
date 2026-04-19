@echo off
setlocal

docker stop open-webui-local >nul 2>nul
echo Open WebUI stopped (if it was running).

endlocal
