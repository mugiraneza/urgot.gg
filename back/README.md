# Backend

## Apercu

Le backend est une application Django + Django REST Framework qui :

- importe les matchs League of Legends depuis les API Riot
- stocke les donnees dans une base locale SQLite
- expose des endpoints REST pour le frontend local
- calcule des vues statistiques a partir des matchs importes

## Configuration

Le backend lit sa configuration :

- depuis les variables d'environnement du systeme
- depuis `C:/git/urgot.gg/.env`
- depuis `C:/git/urgot.gg/back/.env`

Variables minimales :

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `RIOT_KEY`

Exemple de fichier `.env` :

```env
DJANGO_SECRET_KEY=change-me
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,api
RIOT_KEY=RGAPI-xxxxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxx
```

## Lancement local

```powershell
venv\Scripts\activate
pip install -r requirements.txt
cd back
python manage.py migrate
python manage.py runserver
```

## Lancement Docker

Depuis `C:\git\urgot.gg` :

```powershell
Copy-Item .env.example .env
docker compose up --build
```

## URLs utiles

- API : http://127.0.0.1:8000/api/
- Swagger : http://127.0.0.1:8000/swagger/
- ReDoc : http://127.0.0.1:8000/redoc/

## Import batch des joueurs suivis

Quand un joueur lance un import manuel, son Riot ID est maintenant enregistre en base comme joueur suivi. Tu peux ensuite lancer un batch periodique pour reimporter tout le monde.

Un seul batch :

```powershell
python manage.py poll_tracked_imports --once
```

Service en boucle toutes les 30 minutes :

```powershell
python manage.py poll_tracked_imports --interval-minutes 30
```

En Docker, ce role est porte par le service `import-worker`.
