@echo off
cd /d "%~dp0"
echo Starting RVQ Artifact Remover...
python -m rvq_remover.app
