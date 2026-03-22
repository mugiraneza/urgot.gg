# Frontend local

## Stack

- Vite
- Preact
- JavaScript
- Chart.js

## Démarrage

1. Lancer le backend Django sur `http://127.0.0.1:8000`
2. Installer les dépendances:

```powershell
npm install
```

3. Lancer le front:

```powershell
npm run dev
```

Le proxy Vite redirige `/api/*` vers le backend Django local.
Le frontend lit uniquement les endpoints internes `/api/front/...`, eux-mêmes alimentés par la base locale Django.

## Ecrans inclus

- Liste paginée des matchs
- Panneau détail d'une partie
- Statistiques globales
- Tableau des champions
- Graphiques modes de jeu et CS/min
