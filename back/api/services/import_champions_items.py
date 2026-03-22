import requests
import time
from pathlib import Path
from urllib.parse import urlparse
from django.db import transaction
from django.conf import settings
from django.core.files.storage import default_storage

from api.models import Champion, ChampionInfo, ChampionPassive, ChampionSkin, ChampionSpell, ChampionSpellLevelTip, ChampionStats,Item, ItemFrom, ItemInto

# Import de la configuration

def get_image_config():
    return {'DOWNLOAD_IMAGES': True}
def should_download_images():
    return True
def should_download_image_type(image_type):
    return True
def get_download_delay():
    return 0.1
def get_download_timeout():
    return 30

class RiotDataImporter:
    def __init__(self):
        # URL de base pour l'API Data Dragon de Riot
        self.base_url = "https://ddragon.leagueoflegends.com"
        self.version = self.get_latest_version()
        self.champion_data_url = f"{self.base_url}/cdn/{self.version}/data/en_US/champion"
        self.item_data_url = f"{self.base_url}/cdn/{self.version}/data/en_US/item.json"
        
        # URLs pour les images
        self.champion_img_url = f"{self.base_url}/cdn/{self.version}/img/champion"
        self.passive_img_url = f"{self.base_url}/cdn/{self.version}/img/passive"
        self.spell_img_url = f"{self.base_url}/cdn/{self.version}/img/spell"
        self.item_img_url = f"{self.base_url}/cdn/{self.version}/img/item"
        self.skin_img_url = f"{self.base_url}/cdn/img/champion/splash"  # Pour les skins complets
        self.skin_loading_url = f"{self.base_url}/cdn/img/champion/loading"  # Pour les skins loading
        
        # Dossiers locaux pour stocker les images
        self.media_root = getattr(settings, 'MEDIA_ROOT', 'media')
        self.setup_image_directories()
        
    def setup_image_directories(self):
        """Crée les dossiers pour stocker les images"""
        directories = [
            'static/riot_images/champions',
            'static/riot_images/champions/skins',
            'static/riot_images/spells',
            'static/riot_images/passives',
            'static/riot_images/items',
        ]
        
        for directory in directories:
            path = Path(self.media_root) / directory
            path.mkdir(parents=True, exist_ok=True)
            
    def download_image(self, image_url, local_path, max_retries=3):
        """Télécharge une image et la sauvegarde localement avec retry et validation"""
        if not should_download_images():
            return None
            
        for attempt in range(max_retries):
            try:
                response = requests.get(image_url, timeout=get_download_timeout())
                response.raise_for_status()
                
                # Vérifie la taille de l'image
                content_length = response.headers.get('content-length')
                if content_length:
                    size_mb = int(content_length) / (1024 * 1024)
                    max_size = get_image_config().get('MAX_IMAGE_SIZE_MB', 10)
                    if size_mb > max_size:
                        print(f"⚠️ Image trop volumineuse ({size_mb:.2f}MB): {image_url}")
                        return None
                
                # Crée le dossier parent si nécessaire
                local_path = Path(self.media_root) / local_path
                local_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Sauvegarde l'image
                with open(local_path, 'wb') as f:
                    f.write(response.content)
                
                # Vérifie que le fichier n'est pas vide
                if local_path.stat().st_size == 0:
                    local_path.unlink()  # Supprime le fichier vide
                    raise Exception("Fichier téléchargé vide")
                
                # Retourne le chemin relatif pour la base de données
                return str(local_path.relative_to(self.media_root))
                
            except Exception as e:
                print(f"❌ Tentative {attempt + 1}/{max_retries} échouée pour {image_url}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)  # Pause avant retry
                continue
        
        print(f"❌ Échec définitif du téléchargement: {image_url}")
        return None
            
    def download_champion_image(self, image_filename):
        """Télécharge l'image d'un champion"""
        if not image_filename or not should_download_image_type('champion'):
            return None
            
        image_url = f"{self.champion_img_url}/{image_filename}"
        local_path = f"static/riot_images/champions/{image_filename}"
        return self.download_image(image_url, local_path)
    
    def download_spell_image(self, image_filename):
        """Télécharge l'image d'un sort"""
        if not image_filename or not should_download_image_type('spell'):
            return None
            
        image_url = f"{self.spell_img_url}/{image_filename}"
        local_path = f"static/riot_images/spells/{image_filename}"
        return self.download_image(image_url, local_path)
    
    def download_passive_image(self, image_filename):
        """Télécharge l'image d'une passive"""
        if not image_filename or not should_download_image_type('passive'):
            return None
            
        image_url = f"{self.passive_img_url}/{image_filename}"
        local_path = f"static/riot_images/passives/{image_filename}"
        return self.download_image(image_url, local_path)
    
    def download_item_image(self, image_filename):
        """Télécharge l'image d'un objet"""
        if not image_filename or not should_download_image_type('item'):
            return None
            
        image_url = f"{self.item_img_url}/{image_filename}"
        local_path = f"static/riot_images/items/{image_filename}"
        return self.download_image(image_url, local_path)
    
    def download_skin_splash(self, champion_name, skin_num):
        """Télécharge l'image splash d'un skin"""
        if not should_download_image_type('skin'):
            return None
            
        image_filename = f"{champion_name}_{skin_num}.jpg"
        image_url = f"{self.skin_img_url}/{image_filename}"
        local_path = f"static/riot_images/champions/skins/splash_{image_filename}"
        return self.download_image(image_url, local_path)
    
    def download_skin_loading(self, champion_name, skin_num):
        """Télécharge l'image loading d'un skin"""
        if not should_download_image_type('skin'):
            return None
            
        image_filename = f"{champion_name}_{skin_num}.jpg"
        image_url = f"{self.skin_loading_url}/{image_filename}"
        local_path = f"static/riot_images/champions/skins/loading_{image_filename}"
        return self.download_image(image_url, local_path)

        
    def get_latest_version(self):
        """Récupère la dernière version du jeu"""
        try:
            response = requests.get(f"{self.base_url}/api/versions.json")
            response.raise_for_status()
            versions = response.json()
            return versions[0]  # La première version est la plus récente
        except requests.RequestException as e:
            print(f"❌ Erreur lors de la récupération de la version: {e}")
            return "15.15.1"  # Version par défaut

    def get_champion_list(self):
        """Récupère la liste de tous les champions"""
        try:
            response = requests.get(f"{self.champion_data_url}.json")
            response.raise_for_status()
            return response.json()['data']
        except requests.RequestException as e:
            print(f"❌ Erreur lors de la récupération de la liste des champions: {e}")
            return {}

    def get_champion_details(self, champion_id):
        """Récupère les détails d'un champion spécifique"""
        try:
            response = requests.get(f"{self.champion_data_url}/{champion_id}.json")
            response.raise_for_status()
            return response.json()['data'][champion_id]
        except requests.RequestException as e:
            print(f"❌ Erreur lors de la récupération des détails de {champion_id}: {e}")
            return None

    def import_champions(self):
        """Importe tous les champions dans la base de données"""
        print("▶️ Import champions...")
        
        champions_list = self.get_champion_list()
        total_champions = len(champions_list)
        imported_count = 0
        
        for champion_id, champion_basic in champions_list.items():
            try:
                print(f"📥 Import de {champion_basic['name']}...")
                
                # Récupère les détails complets du champion
                champion_details = self.get_champion_details(champion_id)
                if not champion_details:
                    continue
                
                with transaction.atomic():
                    # Télécharge l'image du champion
                    champion_image_path = self.download_champion_image(champion_details['image']['full'])
                    
                    # Crée ou met à jour le champion principal
                    champion, created = Champion.objects.update_or_create(
                        champion_id=champion_id,
                        defaults={
                            'champion_id' : champion_details['key'],
                            'key': champion_details['key'],
                            'name': champion_details['name'],
                            'title': champion_details['title'],
                            'image_full': champion_image_path or champion_details['image']['full'],
                            'image_sprite': champion_details['image']['sprite'],
                            'image_group': champion_details['image']['group'],
                            'image_x': champion_details['image']['x'],
                            'image_y': champion_details['image']['y'],
                            'image_w': champion_details['image']['w'],
                            'image_h': champion_details['image']['h'],
                            'lore': champion_details.get('lore', ''),
                            'blurb': champion_details.get('blurb', ''),
                            'ally_tips': champion_details.get('allytips', []),
                            'enemy_tips': champion_details.get('enemytips', []),
                            'tags': champion_details.get('tags', []),
                            'partype': champion_details.get('partype', ''),
                            'version': self.version,
                        }
                    )
                    
                    # Importe les informations du champion
                    if 'info' in champion_details:
                        info_data = champion_details['info']
                        ChampionInfo.objects.update_or_create(
                            champion=champion,
                            defaults={
                                'attack': info_data.get('attack', 0),
                                'defense': info_data.get('defense', 0),
                                'magic': info_data.get('magic', 0),
                                'difficulty': info_data.get('difficulty', 0),
                            }
                        )
                    
                    # Importe les statistiques du champion
                    if 'stats' in champion_details:
                        stats_data = champion_details['stats']
                        ChampionStats.objects.update_or_create(
                            champion=champion,
                            defaults={
                                'hp': stats_data.get('hp', 0),
                                'hp_per_level': stats_data.get('hpperlevel', 0),
                                'mp': stats_data.get('mp', 0),
                                'mp_per_level': stats_data.get('mpperlevel', 0),
                                'move_speed': stats_data.get('movespeed', 0),
                                'armor': stats_data.get('armor', 0),
                                'armor_per_level': stats_data.get('armorperlevel', 0),
                                'spell_block': stats_data.get('spellblock', 0),
                                'spell_block_per_level': stats_data.get('spellblockperlevel', 0),
                                'attack_range': stats_data.get('attackrange', 0),
                                'hp_regen': stats_data.get('hpregen', 0),
                                'hp_regen_per_level': stats_data.get('hpregenperlevel', 0),
                                'mp_regen': stats_data.get('mpregen', 0),
                                'mp_regen_per_level': stats_data.get('mpregenperlevel', 0),
                                'crit': stats_data.get('crit', 0),
                                'crit_per_level': stats_data.get('critperlevel', 0),
                                'attack_damage': stats_data.get('attackdamage', 0),
                                'attack_damage_per_level': stats_data.get('attackdamageperlevel', 0),
                                'attack_speed_per_level': stats_data.get('attackspeedperlevel', 0),
                                'attack_speed': stats_data.get('attackspeed', 0),
                            }
                        )
                    
                    # # Importe les skins
                    # if 'skins' in champion_details:
                    #     # Supprime les anciens skins
                    #     champion.skins.all().delete()
                        
                    #     for skin_data in champion_details['skins']:
                    #         print(f"   📸 Téléchargement des images pour le skin: {skin_data.get('name', 'Sans nom')}")
                            
                    #         # Télécharge les images du skin (splash et loading)
                    #         splash_path = self.download_skin_splash(champion_details['id'], skin_data.get('num', 0))
                    #         loading_path = self.download_skin_loading(champion_details['id'], skin_data.get('num', 0))
                            
                    #         ChampionSkin.objects.create(
                    #             champion=champion,
                    #             skin_id=skin_data.get('id', ''),
                    #             num=skin_data.get('num', 0),
                    #             name=skin_data.get('name', ''),
                    #             chromas=skin_data.get('chromas', False),
                    #             splash_image=splash_path,
                    #             loading_image=loading_path,
                    #         )
                    
                    # Importe la passive
                    if 'passive' in champion_details:
                        passive_data = champion_details['passive']
                        
                        # Télécharge l'image de la passive
                        passive_image_path = self.download_passive_image(passive_data['image']['full'])
                        
                        ChampionPassive.objects.update_or_create(
                            champion=champion,
                            defaults={
                                'name': passive_data.get('name', ''),
                                'description': passive_data.get('description', ''),
                                'image_full': passive_image_path or passive_data['image'].get('full', ''),
                                'image_sprite': passive_data['image'].get('sprite', ''),
                                'image_group': passive_data['image'].get('group', ''),
                                'image_x': passive_data['image'].get('x', 0),
                                'image_y': passive_data['image'].get('y', 0),
                                'image_w': passive_data['image'].get('w', 0),
                                'image_h': passive_data['image'].get('h', 0),
                            }
                        )
                    
                    # Importe les sorts
                    if 'spells' in champion_details:
                        # Supprime les anciens sorts
                        champion.spells.all().delete()
                        
                        for order, spell_data in enumerate(champion_details['spells']):
                            # Télécharge l'image du sort
                            spell_image_path = self.download_spell_image(spell_data['image']['full'])
                            
                            spell = ChampionSpell.objects.create(
                                champion=champion,
                                spell_id=spell_data.get('id', ''),
                                name=spell_data.get('name', ''),
                                description=spell_data.get('description', ''),
                                tooltip=spell_data.get('tooltip', ''),
                                max_rank=spell_data.get('maxrank', 5),
                                cooldown=spell_data.get('cooldown', []),
                                cooldown_burn=spell_data.get('cooldownBurn', ''),
                                cost=spell_data.get('cost', []),
                                cost_burn=spell_data.get('costBurn', ''),
                                cost_type=spell_data.get('costType', ''),
                                spell_range=spell_data.get('range', []),
                                range_burn=spell_data.get('rangeBurn', ''),
                                effect=spell_data.get('effect', []),
                                effect_burn=spell_data.get('effectBurn', []),
                                vars=spell_data.get('vars', []),
                                image_full=spell_image_path or spell_data['image'].get('full', ''),
                                image_sprite=spell_data['image'].get('sprite', ''),
                                image_group=spell_data['image'].get('group', ''),
                                image_x=spell_data['image'].get('x', 0),
                                image_y=spell_data['image'].get('y', 0),
                                image_w=spell_data['image'].get('w', 0),
                                image_h=spell_data['image'].get('h', 0),
                                max_ammo=str(spell_data.get('maxammo', -1)),
                                resource=spell_data.get('resource', ''),
                                data_values=spell_data.get('datavalues', {}),
                                order=order,
                            )
                            
                            # Importe les level tips si disponibles
                            if 'leveltip' in spell_data:
                                leveltip_data = spell_data['leveltip']
                                ChampionSpellLevelTip.objects.create(
                                    spell=spell,
                                    label=leveltip_data.get('label', []),
                                    effect=leveltip_data.get('effect', []),
                                )
                
                imported_count += 1
                print(f"✅ {champion_details['name']} importé avec succès")
                
                # Petite pause pour éviter de surcharger l'API
                time.sleep(0.1)
                
            except Exception as e:
                print(f"❌ Erreur lors de l'import de {champion_basic.get('name', champion_id)}: {e}")
                continue
        
        print(f"✅ Import champions terminé: {imported_count}/{total_champions} champions importés")

    def get_items_data(self):
        """Récupère les données des objets"""
        try:
            response = requests.get(self.item_data_url)
            response.raise_for_status()
            return response.json()['data']
        except requests.RequestException as e:
            print(f"❌ Erreur lors de la récupération des objets: {e}")
            return {}

    def import_items(self):
        """Importe tous les objets dans la base de données"""
        print("▶️ Import items...")
        
        # Décommentez ces imports si vous avez ajouté les modèles Item
        # from your_app.models import Item, ItemFrom, ItemInto
        
        items_data = self.get_items_data()
        total_items = len(items_data)
        imported_count = 0
        
        print(f"📊 {total_items} objets trouvés")
        
        for item_id, item_data in items_data.items():
            try:
                print(f"📥 Import de {item_data.get('name', 'Sans nom')}...")
                
                # Décommentez ce bloc si vous avez les modèles Item
                with transaction.atomic():
                    # Or (coût) de l'objet
                    gold_data = item_data.get('gold', {})
                    
                    # Télécharge l'image de l'objet
                    item_image_path = self.download_item_image(item_data.get('image', {}).get('full', ''))
                    
                    # Crée ou met à jour l'objet
                    item, created = Item.objects.update_or_create(
                        item_id=item_id,
                        defaults={
                            'name': item_data.get('name', ''),
                            'description': item_data.get('description', ''),
                            'colloq': item_data.get('colloq', ''),
                            'plaintext': item_data.get('plaintext', ''),
                            'gold_base': gold_data.get('base', 0),
                            'gold_purchasable': gold_data.get('purchasable', True),
                            'gold_total': gold_data.get('total', 0),
                            'gold_sell': gold_data.get('sell', 0),
                            'image_full': item_image_path or item_data.get('image', {}).get('full', ''),
                            'image_sprite': item_data.get('image', {}).get('sprite', ''),
                            'image_group': item_data.get('image', {}).get('group', ''),
                            'image_x': item_data.get('image', {}).get('x', 0),
                            'image_y': item_data.get('image', {}).get('y', 0),
                            'image_w': item_data.get('image', {}).get('w', 0),
                            'image_h': item_data.get('image', {}).get('h', 0),
                            'tags': item_data.get('tags', []),
                            'maps': item_data.get('maps', {}),
                            'stats': item_data.get('stats', {}),
                            'version': self.version,
                        }
                    )
                    
                    # Importe les objets "from" (composants requis)
                    if 'from' in item_data:
                        item.from_items.all().delete()
                        for from_item_id in item_data['from']:
                            ItemFrom.objects.create(
                                item=item,
                                from_item_id=from_item_id
                            )
                    
                    # Importe les objets "into" (upgrades possibles)
                    if 'into' in item_data:
                        item.into_items.all().delete()
                        for into_item_id in item_data['into']:
                            ItemInto.objects.create(
                                item=item,
                                into_item_id=into_item_id
                            )
                
                imported_count += 1
                
                
                # Version temporaire qui affiche juste les données
                print(f"🔸 {item_data.get('name', 'Sans nom')} (ID: {item_id})")
                print(f"   Prix: {item_data.get('gold', {}).get('total', 'N/A')}")
                imported_count += 1
                
                # Petite pause
                time.sleep(0.05)
                
            except Exception as e:
                print(f"❌ Erreur lors de l'import de l'objet {item_id}: {e}")
                continue
        
        print("⚠️ Pour vraiment importer les objets, décommentez le code et ajoutez les modèles Item")
        print(f"✅ Import items terminé: {imported_count}/{total_items} objets traités")


def import_champions():
    """Fonction principale pour importer les champions"""
    importer = RiotDataImporter()
    importer.import_champions()


def import_items():
    """Fonction principale pour importer les objets"""
    importer = RiotDataImporter()
    importer.import_items()

