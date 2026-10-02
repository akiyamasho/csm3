@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem Canonical complete build. Pass a source ROM path or keep ../csm3.gba here.
rem The source must be the unmodified Japanese ROM with the documented SHA-1.
set "PATCH_DIR=%~dp0"
set "SOURCE_ROM=%~1"
if "%SOURCE_ROM%"=="" set "SOURCE_ROM=%PATCH_DIR%..\csm3.gba"
for %%I in ("%SOURCE_ROM%") do set "SOURCE_ROM=%%~fI"
set "EXPECTED_SHA1=3f5253fcf57e07ce52472bd29a61d16b98a12376"
set "ACTUAL_SHA1="
set OMP_NUM_THREADS=1
set OPENBLAS_NUM_THREADS=1
set MKL_NUM_THREADS=1
set NUMEXPR_NUM_THREADS=1
pushd "%PATCH_DIR%" || exit /b 2

if not exist "%SOURCE_ROM%" (
  echo ERROR: Source ROM not found: %SOURCE_ROM%
  goto :abort
)
if exist "swordcraft3.gba" (
  echo ERROR: Refusing to overwrite swordcraft3.gba
  goto :abort
)
if exist "swordcraft3-test.gba" (
  echo ERROR: Refusing to overwrite swordcraft3-test.gba
  goto :abort
)
where certutil >nul 2>nul || (echo ERROR: certutil is required to verify the source ROM SHA-1 & goto :abort)
for /f "tokens=*" %%H in ('certutil -hashfile "%SOURCE_ROM%" SHA1 ^| findstr /r /i "^[0-9a-f][0-9a-f ]*$"') do if not defined ACTUAL_SHA1 set "ACTUAL_SHA1=%%H"
set "ACTUAL_SHA1=!ACTUAL_SHA1: =!"
if /I not "%ACTUAL_SHA1%"=="%EXPECTED_SHA1%" (
  echo ERROR: Source ROM SHA-1 is "%ACTUAL_SHA1%"; expected %EXPECTED_SHA1%
  goto :abort
)
copy "%SOURCE_ROM%" swordcraft3.gba >nul || goto :fail

python generate_build_manifest.py --check || goto :fail
python qa\check_translation_integrity.py --no-diff --rom "%SOURCE_ROM%" || goto :fail
where make >nul 2>nul || (echo ERROR: make is required to build script inserters & goto :fail)
start "" /b /wait /belownormal make -C script_inserter -j1 all || goto :fail
where armips >nul 2>nul || (echo ERROR: armips is required on PATH & goto :fail)
start "" /b /wait /belownormal armips swordcraft3.asm || goto :fail
if not exist "swordcraft3-test.gba" (
  echo ERROR: armips did not create swordcraft3-test.gba
  goto :fail
)

start "" /b /wait /belownormal script_inserter\swordcraft3-menu --quiet swordcraft3-test.gba system_messages\magic.txt system_messages\weapons.txt system_messages\link.txt system_messages\effects.txt system_messages\special_attacks.txt system_messages\dictionary.txt system_messages\items.txt system_messages\menu.txt system_messages\bonus.txt system_messages\menu3.txt || goto :fail

set "FAILED=0"
for /f "usebackq tokens=1,2" %%A in ("build_scripts.manifest") do (
  start "" /b /wait /belownormal script_inserter\swordcraft3c --quiet --dry-run swordcraft3-test.gba "%%A" "%%B"
  if errorlevel 1 (
    echo Preflight failure at %%B (%%A)
    set /a FAILED+=1
  )
)
if not "!FAILED!"=="0" (
  echo ERROR: Preflight found !FAILED! script allocation failure(s); no script payloads were inserted.
  goto :fail
)

for /f "usebackq tokens=1,2" %%A in ("build_scripts.manifest") do (
  start "" /b /wait /belownormal script_inserter\swordcraft3c swordcraft3-test.gba "%%A" "%%B" --quiet || goto :fail
)

del swordcraft3.gba
echo Build complete: swordcraft3-test.gba
popd
endlocal
exit /b 0

:fail
del swordcraft3.gba 2>nul
del swordcraft3-test.gba 2>nul
popd
exit /b 1

:abort
popd
exit /b 2
