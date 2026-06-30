@echo off
setlocal
cd /d "%~dp0"

echo.
echo Subiendo publicaciones programadas a GitHub...
echo.

git --version >nul 2>&1
if errorlevel 1 (
  echo ERROR: Git no esta disponible en esta PC.
  pause
  exit /b 1
)

if not exist "calendario_publicaciones.csv" (
  echo ERROR: No se encontro calendario_publicaciones.csv.
  pause
  exit /b 1
)

echo Sincronizando cambios recientes de GitHub...
git pull --rebase --autostash origin master
if errorlevel 1 (
  echo ERROR: No se pudo sincronizar con GitHub antes de preparar cambios.
  echo Si subiste medios desde la web, revisa el mensaje anterior.
  pause
  exit /b 1
)

git add calendario_publicaciones.csv

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $ext=@('.jpg','.jpeg','.png','.webp','.gif','.mp4','.mov','.m4v'); Import-Csv -Path 'calendario_publicaciones.csv' | ForEach-Object { $asset=($_.imagen_archivo + '').Trim(); if ($asset -and $asset -notmatch '^https?://') { $name=Split-Path -Leaf $asset; $path=Join-Path 'posts_programados' $name; if ((Test-Path -LiteralPath $path) -and ($ext -contains ([IO.Path]::GetExtension($name).ToLowerInvariant()))) { git add -- $path } } }"
if errorlevel 1 (
  echo ERROR: No se pudieron preparar los archivos de posts_programados.
  pause
  exit /b 1
)

git diff --cached --quiet
if not errorlevel 1 (
  echo No hay cambios nuevos para subir.
  echo.
  git status --short
  pause
  exit /b 0
)

git commit -m "Actualizar publicaciones programadas"
if errorlevel 1 (
  echo ERROR: No se pudo crear el commit.
  pause
  exit /b 1
)

git pull --rebase --autostash origin master
if errorlevel 1 (
  echo ERROR: No se pudo sincronizar con GitHub. Revisa el mensaje anterior.
  pause
  exit /b 1
)

git push origin master
if errorlevel 1 (
  echo ERROR: No se pudo subir a GitHub. Revisa el mensaje anterior.
  pause
  exit /b 1
)

echo.
echo Listo: publicaciones subidas a GitHub.
pause

