# Nettoyage du projet : supprime les fichiers devenus inutiles.
# Par defaut, AFFICHE seulement ce qui serait supprime. Pour supprimer vraiment :  .\cleanup.ps1 -Apply
param([switch]$Apply)
$racine = (Get-Location).Path
$cibles = @()

# 1. Anciens scripts remplaces par ingestion\collect_bronze.py, load_postgres.py, dbt et ml\
foreach ($f in "ingestion\clean.py", "ingestion\collect.py", "ingestion\collect_extra.py",
               "ingestion\collect_understat.py", "ml\demo_doku.py", "restructure.ps1", "arbo.txt") {
  if (Test-Path $f) { $cibles += (Resolve-Path $f).Path }
}

# 2. Archives telechargees a la racine (deja decompressees)
$cibles += (Get-ChildItem -Path . -Filter *.zip -File -ErrorAction SilentlyContinue).FullName

# 3. Caches et sorties regenerables (hors venv)
$cibles += (Get-ChildItem -Path . -Recurse -Directory -Force -ErrorAction SilentlyContinue |
  Where-Object { $_.FullName -notmatch "\\venv\\" -and
                 ($_.Name -in "__pycache__", ".pytest_cache", ".ipynb_checkpoints") }).FullName
foreach ($d in "dbt\target", "dbt\logs") { if (Test-Path $d) { $cibles += (Resolve-Path $d).Path } }

# 4. .gitkeep inutiles dans les dossiers qui contiennent deja autre chose
$cibles += (Get-ChildItem -Path . -Recurse -Filter .gitkeep -File -Force -ErrorAction SilentlyContinue |
  Where-Object { $_.FullName -notmatch "\\venv\\" -and
                 (Get-ChildItem $_.DirectoryName -Force | Where-Object { $_.Name -ne ".gitkeep" }) }).FullName

$cibles = $cibles | Where-Object { $_ } | Sort-Object -Unique
if (-not $cibles) { Write-Host "Rien a nettoyer." -ForegroundColor Green; exit 0 }

foreach ($c in $cibles) {
  Write-Host ($(if ($Apply) { "Suppression : " } else { "A supprimer : " }) + $c.Replace($racine + "\", ""))
  if ($Apply) { Remove-Item -LiteralPath $c -Recurse -Force }
}
if (-not $Apply) { Write-Host "`nAucun fichier supprime. Relance avec -Apply pour supprimer." -ForegroundColor Yellow }

Write-Host "`nA verifier a la main (non supprime) :" -ForegroundColor Cyan
Get-ChildItem -Force | Where-Object { $_.Name -notin "venv", ".git" } |
  ForEach-Object { "  " + $_.Name }
if (Test-Path data) {
  Get-ChildItem data -Directory | ForEach-Object {
    $mo = [math]::Round(((Get-ChildItem $_.FullName -Recurse -File | Measure-Object Length -Sum).Sum / 1MB), 1)
    "  data\$($_.Name) : $mo Mo"
  }
}
