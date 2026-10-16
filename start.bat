@echo off
chcp 65001 >nul
cd /d "%~dp0"

if "%1"=="" goto :help
if "%1"=="backend" goto :backend
if "%1"=="frontend" goto :frontend
if "%1"=="docker" goto :docker
if "%1"=="docker-down" goto :docker_down
if "%1"=="test" goto :test
if "%1"=="health" goto :health
if "%1"=="all" goto :all
goto :help

:help
echo Usage: start.bat [backend / frontend / docker / docker-down / test / health / all]
echo.
echo Commands:
echo   backend  - Start FastAPI backend (http://127.0.0.1:8000)
echo   frontend - Start Vue frontend (http://localhost:5173)
echo   docker   - Start Vue + API with Docker Compose (http://127.0.0.1:8080)
echo   docker-down - Stop Docker Compose services
echo   test     - Run pytest
echo   health   - Check backend health
echo   all      - Show startup instructions
goto :eof

:backend
echo Starting FastAPI backend at http://127.0.0.1:8000
call conda activate multi_agent_v1
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
goto :eof

:frontend
echo Starting Vue frontend at http://localhost:5173
cd /d "%~dp0frontend-vue"
if not exist node_modules (
  echo Frontend dependencies are missing. Run: npm ci
  goto :eof
)
npm run dev
goto :eof

:docker
echo Starting Vue + API with Docker Compose at http://127.0.0.1:8080
docker compose up --build
goto :eof

:docker_down
echo Stopping Docker Compose services...
docker compose down
goto :eof

:test
echo Running tests...
call conda activate multi_agent_v1
pytest tests\ -v
goto :eof

:health
curl -s http://127.0.0.1:8000/health 2>nul || echo Backend not running
goto :eof

:all
echo Local development mode:
echo 1. Run in window 1: start.bat backend
echo 2. Run in window 2: start.bat frontend
echo 3. Open http://127.0.0.1:5173
echo.
echo Docker mode:
echo 1. Run: start.bat docker
echo 2. Open http://127.0.0.1:8080
goto :eof
