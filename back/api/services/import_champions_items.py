import os
import requests
from django.core.files.base import ContentFile
from api.models import Champion, Ability, Item
# URLs vers Data Dragon (version dynamique possible)
def get_latest_dd_version():
    try:
        response = requests.get("https://ddragon.leagueoflegends.com/api/versions.json")
        response.raise_for_status()
        versions = response.json()
        return versions[0]  # la dernière version
    except Exception as e:
        print("❌ Erreur lors de la récupération de la version DD:", e)
        return "14.14.1"
    
DD_VERSION = get_latest_dd_version()
BASE_URL = f"https://ddragon.leagueoflegends.com/cdn/{DD_VERSION}/"
CHAMP_LIST_URL = f"{BASE_URL}data/en_US/champion.json"
ITEM_LIST_URL = f"{BASE_URL}data/en_US/item.json"
CHAMP_DETAIL_URL_TEMPLATE = f"{BASE_URL}data/en_US/champion/{{champ_name}}.json"

ICON_URLS = {
    "champion": f"{BASE_URL}img/champion/",
    "spell": f"{BASE_URL}img/spell/",
    "item": f"{BASE_URL}img/item/"
}

    
def download_and_attach_image(model_instance, field_name, url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            file_name = url.split("/")[-1]
            getattr(model_instance, field_name).save(file_name, ContentFile(response.content), save=True)
    except Exception as e:
        print(f"Erreur image {url} : {e}")

def import_champions():
    print("▶️ Import champions...")
    champ_list = requests.get(CHAMP_LIST_URL).json()["data"]
    
    for champ_key, champ_data in champ_list.items():
        name = champ_data["name"]
        blurb = champ_data["blurb"]
        image_filename = champ_data["image"]["full"]
        champ_icon_url = ICON_URLS["champion"] + image_filename

        champion, _ = Champion.objects.get_or_create(name=name)
        champion.blurb = blurb
        download_and_attach_image(champion, "icon", champ_icon_url)
        champion.save()

        # Charger détails (skills)
        detail_url = CHAMP_DETAIL_URL_TEMPLATE.replace("{champ_name}", champ_key)
        detail_data = requests.get(detail_url).json()["data"][champ_key]

        for spell in detail_data.get("spells", []):
            ab = Ability.objects.create(
                champion=champion,
                name=spell["name"],
                targeting="N/A",
                affects="N/A",
                spellshieldable="N/A",
                resource=spell.get("costType", ""),
                damage_type="UNKNOWN",
                spell_effects=spell.get("description", ""),
                projectile="",
                on_hit_effects="",
                occurrence="",
                notes="",
                missile_speed="",
                recharge_rate="",
                collision_radius="",
                tether_radius="",
                on_target_cd_static="",
                inner_radius="",
                speed="",
                width="",
                angle="",
                cast_time="",
                effect_radius="",
                target_range=str(spell.get("range", "")),
            )
            # Télécharger icône du sort
            spell_img = spell["image"]["full"]
            download_and_attach_image(ab, "icon", ICON_URLS["spell"] + spell_img)
    print("✅ Import champions...")

def import_items():
    print("▶️ Import items...")
    item_data = requests.get(ITEM_LIST_URL).json()["data"]

    for item_id, item in item_data.items():
        it, _ = Item.objects.get_or_create(
            name=item.get("name", f"Item {item_id}"),
            defaults={
                "effects": item.get("description", ""),
                "unique": False,
                "mythic": "mythic" in item.get("description", "").lower(),
                "range": None,
                "cooldown": "",
                "stats": item.get("stats", {}),
                "purchasable": item.get("gold", {}).get("purchasable", True),
                "tags": item.get("tags", []),
                "total": item.get("gold", {}).get("total", 0),
                "combined": item.get("gold", {}).get("base", 0),
                "sell": item.get("gold", {}).get("sell", 0),
            }
        )
        icon_name = item.get("image", {}).get("full")
        if icon_name:
            download_and_attach_image(it, "icon", ICON_URLS["item"] + icon_name)
        it.save()
    print("✅ Import items...")
