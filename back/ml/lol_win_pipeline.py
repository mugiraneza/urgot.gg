#py lol_win_pipeline.py --data matches.csv --feature_set pregame
#!/usr/bin/env python3 
import argparse 
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, roc_auc_score, brier_score_loss, classification_report
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
import joblib
import warnings

warnings.filterwarnings("ignore", category=UserWarning)

REQUIRED_PREGAME = [
    "win", "queue_type", "patch", "side", "rank_tier"
]

REQUIRED_POST10 = REQUIRED_PREGAME + ["kills_10", "deaths_10", "assists_10", "gold_10", "cs_10"]

def check_columns(df, required):
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Colonnes manquantes: {missing}")

def build_features(df, feature_set):
    # Mise à jour pour s'assurer que toutes les colonnes sont présentes
    if feature_set == "pregame":
        check_columns(df, REQUIRED_PREGAME)
        features = REQUIRED_PREGAME[1:]  # drop target 'win'
    elif feature_set == "post10":
        check_columns(df, REQUIRED_POST10)
        features = REQUIRED_POST10[1:]  # drop target 'win'
    else:
        raise ValueError("feature_set doit être 'pregame' ou 'post10'")

    # Séparation des colonnes catégorielles et numériques
    cat_cols = [c for c in features if df[c].dtype == "object"]
    num_cols = [c for c in features if c not in cat_cols]

    # Colonnes supplémentaires pour les champions (et les équipes)
    champion_columns = [champ for champ in df.columns if champ not in REQUIRED_PREGAME]
    ally_champs = [champ for champ in champion_columns if champ.startswith('ally_')]
    enemy_champs = [champ for champ in champion_columns if champ.startswith('enemy_')]

    # Créer des nouvelles colonnes indiquant si un champion est dans le côté BLUE ou RED
    blue_champs = [col for col in ally_champs if df.loc[df['side'] == 'BLUE', col].any()]
    red_champs = [col for col in enemy_champs if df.loc[df['side'] == 'RED', col].any()]

    features.extend(blue_champs + red_champs)  # Ajouter les champions par équipe

    return features, cat_cols, num_cols


def build_pipeline(cat_cols, num_cols):
    # Rendre OneHotEncoder dense quelle que soit la version de sklearn
    def make_ohe_dense():
        try:
            # scikit-learn >= 1.2
            return OneHotEncoder(handle_unknown="ignore", sparse_output=False)
        except TypeError:
            # scikit-learn < 1.2
            return OneHotEncoder(handle_unknown="ignore", sparse=False)

    cat_pipe = Pipeline([  # Pipeline pour les colonnes catégorielles
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("ohe", make_ohe_dense())
    ])

    num_pipe = Pipeline([  # Pipeline pour les colonnes numériques
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler())
    ])

    preproc = ColumnTransformer([  # Transformation des colonnes
        ("cat", cat_pipe, cat_cols),
        ("num", num_pipe, num_cols)
    ])

    from sklearn.ensemble import HistGradientBoostingClassifier
    model = HistGradientBoostingClassifier(
        learning_rate=0.08,
        max_depth=None,
        max_leaf_nodes=31,
        min_samples_leaf=20,
        l2_regularization=0.0,
        early_stopping=True,
        random_state=42
    )

    pipe = Pipeline([
        ("preproc", preproc),
        ("model", model)
    ])
    return pipe

def evaluate(pipe, X_train, y_train, X_test, y_test):
    # CV on the train split for a stable estimate
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_auc = cross_val_score(pipe, X_train, y_train, cv=cv, scoring="roc_auc")
    cv_acc = cross_val_score(pipe, X_train, y_train, cv=cv, scoring="accuracy")
    print(f"[CV] AUC: {cv_auc.mean():.3f} ± {cv_auc.std():.3f} | ACC: {cv_acc.mean():.3f} ± {cv_acc.std():.3f}")

    # Fit on full train then evaluate on test
    pipe.fit(X_train, y_train)
    proba = pipe.predict_proba(X_test)[:, 1]
    pred = (proba >= 0.5).astype(int)

    acc = accuracy_score(y_test, pred)
    auc = roc_auc_score(y_test, proba)
    brier = brier_score_loss(y_test, proba)
    print(f"[TEST] AUC: {auc:.3f} | ACC: {acc:.3f} | Brier: {brier:.3f}")
    print("\nClassification report:\n", classification_report(y_test, pred, digits=3))

    return proba

def permutation_importances(pipe, X_test, y_test, feature_names, top_k=25):
    try:
        r = permutation_importance(
            pipe, X_test, y_test,
            n_repeats=5, random_state=42, n_jobs=-1, scoring="roc_auc"
        )
        importances = pd.Series(r.importances_mean, index=feature_names)
        importances = importances.sort_values(ascending=False).head(top_k)
        print("\nTop features (permutation importance) sur features brutes :")
        print(importances.to_string())
    except Exception as e:
        print(f"Permutation importance échouée: {e}")

def main():
    print("#> py lol_win_pipeline.py --data matches.csv --feature_set pregame")
    parser = argparse.ArgumentParser(description="LoL Win Predictor")
    parser.add_argument("--data", type=str, required=True, help="Chemin vers matches.csv")
    parser.add_argument("--feature_set", type=str, default="pregame", choices=["pregame", "post10"], help="Jeu de features à utiliser")
    parser.add_argument("--test_size", type=float, default=0.2, help="Part de test")
    parser.add_argument("--out", type=str, default="win_model.pkl", help="Fichier de sortie du pipeline entraîné")
    args = parser.parse_args()

    df = pd.read_csv(args.data)

    # Basic cleaning
    df = df.dropna(subset=["win"]).copy()
    df["win"] = df["win"].astype(int)

    features, cat_cols, num_cols = build_features(df, args.feature_set)

    X = df[features]
    y = df["win"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=args.test_size, random_state=42, stratify=y
    )

    pipe = build_pipeline(cat_cols, num_cols)
    _ = evaluate(pipe, X_train, y_train, X_test, y_test)

    # Compute importances on the test set for a peek at what's predictive
    permutation_importances(pipe, X_test, y_test, feature_names=list(X.columns), top_k=25)

    # Refit on the full dataset before saving (optional but common)
    pipe.fit(X, y)
    joblib.dump(pipe, args.out)
    print(f"\n✅ Modèle enregistré dans: {args.out}")

if __name__ == "__main__":
    main()
