@echo off
rem Double-clique ce fichier pour ouvrir l'interface YouTube -> MP3 (Windows)
title YouTube en MP3
cd /d "%~dp0"
set "PATH=%PATH%;%LOCALAPPDATA%\Microsoft\WinGet\Links"

rem --- Trouver Python ---
set "PY="
py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY python --version >nul 2>&1 && set "PY=python"

rem --- Verifier les outils ---
set "MANQUE="
if not defined PY set "MANQUE=1"
where yt-dlp >nul 2>&1 || set "MANQUE=1"
where ffmpeg >nul 2>&1 || set "MANQUE=1"
if not defined MANQUE goto :raccourci

echo Premiere utilisation : installation des outils necessaires (quelques minutes)...
echo.
where winget >nul 2>&1 || goto :sanswinget
if not defined PY winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements --override "/quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1"
where yt-dlp >nul 2>&1 || winget install -e --id yt-dlp.yt-dlp --accept-source-agreements --accept-package-agreements
where ffmpeg >nul 2>&1 || winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
echo.
echo Installation terminee. Ferme cette fenetre et relance "YouTube en MP3".
pause
exit /b

:sanswinget
echo Il manque "winget" (le programme "App Installer" de Microsoft).
echo Installe "App Installer" depuis le Microsoft Store qui va s'ouvrir, puis relance ce fichier.
start "" "ms-windows-store://pdp/?ProductId=9NBLGGH4NBDZ"
pause
exit /b

:raccourci
rem --- Creer une fois un raccourci sur le Bureau, avec l'icone ---
if exist ".raccourci_cree" goto :lancer
powershell -NoProfile -ExecutionPolicy Bypass -Command "$d=[Environment]::GetFolderPath('Desktop'); $s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d 'YouTube en MP3.lnk')); $s.TargetPath='%~dp0YouTube en MP3.bat'; $s.WorkingDirectory='%~dp0'; $s.IconLocation='%~dp0icone.ico'; $s.Save()" >nul 2>&1 && echo ok> ".raccourci_cree"

:lancer
%PY% yt2mp3_app.py
echo.
echo L'appli s'est arretee.
pause
