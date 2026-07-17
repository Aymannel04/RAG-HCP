# ADR 0005 — Étendre l'ingestion au format DOCX

**Statut :** accepté — 17 juillet 2026

## Contexte

En cherchant un vrai exemple de fichier XLSX pour valider `Extracteur._extraire_xlsx`
(voir JOURNAL.md, 17 juillet), il est apparu que plusieurs publications mensuelles
récurrentes de la catégorie Économie — l'Indice des prix à la consommation (IPC) et
l'Indice des prix à la production industrielle (IPPI), vérifiées directement sur leur
page hcp.ma — ne sont disponibles qu'au format **.docx** (Word), en français et en
arabe, sans alternative PDF ni Excel.

L'ADR 0003 limitait explicitement le périmètre d'ingestion à "PDF/XLSX uniquement". En
l'état, le lien de téléchargement de ces notes (`/attachment/{id}/`) est bien détecté
par `Scraper`, mais le fichier est ensuite rejeté par la vérification des nombres
magiques (`_contenu_semble_valide`) : ce comportement défensif évite un crash, mais a
pour conséquence que ces publications — suivies mensuellement, avec un contenu chiffré
et narratif à part entière — ne contribuent aucun contenu au RAG.

## Décision

Étendre le périmètre d'ingestion pour couvrir aussi le DOCX, au même titre que PDF et
XLSX : `Scraper` détecte, télécharge et valide les pièces jointes `.docx` ; `Extracteur`
en extrait le texte et les tableaux via la bibliothèque `python-docx`. Ce n'est pas un
abandon du principe posé par l'ADR 0003 (le RAG s'indexe sur les documents
téléchargeables, jamais sur le HTML de la page) mais son élargissement à un troisième
format de document bureautique couramment utilisé par HCP.

## Justification

Le HTML de la page ne contient jamais le contenu détaillé de ces notes (juste un court
résumé, comme déjà observé pour les PDF) ; sans support DOCX, ces publications
resteraient invisibles du RAG malgré leur régularité et leur pertinence probable pour
les utilisateurs (indices de prix, suivis mois par mois). Le format DOCX, comme XLSX,
est une archive ZIP structurée en XML : l'extraction de texte et de tableaux y est tout
aussi fiable qu'avec PDF/XLSX, via `python-docx`, bibliothèque mature et standard pour
ce cas d'usage.

## Conséquences

- `db/schema.sql` : `document.type` accepte désormais aussi `'docx'`.
- `src/models.py` : commentaire du champ `Document.type` mis à jour.
- `src/scraper.py` : nouvelle constante `EXTENSIONS_DOCX`, détection étendue dans
  `_detecter_pieces_jointes`, sniffing de Content-Type étendu dans
  `_telecharger_piece_jointe`. `_contenu_semble_valide` renforcé : XLSX et DOCX sont
  tous deux des archives ZIP (signature `PK` identique), donc la seule signature ne
  suffit plus à les distinguer — la fonction vérifie maintenant en plus la présence du
  dossier interne caractéristique du format attendu (`xl/` pour XLSX, `word/` pour
  DOCX). Ce risque de confusion a été identifié concrètement lors du diagnostic du 17
  juillet (fichiers `.docx` mal reconnus comme XLSX invalides).
- `src/extracteur.py` : nouvelle méthode `_extraire_docx` (paragraphes + tableaux via
  `python-docx`), ajoutée au dispatch de `extraire()`.
- `requirements.txt` : ajout de `python-docx`.
- Aucun changement structurel en aval : un `Document` de type `docx` produit du texte
  narratif et éventuellement des tableaux, exactement comme un PDF — `IndexeurTexte`,
  `ConstructeurIndicateurs` et la suite du pipeline n'ont pas besoin d'être modifiés.
- Reste à valider en conditions réelles (télécharger un vrai `.docx` IPC/IPPI et
  vérifier l'extraction bout en bout) — prochaine étape après ce commit.
