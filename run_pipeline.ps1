# Enchaine tout le pipeline : bronze -> PostgreSQL (raw) -> rapprochements -> dbt -> export.
# Prerequis : docker compose up -d, et le bronze deja rempli (bronze_load.py / collect_bronze.py).
# Lancer depuis la racine du projet :  .\run_pipeline.ps1
$py  = ".\venv\Scripts\python.exe"
$dbt = (Resolve-Path ".\venv\Scripts\dbt.exe").Path

function Etape($titre, $commande) {
  Write-Host "`n=== $titre ===" -ForegroundColor Cyan
  & $commande[0] $commande[1..($commande.Length - 1)]
  if ($LASTEXITCODE -ne 0) { Write-Host "Echec : $titre" -ForegroundColor Red; exit 1 }
}

Etape "1. Chargement du bronze dans PostgreSQL (schema raw)" @($py, "ingestion\load_postgres.py")
Etape "2. Rapprochement des identifiants (schema mapping)"   @($py, "ingestion\matching.py")
Push-Location dbt
Etape "3. dbt run (silver et gold)"                          @($dbt, "run",  "--profiles-dir", ".")
Etape "4. dbt test (qualite et volumes)"                     @($dbt, "test", "--profiles-dir", ".")
Pop-Location
Etape "5. Export pour le dashboard"                          @($py, "ml\export_mart.py")
Etape "6. Export de la base d'entrainement du modele"       @($py, "ml\export_ml_base.py")
Etape "7. Modele de valeur (MLflow, predictions, sous-cotes)" @($py, "ml\train_value.py", "--pg")
Write-Host "`nPipeline termine." -ForegroundColor Green
