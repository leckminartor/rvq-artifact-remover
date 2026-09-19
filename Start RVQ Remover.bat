@echo off
cd /d "%~dp0"
echo Starting RVQ Artifact Remover...
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m rvq_remover.app
) else (
    echo No .venv found - installing dependencies...
    python -m venv .venv
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -e ".[app]"
    ".venv\Scripts\python.exe" -m rvq_remover.app
)
