# Prompt de reprise — Générateur de devis Stand 4 You

> Coller ce fichier en début de nouvelle session Claude Code pour reprendre le projet.

---

## Société

SAS Stand 4 You — stands d'exposition événementiels.
- SIRET : 102 806 783 00019 · RCS Nice · TVA : FR 34102806783 · APE : 8230Z
- Siège : 485 route de Saint-Sébastien, 06950 Falicon
- Contact : contact@stand4you.com
- Signataires : **Raphaël Flipo** (co-fondateur stratégie) et **Jérôme Baglan** (co-fondateur technique)

---

## Application

Un unique fichier HTML autonome : **`devis.html`**
- Déployé sur GitHub Pages : https://app.stand4you.com
- Repo GitHub : https://github.com/Stand4You/Stand4You
- Branche de travail : toujours créer une feature branch, puis merger dans `main`

---

## Architecture technique

- **Aucun framework, aucun build** : HTML + CSS + JS vanilla, tout en ligne dans un seul fichier (~1650 lignes, ~148 Ko).
- **Backend : Airtable** via API REST directe (Personal Access Token hardcodé dans le fichier — usage interne uniquement, pas de risque d'exposition publique).
- **Chargement** : `?id=recXXX` dans l'URL → `atLoad()` → lit `Devis_JSON` (état complet URL-encodé) → `restoreState()` restitue l'état. Si pas de JSON → initialisation depuis les champs Airtable + catalogue de prestations.
- **Sauvegarde** : `atSave()` → PATCH Airtable : `safeFields` (numériques, texte, dates, booléens — sans risque de 422) puis `softFields` (single-selects avec `typecast:true`).
- **PDF** : `buildPDF()` ouvre une fenêtre popup HTML → `window.print()`. Footer légal via CSS `@page { @bottom-center { content: "..." } }` (margin box, pas de `position:fixed`). Compteur de pages en `@bottom-right`.

---

## Constantes Airtable (dans `devis.html`)

```javascript
const AT_TOKEN   = 'pat6VmW5CHTS3yid7.1196a4...';  // Personal Access Token
const BASE_ID    = 'appIvAiRsGZRbtwY7';
const TBL_DEVIS        = 'tblaOkJlBzzfDIzl2';
const TBL_CLIENT       = 'tblZwYcnFAM6Pk91a';
const TBL_SALON        = 'tblx2Oy75AR9vX6lR';
const TBL_EVNT         = 'tblKA36jWxmadAKgM';
const TBL_RUBRIQUES    = 'tblkk6r4KHjA7Qxsp';
const TBL_PRESTATIONS  = 'tblmWNl2DQhpZhctW';
const TBL_PROJET       = 'tbl8mOCTVuETbsJaK';
const TBL_DOCS         = 'tbl7al8vppMhiKnhQ';  // CGV FR/EN
const MAKE_WEBHOOK     = '';  // placeholder — webhook Make optionnel
```

---

## Champs Airtable clés

### TBL_DEVIS
| Champ | Type | Rôle |
|---|---|---|
| `Devis_JSON` | Texte long | État complet URL-encodé (source of truth) |
| `Statut` | Single-select | Brouillon / Envoyé / Expiré / Accepté / Refusé / Annulé |
| `Fx_Numero` | Formule | Numéro auto (ex: DEV-2026-42) — ne pas renommer |
| `Regime_TVA` | Single-select | France (TVA) / France (franchise TVA) / UE (autoliquidation) / UE (TVA) / Hors UE (hors champ) |
| `Date_Emission` | Date | ISO YYYY-MM-DD |
| `Date_Expiration` | Date | Calculée dynamiquement |
| `Montant_HT`, `Total_HT`, `Total_TTC` | Nombre | Montants calculés |
| `Acompte_Total`, `Solde_Total`, `Remise_HT` | Nombre | Montants calculés |
| `Frais_Gestion` | Booléen | Rubrique gestion & approvisionnement |
| `Validite_Jours` | Nombre | Durée de validité |

### TBL_PROJET
| Champ | Type | Rôle |
|---|---|---|
| `Fx_Coût_Fournisseur_HT` | Formule | Agrégat devis fournisseurs — **ne pas renommer** |

Ce champ est chargé dans `st.ctx.coutFournisseurHT` → affiché dans le bloc vert "Marge brute prévisionnelle" (UI uniquement, pas dans le PDF). Actuellement rechargé uniquement en statut brouillon.

---

## Logique des statuts et gel

| Statut | Comportement à l'ouverture |
|---|---|
| **Brouillon** | Éditable. `dateEmission` = aujourd'hui. Client/salon rechargés depuis Airtable. |
| **Envoyé / Expiré** | Figé (JSON seul). Déblocage via confirmation modale → réouvre l'édition. |
| **Accepté / Refusé / Annulé** | Lecture seule permanente. Seul un changement de statut permet une modification. |

- Le `Statut` est **toujours** relu depuis Airtable à l'ouverture (peut changer hors UI).
- Pour les statuts figés, **tous les autres champs viennent exclusivement du JSON** — aucune donnée Airtable ne vient écraser la dernière version sauvegardée.

---

## Types de devis

| Code | Libellé | Catalogue |
|---|---|---|
| `n` | Stand nouveau | Rubriques + prestations complètes |
| `r` | Stand remontage | Rubriques + prestations remontage |
| `s` | Stockage | Rubriques stockage |
| `m` | Mobilier | Rubriques mobilier |

---

## Modes TVA

| Code interne | Libellé UI | TVA calculée | Valeur Airtable |
|---|---|---|---|
| `fr` | Client France | Oui (20%) | France (TVA) |
| `fr_na` | Franchise TVA | Non | France (franchise TVA) |
| `eu` | Client UE avec N° TVA | Non | UE (autoliquidation) |
| `eu_ht` | Client UE sans N° TVA | Oui (20%) | UE (TVA) |
| `export` | Client hors UE | Non | Hors UE (hors champ) |

`isFR = st.tvaMode === 'fr' || st.tvaMode === 'eu_ht'`

---

## Fonctionnalités implémentées

- Catalogue dynamique rubriques/prestations depuis Airtable (TBL_RUBRIQUES + TBL_PRESTATIONS)
- Édition complète : désignations, quantités, remises par ligne, remise globale, acompte %
- Rubrique "Gestion & Approvisionnement pour le compte du client" (`fraisGestion`) : checkbox bidirectionnelle, textarea description multilignes, mention légale, export Airtable booléen, rendu PDF avec mention `Coût réel + Frais de gestion`
- Marge brute prévisionnelle (bloc vert, UI uniquement) depuis `Fx_Coût_Fournisseur_HT`
- PDF complet : en-tête, tableau des prestations, totaux, blocs légaux, CGV bilingues (FR/EN chargées depuis TBL_DOCS), footer margin box (`@page @bottom-center`), compteur de pages
- Synchronisation JSON complète + champs Airtable individuels à chaque sauvegarde
- Webhook Make optionnel (placeholder `MAKE_WEBHOOK`)
- Interface et PDF bilingues FR/EN complets
- Gestion des statuts avec gel de l'interface et modales de déblocage

---

## Structure de l'état (`st`)

```javascript
st = {
  lang: 'fr',           // 'fr' | 'en'
  type: 'r',            // 'n' | 'r' | 's' | 'm'
  tvaMode: 'fr',        // 'fr' | 'fr_na' | 'eu' | 'eu_ht' | 'export'
  status: 'brouillon',  // 'brouillon' | 'envoye' | 'expire' | 'accepte' | 'refuse' | 'annule'
  remise: '0',          // remise globale %
  acp: '70',            // acompte %
  fraisGestion: false,
  fraisGestionDesc: '',
  sections: [...],      // rubriques avec leurs lignes
  ctx: {
    _atRecordId: null,  // ID Airtable du devis
    _atClientId: null,
    _atEvtId: null,
    _atProjetId: null,
    _createdBy: '',     // nom du signataire (Raphaël Flipo | Jérôme Baglan)
    num: '',
    dateEmission: '',   // YYYY-MM-DD
    validite: '7',      // jours
    cliSociete: '',
    cliContact: '',
    cliAdresse: '',
    cliEmail: '',
    cliTVA: '',
    cliNature: '',
    salonNom: '',
    salonLieu: '',
    salonDates: '',
    salonSurface: '',
    coutFournisseurHT: '',  // depuis TBL_PROJET.Fx_Coût_Fournisseur_HT
  },
  _atMode: false,
  savedAt: '',
}
```

---

## Développements futurs envisagés

### 1. Envoi automatique du devis par email
Déclenché depuis l'UI au passage en statut "Envoyé".
- **Via Make (recommandé)** : le webhook `MAKE_WEBHOOK` est déjà prévu. Make reçoit le record ID, génère ou récupère le PDF, envoie l'email (Gmail / Brevo / Postmark). Zéro code supplémentaire côté HTML.
- **Via API d'envoi directe** (Resend, Postmark) : appel `fetch` depuis le JS avec token stocké dans le fichier.
- Le template email inclurait : lien `app.stand4you.com?id=recXXX` (vue client) + PDF en pièce jointe ou lien de téléchargement.

### 2. Upload automatique du PDF dans Airtable
Contrainte : `window.print()` génère le PDF côté navigateur — pas de fichier récupérable en JS.
- **Via Make/headless Chrome** : Make reçoit le webhook, lance Puppeteer sur l'URL du devis, génère le PDF, l'uploade en tant qu'attachment Airtable.
- **Via jsPDF ou Paged.js** : remplacement de `window.print()` par une lib JS générant un Blob PDF, puis POST sur l'API Airtable. Plus complexe mais 100% client-side.

### 3. Versioning des PDF dans Airtable
Chaque sauvegarde ou changement de statut crée une nouvelle version du PDF (plutôt qu'écraser).
Nommage suggéré : `DEV-2026-42_v1.pdf`, `DEV-2026-42_v2.pdf`…
Nécessite un compteur de version dans `Devis_JSON` ou un champ Airtable dédié.

### 4. Génération d'un devis miroir dans Pennylane
À la validation (statut Accepté), appel API Pennylane pour créer le devis avec les mêmes lignes.
Points d'attention :
- Mapping client : lier les clients Airtable aux clients Pennylane (par SIREN ou email).
- Mapping lignes : les rubriques S4Y n'ont pas d'équivalent direct en produits Pennylane — prévoir une table de mapping ou des lignes libres.
- Token API Pennylane à stocker dans le fichier comme `AT_TOKEN`.

### 5. Rafraîchissement du coût fournisseur pour tous les statuts
Actuellement `Fx_Coût_Fournisseur_HT` n'est rechargé qu'en brouillon. Pour les statuts figés, on pourrait rafraîchir uniquement ce champ (et la marge prévisionnelle) sans toucher au reste du devis. Implémentation : extraire le fetch du projet de `atLoadLinked()` vers une fonction `refreshCoutFournisseur()` appelée indépendamment du statut.

### 6. Vue client partageable (read-only)
Un lien `?id=recXXX&view=client` ouvre le devis en lecture seule stylisée pour le client, sans les contrôles d'édition, avec bouton "Accepter le devis" qui change le statut dans Airtable et déclenche le workflow Make.

### 7. Historique des modifications
Enregistrer dans Airtable un log horodaté des actions : création, modification, envoi, acceptation, refus. Le JSON contient déjà `savedAt` (timestamp de la dernière sauvegarde).

---

## Fichiers du repo GitHub

| Fichier | Rôle |
|---|---|
| `devis.html` | Application principale (seul fichier à modifier) |
| `CNAME` | Indispensable — mappe `app.stand4you.com` vers GitHub Pages |
| `.nojekyll` | Indispensable — désactive le moteur Jekyll de GitHub Pages |
| `S4U_logo_transparent.png` | Logo utilisé dans l'en-tête du PDF |
| `SPEC_GENERATEUR_DEVIS_S4U.md` | Spécification initiale du projet (archivage) |
| `PROMPT_REPRISE_CLAUDE_CODE.md` | Ce fichier |
