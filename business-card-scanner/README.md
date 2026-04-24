# Business Card Scanner — Stand 4 You (S4U)

**Stack :** Make (Pro) · Claude API (claude-sonnet-4-6) · Airtable (Teams) · Gmail  
**Scénario Make :** `Airtable → CRM — Scan carte de visite`  
**Branche Git :** `claude/business-card-scanner-uE772`

---

## Architecture globale

```
[Make Mobile] Photo + Commentaire + Salon
       ↓
[Webhook] Réception des données binaires
       ↓
[HTTP → Claude API] Vision + extraction JSON (base64 inline)
       ↓
[JSON > Parse JSON] Validation structure
       ↓
[Router] Branchement sur confidence
       ├── High / Medium → [Airtable] Create Record (direct)
       └── Low           → [Gmail] Alerte validation manuelle
                           [Airtable] Create Record (À vérifier = ✓)
       ↓
[Gmail] Confirmation succès (automation@stand4you.com)
```

Fichiers dans ce dossier :
- `config/claude-vision-prompt.txt` — Prompt système à coller dans Make
- `config/make-http-body.json` — Body JSON complet du module HTTP Make
- `config/airtable-schema.json` — Référence des champs Airtable à créer

---

## 1. Structure Airtable — Table "Contacts Salons"

### Nom de la table
`Contacts Salons`

### Champs à créer (dans l'ordre)

| # | Nom du champ | Type Airtable | Détail |
|---|---|---|---|
| 1 | Prénom | Single line text | |
| 2 | Nom | Single line text | |
| 3 | Société | Single line text | |
| 4 | Fonction | Single line text | |
| 5 | Email | Email | |
| 6 | Téléphone | Phone number | Format : automatique |
| 7 | Autres contacts | Long text | Emails/tél supplémentaires extraits par Claude |
| 8 | Commentaire terrain | Long text | Saisi par Raphaël/Jérôme dans Make Mobile |
| 9 | Salon / Événement | Single select | Voir valeurs ci-dessous |
| 10 | Date de scan | Date | Format : DD/MM/YYYY |
| 11 | Statut de relance | Single select | Voir valeurs ci-dessous |
| 12 | Confiance extraction | Single select | Voir valeurs ci-dessous |
| 13 | À vérifier | Checkbox | Coché auto si confidence = low |
| 14 | Raw text | Long text | Texte brut OCR Claude (debug uniquement) |
| 15 | ID Make Run | Single line text | Identifiant run Make pour traçabilité |
| 16 | Source | Single line text | Valeur fixe : "Scan carte — Make Mobile" |

### Valeurs des Single Select

**Salon / Événement** (à compléter selon agenda S4U) :
- SIAL
- Equiphotel
- Batimat
- VivaTech
- SIDO Lyon
- MWC Barcelona
- CES Las Vegas
- Maison & Objet
- Autre

**Statut de relance** :
- À contacter *(valeur par défaut)*
- En cours
- Relancé 1x
- Relancé 2x
- Converti
- Abandonné

**Confiance extraction** :
- High
- Medium
- Low

> **Action manuelle :** Dans Airtable, après avoir créé la table, récupérer :
> - L'**ID de la base** (format `appXXXXXXXXXXXXXX`) — visible dans l'URL
> - Le **nom exact de la table** (`Contacts Salons`)
> - La **clé API Airtable** — Airtable > Account > Developer Hub > Personal access tokens

---

## 2. Scénario Make — Description module par module

### Nomenclature : `Airtable → CRM — Scan carte de visite`

---

### MODULE 0 — DÉCLENCHEUR : Webhooks > Custom webhook

**App :** Webhooks  
**Module :** Custom webhook

**Configuration :**
1. Cliquer "+ Add" → nommer le webhook `Scan Carte S4U`
2. Copier l'URL générée (format : `https://hook.eu1.make.com/XXXXXX`)
3. Cliquer "Determine data structure" pour enregistrer un payload test depuis Make Mobile
4. Cocher "Show advanced settings" → activer la **réponse immédiate** (évite les timeouts mobiles)

**Données reçues :**
- `photo` — fichier binaire (image capturée)
- `commentaire` — texte libre
- `salon` — texte (valeur sélectionnée dans Make Mobile)
- `timestamp` — date/heure ISO 8601 (généré par Make Mobile)

---

### MODULE 1 — HTTP > Make an API Key Auth request (Claude Vision)

**App :** HTTP  
**Module :** Make an API Key Auth request

**Configuration :**

| Paramètre | Valeur |
|---|---|
| URL | `https://api.anthropic.com/v1/messages` |
| Method | POST |
| Body type | Raw |
| Content type | JSON (application/json) |
| Parse response | Yes |

**Headers :**
```
x-api-key        : votre_clé_anthropic
anthropic-version: 2023-06-01
content-type     : application/json
```

> **Auth :** Dans Make, utiliser "Add" sous "API Key Auth" → mettre la clé Anthropic en valeur, header name `x-api-key`.

**Body :** Voir `config/make-http-body.json` — coller le contenu tel quel dans le champ Body de Make, en remplaçant `{{1.photo}}` par la variable photo du webhook (module 1).

**Mapping de la variable image :**  
Dans le body JSON, le champ `data` doit contenir :
```
{{toBASE64(1.photo)}}
```
où `1` = numéro du module Webhook et `photo` = nom du champ image.

**Error handler à ajouter :**  
Clic droit sur le module → "Add error handler" → Retry (3 tentatives, interval 30s)  
Si erreur persistante → route vers module Gmail d'alerte.

---

### MODULE 2 — JSON > Parse JSON

**App :** JSON  
**Module :** Parse JSON

**Configuration :**

| Paramètre | Valeur |
|---|---|
| JSON string | `{{2.data.content[].text}}` *(body retourné par Claude)* |
| Data structure | Créer manuellement avec les champs : prenom, nom, societe, fonction, email, telephone, autres_contacts, confidence, raw_text |

> **Note :** Claude retourne le JSON dans `response.content[0].text`. Dans Make, mapper : `{{2.data.content[1].text}}`.

**Error handler :**  
Clic droit → "Add error handler" → Break → envoyer email d'alerte avec `{{2.data.content[1].text}}` en corps du message.

---

### MODULE 3 — Flow Control > Router

**App :** Flow Control  
**Module :** Router

**Filtre Branche A (High / Medium) :**
- Condition 1 : `{{3.confidence}}` = `high`
- OU Condition 2 : `{{3.confidence}}` = `medium`
- Opérateur entre conditions : OR

**Filtre Branche B (Low) :**
- Condition : `{{3.confidence}}` = `low`
- OU `{{3.confidence}}` est vide (fallback si champ absent)

---

### BRANCHE A — MODULE 4A : Airtable > Create a Record

**App :** Airtable  
**Module :** Create a Record

**Configuration :**

| Paramètre | Valeur |
|---|---|
| Connection | Connexion Airtable S4U (API key) |
| Base | Sélectionner la base S4U |
| Table | Contacts Salons |

**Mapping des champs :**

| Champ Airtable | Variable Make |
|---|---|
| Prénom | `{{3.prenom}}` |
| Nom | `{{3.nom}}` |
| Société | `{{3.societe}}` |
| Fonction | `{{3.fonction}}` |
| Email | `{{3.email}}` |
| Téléphone | `{{3.telephone}}` |
| Autres contacts | `{{3.autres_contacts}}` |
| Commentaire terrain | `{{1.commentaire}}` |
| Salon / Événement | `{{1.salon}}` |
| Date de scan | `{{formatDate(1.timestamp; "DD/MM/YYYY")}}` |
| Statut de relance | `À contacter` *(valeur fixe)* |
| Confiance extraction | `{{3.confidence}}` |
| À vérifier | `false` *(valeur fixe)* |
| Raw text | `{{3.raw_text}}` |
| ID Make Run | `{{1.id}}` *(ou `{{now}}` si non disponible)* |
| Source | `Scan carte — Make Mobile` *(valeur fixe)* |

---

### BRANCHE B — MODULE 4B-1 : Gmail > Send an Email (alerte validation)

**App :** Gmail  
**Module :** Send an Email

**Configuration :**

| Paramètre | Valeur |
|---|---|
| Connection | Connexion Gmail S4U |
| To | `automation@stand4you.com` |
| Subject | `[S4U] Carte à vérifier manuellement — Confiance faible` |
| Content type | HTML |
| Body | Voir template ci-dessous |

**Template email alerte :**
```html
<h2>Carte de visite à vérifier — Confiance LOW</h2>
<p><strong>Salon :</strong> {{1.salon}}</p>
<p><strong>Date :</strong> {{formatDate(1.timestamp; "DD/MM/YYYY à HH:mm")}}</p>
<hr>
<h3>Données extraites (à vérifier) :</h3>
<ul>
  <li><strong>Prénom :</strong> {{3.prenom}}</li>
  <li><strong>Nom :</strong> {{3.nom}}</li>
  <li><strong>Société :</strong> {{3.societe}}</li>
  <li><strong>Fonction :</strong> {{3.fonction}}</li>
  <li><strong>Email :</strong> {{3.email}}</li>
  <li><strong>Téléphone :</strong> {{3.telephone}}</li>
</ul>
<p><strong>Texte brut détecté :</strong><br>{{3.raw_text}}</p>
<p><strong>Commentaire terrain :</strong> {{1.commentaire}}</p>
<hr>
<p>Le contact a été créé dans Airtable avec "À vérifier = ✓".<br>
<a href="https://airtable.com">Ouvrir Airtable pour corriger</a></p>
```

---

### BRANCHE B — MODULE 4B-2 : Airtable > Create a Record

Même configuration que **MODULE 4A** avec une différence :

| Champ Airtable | Valeur |
|---|---|
| À vérifier | `true` *(coché)* |
| Statut de relance | `À contacter` |

---

### MODULE 5 — Gmail > Send an Email (confirmation succès)

**App :** Gmail  
**Module :** Send an Email  
**Position :** Après les deux branches (ajouter sur chaque branche ou utiliser une route commune)

**Configuration :**

| Paramètre | Valeur |
|---|---|
| To | `automation@stand4you.com` |
| Subject | `[S4U] Contact scanné — {{3.prenom}} {{3.nom}} ({{3.societe}})` |
| Body | `Contact créé dans Airtable. Salon : {{1.salon}}. Confiance : {{3.confidence}}.` |

---

## 3. Prompt Claude Vision — Version finale

Le prompt complet est dans `config/claude-vision-prompt.txt`.

**À coller dans le champ `system` du body JSON Make.**

---

## 4. Configuration HTTP Module (Make → Claude API)

Le body JSON complet est dans `config/make-http-body.json`.

### Paramètres clés

| Paramètre | Valeur |
|---|---|
| URL | `https://api.anthropic.com/v1/messages` |
| Méthode | POST |
| Modèle | `claude-sonnet-4-6` |
| max_tokens | `500` |
| image media_type | `image/jpeg` (ou `image/png` selon source) |

### Headers exacts

```json
{
  "x-api-key": "sk-ant-VOTRE_CLE_ICI",
  "anthropic-version": "2023-06-01",
  "content-type": "application/json"
}
```

### Encodage image base64 dans Make

Dans le champ `data` du body JSON, utiliser la formule Make :
```
{{toBASE64(1.photo)}}
```

Pour détecter automatiquement le type MIME :
```
{{if(contains(get(1.photo; "name"); ".png"); "image/png"; "image/jpeg")}}
```

---

## 5. Error Handler — Architecture complète

### Tableau des défaillances

| Point de défaillance | Comportement Make | Module Make | Action corrective |
|---|---|---|---|
| **Photo illisible / floue** | Claude retourne `confidence: "low"` | Router → Branche B | Email validation manuelle + record Airtable avec `À vérifier = true` |
| **Claude API timeout ou erreur 5xx** | Error Handler sur module HTTP | Tools > Set error handler → Retry | 3 tentatives (30s, 60s, 120s). Si échec : email à `automation@stand4you.com` + Break |
| **JSON malformé retourné par Claude** | Erreur sur JSON > Parse JSON | Tools > Set error handler → Break | Email avec contenu brut `{{2.data.content[1].text}}` pour debug manuel |
| **Champ email manquant** | Filtre conditionnel dans mapping Airtable | Router + filtre `{{3.email}} is empty` | Forcer `À vérifier = true` + ajouter note dans Commentaire terrain |
| **Doublon détecté dans Airtable** | Airtable > Search Records avant création | Airtable > Search Records → Router | Si doublon : Airtable > Update Record (mise à jour) au lieu de Create |
| **Airtable API error** | Error Handler sur module Airtable | Tools > Set error handler → Retry | 2 tentatives (15s, 30s). Si échec : email avec données JSON brutes |
| **Make Mobile hors connexion** | Données en queue locale Make Mobile | Natif Make Mobile | Envoi automatique à la reconnexion Wi-Fi/4G. Aucune config supplémentaire. |

### Configuration de l'Error Handler (module HTTP Claude)

```
Clic droit sur le module HTTP → "Add error handler"
→ Type : Retry
→ Max number of attempts : 3
→ Interval : 30 seconds
→ After retries : Break (+ route vers Gmail alerte)
```

### Email d'alerte erreur système

**Subject :** `[S4U][ERREUR] Scan carte échoué — Action requise`  
**To :** `automation@stand4you.com`  
**Body :**
```
Une erreur est survenue lors du scan de carte de visite.

Étape en échec : {{error.message}}
Code erreur : {{error.type}}
Salon : {{1.salon}}
Timestamp : {{formatDate(now; "DD/MM/YYYY à HH:mm")}}

Vérifier le scénario Make : Airtable → CRM — Scan carte de visite
```

### Gestion doublon — Module Airtable > Search Records

Insérer **avant** le module Create Record :

**App :** Airtable  
**Module :** Search Records

| Paramètre | Valeur |
|---|---|
| Table | Contacts Salons |
| Filter by formula | `AND({Email}="{{3.email}}", {Salon / Événement}="{{1.salon}}")` |
| Max records | 1 |

Puis Router :
- Si `{{5.id}}` n'est pas vide → **Airtable > Update Record** (mettre à jour l'existant)
- Sinon → **Airtable > Create a Record**

---

## 6. Configuration Make Mobile

### Création du bouton scénario

1. **Sur desktop Make** : Scénario ouvert → cliquer l'icône "..." en haut → "Make Mobile settings"
2. Activer "Show in Make Mobile"
3. Nommer le bouton : `Scan Carte S4U`
4. Icône suggérée : 📷 ou carte de visite

### Champs exposés dans l'interface mobile

Configurer dans le module Webhook (onglet "Input fields") :

| Champ | Type Make Mobile | Label affiché | Requis |
|---|---|---|---|
| `photo` | Camera / Photo Library | Photo de la carte | Oui |
| `commentaire` | Text (multiline) | Commentaire terrain | Non |
| `salon` | Select | Salon / Événement | Oui |

**Valeurs du Select `salon` :** Reprendre les valeurs de la colonne Airtable (SIAL, Equiphotel, etc.)

### Procédure de test depuis l'app

1. Ouvrir Make Mobile (iOS ou Android) → se connecter avec le compte Make S4U
2. Le bouton "Scan Carte S4U" apparaît dans l'onglet "Scenarios"
3. Prendre en photo une carte de visite test (carte claire, bonne luminosité)
4. Remplir "Commentaire" et sélectionner un salon
5. Appuyer sur "Run"
6. Vérifier dans Make (desktop) → History → le run apparaît
7. Vérifier dans Airtable → table "Contacts Salons" → la fiche est créée

### Gestion du mode hors-ligne

Make Mobile mémorise les scans non envoyés en local tant que la connexion est absente.  
À la reconnexion (Wi-Fi ou 4G), les données sont envoyées automatiquement.  
**Recommandation salon :** Activer le partage de connexion (hotspot) si le Wi-Fi du salon est instable.  
**Aucune configuration supplémentaire requise** dans Make pour ce comportement.

---

## 7. Guide d'implémentation — Étapes ordonnées

### Étape 1 — Créer la table Airtable

1. Ouvrir Airtable → votre workspace S4U → "+ Add a base" (ou base existante)
2. Créer une nouvelle table → nommer `Contacts Salons`
3. Créer tous les champs listés en §1, dans l'ordre du tableau
4. Pour les Single Select : ajouter toutes les valeurs avant de finir
5. Vérifier que le champ "Email" a bien le type `Email` (pas "Single line text")

### Étape 2 — Récupérer les identifiants Airtable

1. **ID de base :** Ouvrir la base dans Airtable → URL → `https://airtable.com/appXXXXXXXXX/...` → copier `appXXXXXXXXX`
2. **Token API :** Airtable → avatar → Developer hub → Personal access tokens → "+ Add token"  
   Scopes requis : `data.records:read`, `data.records:write`, `schema.bases:read`  
   Access : sélectionner la base S4U uniquement

### Étape 3 — Récupérer la clé API Claude

1. Aller sur [console.anthropic.com](https://console.anthropic.com)
2. Se connecter avec le compte Anthropic S4U
3. API Keys → "+ Create Key" → nommer `Make-S4U-Scanner`
4. Copier la clé (format `sk-ant-api03-...`) — ne s'affiche qu'une fois

### Étape 4 — Créer le scénario Make sur desktop

1. Ouvrir [make.com](https://make.com) → compte S4U
2. "+ Create a new scenario"
3. Nommer : `Airtable → CRM — Scan carte de visite`
4. Mettre en pause le scheduling (ne pas activer "On" tant que les tests ne sont pas terminés)

### Étape 5 — Configurer module par module

**Ordre recommandé :**

1. Ajouter le module **Webhooks > Custom webhook** → copier l'URL générée
2. Ajouter le module **HTTP > Make an API Key Auth request** :
   - Coller le body depuis `config/make-http-body.json`
   - Remplacer `VOTRE_CLE_ANTHROPIC` dans les headers
   - Mapper `{{toBASE64(1.photo)}}` dans le champ `data`
3. Ajouter **JSON > Parse JSON** → mapper `{{2.data.content[1].text}}`
4. Ajouter **Flow Control > Router** → configurer les filtres (§2 Module 3)
5. Sur chaque branche, ajouter les modules Airtable et Gmail (§2 Branches A et B)
6. Ajouter les error handlers (clic droit sur modules HTTP et Airtable)
7. Ajouter le module Gmail de confirmation finale

### Étape 6 — Test avec une carte de visite réelle

**Procédure :**
1. Dans Make, cliquer "Run once" (mode test manuel, sans Make Mobile)
2. Dans un autre onglet, envoyer une requête test au webhook avec un outil comme Postman ou `curl` :
   ```bash
   curl -X POST https://hook.eu1.make.com/VOTRE_HOOK \
     -F "photo=@/path/to/carte.jpg" \
     -F "commentaire=Test salon" \
     -F "salon=SIAL"
   ```
3. Vérifier chaque module dans Make History (bulles vertes = succès)
4. Vérifier la création du record dans Airtable
5. Vérifier la réception de l'email de confirmation

**Cas à tester :**
- [ ] Carte nette → confidence "high" → record créé sans À vérifier
- [ ] Photo floue volontairement → confidence "low" → email alerte + À vérifier coché
- [ ] Carte avec 2 emails → les deux apparaissent (email principal + autres_contacts)
- [ ] Carte bilingue FR/EN → extraction correcte

### Étape 7 — Configurer Make Mobile

1. Sur desktop Make, scénario ouvert → "..." → "Mobile settings" → activer
2. Configurer les champs input (photo, commentaire, salon) — voir §6
3. Sur téléphone : ouvrir Make Mobile → scénario visible → taper pour accéder
4. Faire un test complet (photo réelle, commentaire, salon sélectionné)

### Étape 8 — Test end-to-end depuis le mobile

1. Raphaël ou Jérôme prend une vraie carte de visite sous bonne lumière
2. Ouvre Make Mobile → "Scan Carte S4U" → photo → commentaire → salon → Run
3. Vérifier Make History → tout vert
4. Vérifier Airtable → fiche créée avec toutes les données
5. Vérifier boîte `automation@stand4you.com` → email de confirmation reçu

### Étape 9 — Mise en production

1. Dans Make, activer le scheduling du scénario (passer de OFF à ON)
2. Vérifier que l'abonnement Make couvre le nombre d'opérations prévu (estimé : ~10 ops/scan)
3. Partager l'accès Make Mobile avec Raphaël et Jérôme (Make → Team → inviter les membres)
4. Briefer les utilisateurs sur la procédure : bonne luminosité, cadrage centré, commentaire immédiat
5. Prévoir une vérification hebdomadaire d'Airtable pour traiter les fiches "À vérifier"

---

## Estimation des opérations Make par scan

| Module | Ops Make consommées |
|---|---|
| Webhook | 1 |
| HTTP (Claude) | 1 |
| JSON Parse | 1 |
| Router | 1 |
| Airtable Search (doublon) | 1 |
| Airtable Create/Update | 1 |
| Gmail (si Low) | 1 |
| Gmail confirmation | 1 |
| **Total** | **~8–10 ops/scan** |

Plan Make Pro : 10 000 ops/mois → environ **1 000 scans/mois** inclus.

---

*Stand 4 You (S4U) — Usage interne — Document technique confidentiel*
