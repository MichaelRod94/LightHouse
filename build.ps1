# Construye dist\LightHouse (onedir) y dist\LightHouse-<VERSION>-win64.zip
param([string]$Python = "python")
$ErrorActionPreference = "Continue"  # stderr nativo (avisos de pip, logs de PyInstaller) no debe abortar; se revisa $LASTEXITCODE
Set-Location $PSScriptRoot
function Check($what) { if ($LASTEXITCODE -ne 0) { throw "$what fallo (codigo $LASTEXITCODE)" } }

& $Python --version
if (-not (Test-Path .venv-build\Scripts\python.exe)) { & $Python -m venv .venv-build; Check "venv" }
$vpy = ".\.venv-build\Scripts\python.exe"
& $vpy -m pip install -q --disable-pip-version-check -r requirements.txt -r requirements-build.txt; Check "pip install"

& $vpy -m lighthouse --test; Check "self-check"

& $vpy -m PyInstaller lighthouse.spec --noconfirm --clean; Check "PyInstaller"

$exe = ".\dist\LightHouse\LightHouse.exe"
$p = Start-Process $exe -ArgumentList "--test" -Wait -PassThru
if ($p.ExitCode -ne 0) { throw "el exe fallo --test (codigo $($p.ExitCode)); ver %LOCALAPPDATA%\LightHouse\logs" }

Copy-Item LEEME.txt dist\LightHouse\ -Force
$ver = (Select-String -Path lighthouse\__init__.py -Pattern 'VERSION\s*=\s*"([^"]+)"').Matches[0].Groups[1].Value
$zip = "dist\LightHouse-$ver-win64.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path dist\LightHouse -DestinationPath $zip
"dist\LightHouse: {0:N1} MB" -f ((Get-ChildItem dist\LightHouse -Recurse | Measure-Object Length -Sum).Sum / 1MB)
"{0}: {1:N1} MB" -f $zip, ((Get-Item $zip).Length / 1MB)

