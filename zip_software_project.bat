@echo off
setlocal

set "SOURCE=D:\projects\cmsc-190\dev"
set "DEST_DIR=D:\projects\cmsc-190"
set "ZIP_NAME=dev.zip"
set "ZIP_PATH=%DEST_DIR%\%ZIP_NAME%"

if not exist "%SOURCE%" exit /b 1
if not exist "%DEST_DIR%" mkdir "%DEST_DIR%"
if exist "%ZIP_PATH%" del /f /q "%ZIP_PATH%"

tar.exe ^
    --exclude="outputs_main" ^
    --exclude="outputs_ref_comparison" ^
    --exclude="__pycache__" ^
    -a -c -f "%ZIP_PATH%" ^
    -C "D:\projects\cmsc-190" "dev"

exit /b