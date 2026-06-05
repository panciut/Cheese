# Crea venv e installa dipendenze per le metriche di valutazione.
# Esegui dalla root del progetto: .\eval_metrics\setup.ps1

$ErrorActionPreference = "Stop"
$venvDir = "eval_metrics\.venv"

Write-Host "Creazione venv in $venvDir ..."
python -m venv $venvDir

Write-Host "Attivazione venv ..."
& "$venvDir\Scripts\Activate.ps1"

Write-Host "Aggiornamento pip ..."
python -m pip install --upgrade pip --quiet

Write-Host "Installazione dipendenze ..."
pip install -r eval_metrics\requirements.txt

Write-Host ""
Write-Host "Setup completato."
Write-Host "Per attivare il venv in futuro:"
Write-Host "  .\eval_metrics\.venv\Scripts\Activate.ps1"
Write-Host ""
Write-Host "Poi usa:"
Write-Host "  python eval_metrics\compute_metrics.py predictions_m1.csv predictions_m3.csv ..."
