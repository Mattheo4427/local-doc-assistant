@echo off
setlocal EnableDelayedExpansion

cd /d %~dp0

set "CONTAINER_NAME=open-webui-local"
set "IMAGE_NAME=ghcr.io/open-webui/open-webui:main"
set "HOST_PORT=3000"
set "WEBUI_AUTH=False"
set "OLLAMA_BASE_URL=http://host.docker.internal:11434"
set "OLLAMA_HOST_VALUE=0.0.0.0:11434"

where docker >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Docker is required to run Open WebUI.
  echo         Install Docker Desktop and start it, then retry.
  exit /b 1
)

docker info >nul 2>nul
if errorlevel 1 (
  if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" (
    echo [INFO] Docker Desktop engine is not running. Starting Docker Desktop...
    start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
    echo [INFO] Waiting for Docker engine to become ready...
    for /L %%I in (1,1,45) do (
      docker info >nul 2>nul
      if not errorlevel 1 goto :docker_ready
      timeout /t 2 /nobreak >nul
    )
  )

  docker info >nul 2>nul
  if errorlevel 1 (
    echo [ERROR] Docker Desktop engine is not running.
    echo         Open Docker Desktop and wait until it shows "Engine running".
    echo         If prompted, switch to Linux containers.
    exit /b 1
  )
)

:docker_ready

where ollama >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Ollama is not installed or not in PATH.
  echo         Install Ollama and ensure it is running, then retry.
  exit /b 1
)

call :wait_for_ollama
if not errorlevel 1 goto :ollama_ready

echo [INFO] Ollama API is not reachable. Attempting to start Ollama...
if exist "%LocalAppData%\Programs\Ollama\Ollama app.exe" (
  start "" "%LocalAppData%\Programs\Ollama\Ollama app.exe"
)
start "" /min cmd /c "set OLLAMA_HOST=%OLLAMA_HOST_VALUE% && ollama serve"

call :wait_for_ollama
if errorlevel 1 (
  echo [ERROR] Ollama did not become ready on http://localhost:11434.
  echo         Start Ollama manually, then retry.
  exit /b 1
)

:ollama_ready

set "FOUND_CONTAINER="
docker container inspect %CONTAINER_NAME% >nul 2>nul
if not errorlevel 1 set "FOUND_CONTAINER=1"

if defined FOUND_CONTAINER (
  set "CURRENT_URL="
  set "CURRENT_AUTH="
  for /f "usebackq tokens=1,* delims==" %%A in (`docker inspect -f "{{range .Config.Env}}{{println .}}{{end}}" %CONTAINER_NAME%`) do (
    if /I "%%A"=="OLLAMA_BASE_URL" set "CURRENT_URL=%%B"
    if /I "%%A"=="WEBUI_AUTH" set "CURRENT_AUTH=%%B"
  )

  if /I not "!CURRENT_URL!"=="%OLLAMA_BASE_URL%" (
    echo [INFO] Recreating container to apply OLLAMA_BASE_URL.
    docker rm -f %CONTAINER_NAME% >nul 2>nul
    set "FOUND_CONTAINER="
  )

  if /I not "!CURRENT_AUTH!"=="%WEBUI_AUTH%" (
    echo [INFO] Recreating container to disable WebUI auth onboarding.
    docker rm -f %CONTAINER_NAME% >nul 2>nul
    set "FOUND_CONTAINER="
  )
)

if defined FOUND_CONTAINER (
  echo [INFO] Starting existing Open WebUI container...
  docker start %CONTAINER_NAME% >nul
  if errorlevel 1 exit /b 1
) else (
  echo [INFO] Creating Open WebUI container...
  set "CREATED="
  echo [INFO] Trying image: %IMAGE_NAME%
  docker run -d ^
    --name %CONTAINER_NAME% ^
    -p %HOST_PORT%:8080 ^
    --add-host=host.docker.internal:host-gateway ^
    -e OLLAMA_BASE_URL=%OLLAMA_BASE_URL% ^
    -e WEBUI_AUTH=%WEBUI_AUTH% ^
    -v open-webui:/app/backend/data ^
    %IMAGE_NAME% >nul
  if not errorlevel 1 set "CREATED=1"

  if not defined CREATED (
    echo [WARN] Initial GHCR pull/start failed. Retrying after docker logout ghcr.io...
    docker logout ghcr.io >nul 2>nul
    docker run -d ^
      --name %CONTAINER_NAME% ^
      -p %HOST_PORT%:8080 ^
      --add-host=host.docker.internal:host-gateway ^
      -e OLLAMA_BASE_URL=%OLLAMA_BASE_URL% ^
      -e WEBUI_AUTH=%WEBUI_AUTH% ^
      -v open-webui:/app/backend/data ^
      %IMAGE_NAME% >nul
    if not errorlevel 1 set "CREATED=1"
  )

  if not defined CREATED (
    echo [ERROR] Could not pull/start Open WebUI image from GHCR.
    echo         Try manually:
    echo         docker logout ghcr.io
    echo         docker pull ghcr.io/open-webui/open-webui:main
    exit /b 1
  )
)

echo [INFO] Waiting for Open WebUI to become ready...
call :wait_for_webui
if errorlevel 1 (
  echo [ERROR] Open WebUI did not become ready on http://localhost:%HOST_PORT%.
  echo         Check logs with: docker logs --tail 200 %CONTAINER_NAME%
  exit /b 1
)

echo [RUN] Open WebUI is available at: http://localhost:%HOST_PORT%
start "" "http://localhost:%HOST_PORT%"

endlocal
exit /b 0

:wait_for_ollama
for /L %%I in (1,1,30) do (
  powershell -NoProfile -Command "try { Invoke-RestMethod -Uri 'http://localhost:11434/api/tags' -Method Get | Out-Null; exit 0 } catch { exit 1 }" >nul 2>nul
  if not errorlevel 1 exit /b 0
  timeout /t 2 /nobreak >nul
)
exit /b 1

:wait_for_webui
for /L %%I in (1,1,45) do (
  powershell -NoProfile -Command "try { Invoke-RestMethod -Uri 'http://localhost:%HOST_PORT%/api/version' -Method Get | Out-Null; exit 0 } catch { exit 1 }" >nul 2>nul
  if not errorlevel 1 exit /b 0
  timeout /t 2 /nobreak >nul
)
exit /b 1
