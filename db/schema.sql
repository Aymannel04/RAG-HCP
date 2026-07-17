-- Traduction SQL du MLD (voir docs/conception_uml_v3.pdf, figure 3).
-- Ne couvre que la partie relationnelle du système : l'index vectoriel des
-- embeddings est une structure distincte (Chroma), volontairement hors de ce schéma
-- (voir docs/conception_uml_v3.pdf, section 3 - analyse du MCD).

CREATE TABLE IF NOT EXISTS document (
    id_document       INTEGER PRIMARY KEY AUTOINCREMENT,
    url               TEXT NOT NULL UNIQUE,
    titre             TEXT NOT NULL,
    date_publication  TEXT,
    langue            TEXT NOT NULL DEFAULT 'fr',
    categorie         TEXT,
    type              TEXT NOT NULL CHECK (type IN ('html', 'pdf', 'xlsx', 'api', 'docx'))
);

CREATE TABLE IF NOT EXISTS chunk (
    id_chunk     INTEGER PRIMARY KEY AUTOINCREMENT,
    id_document  INTEGER NOT NULL,
    texte        TEXT NOT NULL,
    position     INTEGER NOT NULL,
    embedding    BLOB,
    FOREIGN KEY (id_document) REFERENCES document (id_document) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS indicateur (
    id_indicateur  INTEGER PRIMARY KEY AUTOINCREMENT,
    nom            TEXT NOT NULL,
    valeur         REAL NOT NULL,
    unite          TEXT,
    periode        TEXT NOT NULL,
    region         TEXT,
    id_document    INTEGER NOT NULL,
    code_bds       TEXT,  -- code indicateur BDS (ex. "I3181"), NULL si extrait d'un PDF/XLSX.
                           -- Sert de clé de cache pour la stratégie cache-aside (ADR 0004) :
                           -- avant un appel API en direct, on vérifie s'il existe déjà une
                           -- ligne avec ce code_bds pour la période demandée.
    FOREIGN KEY (id_document) REFERENCES document (id_document) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chunk_document ON chunk (id_document);
CREATE INDEX IF NOT EXISTS idx_indicateur_document ON indicateur (id_document);
CREATE INDEX IF NOT EXISTS idx_indicateur_nom_periode ON indicateur (nom, periode);
CREATE INDEX IF NOT EXISTS idx_indicateur_code_bds ON indicateur (code_bds);
