@echo off
set "MSYSTEM=MINGW64"
set "MSYS2_USR_BIN=%~dp0ProxSpace\ProxSpace\msys2\usr\bin"
set "MSYS2_MINGW_BIN=%~dp0ProxSpace\ProxSpace\msys2\mingw64\bin"
set "PATH=%MSYS2_MINGW_BIN%;%MSYS2_USR_BIN%;%PATH%"

cd /d "%~dp0ProxSpace\ProxSpace\pm3\proxmark3"
bash pm3 %*
