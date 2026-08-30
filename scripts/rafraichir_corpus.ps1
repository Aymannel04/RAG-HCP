# scripts/rafraichir_corpus.ps1
#
# Tache planifiee nocturne (voir ADR 0004, docs/adr/0004-api-bds-pour-les-indicateurs.md :
# "un script planifie, ex. une fois par jour" -- prevu des le depart mais jamais reellement
# cable a un vrai planificateur avant le 27/08, voir JOURNAL.md) : appelle
# scripts/rafraichir_corpus.py, qui enchaine indexation des publications, indicateurs
# BDS, puis vide le cache NOTION seulement si de vraies nouveautes sont apparues.
#
# Concu pour etre appele par le Planificateur de taches Windows (voir instructions
# d'enregistrement en bas de ce fichier) -- pas fait pour etre lance a la main, sauf pour
# tester ce script lui-meme avant de l'enregistrer.
#
# La resilience par etape (un echec sur l'une n'empeche pas les autres) vit maintenant
# cote Python dans scripts/rafraichir_corpus.py::executer -- ce fichier PowerShell ne
# fait plus qu'orchestrer l'appel et ecrire le log.

$ErrorActionPreference = "Continue"
Set-Location "$PSScriptRoot\.."

$horodatage = Get-Date -Format "yyyy-MM-dd_HH-mm"
$dossierLogs = "logs"
if (-not (Test-Path $dossierLogs)) { New-Item -ItemType Directory -Path $dossierLogs | Out-Null }
$fichierLog = "$dossierLogs\rafraichissement_$horodatage.log"

& ".\venv\Scripts\Activate.ps1"

"=== $(Get-Date) : debut rafraichissement ===" | Out-File -FilePath $fichierLog -Append

python -m scripts.rafraichir_corpus *>> $fichierLog
"--- rafraichir_corpus termine (code sortie $LASTEXITCODE) ---" | Out-File -FilePath $fichierLog -Append

"=== $(Get-Date) : fin rafraichissement ===" | Out-File -FilePath $fichierLog -Append

# --- Enregistrement comme tache planifiee (a executer UNE FOIS, dans un terminal
# PowerShell normal sur ta machine, pas depuis ce fichier) ------------------------
#
#   schtasks /create /tn "RAG_HCP_Rafraichissement_Nocturne" `
#     /tr "powershell.exe -ExecutionPolicy Bypass -File `"C:\Users\Ayman\OneDrive\Desktop\RAG HCP\scripts\rafraichir_corpus.ps1`"" `
#     /sc daily /st 03:00
#
# Verifier ensuite qu'elle existe :  schtasks /query /tn "RAG_HCP_Rafraichissement_Nocturne"
# La lancer manuellement pour tester : schtasks /run /tn "RAG_HCP_Rafraichissement_Nocturne"
# La supprimer si besoin :            schtasks /delete /tn "RAG_HCP_Rafraichissement_Nocturne" /f
#
# Attention : la tache ne s'execute que si le PC est allume a 3h du matin (pas de
# reveil automatique par defaut). Si ce n'est pas le cas, changer /st pour une heure
# ou le PC est habituellement allume, ou ajouter /sc onlogon en complement.
