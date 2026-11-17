@echo off
rem Startet Ghidra headless mit eigenem Einstellungsordner.
rem Grund: Die Claude-Desktop-App virtualisiert %APPDATA%; Ghidras OSGi-Framework
rem (Felix) bricht dann mit "The data file must be inside the data dir" ab.
rem Aufruf: tools\ghidra-headless.bat <Projektordner> <Projektname> [weitere analyzeHeadless-Argumente]
setlocal
if not defined GHIDRA_INSTALL_DIR set "GHIDRA_INSTALL_DIR=C:\tools\ghidra_12.2_PUBLIC"
if not defined JAVA_HOME set "JAVA_HOME=C:\Program Files\Java\jdk-25"
set "APPDATA=C:\tools\ghidra-home\Roaming"
set "LOCALAPPDATA=C:\tools\ghidra-home\Local"
if not exist "%APPDATA%" mkdir "%APPDATA%"
if not exist "%LOCALAPPDATA%" mkdir "%LOCALAPPDATA%"
call "%GHIDRA_INSTALL_DIR%\support\analyzeHeadless.bat" %* < NUL
exit /b %ERRORLEVEL%
