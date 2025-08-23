import pandas as pd
from sklearn.preprocessing import OneHotEncoder

# Charger le fichier CSV
df = pd.read_csv('matches.csv')

# Vectorisation des champions alliés (ally_champ1 à ally_champ4)
ally_columns = ['ally_champ1', 'ally_champ2', 'ally_champ3', 'ally_champ4']
ally_champs = df[ally_columns].stack().unique()  # Récupérer les champions uniques
ally_champs_dict = {champ: idx for idx, champ in enumerate(ally_champs)}

# Créer des colonnes binaires pour chaque champion allié
ally_columns_list = []
for champ in ally_champs:
    ally_columns_list.append(pd.DataFrame({
        f'ally_{champ}': df[ally_columns].apply(lambda row: champ in row.values, axis=1).astype(int)
    }))

# Concaténer les nouvelles colonnes alliées
df = pd.concat([df] + ally_columns_list, axis=1)

# Vectorisation des champions ennemis (enemy_champ1 à enemy_champ5)
enemy_columns = ['enemy_champ1', 'enemy_champ2', 'enemy_champ3', 'enemy_champ4', 'enemy_champ5']
enemy_champs = df[enemy_columns].stack().unique()  # Récupérer les champions uniques
enemy_champs_dict = {champ: idx for idx, champ in enumerate(enemy_champs)}

# Créer des colonnes binaires pour chaque champion ennemi
enemy_columns_list = []
for champ in enemy_champs:
    enemy_columns_list.append(pd.DataFrame({
        f'enemy_{champ}': df[enemy_columns].apply(lambda row: champ in row.values, axis=1).astype(int)
    }))

# Concaténer les nouvelles colonnes ennemies
df = pd.concat([df] + enemy_columns_list, axis=1)

# Vectorisation de la colonne 'lane' (Top, Mid, Bot) via OneHotEncoding
lane_encoder = OneHotEncoder(sparse_output=False)
lane_encoded = lane_encoder.fit_transform(df[['lane']])

# Ajouter les nouvelles colonnes 'lane_Top', 'lane_Middle', 'lane_Bottom'
lane_df = pd.DataFrame(lane_encoded, columns=lane_encoder.categories_[0])
df = pd.concat([df, lane_df], axis=1)

# Vectorisation de la colonne 'side' (RED, BLUE) via OneHotEncoding
side_encoder = OneHotEncoder(sparse_output=False)
side_encoded = side_encoder.fit_transform(df[['side']])

# Ajouter les nouvelles colonnes 'side_BLUE' et 'side_RED'
side_df = pd.DataFrame(side_encoded, columns=side_encoder.categories_[0])
df = pd.concat([df, side_df], axis=1)

# Vectorisation de la colonne 'champion' via OneHotEncoding
champion_encoder = OneHotEncoder(sparse_output=False)
champion_encoded = champion_encoder.fit_transform(df[['champion']])

# Ajouter les nouvelles colonnes 'champion_' suivi du nom du champion
champion_df = pd.DataFrame(champion_encoded, columns=champion_encoder.categories_[0])
df = pd.concat([df, champion_df], axis=1)

# Afficher le DataFrame avec les nouvelles colonnes vectorisées
# import caas_jupyter_tools as tools; tools.display_dataframe_to_user(name="DataFrame Vectorisé", dataframe=df)

# Sauvegarder le DataFrame avec les nouvelles colonnes
df.to_csv('fichier_vectorise.csv', index=False)
