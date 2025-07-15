from typing import Tuple
import requests
import os

RIOT_API_KEY = os.getenv("RIOT_KEY")
HEADERS = {"X-Riot-Token": RIOT_API_KEY}
# Table de correspondance « région LoL » ➔ « cluster de routage API »
REGION_TO_CLUSTER = {
    "br1":  "americas",
    "eun1": "europe",
    "euw1": "europe",
    "jp1":  "asia",
    "kr":   "asia",
    "la1":  "americas",
    "la2":  "americas",
    "na1":  "americas",
    "oc1":  "americas",
    "tr1":  "europe",
    "ru":   "europe",
}

def get_riot_id_by_puuid(
    puuid: str,
    region: str = "euw1",
    timeout: int = 10
) -> Tuple[str, str]:
    """
    Retourne (gameName, tagLine) pour un PUUID donné.

    Parameters
    ----------
    puuid : str
        Le PUUID (78 caractères).
    api_key : str
        Votre clé API Riot (développement : valable 24 h).
    region : str, optional
        Région LoL du joueur (« euw1 », « na1 », etc.). Default « euw1 ».
    timeout : int, optional
        Timeout réseau en secondes. Default 10.

    Raises
    ------
    ValueError
        Si la région est inconnue.
    RuntimeError
        Si l’API répond par une erreur (404, 429, etc.).
    """
    cluster = REGION_TO_CLUSTER.get(region.lower())
    if not cluster:
        raise ValueError(f"Région inconnue : {region}")

    url = f"https://{cluster}.api.riotgames.com/riot/account/v1/accounts/by-puuid/{puuid}"
    headers =HEADERS

    response = requests.get(url, headers=headers, timeout=timeout)

    if response.status_code == 200:
        data = response.json()
        return data.get("gameName"), data.get("tagLine")
    elif response.status_code == 404:
        raise RuntimeError("Aucun compte trouvé pour ce PUUID.")
    elif response.status_code == 429:
        raise RuntimeError("Limite de requêtes dépassée (HTTP 429).")
    else:
        raise RuntimeError(f"Erreur {response.status_code} : {response.text}")
