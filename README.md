# Local Document Assistant

Local document chat app using Open WebUI + Ollama.

## Requirements

Required for normal use:

- Docker Desktop (running)
- Ollama (installed)
- At least one Ollama model pulled (example: `qwen2.5:3b`)

Optional (only for CLI scripts):

- Python 3.10+

## Run

Windows:

```powershell
.\run_app.bat
```

Linux:

```bash
./run_app.sh
```

App URL:

```text
http://localhost:3000
```

Stop:

Windows:

```powershell
.\stop_app.bat
```

Linux:

```bash
./stop_app.sh
```

## First-Time Ollama Setup

Pull a fast model:

```powershell
ollama pull qwen2.5:3b
```

Check models:

```powershell
ollama list
```

## Windows Desktop Shortcut

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\create_windows_desktop_shortcut.ps1
```

Custom icon file (optional): `assets\app.ico`

## Optional Python CLI

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py ingest --docs-dir docs --reset
python main.py chat
```
