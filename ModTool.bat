@echo off
chcp 65001 >nul 2>&1
title Catspeak Mod Tool
cd /d "%~dp0"

:menu
cls
echo.
echo   ============================================================
echo     Catspeak Mod Validation Tool v2.0
echo   ============================================================
echo.
echo     [1] Check all mods (STONKS-9800 rules)
echo     [2] Check all mods (generic Catspeak only)
echo     [3] Check a single mod file
echo     [4] Check a single mod file (generic only)
echo     [5] Create new mod from template
echo     [6] Create new advanced mod from template
echo     [7] Scan and list all mods
echo     [8] Export config for another game
echo     [9] Check with custom game config
echo     [0] Exit
echo.
set /p choice="   Choice: "

if "%choice%"=="1" goto check_mods
if "%choice%"=="2" goto check_mods_generic
if "%choice%"=="3" goto check_single
if "%choice%"=="4" goto check_single_generic
if "%choice%"=="5" goto init_basic
if "%choice%"=="6" goto init_advanced
if "%choice%"=="7" goto scan_mods
if "%choice%"=="8" goto export_config
if "%choice%"=="9" goto check_with_config
if "%choice%"=="0" goto exit
goto menu

:check_mods
cls
echo   Checking all mods (STONKS-9800 rules)...
echo.
python "%~dp0mod_tool.py" check-all mods
echo.
pause
goto menu

:check_mods_generic
cls
echo   Checking all mods (generic Catspeak only)...
echo.
python "%~dp0mod_tool.py" --generic check-all mods
echo.
pause
goto menu

:check_single
cls
set /p filepath="   Path to .meow file: "
if "%filepath%"=="" goto menu
echo.
echo   Checking: %filepath%
echo.
python "%~dp0mod_tool.py" check "%filepath%" --verbose
echo.
pause
goto menu

:check_single_generic
cls
set /p filepath="   Path to .meow file: "
if "%filepath%"=="" goto menu
echo.
echo   Checking (generic): %filepath%
echo.
python "%~dp0mod_tool.py" --generic check "%filepath%" --verbose
echo.
pause
goto menu

:init_basic
cls
set /p modname="   Mod name: "
if "%modname%"=="" goto menu
echo.
python "%~dp0mod_tool.py" init "%modname%"
echo.
pause
goto menu

:init_advanced
cls
set /p modname="   Mod name: "
if "%modname%"=="" goto menu
set /p author="   Author (optional): "
set author_arg=
if not "%author%"=="" set author_arg=--author "%author%"
echo.
python "%~dp0mod_tool.py" init "%modname%" --advanced %author_arg%
echo.
pause
goto menu

:scan_mods
cls
echo   Scanning mods in mods/ ...
echo.
python "%~dp0mod_tool.py" scan mods
echo.
pause
goto menu

:export_config
cls
set /p gamename="   Game name: "
if "%gamename%"=="" goto menu
echo.
python "%~dp0mod_tool.py" --export-config "%gamename%"
echo.
pause
goto menu

:check_with_config
cls
set /p configfile="   Path to game config JSON: "
if "%configfile%"=="" goto menu
set /p target="   Path to .meow file or directory: "
if "%target%"=="" goto menu
echo.
python "%~dp0mod_tool.py" --config "%configfile%" check "%target%" --verbose
echo.
pause
goto menu

:exit
exit /b 0
