# Docker

## Prerequis

- Docker Desktop lance
- un fichier `.env` a la racine du projet

Tu peux partir de `\.env.example` :

```powershell
Copy-Item .env.example .env
```

Si tu veux importer des matchs Riot, renseigne `RIOT_KEY` dans `.env`.

## Lancer le projet

```powershell
docker compose up --build
```

## Acces

- Frontend: http://localhost
- API Django: http://localhost:8000/api/
- Swagger: http://localhost:8000/swagger/

## Ce que fait la configuration

- `api` construit le backend Django dans `back/Dockerfile`
- `frontend` construit le frontend Preact puis le sert via Nginx
- les requetes `/api/...` du frontend sont proxifiees vers le conteneur Django
- la base SQLite reste dans `back/import_db.sqlite3` via le montage du dossier `back`
