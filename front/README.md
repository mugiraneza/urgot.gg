# Frontend local

## Stack

- Vite
- Preact
- JavaScript
- Chart.js

## Démarrage

1. Lancer le backend Django sur `http://127.0.0.1:8000`
2. Installer les dépendances :

```powershell
npm install
```

3. Lancer le front :

```powershell
npm run dev
```

Le proxy Vite redirige `/api/*` vers le backend Django local.  
Le frontend lit uniquement les endpoints internes `/api/front/...`, eux-mêmes alimentés par la base locale Django.

## Écrans inclus

- Liste paginée des matchs
- Panneau détail d'une partie
- Statistiques globales
- Tableau des champions
- Graphiques modes de jeu, LP et CS/min

## Recherches récentes

Les `Riot ID` recherchés récemment sont mis en cache à deux niveaux :

- côté backend via le cache Django
- côté frontend via `localStorage`

Le frontend fusionne les deux sources pour afficher une liste de suggestions récentes directement sous le champ de recherche.

## Suivi du LP

Le dashboard affiche une courbe `Évolution LP`.

### Fonctionnement

- le backend interroge l'état classé courant du joueur via l'API Riot `league-v4`
- un snapshot est enregistré après l'import des nouvelles parties
- le frontend lit ces snapshots via `/api/front/dashboard/`

### Limite importante

Riot ne fournit pas directement le `LP gagné/perdu` dans les données de match.  
Le suivi est donc fiable pour un import fait régulièrement au fil des parties, mais il ne permet pas de reconstruire parfaitement un historique LP ancien match par match après coup.

## UI

L'interface utilise un style neumorphique clair :

- cartes et panneaux en neo morphisme
