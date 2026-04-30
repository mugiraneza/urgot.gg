# urgot.gg
![Page d'acceuil](/front.png?raw=true "Page d'acceuil")

Application locale d'analyse League of Legends avec :

- un backend Django dans [C:/git/urgot.gg/back](C:/git/urgot.gg/back)
- un frontend Preact dans [C:/git/urgot.gg/front](C:/git/urgot.gg/front)

## Configuration

Le projet n'utilise plus `env.py`.

La configuration est lue directement :

- depuis les variables d'environnement
- depuis [C:/git/urgot.gg/.env](C:/git/urgot.gg/.env)
- depuis [C:/git/urgot.gg/back/.env](C:/git/urgot.gg/back/.env)

Tu peux partir de [C:/git/urgot.gg/.env.example](C:/git/urgot.gg/.env.example).

Exemple minimal :

```env
DJANGO_SECRET_KEY=change-me
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,api
RIOT_KEY=
API_GUNICORN_WORKERS=2
RIOT_IMPORT_CACHE_MAX_SIZE=1000
API_MEM_LIMIT=768m
API_MEM_RESERVATION=512m
```

Reglage memoire utile si l'API consomme trop de RAM :

- `API_GUNICORN_WORKERS` controle le nombre de processus Gunicorn pour l'API.
- `RIOT_IMPORT_CACHE_MAX_SIZE` borne les caches memoire utilises par l'import Riot.
- `API_MEM_LIMIT` et `API_MEM_RESERVATION` limitent la RAM du conteneur API.

## Lancement Docker

Depuis `C:\git\urgot.gg` :

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Acces :

- Frontend : [http://localhost](http://localhost)
- API : [http://localhost:8000/api/](http://localhost:8000/api/)
- Swagger : [http://localhost:8000/swagger/](http://localhost:8000/swagger/)

## Lancement local

Backend :

```powershell
venv\Scripts\activate
pip install -r requirements.txt
cd back
python manage.py migrate
python manage.py runserver
```

Frontend :

```powershell
cd front
npm install
npm run dev
```

## Batch auto toutes les 30 minutes

Nouvelle approche recommandee : chaque joueur importe manuellement une premiere fois, ce qui l'inscrit dans la liste des joueurs suivis. Ensuite un service backend relance l'import pour tous les inscrits toutes les 30 minutes.

Lancer un seul batch :

```powershell
cd back
python manage.py poll_tracked_imports --once
```

Lancer le service en boucle :

```powershell
cd back
python manage.py poll_tracked_imports --interval-minutes 30
```

Avec Docker, ce batch est maintenant lance automatiquement via le service `import-worker` quand tu fais `docker compose up --build`.
