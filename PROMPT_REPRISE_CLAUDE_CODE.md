# Prompt de reprise — Générateur de devis S4U
## À coller au démarrage d'une session Claude Code

---

## Contexte général

Tu reprends le développement d'un outil de génération de devis pour **Stand 4 You (S4U)**, une SAS standiste premium basée à Nice (French Riviera).

Les fichiers de référence sont dans ce projet :
- `devis.html` — l'outil complet (single-file HTML, ~148 000 caractères)
- `SPEC_GENERATEUR_DEVIS_S4U.md` — spécification technique exhaustive
- Ce fichier — prompt de reprise et état actuel

**Je travaille avec des logiciels en français** (Airtable, Wix, GitHub en français). Lors de nos échanges, utilise les noms de menus et rubriques en français (ex : "Sources de données" et pas "Data sources", "Publier" et pas "Publish", etc.).

---

## Stack technique

| Outil | Rôle |
|---|---|
| **Airtable** (Teams) | CRM + base de données — source de vérité |
| **Make** (Pro) | Automatisations (webhook → Pennylane) |
| **Wix** (Light) | Site web + hébergement futur de l'outil |
| **Pennylane** (Premium) | Comptabilité / facturation |
| **Google Workspace** | Drive, emails |

Identité visuelle : Navy `#0D1B2A` · Gold `#C9A96E` · Cream `#F5F5F0` · Steel `#6B7280` · Azure `#0B8FCC`
Typographies : Cormorant Garamond (titres) + DM Sans (corps)

---

## ⚠️ TÂCHE PRIORITAIRE — Remettre l'outil en service

L'outil est actuellement **non fonctionnel** pour deux raisons :

### 1. Migration Airtable

La base Airtable a été transférée sur un nouveau compte. Les credentials sont déjà mis à jour dans `devis.html` :

```javascript
const AT_TOKEN = 'pat6VmW5CHTS3yid7.1196a4e3d39bf3ad8cfd3cbabe99f96c9281d4444eb75a5d838f5adc4a65f23d';
const BASE_ID  = 'appIvAiRsGZRbtwY7';
```

Les IDs de tables sont supposés identiques (migration Airtable préserve les IDs) :
```javascript
const TBL_DEVIS  = 'tblaOkJlBzzfDIzl2';
const TBL_CLIENT = 'tblZwYcnFAM6Pk91a';
const TBL_SALON  = 'tblx2Oy75AR9vX6lR';
const TBL_EVNT   = 'tblKA36jWxmadAKgM';
```

**À vérifier en priorité** : tester un appel API avec le nouveau token sur la nouvelle base pour confirmer que les IDs de tables sont bien les mêmes. Si différents → les mettre à jour dans `devis.html`.

Test rapide à faire :
```bash
curl "https://api.airtable.com/v0/appIvAiRsGZRbtwY7/tblaOkJlBzzfDIzl2?maxRecords=1" \
  -H "Authorization: Bearer pat6VmW5CHTS3yid7.1196a4e3d39bf3ad8cfd3cbabe99f96c9281d4444eb75a5d838f5adc4a65f23d"
```

### 2. Migration hébergement : GitHub Pages → Wix

L'outil était hébergé sur GitHub Pages (`https://stand4you.com/devis.html`). Il doit migrer vers **Wix** dans le cadre du déploiement du site web S4U.

**Recommandation d'hébergement sur Wix :**

Wix ne permet pas d'héberger des fichiers HTML arbitraires directement (ce n'est pas un hébergement de fichiers statiques classique). Les options sont :

**Option A — Wix Velo (recommandée)**
Wix Velo permet d'intégrer du code custom dans des pages Wix. L'outil peut être intégré dans une page Wix dédiée via un composant HTML embarqué (iFrame ou injection directe via Velo). Avantage : reste dans l'écosystème Wix, accès via une URL propre type `stand4you.com/devis`.

Étapes :
1. Dans Wix Editor → "Ajouter des éléments" → "Intégrer et connecter" → "Intégration HTML (iFrame)"
2. Coller le contenu de `devis.html` dans le composant HTML
3. Ajuster la hauteur du composant pour qu'il occupe toute la page (min 900px)
4. Publier la page en accès restreint (connexion requise — usage interne uniquement)

Limite : les iFrames Wix ont des contraintes de taille et certaines API navigateur (window.print(), window.open()) peuvent être bloquées par le contexte iFrame.

**Option B — Wix + fichier hébergé ailleurs (fallback)**
Si les contraintes iFrame posent problème pour l'impression PDF :
- Héberger `devis.html` sur **Google Drive** (partage public) ou sur un **bucket Google Cloud Storage**
- Pointer depuis Wix vers cette URL externe
- Avantage : aucune contrainte iFrame, window.print() fonctionne
- Inconvénient : URL moins propre

**Option C — Garder GitHub Pages temporairement**
Si la migration Wix est bloquante à court terme, GitHub Pages peut rester l'hébergeur le temps de stabiliser l'outil. Le domaine `stand4you.com` peut pointer vers GitHub Pages via CNAME.

→ **Commencer par tester l'Option A** (Velo iFrame). Si window.print() est bloqué → basculer sur Option B.

---

## Architecture de l'outil (résumé)

- **Single-file HTML** — pas de framework, pas de dépendances CDN sauf Google Fonts
- **100% Airtable** — pas de localStorage, pas de backend
- L'outil s'ouvre via `?id=recXXX` (record ID Airtable)
- Sauvegarde automatique debounce 2s → `atSave()`
- `render()` reconstruit tout le DOM depuis l'objet `st`
- `updT()` met à jour uniquement les totaux sans re-render

---

## État de l'outil — version actuelle (v7)

### ✅ Fonctionnel
- Chargement depuis Airtable via `?id=recXXX`
- 13 rubriques de prestations avec catalogue FR/EN
- Rubrique 1 "Étude & Maîtrise d'œuvre" avec Phase 1 et Phase 2
- Rubrique 12 "Stockage" avec calcul Qté × P.U. × période
- Calculs : Total HT, remise (%/€), 3 modes TVA (FR/UE/Export)
- Acompte configurable en %, solde calculé
- Blocs légaux éditables (non inclus, conditions financières, PI)
- Traduction FR/EN complète
- Génération PDF : header navy, logo PNG, titre DEVIS centré, sous-titre doré, tableau prestations, totaux, CGPLV 10 articles, zone signatures
- Bloc signataire dynamique (Raphaël / Jérôme selon `Créé par` Airtable)
- Alertes pré-PDF non bloquantes (client manquant, adresse, N° TVA UE)
- Rubriques vides masquées dans le PDF
- Impression auto au chargement de la fenêtre PDF (500ms)
- Verrouillage interface si statut Accepté/Refusé
- Header app en navy (logo, nom, tagline)
- N° TVA client affiché dans le bloc client éditeur
- localStorage supprimé (outil 100% Airtable)

### ⚠️ Backlog prioritaire
1. **Webhook Make → Pennylane** — payload JSON prêt dans `triggerMake()`, constante `MAKE_WEBHOOK` vide. Scénario Make à construire : déclencheur = statut Airtable passe à "Accepté" → créer devis dans Pennylane.
2. **Statut "Expiré"** — à ajouter dans Airtable (single select) + dictionnaire couleurs dans l'outil + automatisation Airtable : `Date_Expiration < TODAY()` ET `Statut = "Envoyé"` → passer à "Expiré".
3. **Date_Expiration** — champ Formula Airtable à créer : `DATEADD({Date_Emission}, {Validite_jours}, 'days')`.
4. **Onglets Remontage / Stockage / Mobilier** — placeholders "bientôt disponible", types `r`, `s`, `m` dans `st.type`.
5. **CGPLV externalisée** — actuellement codée en dur dans `buildPDF()`. Envisager champ Attachment Airtable à moyen terme.
6. **Numéros de téléphone dans le pied de page PDF** — format `+33 6 XX XX XX XX` (sans le 0 initial) à vérifier.

### ❌ Non implémenté
- Interface Airtable pour Jérôme : opérationnelle côté Airtable, mais le formulaire de création redirige vers `devis.html?id={record_id}` — à tester sur le nouvel hébergement.

---

## Credentials et références

### Airtable
```
Token   : pat6VmW5CHTS3yid7.1196a4e3d39bf3ad8cfd3cbabe99f96c9281d4444eb75a5d838f5adc4a65f23d
Base    : appIvAiRsGZRbtwY7
Devis   : tblaOkJlBzzfDIzl2
Client  : tblZwYcnFAM6Pk91a
Salon   : tblx2Oy75AR9vX6lR
Evnt    : tblKA36jWxmadAKgM
```

### Make
```
Webhook : MAKE_WEBHOOK (constante dans devis.html — vide actuellement)
Scénario à créer : Airtable → Pennylane — Création devis
```

### Identité légale S4U
```
Dénomination  : Stand 4 You
Forme         : SAS
Capital       : 5 000 €
SIRET         : 102 806 783 00019
RCS           : Nice
TVA           : FR 34 102 806 783
APE           : 43.32A
Siège         : 485, route de Saint-Sébastien – 06950 Falicon
Email         : contact@stand4you.com
Site          : stand4you.com
```

### Signataires
```
Raphaël Flipo  — Co-fondateur · Stratégie & Développement
  raphael.flipo@stand4you.com · +33 6 27 81 33 08

Jérôme Baglan  — Co-fondateur · Technique & Commercial
  jerome.baglan@stand4you.com · +33 6 64 43 22 75
```

---

## Conventions de développement (non négociables)

- **Code modulaire** : chaque fonction fait une seule chose
- **Documenté** : commentaires sur les blocs logiques
- **Error handling** : try/catch sur toutes les opérations Airtable
- **Livrer le fichier HTML complet** — pas de diffs partiels
- **Pas de framework JS** — pas de React, Vue, etc.
- **Pas de dépendances** sauf Google Fonts
- Tester un appel Airtable avant toute livraison de code modifiant les credentials

---

## Consignes de communication

- Réponses en **français**
- Noms de menus/rubriques en **français** (Wix, Airtable, GitHub)
- Réponses directes et actionnables — pas de théorie sans application concrète
- Pour toute tâche technique complexe → proposer **2 options** : rapide/simple ET robuste/évolutive
- Si ambiguïté → poser une question ciblée avant de coder
