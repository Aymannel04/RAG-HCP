# Guide personnel — Sprint 2 et Sprint 3 en détail

But de ce document : que tu puisses, en le relisant, ré-expliquer et refaire toi-même
chaque morceau du projet sans avoir besoin de reposer la question. Chaque section suit
le même schéma : **le problème** (pourquoi ce bout de code existe), **la décision**
(ce qu'on a choisi de faire), **le code réel** (extrait exact du fichier), **le piège**
(ce qui a foiré en conditions réelles, si applicable).

---

## Partie 0 — Le fil rouge à comprendre avant tout : la "fonction injectable"

Ce pattern revient partout (`IndexeurTexte`, `RetrievalReranker`, `Generateur`) donc il
faut le comprendre une fois pour toutes.

**Le problème.** Certaines étapes ont besoin d'un gros modèle d'IA (BGE-M3 pour les
embeddings, ~2 Go ; bge-reranker-v2-m3, ~600 Mo ; Mistral pour la génération). Ces
modèles sont lents/lourds à charger et pas toujours disponibles (pas de réseau dans le
bac à sable de développement). Si le code appelle le vrai modèle en dur, impossible de
tester la logique autour (le découpage, le tri, le format de citation...) sans attendre
un téléchargement de 2 Go à chaque test.

**La décision.** Chaque classe qui a besoin d'un modèle accepte, dans son constructeur,
une fonction optionnelle qui fait le travail à sa place :

```python
class IndexeurTexte:
    def __init__(self, dossier_chroma=None, fonction_embedding=None):
        self._fonction_embedding = fonction_embedding   # None par defaut
        self._modele = None                              # charge plus tard, si besoin

    def _embarquer(self, textes):
        if self._fonction_embedding is not None:
            return self._fonction_embedding(textes)       # <- utilise en test
        if self._modele is None:
            from sentence_transformers import SentenceTransformer
            self._modele = SentenceTransformer("BAAI/bge-m3")   # <- utilise en vrai
        return self._modele.encode(textes, normalize_embeddings=True).tolist()
```

En test, on donne une fausse fonction (juste un calcul simple) : le test tourne en une
fraction de seconde, sans réseau. En vrai (sur ta machine, dans `scripts/*.py`), on ne
donne rien, donc le code va chercher le vrai modèle tout seul.

**Pourquoi c'est important à comprendre** : les 3 autres endroits qui suivent ce même
principe sont `RetrievalReranker(indexeur, fonction_reranking=None)`,
`Generateur(conn, fonction_generation=None)`, et même le chemin "chiffré" de
`Generateur` n'a besoin d'aucune fonction du tout (voir Partie 2).

---

## Partie 1 — Sprint 2 : de la publication brute au chunk indexé

### 1.1 Vue d'ensemble

```
Scraper  -->  Extracteur  -->  IndexeurTexte  -->  base_donnees (SQLite)
(trouve      (extrait le      (découpe, calcule    (enregistre document,
 et télécharge texte du PDF/   les embeddings,       chunk, indicateur)
 les fichiers) DOCX/XLSX)      indexe Chroma+BM25)
```

Chaque flèche correspond à un vrai appel de fonction dans
`scripts/indexer_documents.py::indexer_document`.

### 1.2 Découverte automatique des publications (ADR 0006)

**Le problème.** Au Sprint 1, on avait une liste figée de 27 URLs tapées à la main
(`data/seed_urls.py`). Ça ne peut jamais couvrir tout l'historique de hcp.ma, ni détecter
une nouvelle publication.

**La décision.** hcp.ma a des pages "listing" paginées (ex.
`Publications-Marche-du-travail_r425.html`), triées du plus récent au plus ancien, avec
une pagination `?start=0`, `?start=5`, etc. On lit la page 1, on en extrait les liens
d'articles, et on suit la pagination si besoin.

```python
def decouvrir_urls_liste(self, url_listing, max_pages=None):
    resp = requests.get(url_listing, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(resp.text, "lxml")

    urls_trouvees = []
    for url in self._filtrer_urls_arabe(self._extraire_urls_articles(soup, url_listing)):
        urls_trouvees.append(url)

    paliers = self._increments_pagination(soup)   # ex. [5, 10, 15, ...] deduit de la page
    if max_pages is not None:
        paliers = paliers[: max(0, max_pages - 1)]

    for palier in paliers:
        url_page = f"{url_listing}?start={palier}&show=&order="
        resp = requests.get(url_page, headers=HEADERS, timeout=15)
        nouvelles = [...]  # meme extraction sur cette page
        if not nouvelles:
            break   # fin du listing atteinte
        urls_trouvees += nouvelles
    return urls_trouvees
```

Deux usages du même mécanisme, juste en changeant `max_pages` :
- `max_pages=1` : seulement la page la plus récente → détection de "fraîcheur" (usage
  quotidien).
- `max_pages=None` : toutes les pages → collecte historique complète.

**Pourquoi extraire les liens seulement dans des titres `<h2>`-`<h5>`.** Premier essai :
on cherchait n'importe quel `<a>` dont l'URL ressemble à un article
(`..._a1234.html`). Ça attrapait aussi le lien du menu "Tout sur HCP"
(`Qui-sommes-nous_a3079.html`), qui suit le même motif d'URL mais n'est pas un article.
Trouvé par un test écrit AVANT le code (on a écrit le test, il a échoué, on a corrigé).
Solution : n'accepter un lien que s'il est dans un titre de section, comme les vrais
articles le sont sur la page.

**Le piège trouvé en réel (langue).** La première exécution réelle a fait remonter une
page en arabe (`...-version-Ar_a4217.html`). Solution : détecter la langue (même
fonction `_detecter_langue` que pour les pièces jointes PDF, réutilisée) et l'écarter par
défaut.

**Le fichier `data/listing_urls.py`** liste, pour chaque catégorie, la ou les pages
listing à parcourir : Marché du travail a UNE SEULE page qui couvre toute la catégorie,
Économie et Population ont chacune plusieurs pages (une par sous-thème). Ça a été vérifié
à la main en lisant le vrai site.

### 1.3 Support DOCX (ADR 0005)

**Le problème.** Certaines notes hcp.ma (indices IPC/IPPI) sont en `.docx`, pas en
PDF/XLSX.

**Le piège technique.** DOCX et XLSX sont TOUS LES DEUX des fichiers ZIP en interne
(même signature binaire `PK`). Pour les distinguer, on regarde quel dossier interne le
ZIP contient : `word/document.xml` pour DOCX, `xl/workbook.xml` pour XLSX.

**Le code d'extraction** utilise `python-docx` :

```python
def _extraire_docx(self, chemin):
    doc = DocxDocument(chemin)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
```

### 1.4 Chunking — découper le texte en morceaux

**Le problème.** Un embedding (voir 1.5) résume un texte en un vecteur de nombres. Si tu
donnes un document entier de 50 pages, le vecteur devient une moyenne floue de tout —
inutilisable pour retrouver un passage précis. Il faut découper le texte en morceaux
("chunks") de taille raisonnable, chacun avec son propre embedding.

**La décision.** Découpage par paragraphe (jamais au milieu d'une phrase), avec un
"empaquetage glouton" : on accumule des paragraphes entiers jusqu'à ~1500 caractères,
puis on démarre un nouveau chunk. Chaque nouveau chunk reprend les 200 derniers
caractères du précédent (le "chevauchement" ou "overlap"), pour ne pas couper le
contexte en plein milieu d'une idée.

```python
TAILLE_CHUNK_CARACTERES = 1500
CHEVAUCHEMENT_CARACTERES = 200

def _decouper_en_chunks(texte, taille_max=1500, chevauchement=200):
    paragraphes = [p.strip() for p in texte.split("\n") if p.strip()]
    chunks, courant = [], ""
    for paragraphe in paragraphes:
        if len(paragraphe) > taille_max:              # paragraphe geant (ex. tableau aplati)
            if courant:
                chunks.append(courant); courant = ""
            pas = max(taille_max - chevauchement, 1)
            for i in range(0, len(paragraphe), pas):
                chunks.append(paragraphe[i : i + taille_max])   # tronconne a la dure
            continue
        candidat = f"{courant}\n{paragraphe}" if courant else paragraphe
        if len(candidat) <= taille_max:
            courant = candidat                          # on continue a remplir
        else:
            chunks.append(courant)                       # chunk plein, on le ferme
            amorce = courant[-chevauchement:] if chevauchement else ""
            courant = f"{amorce}\n{paragraphe}" if amorce else paragraphe
    if courant:
        chunks.append(courant)
    return chunks
```

**Pourquoi 1500/200 et pas une autre valeur ?** Ce n'est écrit nulle part dans les
documents de conception — c'est une décision d'implémentation, justifiée dans le code :
1500 caractères ≈ 300-400 tokens en français, une taille standard pour ce genre de
système. Chiffres choisis, pas mesurés scientifiquement — si un jour la qualité de
recherche déçoit, c'est un des premiers paramètres à essayer de changer.

**Pourquoi par caractères et pas par "vrais tokens" du modèle ?** Compter les tokens
exacts demanderait de charger le tokenizer de BGE-M3 — un modèle de 2 Go — juste pour
découper du texte. Une approximation par caractères évite cette dépendance lourde.

### 1.5 Embeddings — transformer du texte en vecteur de nombres

**C'est quoi.** Un embedding, c'est une fonction qui prend un texte et renvoie une liste
de nombres (ex. 1024 nombres pour BGE-M3) qui représente le "sens" de ce texte. Deux
textes proches en sens ont des vecteurs proches (mesurable par un calcul de similarité
cosinus). C'est ce qui permet une recherche "sémantique" : trouver un passage pertinent
même s'il n'utilise pas exactement les mêmes mots que la question.

**Le modèle choisi : BGE-M3** (`BAAI/bge-m3`, via la bibliothèque
`sentence-transformers`). Choisi (ADR 0002) parce que multilingue (français couvert),
open source (gratuit, pas d'API payante), et installable localement.

**Le code** (voir aussi Partie 0 pour le pattern injectable) :

```python
def _embarquer(self, textes):
    if self._fonction_embedding is not None:
        return self._fonction_embedding(textes)
    if self._modele is None:
        from sentence_transformers import SentenceTransformer
        self._modele = SentenceTransformer("BAAI/bge-m3")
    return self._modele.encode(textes, normalize_embeddings=True).tolist()
```

**Validé en réel** : dimension 1024 confirmée (signature exacte de BGE-M3), recherche
testée sur "produit intérieur brut" → résultats tous pertinents.

### 1.6 Indexation hybride : Chroma (sémantique) + BM25 (lexical) + fusion RRF

**Le problème.** La recherche par embedding (sémantique) est puissante mais peut rater
une correspondance de mot-clé exact (ex. un code, un sigle). La recherche par mots-clés
classique (lexicale) est précise sur les mots exacts mais aveugle au sens. On fait les
deux et on combine.

**ChromaDB** stocke les embeddings et fait la recherche par similarité (`collection.query`).
**BM25** (bibliothèque `rank_bm25`) fait la recherche par mots-clés — reconstruit à la
demande à chaque recherche (pas de sauvegarde native de cette bibliothèque, mais assez
rapide à l'échelle du prototype).

**La fusion : Reciprocal Rank Fusion (RRF).** Le score dense (cosinus) est entre 0 et 1,
le score BM25 n'est pas borné — impossible de les comparer directement. RRF ignore les
scores et ne regarde que le RANG de chaque résultat dans chaque liste :

```python
@staticmethod
def _fusionner_rrf(listes_classees, top_k, k_rrf=60):
    scores = {}
    for liste in listes_classees:
        for rang, id_ in enumerate(liste):
            scores[id_] = scores.get(id_, 0.0) + 1.0 / (k_rrf + rang + 1)
    classement = sorted(scores.keys(), key=lambda i: scores[i], reverse=True)
    return classement[:top_k]
```

`k_rrf=60` est la valeur standard de la littérature (papier Cormack et al., 2009), pas
inventée au hasard.

**Piège technique découvert en testant** : `collection.get(ids=[...])` de Chroma ne
garantit PAS de renvoyer les résultats dans l'ordre demandé. Il faut donc reconstruire
l'ordre soi-même après coup, ce que fait `rechercher()` :

```python
resultats = self._collection.get(ids=ids_fusionnes, include=["documents", "metadatas"])
chunks_par_id = {...}  # dict id -> Chunk
return [chunks_par_id[id_] for id_ in ids_fusionnes if id_ in chunks_par_id]  # re-ordonne
```

### 1.7 Persistance SQLite (`src/base_donnees.py`)

**Le problème.** Les documents, chunks et indicateurs doivent survivre entre deux
exécutions du programme — donc écrits dans une vraie base de données, pas juste en
mémoire.

**Dédoublonnage document** : la colonne `document.url` a une contrainte `UNIQUE` dans
`db/schema.sql`. `inserer_document` vérifie si l'URL existe déjà avant d'insérer :

```python
def inserer_document(conn, document):
    existant = conn.execute("SELECT id_document FROM document WHERE url = ?", (document.url,)).fetchone()
    if existant:
        return existant[0]          # deja connu, on ne duplique pas
    curseur = conn.execute("INSERT INTO document (...) VALUES (...)", (...))
    conn.commit()
    return curseur.lastrowid
```

**Dédoublonnage indicateur** (plus subtil) : pas de contrainte UNIQUE dans le schéma,
donc c'est le code qui fait l'upsert (update si ça existe, insert sinon) sur la
combinaison (nom, période, région, code_bds) :

```python
existant = conn.execute(
    "SELECT id_indicateur FROM indicateur WHERE nom = ? AND periode = ? AND region IS ? AND code_bds IS ?",
    (indicateur.nom, indicateur.periode, indicateur.region, indicateur.code_bds),
).fetchone()
if existant:
    conn.execute("UPDATE indicateur SET valeur = ? WHERE id_indicateur = ?", (...))
else:
    conn.execute("INSERT INTO indicateur (...) VALUES (...)", (...))
```

Pourquoi nécessaire : le pré-remplissage BDS (`preremplir_indicateurs_bds.py`) est fait
pour tourner régulièrement (chaque nuit, idéalement) — sans cet upsert, chaque exécution
créerait des doublons à l'infini.

**Astuce SQL à retenir** : `region IS ?` et pas `region = ?` — en SQL, `NULL = NULL` est
FAUX (NULL n'est jamais égal à rien, même pas à lui-même), il faut `IS` pour comparer une
valeur qui peut être NULL.

**Embedding en base** : une liste de nombres Python est convertie en bytes bruts (BLOB)
via le module standard `array` — pas de dépendance externe :

```python
def _embedding_vers_blob(embedding):
    return array.array("f", embedding).tobytes()      # "f" = float 32 bits

def blob_vers_embedding(blob):
    tampon = array.array("f")
    tampon.frombytes(blob)
    return list(tampon)
```

### 1.8 Scripts d'orchestration

- `scripts/indexer_documents.py` : la boucle complète, catégorie par catégorie, page
  listing par page listing. Ignore explicitement les documents `type == "html"` (ADR
  0003 : le RAG ne s'indexe jamais sur le HTML brut de la page, seulement sur les
  pièces jointes PDF/XLSX/DOCX). Option `--limite N` pour un test rapide.
- `scripts/preremplir_indicateurs_bds.py` : pour chaque code d'indicateur curé
  (`data/indicateurs_cures.py`), appelle l'API BDS, transforme en lignes `Indicateur`,
  upsert en base.
- `scripts/inspecter_index.py` : outil de vérification — résumé de ce qu'il y a en
  base + option `--recherche "question"` pour tester une vraie recherche.

**Résultat validé en réel (20 juillet 2026)** : run complet sans limite → 151 documents,
6999 chunks, dont 2 vrais DOCX indexés avec succès.

---

## Partie 2 — Sprint 3 : du texte indexé à la réponse

### 2.1 Vue d'ensemble — les deux chemins

C'est l'idée fondatrice du projet entier (ADR 0001, dès le Sprint 1) : **on ne traite
pas pareil une question sur un chiffre précis et une question qui demande une
explication.**

```
Question utilisateur
       |
   Routeur.classifier(question)
       |
   +---+---+
   |       |
 CHIFFRE  NOTION
   |       |
LookupStructure   RetrievalReranker
(requete SQL       (recherche hybride
 exacte)            + reranking)
   |       |
   +---+---+
       |
   Generateur.generer_reponse(question, contexte)
       |
    Reponse (texte + source)
```

Toute cette chaîne est câblée dans `scripts/poser_question.py::poser_question`.

### 2.2 Routeur — classifier la question

**Le problème.** Il faut décider, avant toute recherche, si la question porte sur un
chiffre précis ("quel est le taux de chômage ?") ou une notion à expliquer ("c'est quoi
le RGPH ?").

**La décision : heuristique de mots-clés, pas de LLM.** Le squelette d'origine prévoyait
un appel LLM pour classifier. On a choisi une simple liste de mots-clés à la place —
déjà proposée comme option V1 dans une note envoyée à l'encadrante, et ça évite de
dépendre du choix du LLM (qui n'était pas encore tranché à ce moment du projet).

```python
MOTS_NOTION = ["pourquoi", "comment", "expliquer", "definir", "tendance", "analyse", ...]
MOTS_CHIFFRE = ["combien", "quel est le taux", "taux de", "nombre de", ...]

def classifier(self, question):
    signal = question.lower().strip()
    if any(mot in signal for mot in MOTS_NOTION):
        return TypeQuestion.NOTION       # priorite au signal narratif
    if any(mot in signal for mot in MOTS_CHIFFRE):
        return TypeQuestion.CHIFFRE
    if PATTERN_PERIODE.search(signal):   # une annee/trimestre sans autre mot-cle
        return TypeQuestion.CHIFFRE
    return TypeQuestion.NOTION           # par defaut, plus sur (voir ci-dessous)
```

**Pourquoi NOTION est prioritaire sur CHIFFRE en cas de conflit.** Une question comme
"pourquoi le chômage a-t-il augmenté ?" contient à la fois un signal narratif
("pourquoi") et un mot lié aux chiffres ("chômage"). Seul `RetrievalReranker` (recherche
dans le texte des rapports) peut répondre au "pourquoi" — `LookupStructure` ne renvoie
qu'un chiffre brut, sans explication. D'où la priorité au signal narratif.

**Pourquoi NOTION par défaut plutôt que CHIFFRE.** Si la classification se trompe côté
NOTION, `RetrievalReranker` peut quand même trouver un chiffre s'il apparaît dans le
texte d'un rapport. Si elle se trompe côté CHIFFRE, `LookupStructure` répond
"indicateur non trouvé" sans avoir rien cherché d'autre. Mieux vaut le défaut le moins
risqué.

### 2.3 LookupStructure — retrouver un indicateur exact

**Le problème.** Une fois qu'on sait que la question porte sur un chiffre, il faut
retrouver LEQUEL des ~20 indicateurs en base correspond à la question, et quelle ligne
précise (quelle période, quelle région).

**Le vrai défi : les noms d'indicateurs en base ne sont jamais formulés comme une
question.** Ils viennent tels quels de l'API BDS, ex. `"Taux de chômage selon le
Milieu, le sexe et le groupe d'âges"`. Une question réelle dit "quel est le taux de
chômage actuel ?" — aucune correspondance exacte possible.

**La décision : recouvrement de tokens.** On découpe la question ET chaque nom
d'indicateur en mots (en ignorant les mots-outils comme "le", "de", "est"), et on compte
combien de mots ils ont en commun. Le nom avec le plus de mots en commun gagne.

```python
MOTS_OUTILS = {"le", "la", "les", "de", "du", "est", "quel", "pour", ...}

@staticmethod
def _tokeniser(texte):
    tokens = re.findall(r"\w+", _normaliser_accents(texte.lower()))
    return {t for t in tokens if t not in MOTS_OUTILS}

@classmethod
def _meilleur_nom_correspondant(cls, question, noms_disponibles):
    tokens_question = cls._tokeniser(question)
    scores = {nom: len(tokens_question & cls._tokeniser(nom)) for nom in noms_disponibles}
    meilleur_score = max(scores.values(), default=0)
    if meilleur_score == 0:
        return None
    meilleurs_noms = [nom for nom in noms_disponibles if scores[nom] == meilleur_score]
    if len(meilleurs_noms) > 1 and meilleur_score <= 1:
        return None            # <- voir le bug ci-dessous
    return meilleurs_noms[0]
```

**Bug réel n°1 trouvé le 21 juillet : match ambigu.** Presque tous les noms
d'indicateurs commencent par "Taux". Une question comme "quel est le taux de travail ?"
ne partage que le mot "taux" avec PLEIN d'indicateurs différents (urbanisation,
activité, emploi, chômage...) — ils étaient tous à égalité de score, et le code
choisissait arbitrairement le premier inséré en base ("Taux d'urbanisation"), donnant
une réponse fausse mais présentée avec assurance. **Correction** : si plusieurs noms
sont à égalité ET que le score n'est que de 1 (un seul mot commun, probablement "taux"
tout seul), on refuse de trancher — on renvoie `None`, ce qui fait basculer sur
`RetrievalReranker` (voir 2.6, `poser_question`), plus honnête qu'un mauvais chiffre.

**Bug réel n°2 trouvé le 21 juillet : accents.** "chomage" tapé sans accent (très
courant en usage réel) ne correspondait pas à "chômage" dans le nom en base — deux mots
différents pour Python. **Correction** : `_normaliser_accents` retire les accents des
deux côtés avant de comparer (via `unicodedata`, qui décompose "ô" en "o" + accent, puis
on jette l'accent) :

```python
def _normaliser_accents(texte):
    forme_decomposee = unicodedata.normalize("NFD", texte)
    return "".join(c for c in forme_decomposee if unicodedata.category(c) != "Mn")
```

**Extraction de la période et de la région.** Une fois le bon `nom` trouvé, on cherche
une année (`\b(19|20)\d{2}\b`) ou un trimestre (`\bT[1-4]\b`) dans la question par
expression régulière, et on vérifie si une région connue pour cet indicateur apparaît
littéralement dans la question. Si rien n'est trouvé, on prend la période la plus
récente en base (`ORDER BY periode DESC LIMIT 1`).

**Limite connue, non corrigée (documentée dans TODO.md)** : ça ne comprend pas "pour
les femmes" → "Féminin" (mots différents), et les indicateurs croisent souvent
sexe+milieu+âge dans le même champ `region` — un correctif hâtif risquerait de renvoyer
un sous-groupe très spécifique maquillé en réponse générale. Volontairement laissé de
côté pour un futur sprint, avec une vraie réflexion plutôt qu'un rustine.

### 2.4 RetrievalReranker — recherche hybride + reranking (ADR 0007)

**Le problème.** `IndexeurTexte.rechercher` (Sprint 2) donne déjà des résultats
raisonnables, mais un modèle spécialisé peut encore affiner le classement des meilleurs
candidats.

**La différence bi-encoder vs cross-encoder** (important à comprendre) :
- BGE-M3 (Sprint 2) est un "bi-encoder" : il calcule l'embedding de la question et
  l'embedding de chaque passage SÉPARÉMENT, puis compare les deux vecteurs. Rapide,
  utilisable sur tout le corpus.
- Le reranker est un "cross-encoder" : il regarde la question ET le passage EN MÊME
  TEMPS, dans un seul passage dans le modèle. Plus précis, mais trop lent pour tout le
  corpus — utilisé seulement sur les ~20 meilleurs candidats déjà remontés par la
  recherche hybride.

**Le modèle choisi : `BAAI/bge-reranker-v2-m3`** — même famille que BGE-M3, donc même
justification (multilingue, gratuit, local).

```python
def rechercher_et_trier(self, question, top_k=5):
    marge = max(top_k * 4, 20)
    candidats = self._indexeur.rechercher(question, top_k=marge)   # etape 1 : recherche large
    if not candidats:
        return []
    scores = self._reranker(question, [c.texte for c in candidats])  # etape 2 : affiner
    classement = sorted(zip(candidats, scores), key=lambda p: p[1], reverse=True)
    return [chunk for chunk, _ in classement[:top_k]]

def _reranker(self, question, textes):
    if self._fonction_reranking is not None:
        return self._fonction_reranking(question, textes)     # test
    if self._modele is None:
        from sentence_transformers import CrossEncoder
        self._modele = CrossEncoder("BAAI/bge-reranker-v2-m3")
    paires = [[question, texte] for texte in textes]
    return self._modele.predict(paires).tolist()               # vrai modele
```

### 2.5 Generateur — rédiger la réponse finale

**Le point le plus important à retenir : les deux chemins ne fonctionnent PAS pareil.**

**Chemin chiffré : aucun LLM.** D'après le dossier de conception : le Generateur "n'intervient
qu'en toute fin de chaîne pour mettre cette valeur en forme dans une phrase, sans marge
d'interprétation sur le chiffre". C'est juste un gabarit de texte (f-string) :

```python
def _generer_reponse_chiffree(self, indicateur):
    region = f", {indicateur.region}" if indicateur.region else ""
    unite = self._unite_formatee(indicateur.unite)
    texte = (
        f"D'après les données du HCP, {indicateur.nom} s'élève à "
        f"{indicateur.valeur:g}{unite} pour la période {indicateur.periode}{region}."
    )
    titre, url, date_publication = self._recuperer_document(indicateur.id_document)
    return Reponse(texte=texte, source_url=url, source_titre=titre, source_date=date_publication)
```

Zéro risque d'invention : le texte est entièrement dérivé de données déjà vérifiées en
base. C'est LE point fort de l'architecture entière (ADR 0001) : jamais de LLM entre
l'utilisateur et un chiffre officiel.

**Bug réel trouvé : unité en majuscules.** L'API BDS renvoie parfois l'unité en toutes
lettres ("POURCENTAGE" au lieu de "%"), jamais normalisée nulle part → "9 POURCENTAGE"
au lieu de "9%". Corrigé par `_unite_formatee` :

```python
@staticmethod
def _unite_formatee(unite):
    if not unite:
        return ""
    nettoye = unite.strip()
    if nettoye.lower() in {"pourcentage", "pour cent", "percent", "%"}:
        return "%"                              # pas d'espace avant
    if len(nettoye) <= 4:
        return f" {nettoye}"                    # code court (MAD, USD...), garde tel quel
    return f" {nettoye.lower()}"                 # sinon, minuscules + espace
```

**Chemin notion : LLM obligatoire, injectable.** Synthétiser plusieurs passages en une
réponse cohérente demande une vraie génération de texte — impossible sans LLM. Sans
fonction injectée, le code refuse plutôt que d'improviser :

```python
def _generer_reponse_notion(self, question, chunks):
    if self._fonction_generation is None:
        raise NotImplementedError("Aucune fonction de generation configuree...")
    texte_contexte = "\n\n".join(chunk.texte for chunk in chunks)
    texte = self._fonction_generation(question, texte_contexte)
    titre, url, date_publication = self._recuperer_document(chunks[0].id_document)
    return Reponse(texte=texte, source_url=url, source_titre=titre, source_date=date_publication)
```

**Cas "pas d'information"** : si le contexte est vide (aucun chunk trouvé, aucun
indicateur trouvé), on renvoie un message explicite plutôt que d'inventer :

```python
if contexte is None or (isinstance(contexte, list) and not contexte):
    return Reponse(texte="Je n'ai pas trouvé d'information sur ce sujet...", source_url="", source_titre="", source_date=None)
```

### 2.6 Le choix du LLM : Mistral (`src/llm_mistral.py`)

**Contexte de la décision.** Le choix du LLM était identifié comme LE point bloquant du
Sprint 3 depuis l'ADR 0002 ("doit être validé avec l'encadrante"). Réponse obtenue le
21 juillet : "n'importe quel LLM gratuit qui fait le travail". Comparaison faite entre
Google Gemini, Groq et Mistral (quotas gratuits, qualité, rapidité) — Mistral choisi
pour la qualité du français (entreprise française) et la cohérence.

**Le code : appel REST direct, pas de SDK** (même style que `bds_client.py`) :

```python
def generer(question, texte_contexte):
    cle_api = os.environ.get("MISTRAL_API_KEY")
    if not cle_api:
        raise RuntimeError("MISTRAL_API_KEY manquante...")
    reponse = requests.post(
        "https://api.mistral.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {cle_api}"},
        json={
            "model": "mistral-small-latest",
            "messages": [
                {"role": "system", "content": PROMPT_SYSTEME},   # impose le grounding strict
                {"role": "user", "content": f"Contexte :\n{texte_contexte}\n\nQuestion : {question}"},
            ],
            "temperature": 0.2,   # factuel, pas creatif
        },
    )
    return reponse.json()["choices"][0]["message"]["content"].strip()
```

Le `PROMPT_SYSTEME` est ce qui force le grounding : "réponds UNIQUEMENT à partir du
contexte fourni... si le contexte ne permet pas de répondre, dis-le explicitement".
Sans cette instruction, rien n'empêche Mistral d'improviser.

**La clé API se met dans un fichier `.env`** (jamais commité, dans `.gitignore`),
lu automatiquement par `python-dotenv` (`load_dotenv()` en haut du fichier).

### 2.7 L'orchestration : `scripts/poser_question.py`

C'est la fonction qui relie tout :

```python
def poser_question(conn, reranker, routeur, generateur, question):
    type_question = routeur.classifier(question)

    if type_question == TypeQuestion.CHIFFRE:
        indicateur = LookupStructure(conn).rechercher_indicateur(question)
        if indicateur is not None:
            return generateur.generer_reponse(question, indicateur)
        # repli : pas d'indicateur trouve, on retente cote texte plutot que d'abandonner

    chunks = reranker.rechercher_et_trier(question)
    return generateur.generer_reponse(question, chunks)
```

Le repli CHIFFRE → NOTION (si `LookupStructure` ne trouve rien) est important : plutôt
que de répondre "indicateur non trouvé" sèchement, on retente une recherche textuelle,
qui peut quand même trouver l'info dans un rapport.

---

## Partie 3 — Ce que tu dois pouvoir refaire seul

Si tu peux répondre à ces questions sans regarder le code, tu as compris :

1. Pourquoi `IndexeurTexte`, `RetrievalReranker` et `Generateur` acceptent tous une
   fonction optionnelle en plus de leurs vrais paramètres — et pourquoi c'est le même
   principe à chaque fois.
2. Pourquoi le RAG n'indexe jamais le HTML des pages hcp.ma, seulement leurs pièces
   jointes (ADR 0003).
3. Pourquoi la fusion RRF utilise le RANG des résultats et pas leur score brut.
4. Pourquoi le chemin "chiffré" de `Generateur` n'appelle jamais de LLM, contrairement
   au chemin "notion" — et ce que ça veut dire pour le risque d'hallucination.
5. Les 3 bugs réels du 21 juillet et pourquoi chacun était invisible dans les tests
   avec données factices (match ambigu sur "taux", accents, unité en majuscules).
6. Pourquoi la limite "pour les femmes" n'a pas été corrigée à la va-vite.

Si un point n'est pas clair en le relisant, va voir le fichier source cité — chaque
section pointe vers le vrai fichier (`src/...py`) où creuser.
