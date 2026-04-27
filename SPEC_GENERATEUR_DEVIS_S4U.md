# Spécification technique — Générateur de devis S4U
## Stand 4 You · Version de référence : v7

> **Destination** : transfert vers Claude Code ou tout développeur reprenant le projet.
> Ce document décrit exhaustivement la logique métier, les structures de données,
> les règles de calcul et les flux d'intégration. Zéro ambiguïté tolérée.

---

## 1. Architecture générale

### Type d'application
Single-file HTML (`devis.html`), sans framework JS, sans dépendances CDN sauf Google Fonts.
Déployé sur GitHub Pages : `https://stand4you.com/devis.html`

### Principes fondamentaux
- **Pas de backend.** Tout le state est en mémoire (objet `st`), persisté dans Airtable.
- **Source de vérité : Airtable.** Le champ `Devis_JSON` stocke l'état sérialisé complet.
- **Mode Airtable exclusif.** Pas de localStorage. L'outil s'ouvre toujours via `?id=recXXX`.
- **render() reconstruit tout le DOM.** Sauf `updT()` qui met à jour les nœuds de totaux sans re-render (préserve le focus).
- **Sauvegarde automatique.** Debounce 2 secondes sur toute modification → `atSave()`.

### Credentials Airtable (à ne jamais exposer publiquement)
```
AT_TOKEN = pat6VmW5CHTS3yid7.1196a4e3d39bf3ad8cfd3cbabe99f96c9281d4444eb75a5d838f5adc4a65f23d
BASE_ID  = appIvAiRsGZRbtwY7
```

### IDs des tables Airtable
| Constante | ID | Contenu |
|---|---|---|
| `TBL_DEVIS` | `tblaOkJlBzzfDIzl2` | Enregistrements devis |
| `TBL_CLIENT` | `tblZwYcnFAM6Pk91a` | Clients |
| `TBL_SALON` | `tblx2Oy75AR9vX6lR` | Salons |
| `TBL_EVNT` | `tblKA36jWxmadAKgM` | Événements |

---

## 2. Structure de l'état (`st`)

L'objet `st` est la source de vérité en mémoire. Il est sérialisé en JSON dans `Devis_JSON`.

```javascript
st = {
  // Type de devis
  type: 'n',           // 'n' = nouveau stand (seul type actif)
                       // 'r' = remontage, 's' = stockage, 'm' = mobilier (placeholders)

  // Sections de prestations (tableau ordonné)
  sections: [ /* voir §4 */ ],

  // Remise globale
  remise: '0',         // valeur numérique en string
  rt: '%',             // type : '%' ou '€'

  // TVA
  tvaMode: 'fr',       // 'fr' (20%) | 'eu' (autoliquidation) | 'export' (non applicable)

  // Acompte
  acp: '50',           // pourcentage de l'acompte sur TTC (string)

  // Langue
  lang: 'fr',          // 'fr' | 'en'

  // Blocs légaux éditables
  legal: { /* voir §7 */ },

  // Contexte du devis
  ctx: {
    // Numérotation
    num: '',                    // ex: "DEV-2026-001" (généré par Airtable Fx_Numero)
    dateEmission: 'YYYY-MM-DD', // date ISO, défaut = aujourd'hui
    validite: '7',              // durée en jours (string)

    // Client
    cliSociete: '',
    cliContact: '',             // nom du contact (non affiché en éditeur, conservé en JSON)
    cliEmail: '',
    cliAdresse: '',
    cliTVA: '',                 // N° TVA intracommunautaire (obligatoire si tvaMode='eu')
    cliNature: 'fr',            // 'fr' | 'eu' | 'export' — alimente tvaMode au chargement

    // Salon / événement
    salonNom: '',
    salonLieu: '',
    salonDates: '',
    salonSurface: '',           // en m², string

    // Contrôle UI
    ctxOpen: true,              // panneau client ouvert ou replié

    // Airtable record IDs (liens)
    _atRecordId: null,          // ID de l'enregistrement Devis courant
    _atClientId: null,          // ID du client lié
    _atEvtId: null,             // ID de l'événement lié

    // Signataire
    _createdBy: null,           // nom du créateur (depuis champ Airtable "Créé par")
  },

  // Statut du devis
  status: 'brouillon',         // 'brouillon' | 'envoye' | 'accepte' | 'refuse'
                                // Note : 'expiré' à ajouter (voir backlog)

  // Métadonnées
  savedAt: null,               // ISO timestamp de la dernière sauvegarde Airtable
  _atMode: false,              // true si chargé depuis Airtable (désactive l'édition client/salon)
}
```

---

## 3. Catalogue des sections (`SC`)

14 sections numérotées 0–13. Les sections 0–8 sont activées par défaut (`DEFS_IDX = [0,1,2,3,4,5,6,7,8]`).

| Index | Nom | Type | Particularité |
|---|---|---|---|
| 0 | Étude & Maîtrise d'œuvre | `hasPhases` | 2 phases indépendantes |
| 1 | Revêtement de sol & Habillage mural | standard | — |
| 2 | Menuiserie & Agencement | standard | — |
| 3 | Électricité & Éclairage | standard | — |
| 4 | Audiovisuel & Digital | standard | — |
| 5 | Mobilier & Accessoires | standard | — |
| 6 | Enseigne & Visibilité | standard | — |
| 7 | Signalétique & Visuels | standard | — |
| 8 | Transport & Logistique | standard | — |
| 9 | Restauration & Hospitalité | standard | — |
| 10 | Nettoyage & Préparation | standard | — |
| 11 | Permanence & Assistance technique | standard | — |
| 12 | Stockage & Conservation | `perLine` | Calcul Qté × PU × période |
| 13 | Autre | standard | — |

### Types de sections

**Standard** : montant HT global saisi manuellement + liste de lignes de détail (labels).
```javascript
section = {
  id: Number,          // ID unique local (nSid++)
  name: String,        // nom de la section (depuis SC[ci].name)
  ci: Number,          // index dans SC
  ht: '',              // montant HT saisi (string)
  off: false,          // true = section offerte (montant = 0 dans calcul)
  lines: [ /* lignes */ ],
}
```

**hasPhases** (section 0 uniquement) : deux sous-totaux indépendants.
```javascript
section = {
  id, name, ci,
  phases: [
    { ht: '', off: false },   // Phase 1
    { ht: '', off: false },   // Phase 2
  ],
  lines: [ /* lignes */ ],
}
```
Règle : si une seule phase est offerte → afficher le total de la phase non offerte dans l'en-tête replié. Si les deux phases sont offertes → afficher badge "Offert".

**perLine** (section 12) : chaque ligne a sa propre quantité × prix unitaire × période.
```javascript
section = {
  id, name, ci,
  perLine: true,
  lines: [ /* lignes perLine */ ],
}
```

### Structure d'une ligne

```javascript
line = {
  id: Number,           // ID unique local (nLid++)
  cat: String,          // catégorie du catalogue (clé de SC[ci].groups[g].cats)
  g: Number,            // index du groupe dans SC[ci].groups
  custom: false,        // true = catégorie personnalisée (saisie libre)
  ctxt: '',             // texte si custom=true
  desc: '',             // description libre (sous le label)
  lineHt: '',           // montant HT (sections standard)
  lineOff: false,       // true = ligne offerte

  // Champs spécifiques perLine (section 12)
  storageType: true,
  qty: '',              // quantité
  uprice: '',           // prix unitaire
  period: 'mois',       // 'mois' | 'semaine' | 'jour'
}
```

---

## 4. Règles de calcul

### Fonction `calc()` — résultat

```
ht    = somme de toutes les sections non offertes
rmt   = remise appliquée (% ou € selon rt)
ap    = ht - rmt  (assiette TVA)
tva   = ap × 20%  si tvaMode='fr', sinon 0
ttc   = ap × 1.2  si tvaMode='fr', sinon ap
acompte = ttc × (acp / 100)
solde   = ttc × (1 - acp / 100)
```

### Calcul par type de section

| Type | Formule |
|---|---|
| Standard | `ht` si `!off`, sinon `0` |
| hasPhases | `Σ phases[i].ht` pour chaque phase où `!ph.off` |
| perLine | `Σ lignes` où `lineAmt(l) = qty × uprice` si `!lineOff`, sinon `0` |

### Remise
- Type `%` : `rmt = ht × remise / 100`
- Type `€` : `rmt = min(remise, ht)` (ne peut pas dépasser le total HT)

### Modes TVA
| Mode | Label FR | Label EN | TVA | Mention légale |
|---|---|---|---|---|
| `fr` | France — TVA 20% | France — 20% VAT | 20% sur AP | — |
| `eu` | UE — Autoliquidation | EU — Reverse charge | 0% | "TVA autoliquidée par le preneur — Art. 283-2 du CGI" |
| `export` | Hors UE — TVA non applicable | Non-EU — VAT not applicable | 0% | "TVA non applicable — Art. 262 ter I du CGI" |

---

## 5. Flux Airtable

### Chargement (`atLoad(recordId)`)

```
1. GET /v0/{BASE_ID}/TBL_DEVIS/{recordId}
2. Si Devis_JSON présent → restoreState(JSON.parse) → fin
3. Sinon initialise depuis les champs :
   - num ← Fx_Numero
   - status ← Statut (normalize: "Brouillon" → "brouillon")
   - salonSurface ← Surface_(m2)
   - _createdBy ← "Créé par".name
4. GET client lié (CLIENT_Nom[0]) → cliSociete, cliContact, cliEmail, cliAdresse, cliTVA, cliNature
5. GET événement lié (EVENEMENT[0]) → salonDates (Date_Debut + Date_Fin)
6. GET salon lié depuis l'événement → salonNom, salonLieu
7. uTVA(cliNature) → met à jour tvaMode
8. render()
```

### Sauvegarde (`atSave()`)
Déclenchée après debounce 2s sur toute modification.

**Champs écrits dans TBL_DEVIS :**
```
Devis_JSON   → JSON.stringify(st)          (état complet)
Montant_HT   → calc().ht   (arrondi 2 déc.)
Montant_TTC  → calc().ttc  (arrondi 2 déc.)
Acompte_HT   → calc().acompte (arrondi 2 déc.)
Solde_HT     → calc().solde   (arrondi 2 déc.)
Statut       → statMap[st.status]  ("Brouillon"|"Envoyé"|"Accepté"|"Refusé")
Langue       → st.lang
```

### Champs lus depuis Airtable (jamais écrits par l'outil)
```
Fx_Numero        → numéro de devis (formule Airtable)
CLIENT_Nom       → linked record → table Client
EVENEMENT        → linked record → table Evenement
Surface_(m2)     → surface du stand
Créé par         → objet {name, email} — détermine le signataire
Ouvrir l'URL     → formule Airtable : "https://stand4you.com/devis.html?id=" & RECORD_ID()
```

### Verrouillage
Si `status = 'accepte'` ou `status = 'refuse'` → toute l'interface passe en `readonly`.
Le statut n'est modifiable que depuis Airtable.

### Webhook Make → Pennylane
Déclenché quand le statut passe à `accepte`.

**Payload JSON envoyé :**
```json
{
  "devisNum": "DEV-2026-001",
  "client": "Acme Corp.",
  "salon": "MIPIM 2027",
  "montantHT": 12000.00,
  "montantTTC": 14400.00,
  "acompte": 7200.00,
  "solde": 7200.00,
  "tvaMode": "fr",
  "langue": "fr",
  "recordId": "recXXXXXXXX"
}
```
URL : constante `MAKE_WEBHOOK` (vide = désactivé).

---

## 6. Signataires

Dictionnaire statique dans le code. La clé est le nom exact du compte Airtable.

```javascript
SIGNATAIRES = {
  'Raphaël Flipo': {
    nom: 'Raphaël Flipo',
    titre_fr: 'Co-fondateur · Stratégie & Développement',
    titre_en: 'Co-founder · Strategy & Business Development',
    email: 'raphael.flipo@stand4you.com',
    tel: '+33 6 27 81 33 08'
  },
  'Jérôme Baglan': {
    nom: 'Jérôme Baglan',
    titre_fr: 'Co-fondateur · Technique & Commercial',
    titre_en: 'Co-founder · Technical & Commercial',
    email: 'jerome.baglan@stand4you.com',
    tel: '+33 6 64 43 22 75'
  }
}
```

`getSig()` → retourne `SIGNATAIRES[st.ctx._createdBy]` ou `null` si non reconnu.
Si `null` → bloc "Établi par" absent du PDF et de l'éditeur.

---

## 7. Blocs légaux éditables (`LEGAL_DEF`)

Trois blocs, disponibles en FR et EN, éditables dans l'interface avant génération PDF.

| Clé | Titre FR | Titre EN |
|---|---|---|
| `nonInclus` | Éléments non inclus | Items not included |
| `conditions` | Conditions financières | Payment terms |
| `propriete` | Propriété intellectuelle | Intellectual property |

Chaque bloc est une `<textarea>` pré-remplie depuis `LEGAL_DEF[lang][clé]`.
Les modifications sont sauvegardées dans `st.legal` → sérialisées dans `Devis_JSON`.

---

## 8. Génération PDF (`buildPDF()`)

### Déclenchement
Bouton "Générer le PDF" → `checkAlerts()` → confirmation si alertes → `printD()` → `window.open()` → injection HTML → `window.print()` auto (délai 500ms).

### Alertes pré-PDF (non bloquantes)
Avertissements affichés en `confirm()` si :
- `cliSociete` vide
- `cliAdresse` vide
- `salonNom` vide
- `tvaMode = 'eu'` ET `cliTVA` vide

### Structure du PDF (ordre d'apparition)

```
1. En-tête navy (#0D1B2A)
   - Logo S4U (PNG base64, fond transparent)
   - "Stand 4 You" + tagline "Your brand. Our stand."
   - N° devis · Date émission · Date validité

2. Bandeau titre centré
   - "DEVIS" (Cormorant Garamond 28px, navy, uppercase)
   - Sous-titre en doré italique (FR/EN selon langue)

3. Info-strip client + salon (grille 2 colonnes)
   - Client : société, contact, adresse, email, N° TVA
   - Salon : nom, lieu, dates, surface

4. Tableau des prestations
   - Col 1 : numéro (doré, Cormorant)
   - Col 2 : désignation + lignes de détail
   - Col 3 : montant HT (aligné à droite)
   - Rubriques vides → masquées (filtrées avant rendu)
   - Rubriques offertes → badge "Offert" + montant barré si applicable

5. Tableau des totaux (aligné à droite, 290px)
   - Total HT avant remise (si remise > 0)
   - Remise (si remise > 0)
   - Total HT après remise
   - TVA 20% (si tvaMode='fr') ou mention légale autoliquidation/export
   - Total TTC
   - Acompte (X%)
   - Solde

6. Blocs légaux
   - Éléments non inclus
   - Conditions financières
   - Propriété intellectuelle

7. Encadré d'acceptation
   - Texte légal d'acceptation (FR/EN)

8. Zone de signatures (2 colonnes)
   - Gauche : "Client — Bon pour accord" (date, nom, qualité, signature)
   - Droite : "Stand 4 You — Établi par" (nom, titre, email, tél du signataire)

9. CGPLV (10 articles)
   - Intégrés dans le PDF, non modifiables depuis l'outil
   - À externaliser dans une version future (voir backlog)

10. Pied de page (fixed bottom, répété toutes les pages)
    - Mentions légales complètes S4U
    - contact@stand4you.com
```

### Pied de page légal (constante `FT`)
```
SAS Stand 4 You · Capital social 5 000 € · SIRET 102 806 783 00019
· RCS Nice · N° TVA : FR 34102806783 · Code APE : 43.32A
Siège : 485, route de Saint-Sébastien – 06950 Falicon · contact@stand4you.com
```

### Marges PDF
```
@page { size: A4 portrait; margin: 16mm 14mm 20mm; }
.wrap { padding: 0; }
footer.rf { position: fixed; bottom: 0; height: 18mm; }
```

---

## 9. Champs Airtable — détail par table

### Table `Devis`
| Champ | Type | Rôle |
|---|---|---|
| `Fx_Numero` | Formula | N° devis auto (ex: "DEV-2026-001") |
| `Statut` | Single select | Brouillon / Envoyé / Accepté / Refusé |
| `CLIENT_Nom` | Linked → Client | Client lié |
| `EVENEMENT` | Linked → Evenement | Événement lié |
| `Surface_(m2)` | Number | Surface du stand |
| `Devis_JSON` | Long text | État complet sérialisé (source de vérité) |
| `Montant_HT` | Currency | Total HT calculé |
| `Montant_TTC` | Currency | Total TTC calculé |
| `Acompte_HT` | Currency | Acompte calculé |
| `Solde_HT` | Currency | Solde calculé |
| `Langue` | Single select | fr / en |
| `Créé par` | Created by | Détermine le signataire |
| `Ouvrir l'URL` | Formula | URL d'accès à l'outil |

### Table `Client`
| Champ | Type | Rôle |
|---|---|---|
| `Nom` | Text | Raison sociale |
| `Adresse` | Text | Adresse complète |
| `Contact_Nom` | Text | Nom du contact |
| `Email` | Email | Email du contact |
| `Numero_TVA` | Text | N° TVA intracommunautaire |
| `Nature_TVA` | Single select | fr / eu / export |

### Table `Evenement`
| Champ | Type | Rôle |
|---|---|---|
| `Fx_Nom` | Formula | Nom complet de l'événement |
| `Salon` | Linked → Salon | Salon lié |
| `Date_Debut` | Date | Date de début |
| `Date_Fin` | Date | Date de fin |

### Table `Salon`
| Champ | Type | Rôle |
|---|---|---|
| `Nom` | Text | Nom du salon |
| `Adresse` | Text | Adresse / lieu |

---

## 10. Identité visuelle (CSS)

| Variable | Valeur | Usage |
|---|---|---|
| `--navy` | `#0D1B2A` | Titres, en-têtes, structure |
| `--gold` | `#C9A96E` | Accents, filets, signatures |
| `--cream` | `#F5F5F0` | Fond principal |
| `--sgray` | `#6B7280` | Textes secondaires |
| `--azure` | `#0B8FCC` | CTAs, liens |

Typographie : **Cormorant Garamond** (titres) + **DM Sans** (corps).

---

## 11. Backlog — points ouverts

| Priorité | Item | Notes |
|---|---|---|
| 🔴 | Webhook Make → Pennylane | Payload prêt, scénario Make à construire |
| 🔴 | Statut "Expiré" | À ajouter dans Airtable single select + dictionnaire couleurs + automation Airtable (Date_Expiration < TODAY() ET Statut = Envoyé) |
| 🟡 | Onglets Remontage / Stockage / Mobilier | Placeholders "bientôt disponible" — types `r`, `s`, `m` dans `st.type` |
| 🟡 | CGPLV externalisée | Actuellement codée en dur — envisager champ Attachment Airtable ou fichier séparé |
| 🟡 | Date_Expiration champ Airtable calculé | `DATEADD({Date_Emission}, {Validite_jours}, 'days')` |
| 🟢 | Code APE | 43.32A attribué — révision possible vers 74.10Z (Design) ou 82.30Z (Organisation salons) à valider avec expert-comptable |
| 🟢 | Numérotation devis | Actuellement via formule Airtable `Fx_Numero` — s'assurer que l'incrément est correct sur la nouvelle base |
| 🟢 | Interface Airtable Jérôme | Dashboard + formulaire de création → redirect `devis.html?id={record_id}` opérationnel |

---

## 12. Règles de nommage et conventions code

- **`render()`** : reconstruit tout le DOM depuis `st`. Appel systématique après toute mutation d'état.
- **`updT()`** : met à jour uniquement les nœuds de totaux (sans re-render). Préserve le focus des inputs actifs.
- **`scheduleSave()`** : debounce 2s → `atSave()`.
- **`uCtx(key, val)`** : met à jour `st.ctx[key]`.
- **`uTVA(val)`** : met à jour `st.tvaMode` + re-render.
- **IDs locaux** : `nSid` (sections, start 20) et `nLid` (lignes, start 300) — incrémentés à chaque création.
- **Nomenclature Make** : `[OUTIL SOURCE] → [OUTIL CIBLE] — [Action]`

---

*Document généré le 23 avril 2026 — Stand 4 You SAS — Usage interne uniquement*
