@echo off
rem AgentTeam Windows launcher. ASCII only.
setlocal EnableExtensions
chcp 65001 >nul 2>&1
cd /d "%~dp0"

set "PY=python"
set "PORT=8765"
set "INTERACTIVE=0"
set "RC=0"

python -c "import sys" >nul 2>&1
if not errorlevel 1 goto :py_ready
set "PY=py -3"
py -3 -c "import sys" >nul 2>&1
if not errorlevel 1 goto :py_ready
echo [ERROR] Python 3.10+ was not found.
echo Install Python 3.10+ and enable "Add Python to PATH".
exit /b 1

:py_ready
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.10+ is required.
    exit /b 1
)

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

if not "%~2"=="" set "PORT=%~2"

if "%~1"=="" goto :menu
if /i "%~1"=="project" goto :project
if /i "%~1"=="check" goto :check
if /i "%~1"=="sim" goto :sim
if /i "%~1"=="w3" goto :w3
if /i "%~1"=="dashboard" goto :dashboard
if /i "%~1"=="test" goto :test
if /i "%~1"=="fi" goto :fi
if /i "%~1"=="caps" goto :caps
if /i "%~1"=="eval" goto :eval
if /i "%~1"=="demo" goto :demo
if /i "%~1"=="real" goto :real
if /i "%~1"=="kb" goto :kb
if /i "%~1"=="setup" goto :setup
if /i "%~1"=="all" goto :all
if /i "%~1"=="help" goto :help
if /i "%~1"=="--help" goto :help
if /i "%~1"=="-h" goto :help
echo [ERROR] Unknown command: %~1
set "RC=2"
goto :finish

:menu
set "INTERACTIVE=1"
echo.
echo ============================================================
echo   AgentTeam Launcher
echo ============================================================
echo   1. Start a project from a design/requirement document
echo   2. Start built-in sample project (offline)
echo   3. Start built-in sample project (real local Qwen)
echo   4. Environment check and selfcheck
echo   5. v4.1 orchestration simulation
echo   6. W3 parallel/serial and dashboard build
echo   7. Start dashboard on http://localhost:%PORT%
echo   8. Unit tests and selfchecks
echo   9. Offline evaluation suite
echo   10. Failure-injection acceptance suite
echo   11. Model capability probe (offline)
echo   0. Exit
echo.
set "CHOICE="
set /p "CHOICE=Select [0-9,10,11]: "
if not defined CHOICE goto :menu
if "%CHOICE%"=="0" goto :done
if "%CHOICE%"=="1" goto :project
if "%CHOICE%"=="2" goto :demo
if "%CHOICE%"=="3" goto :real
if "%CHOICE%"=="4" goto :check
if "%CHOICE%"=="5" goto :sim
if "%CHOICE%"=="6" goto :w3
if "%CHOICE%"=="7" goto :dashboard
if "%CHOICE%"=="8" goto :test
if "%CHOICE%"=="9" goto :eval
if "%CHOICE%"=="10" goto :fi
if "%CHOICE%"=="11" goto :caps
echo Invalid choice.
goto :menu

:project
echo.
echo [project] Start a project from a design or requirement document.
echo [project] Supported files: .md, .yaml, .yml, .txt
echo [project] Tip: drag the file into this window, or type its full path.
echo [project] Example: requirements\examples\csv-export\selected.md
set "DESIGN=%~2"
if defined DESIGN goto :project_design_ready
echo.
echo [project] Requirement files found under requirements\:
dir /b /s requirements\*.md 2>nul
dir /b /s requirements\*.yaml 2>nul
dir /b /s requirements\*.yml 2>nul
:project_prompt
set "DESIGN="
set /p "DESIGN=Design document: "
:project_design_ready
if not defined DESIGN goto :menu
set "DESIGN=%DESIGN:"=%"
if exist "%DESIGN%" goto :project_design_exists
echo [ERROR] File not found: %DESIGN%
set "PROJECT_RETRY="
set /p "PROJECT_RETRY=Try another file? [y/N]: "
if /i "%PROJECT_RETRY%"=="y" goto :project_prompt
goto :menu

:project_design_exists
set "PNAME=%~3"
if defined PNAME goto :project_name_ready
set "PNAME="
set /p "PNAME=Project name (blank = auto): "
:project_name_ready
if not defined PNAME set "PNAME=project-%RANDOM%"
set "PROJECT=projects\%PNAME%"
set "FORCE="
if not exist "%PROJECT%" goto :project_name_ok
echo [WARN] Project directory already exists: %PROJECT%
set "OVERWRITE="
set /p "OVERWRITE=Overwrite existing project files? [y/N]: "
if /i not "%OVERWRITE%"=="y" goto :menu
set "FORCE=--force"

:project_name_ok

set "MODE=%~4"
if defined MODE goto :project_mode_ready
set "MODE="
echo.
echo   1. Offline (stub, fast, no model calls)
echo   2. Real (local Qwen, DeepSeek fallback)
set /p "MODE=Select [1/2] (default 1): "
:project_mode_ready
set "RUNMODE=--offline"
if "%MODE%"=="2" set "RUNMODE=--real"
if /i "%MODE%"=="real" set "RUNMODE=--real"
if /i "%MODE%"=="offline" set "RUNMODE=--offline"

set "ROLES=pm,product,ui,arch,backend,frontend,review,qa,security,ops,kb,retro"
if not "%RUNMODE%"=="--real" goto :project_kb
echo.
echo   1. Core roles: pm,product,arch,backend,frontend
echo   2. All 12 roles (slower and more expensive)
set "ROLECHOICE="
set /p "ROLECHOICE=Select [1/2] (default 1): "
if "%ROLECHOICE%"=="2" goto :project_kb
set "ROLES=pm,product,arch,backend,frontend"

:project_kb
set "KBFLAG="
if exist "data\knowledge.db" set "KBFLAG=--kb"

echo.
echo [project] Design:  %DESIGN%
echo [project] Project: %PROJECT%
echo [project] Mode:    %RUNMODE%
echo [project] Roles:   %ROLES%
echo [project] KB:      %KBFLAG%
echo.
%PY% start_project.py --requirements "%DESIGN%" --project-dir "%PROJECT%" %RUNMODE% --roles %ROLES% %KBFLAG% --tool-profile basic %FORCE%
if errorlevel 1 goto :fail
echo.
echo [project] Completed. Records: %PROJECT%\artifacts
echo [project] Dashboard: start.bat dashboard  (then open projects.html)
goto :done

:check
echo.
echo [check] Environment and model availability...
%PY% -m orchestrator.cli check-env --offline
if errorlevel 1 goto :fail
echo [check] Orchestrator selfcheck...
%PY% -m orchestrator.selfcheck
if errorlevel 1 goto :fail
echo [check] OK
goto :done

:sim
echo.
echo [sim] Running v4.1 orchestration simulation...
%PY% -I sim\dryrun.py
if errorlevel 1 goto :fail
echo [sim] Running protocol selfcheck...
%PY% -I sim\selfcheck.py
if errorlevel 1 goto :fail
echo [sim] Outputs: sim\out\v4
goto :done

:w3
echo.
echo [w3] Running parallel and serial simulations...
%PY% sim\w3.py --mode both
if errorlevel 1 goto :fail
echo [w3] Running W3 selfcheck and dashboard build...
%PY% -I sim\w3_selfcheck.py
if errorlevel 1 goto :fail
echo [w3] Dashboard: dashboard\index.html
goto :done

:dashboard
echo.
echo [dashboard] Starting server at http://localhost:%PORT%
echo [dashboard] Press Ctrl+C to stop.
start "" /b cmd /c "timeout /t 2 >nul & explorer http://localhost:%PORT%"
%PY% dashboard\serve.py --port %PORT%
if errorlevel 1 goto :fail
goto :done

:test
echo.
echo [test] Unit tests...
%PY% -m unittest discover -s tests -v
if errorlevel 1 goto :fail
echo [test] Orchestrator selfcheck...
%PY% -m orchestrator.selfcheck
if errorlevel 1 goto :fail
echo [test] v4.1 protocol selfcheck...
%PY% -I sim\selfcheck.py
if errorlevel 1 goto :fail
echo [test] W3 selfcheck...
%PY% -I sim\w3_selfcheck.py
if errorlevel 1 goto :fail
echo [test] Spec validation...
%PY% -I specs\validate_specs.py
if errorlevel 1 goto :fail
echo [test] Failure-injection acceptance suite...
%PY% eval\failure_injection.py
if errorlevel 1 goto :fail
echo [test] Model capability contract probe...
%PY% -m orchestrator.cli model-capabilities --offline
if errorlevel 1 goto :fail
echo [test] OK
goto :done

:fi
echo.
echo [fi] Deterministic failure-injection acceptance suite...
%PY% eval\failure_injection.py
if errorlevel 1 goto :fail
goto :done

:caps
echo.
echo [caps] Model capability probe (offline contract)...
%PY% -m orchestrator.cli model-capabilities --offline
if errorlevel 1 goto :fail
goto :done

:eval
echo.
echo [eval] Offline evaluation suite. This may take a few minutes.
%PY% eval\run_eval.py --offline
if errorlevel 1 goto :fail
%PY% eval\role_eval.py --offline --full
if errorlevel 1 goto :fail
%PY% eval\prompt_regression.py --offline
if errorlevel 1 goto :fail
%PY% eval\kb_eval.py
if errorlevel 1 goto :fail
echo [eval] Reports: eval\out
goto :done

:demo
echo.
echo [demo] Offline 12-role sample project...
set "PROJECT=projects\example-csv-export-launcher-%RANDOM%"
%PY% start_project.py --requirements requirements\examples\csv-export\selected.md --project-dir "%PROJECT%" --offline
if errorlevel 1 goto :fail
echo [demo] Project: %PROJECT%
echo [demo] Open the dashboard and select this project.
goto :done

:real
echo.
echo [real] This calls local Ollama Qwen and may take several minutes.
echo [real] Ollama must be running and the configured model must be installed.
set "CONFIRM="
set /p "CONFIRM=Continue? [y/N]: "
if /i not "%CONFIRM%"=="y" goto :done
set "PROJECT=projects\example-csv-export-real-launcher-%RANDOM%"
%PY% start_project.py --requirements requirements\examples\csv-export\selected.md --project-dir "%PROJECT%" --real --roles pm,product,arch,backend,frontend --kb --tool-profile basic
if errorlevel 1 goto :fail
echo [real] Project: %PROJECT%
goto :done

:kb
echo.
echo [kb] Building knowledge index. bge-m3 indexing may take a few minutes.
echo [kb] Use "start.bat kb hash" for a fast offline index.
set "KB_BACKEND=auto"
if not "%~2"=="" set "KB_BACKEND=%~2"
%PY% -m orchestrator.cli kb-index --backend %KB_BACKEND%
if errorlevel 1 goto :fail
echo [kb] Index stats...
%PY% -m orchestrator.cli kb-stats
if errorlevel 1 goto :fail
goto :done

:setup
echo.
echo [setup] Creating local config and env files if missing...
if not exist "config\config.yaml" (
    copy /Y "config\config.example.yaml" "config\config.yaml" >nul
    echo [setup] Created config\config.yaml
)
if not exist ".env" (
    copy /Y ".env.example" ".env" >nul
    echo [setup] Created .env
)
echo [setup] Installing runtime and dev dependencies...
%PY% -m pip install --upgrade pip
if errorlevel 1 goto :fail
%PY% -m pip install -r requirements.txt -r requirements-dev.txt
if errorlevel 1 goto :fail
echo [setup] Done. Edit .env and set DEEPSEEK_API_KEY if needed.
goto :done

:all
echo.
echo [all] Running the local validation pipeline...
%PY% -m orchestrator.cli check-env --offline
if errorlevel 1 goto :fail
%PY% -m orchestrator.selfcheck
if errorlevel 1 goto :fail
%PY% -I sim\dryrun.py
if errorlevel 1 goto :fail
%PY% -I sim\selfcheck.py
if errorlevel 1 goto :fail
%PY% sim\w3.py --mode both
if errorlevel 1 goto :fail
%PY% -I sim\w3_selfcheck.py
if errorlevel 1 goto :fail
%PY% dashboard\build.py
if errorlevel 1 goto :fail
echo [all] OK. Dashboard: dashboard\index.html
goto :done

:help
echo.
echo Usage: start.bat [command] [args]
echo.
echo Commands:
echo   project     Start a project from a design/requirement document
echo               Usage: start.bat project [file] [name] [offline^|real]
echo   check       Environment check and orchestrator selfcheck
echo   sim         v4.1 orchestration simulation and selfcheck
echo   w3          W3 parallel/serial, selfcheck and dashboard build
echo   dashboard   Serve dashboard at http://localhost:8765
echo   test        Unit tests, selfchecks, spec validation, failure injection
echo   fi          Failure-injection acceptance suite
echo   caps        Model capability probe (offline contract)
echo   eval        Offline evaluation suite
echo   demo        Offline 12-role sample project
echo   real        Real local Qwen sample project
echo   kb          Build and inspect the knowledge index
echo   setup       Create config/.env and install dependencies
echo   all         Run the local validation pipeline
echo   help        Show this help
echo.
echo   (no command) Interactive menu
echo   Examples:
echo     start.bat project requirements\examples\csv-export\selected.md my-app offline
echo     start.bat project "C:\designs\ledger.md" ledger-app real
echo     start.bat dashboard 9000
goto :done

:fail
echo.
echo [FAILED] The last command returned a non-zero exit code.
set "RC=1"
goto :finish

:done
set "RC=0"
goto :finish

:finish
if "%INTERACTIVE%"=="1" pause
exit /b %RC%
