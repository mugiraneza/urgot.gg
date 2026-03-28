# urgot.gg

## Aperçu

![Page d'acceuil](/front.png?raw=true "Page d'acceuil")

`urgot.gg` est un projet local d’analyse League of Legends construit autour d’une base de matchs importés depuis Riot.

Le projet permet de :

- importer les parties d’un joueur à partir de son `Riot ID`
- conserver les matchs et leurs détails dans une base locale
- afficher un dashboard frontend orienté historique et statistiques
- suivre les recherches récentes
- suivre l’évolution du LP au fil des imports

## Architecture

### Backend

Le backend Django :

- importe les données Riot
- stocke les matchs, participants, objets, champions et snapshots de rang
- expose les endpoints REST consommés par le frontend
- sert les assets Riot téléchargés localement

Documentation backend : [back/README.md](C:/git/urgot.gg/back/README.md)

### Frontend

Le frontend Preact :

- interroge uniquement les endpoints `/api/front/...`
- affiche un dashboard local avec une interface neumorphique
- propose une recherche avec suggestions de `Riot ID` récents
- affiche des graphiques pour les modes de jeu, le LP et le CS/min

Documentation frontend : [front/README.md](C:/git/urgot.gg/front/README.md)

## Structure du dépôt

- [back](C:/git/urgot.gg/back) : backend Django
- [front](C:/git/urgot.gg/front) : frontend Vite/Preact
- [static](C:/git/urgot.gg/static) : assets statiques de projet 
- [docker-compose.yml](C:/git/urgot.gg/docker-compose.yml) : orchestration Docker (ne fonctionne pas encore)
- [requirements.txt](C:/git/urgot.gg/requirements.txt) : dépendances Python racine

## Fonctionnalités clés

### Import des matchs

Le backend importe les matchs via Riot et remplit la base locale avec :

- métadonnées de match
- participants
- rang courant du joueur importé
- objets et champions liés
- chronologie de morts et progression des sorts

### Recherches récentes

Les `Riot ID` récents sont conservés :

- côté backend via le cache Django
- côté frontend via `localStorage`

Cela permet un affichage rapide des suggestions récentes même avant le retour complet de l’API.

### Suivi LP

Le projet suit l’évolution du LP par snapshots :

- après un import de nouvelles parties, le backend enregistre l’état classé courant
- le frontend affiche ensuite une courbe `Évolution LP`

Limite importante :
Riot ne fournit pas le `LP gagné/perdu` directement dans les données du match. Le suivi est donc pensé pour un usage au fil de l’eau, pas pour reconstituer parfaitement un historique ancien.

## Démarrage rapide

### Préparer `env.py`

Avant de lancer le backend, il faut créer :

- [back/env.py](C:/git/urgot.gg/back/env.py)

Exemple :

```python
import os


def setEnv():
    os.environ.setdefault("DJANGO_SECRET_KEY", "change-me-dev-secret")
    os.environ.setdefault("DJANGO_DEBUG", "True")
    os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost")
    os.environ.setdefault("RIOT_KEY", "RGAPI-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
```

La clé Riot se récupère sur le portail officiel :

- [Riot Developer Portal](https://developer.riotgames.com/docs/portal)

La documentation officielle indique qu’une clé de développement est générée quand on se connecte au portail avec son compte Riot. Elle expire toutes les 24 heures, donc il faut la renouveler régulièrement pour le développement local.

### Backend

```powershell
venv\Scripts\activate
pip install -r requirements.txt
cd back
python manage.py migrate
python manage.py runserver
```

### Frontend

Dans un second terminal :

```powershell
cd front
npm install
npm run dev
```

## URLs utiles

- Backend API : [http://127.0.0.1:8000/api/](http://127.0.0.1:8000/api/)
- Swagger : [http://127.0.0.1:8000/swagger/](http://127.0.0.1:8000/swagger/)
- ReDoc : [http://127.0.0.1:8000/redoc/](http://127.0.0.1:8000/redoc/)
- Frontend Vite : généralement [http://127.0.0.1:5173/](http://127.0.0.1:5173/)

## Notes techniques

- la base active actuelle est SQLite
- le frontend consomme une API simplifiée pensée pour l’interface locale
- l’UI suit un style neumorphique clair
- la liste de suggestions du champ de recherche est custom pour être stylable, contrairement à une `datalist` native

## Docker

Un fichier [docker-compose.yml](C:/git/urgot.gg/docker-compose.yml) est présent, mais la configuration actuelle semble viser un setup différent de la base SQLite locale utilisée par `back/settings.py`. Il peut servir de base, mais mérite une harmonisation avant usage en production ou en environnement partagé.
