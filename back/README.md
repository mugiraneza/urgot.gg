# Backend

## Aperçu

Le backend est une application Django + Django REST Framework qui :

- importe les matchs League of Legends depuis les API Riot
- stocke les données dans une base locale SQLite
- expose des endpoints REST pour le frontend local
- calcule des vues statistiques à partir des matchs importés
- sert les assets Riot téléchargés localement

## Stack

- Django 5.2
- Django REST Framework
- drf-yasg
- SQLite
- requests
- matplotlib
- joblib

## Arborescence utile

- [manage.py](C:/git/urgot.gg/back/manage.py) : point d’entrée Django
- [back/settings.py](C:/git/urgot.gg/back/back/settings.py) : configuration principale
- [back/urls.py](C:/git/urgot.gg/back/back/urls.py) : routes globales + Swagger
- [api/models.py](C:/git/urgot.gg/back/api/models.py) : modèles métier
- [api/views.py](C:/git/urgot.gg/back/api/views.py) : endpoints REST
- [api/services/riot_importer.py](C:/git/urgot.gg/back/api/services/riot_importer.py) : import des matchs Riot
- [api/services/import_champions_items.py](C:/git/urgot.gg/back/api/services/import_champions_items.py) : import des champions et objets
- [api/tests.py](C:/git/urgot.gg/back/api/tests.py) : tests backend

## Variables d’environnement

Le backend attend au minimum :

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `RIOT_KEY`

La configuration est chargée par [back/settings.py](C:/git/urgot.gg/back/back/settings.py) via `back.env`.

### Fichier `env.py` à créer

Avant de lancer le backend, il faut créer le fichier :

- [urgot.gg/back/back/env.py](urgot.gg/back/back/env.py)

Ce fichier doit se trouver directement dans le dossier [back/back](urgot.gg/back/back), au même niveau que [settings.py](urgot.gg/back/back/settings.py).

voici le contenu minimal de se ficher:

```python
import os


def setEnv():
    # Base de données PostgreSQL
    os.environ['POSTGRES_DBNAME']='lol_data_full'
    os.environ['POSTGRES_USER']=''
    os.environ['POSTGRES_PASS']=''
    os.environ['POSTGRES_HOST']='db'
    os.environ['POSTGRES_PORT']='5432'

    # Django
    os.environ['DJANGO_SECRET_KEY']="j|X@C:hN$xxxxxxxxxxxxxx|@ibw$WXO|U$wxxxxxxxxxxxxxxxxxxxxxx.R"
    os.environ['DJANGO_DEBUG']='True'
    os.environ['DJANGO_ALLOWED_HOSTS']='localhost,127.0.0.1'

    #  RIOT
    os.environ['RIOT_KEY']='RGAPI-xxxxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxx'
```

### Où trouver la clé API Riot

La clé Riot se récupère sur le portail officiel Riot Developer :

- [Riot Developer Portal](https://developer.riotgames.com/docs/portal)

D’après la documentation officielle, il suffit de se connecter au portail avec un compte Riot pour obtenir une clé de développement associée au compte. La documentation précise aussi que :

- une `development API key` est générée à la connexion au portail
- cette clé expire toutes les 24 heures et doit être régénérée régulièrement
- pour un usage plus durable, il faut enregistrer son projet afin de demander une clé `personal` ou `production`

Tu peux donc commencer avec une clé de développement pour les tests locaux, puis passer à une clé plus stable si le projet évolue.

## Installation locale

Depuis la racine du projet :

```powershell
venv\Scripts\activate
pip install -r requirements.txt
cd back
python manage.py migrate
python manage.py runserver
```

Le backend démarre sur `http://127.0.0.1:8000`.

Si le projet ne démarre pas, vérifie d’abord que [env.py](C:/git/urgot.gg/back/env.py) existe bien et que `RIOT_KEY` est renseignée.

## Base de données

Le projet utilise actuellement une base SQLite locale :

- [import_db.sqlite3](C:/git/urgot.gg/back/import_db.sqlite3)

Le fichier est déclaré dans [back/settings.py](C:/git/urgot.gg/back/back/settings.py).

## Documentation API

Une fois le backend lancé :

- Swagger UI : [http://127.0.0.1:8000/swagger/](http://127.0.0.1:8000/swagger/)
- ReDoc : [http://127.0.0.1:8000/redoc/](http://127.0.0.1:8000/redoc/)

## Fonctionnalités principales

### Import Riot

Le service [riot_importer.py](C:/git/urgot.gg/back/api/services/riot_importer.py) permet de :

- résoudre un `Riot ID` en `puuid`
- récupérer les ids de matchs
- importer les matchs, participants, équipes, bans, objectifs et morts
- enrichir les participants avec le rang courant
- enregistrer un snapshot LP après import

### Import champions et objets

Le service [import_champions_items.py](C:/git/urgot.gg/back/api/services/import_champions_items.py) :

- importe les champions depuis Data Dragon
- importe les objets et leurs relations `from` / `into`
- télécharge les assets Riot localement

### Dashboard frontend

Les endpoints `/api/front/...` servent une vue simplifiée et agrégée pour le frontend :

- dashboard global
- liste paginée des matchs
- historique des `Riot ID` récents

## Cache

Le backend utilise le cache Django pour conserver les `Riot ID` récemment recherchés.

Ce cache sert notamment à :

- réafficher rapidement les recherches récentes
- alimenter les suggestions du champ de recherche dans le frontend

## Suivi du LP

Le backend stocke des snapshots de rang dans le modèle `RankSnapshot`.

### Fonctionnement

- le rang courant est lu via l’API Riot `league-v4`
- un snapshot est associé au match le plus récent du lot importé
- le frontend peut ensuite construire une courbe d’évolution LP

### Limite

L’API Riot ne fournit pas le delta de LP exact dans les données de match.  
Le système suit donc correctement l’évolution au fil des imports, mais ne peut pas reconstruire parfaitement un historique LP ancien match par match.

## Tests

Lancer les tests backend :

```powershell
venv\Scripts\python.exe back\manage.py test
```

Pour des tests ciblés :

```powershell
venv\Scripts\python.exe back\manage.py test api.tests.FrontApiViewTests api.tests.RiotImporterAdvancedFieldsTests
```
