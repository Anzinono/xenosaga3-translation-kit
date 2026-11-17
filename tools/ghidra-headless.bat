@echo off
rem Runs Ghidra headless with its own settings folder.
rem Reason: the Claude desktop app virtualises %APPDATA%; Ghidra's OSGi framework
rem (Felix) then aborts with "The data file must be inside the data dir".
rem Usage: tools\ghidra-headless.bat <project folder> <project name> [further analyzeHeadless arguments]
setlocal
if not defined GHIDRA_INSTALL_DIR set "GHIDRA_INSTALL_DIR=C:\tools\ghidra_12.2_PUBLIC"
if not defined JAVA_HOME set "JAVA_HOME=C:\Program Files\Java\jdk-25"
set "APPDATA=C:\tools\ghidra-home\Roaming"
set "LOCALAPPDATA=C:\tools\ghidra-home\Local"
if not exist "%APPDATA%" mkdir "%APPDATA%"
if not exist "%LOCALAPPDATA%" mkdir "%LOCALAPPDATA%"
call "%GHIDRA_INSTALL_DIR%\support\analyzeHeadless.bat" %* < NUL
exit /b %ERRORLEVEL%
