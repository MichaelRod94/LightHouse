<#
.SYNOPSIS
  Regenera la intro: app.json, escena.blend, cuadros/, preview.mp4 y tira.png de cada concepto.

.DESCRIPTION
  Funciona desde cualquier carpeta que tenga este script, comun.py y una o más subcarpetas con
  build.py + params.json (o build.py al lado del script). La raíz del repo se busca hacia arriba
  (la carpeta que contiene lighthouse\__init__.py) para leer nombre, versión y looks de la app.

.EXAMPLE
  .\generar.ps1                          # todos los conceptos de esta carpeta
  .\generar.ps1 -Concepto C-primer-golpe
  .\generar.ps1 -SoloEscena              # solo reconstruye escena.blend, sin renderizar
  .\generar.ps1 -ReusarCapas             # C: recompone niveles y preview sin volver a renderizar los pases EXR

  Blender se busca en $env:BLENDER_PATH, en el PATH o en "C:\Program Files\Blender Foundation\Blender *".
#>
param(
    [string[]]$Concepto,
    [switch]$SoloEscena,
    [switch]$ReusarCapas
)
$ErrorActionPreference = "Stop"
$aqui = Split-Path -Parent $MyInvocation.MyCommand.Path

$raiz = $aqui
while ($raiz -and -not (Test-Path (Join-Path $raiz "lighthouse\__init__.py"))) { $raiz = Split-Path -Parent $raiz }
if (-not $raiz) { throw "No encuentro la raíz del repo (carpeta con lighthouse\__init__.py) por encima de $aqui" }

$blender = $env:BLENDER_PATH
if (-not $blender) { $c = Get-Command blender -ErrorAction SilentlyContinue; if ($c) { $blender = $c.Source } }
if (-not $blender) {
    $blender = Get-ChildItem "C:\Program Files\Blender Foundation\Blender *\blender.exe" -ErrorAction SilentlyContinue |
        Sort-Object { [version]($_.Directory.Name -replace '[^\d.]', '') } | Select-Object -Last 1 -ExpandProperty FullName
}
if (-not $blender -or -not (Test-Path $blender)) { throw "No encuentro Blender. Define `$env:BLENDER_PATH." }

# app.json (junto a este script): nombre, versión, autor y colores de los looks 2, 3 y 4, leídos de la app
$appJson = Join-Path $aqui "app.json"
Push-Location $raiz
try {
    python -c "import json, sys, lighthouse, lighthouse.scene as s; open(sys.argv[1], 'w', encoding='utf-8').write(json.dumps({'app': 'LightHouse', 'version': lighthouse.VERSION, 'autor': lighthouse.__author__, 'looks': {k: list(s.LOOKS[k][2]) for k in ('2', '3', '4')}}, ensure_ascii=False, indent=2) + '\n')" $appJson
    if ($LASTEXITCODE -ne 0) { throw "No se pudo generar app.json" }
} finally { Pop-Location }

if (-not $Concepto) {
    $Concepto = @(Get-ChildItem $aqui -Directory | Where-Object { Test-Path (Join-Path $_.FullName "build.py") } | ForEach-Object Name)
    if (-not $Concepto -and (Test-Path (Join-Path $aqui "build.py"))) { $Concepto = @(".") }
}
foreach ($c in $Concepto) {
    $build = Join-Path (Join-Path $aqui $c) "build.py"
    $extra = @()
    if (-not $SoloEscena) { $extra += "--render" }
    if ($ReusarCapas) { $extra += "--reusar-capas" }
    Write-Host "== $c" -ForegroundColor Cyan
    # stdout filtrado a las líneas [intro]; los errores de Python salen por stderr tal cual
    $t = Measure-Command { & $blender --background --factory-startup --python-exit-code 1 --python $build -- @extra | Where-Object { $_ -match '^\[intro\]|Error' } | ForEach-Object { Write-Host $_ } }
    if ($LASTEXITCODE -ne 0) { throw "Blender falló en $c (código $LASTEXITCODE)" }
    Write-Host ("   {0:N1} s" -f $t.TotalSeconds)
}
