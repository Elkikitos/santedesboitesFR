# santedesboitesFR
Permet de comprendre la dynamique de santé des entreprises en France. Basée sur une source officielle open data FR. 
App à utiliser en local avec call api au clic. 

Créé par Jerome TOSCANO_ Free to use

# Annonces BODACC en France

Application cartographique pour explorer les annonces commerciales du BODACC (Bulletin officiel des annonces civiles et commerciales) : immatriculations, créations d’établissement, modifications, ventes et cessions, radiations, procédures collectives, dépôts des comptes… par région, département et commune.

Tout tient dans un fichier HTML autonome, sans installation : un double-clic suffit pour l’ouvrir. Deux petits scripts Python, facultatifs, permettent de joindre le BODACC de façon fiable et d’embarquer toutes les annonces pour un usage hors ligne.

> Le BODACC publie des événements juridiques. Une « cession » est une vente conclue, pas une entreprise à vendre.

## Ce que fait l’application

- **Fenêtre d’accueil** avec des questions toutes prêtes (« Les défaillances d’entreprises dans le Gers », « La dynamique de création d’entreprises dans le Rhône »…) ou à composer (thème + territoire) : la carte et les chiffres se règlent automatiquement.
- **Deux grands indicateurs** : *entreprises qui vont bien* (immatriculations et créations d’établissement) et *entreprises en difficulté* (procédures collectives, conciliations, rétablissements professionnels), rapportés à 10 000 habitants et comparés à la France.
- **Carte de France** : un cercle par département, ou par commune une fois un département choisi, dont l’anneau est découpé par statut d’annonce, chacun avec sa couleur.
- **Filtres** par zone (région, département, commune), période (année en cours par défaut), secteur d’activité et taille (capital social, ou prix déclaré pour les cessions).
- **Indicateurs de dynamique** sur la carte et dans le panneau :
  - solde net = immatriculations + créations d’établissement − radiations, aussi ramené à 10 000 habitants ;
  - pression des défaillances = procédures collectives pour 100 immatriculations ;
  - comparaison systématique à la France entière et graphique du solde mois par mois.
- **Détail par statut**, classé à partir du texte des annonces : nature du jugement, motif de radiation, type de modification, catégorie d’immatriculation, secteur d’activité, type de dépôt des comptes.
- **Dynamique par secteur** : un tableau croisant secteurs et statuts (immatriculations, créations, cessions, radiations, procédures collectives).
- **Détail des cessions** : secteur, prix médian déclaré, tranches de prix, liste triable.
- **Listes d’annonces** filtrables et exportables en CSV, avec un lien vers chaque annonce sur bodacc.fr.
- **Interface repliable** : menu des statuts et panneau de droite masquables, réglages mémorisés dans le navigateur.
- **Guide d’utilisation intégré** : bouton « Guide » en haut de l’écran, ou adresse terminée par `#guide`.

## Démarrage rapide

### 1. Ouvrir le fichier

Téléchargez `annonces-bodacc-france.html` et ouvrez-le dans un navigateur récent (Chrome, Edge, Firefox ou Safari).

Les cessions de janvier 2025 à juin 2026 sont embarquées dans le fichier. Les autres statuts sont lus en direct dans l’API du BODACC si le navigateur l’autorise depuis un fichier local, ce qui n’est pas toujours le cas.

### 2. Lancer le serveur local (recommandé)

```bash
python lancer_bodacc.py
```

Le script :

1. teste la connexion au BODACC et affiche le résultat dans le terminal ;
2. ouvre l’application sur http://localhost:8000 ;
3. relaie les requêtes de l’application vers le BODACC. C’est Python qui interroge l’API, ce qui évite les blocages du navigateur entre sites (CORS).

Laissez la fenêtre du terminal ouverte pendant l’utilisation ; `Ctrl+C` pour arrêter.

### 3. Construire la base complète (hors ligne)

Depuis l’application lancée avec `lancer_bodacc.py`, cliquez sur **« Actualiser la base complète »**, ou en ligne de commande :

```bash
python construire_base_bodacc.py
```

Le script produit `annonces-bodacc-france-complet.html`, qui contient les annonces de tous les statuts et fonctionne sans connexion.

| Option | Effet |
|---|---|
| `--departements 33,24,40` | Limite le détail annonce par annonce à ces départements. Les volumes par statut restent nationaux. |
| `--depuis 2025-01-01` | Début de la période. Le 1er janvier 2025 est le plus tôt possible. |
| `--jusqu 2026-11-08` | Fin de la période. Par défaut : aujourd’hui. |
| `--tout` | Ajoute le détail des modifications et des dépôts des comptes. Plusieurs millions d’annonces : fichier très lourd. |
| `--sortie fichier.html` | Nom du fichier produit. |

Les téléchargements sont mis en cache dans `.cache_bodacc/`. Une exécution interrompue reprend là où elle s’était arrêtée, et une actualisation ne retélécharge que les semaines récentes.

La première construction pour la France entière est longue (plusieurs centaines de téléchargements). Commencer par quelques départements permet d’essayer rapidement.

### Prérequis

- Un navigateur récent, avec la prise en charge de `DecompressionStream`.
- Pour le fond de carte CARTO, une clé d’API gratuite à demander sur [carto.com/basemaps/apikey](https://carto.com/basemaps/apikey/). Saisissez-la dans le champ « Clé d’API CARTO » en haut de l’application ; elle est gardée dans le navigateur, jamais dans le fichier. Si vous restreignez la clé à des domaines, autorisez `localhost`. Sans clé, choisissez « OpenStreetMap » ou « Aucun (contours seuls) ».
- Python 3.8 ou plus récent pour les scripts. Ils n’utilisent que la bibliothèque standard.
- Derrière un proxy d’entreprise, définissez `HTTPS_PROXY` (et `HTTP_PROXY`) avant de lancer les scripts.

## Contenu du dépôt

| Fichier | Rôle |
|---|---|
| `annonces-bodacc-france.html` | L’application : interface, carte (Leaflet), contours, référentiel des communes et cessions embarquées. Sert aussi de modèle au script de construction. |
| `lancer_bodacc.py` | Serveur local : sert l’application, relaie l’API du BODACC et pilote l’actualisation de la base. |
| `construire_base_bodacc.py` | Télécharge les annonces de tous les statuts et produit le fichier complet. |
| `README.md` | Ce document. |

### Fonctionnement technique

- **Données embarquées** : elles sont stockées en JSON compressé (gzip), puis encodé en base64, dans une balise `<script id="payload">`. Le navigateur les décompresse au chargement avec `DecompressionStream`.
- **Contenu de la base complète** : `construire_base_bodacc.py` ajoute une clé `extra` aux données embarquées. Elle contient les volumes par mois, département, commune et statut, plus une ligne par annonce pour les statuts détaillés : date, commune, SIREN, capital social, et des index vers des dictionnaires (activité, nature, catégorie, motif).
- **Sources selon le mode** : sans base complète, l’application interroge l’API Opendatasoft v2.1 du BODACC, avec des agrégations `group_by` pour les volumes et `records` pour les listes. Avec la base complète, tout est calculé localement.
- **Cessions récentes** : celles publiées après le jeu de référence sont récupérées automatiquement et gardées dans le navigateur (IndexedDB).
- **Adresses de l’API** : `www.bodacc.fr/api/explore/v2.1/…` en priorité, `bodacc-datadila.opendatasoft.com` en secours.

## Méthode et limites

- **Secteur** : il est déduit de mots-clés appliqués à l’activité déclarée, car le BODACC ne publie pas de code NAF. « Non classé » regroupe surtout les annonces sans activité renseignée.
- **Nature des jugements, motifs de radiation, types de modification** : ils sont classés par mots-clés sur le texte des annonces. Ces classements sont indicatifs ; la catégorie « non précisé » apparaît quand le texte ne permet pas de trancher.
- **Prix de cession** : c’est le prix du fonds ou des titres tel que déclaré dans l’annonce, pas une valorisation d’entreprise. Environ 30 % des annonces de cession n’en publient pas.
- **Taille** : le BODACC ne publie ni effectif ni chiffre d’affaires. Elle est approchée par le capital social déclaré, et par le prix de cession pour les ventes. Les entreprises individuelles n’ont pas de capital social et sont classées « Non renseignée ».
- **Filtres secteur et taille en mode direct** : ils s’appliquent au détail par statut, aux listes et aux cessions, mais pas aux volumes de la carte, que l’API fournit sans ces dimensions. Avec la base complète, tout est filtré.
- **Défaillances** : l’indicateur compte toutes les annonces de procédures collectives (ouvertures, plans, clôtures…), pas seulement les ouvertures.
- **Solde net** : les créations d’établissement peuvent concerner des entreprises déjà immatriculées, ce qui le gonfle un peu.
- **Doublons** : une même opération peut donner lieu à plusieurs annonces (plusieurs greffes, rectificatifs). Aucun dédoublonnage n’est fait.
- **Communes** : elles sont reconnues d’après le nom de commune de l’annonce, pour environ 98 % des cessions. Les noms non reconnus comptent dans leur département sans apparaître en point sur la carte.
- **Échantillon en mode direct** : sans base complète, le détail par statut porte sur les 1 000 annonces les plus récentes de la sélection (extensible jusqu’à 10 000).

## Données personnelles

Les annonces du BODACC sont publiques, mais l’application ne conserve aucun nom de personne ni d’entreprise, ni de mandataire. Elle garde uniquement la date, la commune, le SIREN, le capital social, l’activité déclarée et la nature de l’annonce. Le champ des personnes est lu pour en extraire le seul montant du capital, puis écarté. Chaque ligne renvoie à l’annonce officielle sur bodacc.fr.

## Sources et licences

| Élément | Source | Licence |
|---|---|---|
| Annonces commerciales | [BODACC](https://www.bodacc.fr), DILA | Licence Ouverte Etalab |
| Cessions ligne à ligne 2025 – S1 2026 (prix extrait, secteur normalisé) | [Passage Transmission sur data.gouv.fr](https://www.data.gouv.fr/datasets/cessions-dentreprises-au-bodacc-ligne-a-ligne-avec-prix-et-secteur) | Licence Ouverte |
| Contours des départements et communes | [france-geojson](https://github.com/gregoiredavid/france-geojson), d’après IGN Admin Express | Licence Ouverte |
| Communes, départements, régions, populations | [@etalab/decoupage-administratif](https://github.com/etalab/decoupage-administratif) | MIT (code) ; données Licence Ouverte |
| Bibliothèque cartographique | [Leaflet](https://leafletjs.com) 1.9.4 | BSD-2-Clause |
| Fonds de carte (affichés en ligne seulement) | © [OpenStreetMap](https://www.openstreetmap.org/copyright), © [CARTO](https://carto.com/attributions) (clé d’API requise) | [Conditions CARTO](https://carto.com/legal/basemap-terms/), [politique d’usage des tuiles OSM](https://operations.osmfoundation.org/policies/tiles/) |
| Police | Source Sans 3 (Google Fonts) | SIL Open Font License |

Le code de l’application est publié sous licence **MIT** (voir `LICENSE`). Les données conservent leurs licences d’origine ; mentionnez les sources ci-dessus en cas de réutilisation.

## Contribuer

Les contributions sont bienvenues, en particulier pour :

- affiner les règles de classement (secteurs, natures de jugement, motifs de radiation) à partir d’intitulés réels ;
- ajouter un dédoublonnage des annonces publiées par plusieurs greffes ;
- proposer d’autres indicateurs ou d’autres découpages territoriaux (EPCI, bassins d’emploi).

Pour signaler un problème, ouvrez une *issue* en joignant la ligne d’erreur affichée par le script ou par l’application.
