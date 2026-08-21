# dca/logo_manager.py
# Recherche locale d'un logo dans LOGO_DIR
# Accepte label=... et ticker=...
# Supporte toutes les majuscules/minuscules

import os
from PIL import Image, ImageDraw
from dca.config import LOGO_DIR, AUTO_DOWNLOAD_LOGOS

# Les logos du dossier LOGO_DIR sont très hétérogènes : certains ont un fond
# transparent, d'autres un fond blanc opaque, dans des résolutions allant de
# 128px à plus de 2500px. get_display_logo() en produit une version normalisée
# (fond transparent, recadrée sur le contenu utile) mise en cache sur disque.
_CACHE_SUBDIR = ".cache"


def find_or_download_logo(label: str = None, ticker: str = None) -> str | None:
    """
    Cherche un logo local dans LOGO_DIR (aucun téléchargement réel n'est
    effectué malgré le nom, conservé pour compatibilité). Retourne None
    si AUTO_DOWNLOAD_LOGOS=false dans le .env, ou si rien n'est trouvé.
    Exemple :
        Visa --> visa.png
        Ubisoft --> ubisoft.png
        V --> visa.png (si label vaut 'Visa')
    """

    if not AUTO_DOWNLOAD_LOGOS:
        return None

    if not LOGO_DIR or not os.path.isdir(LOGO_DIR):
        return None

    candidates = []

    # -------- label --------
    if label:
        base = label.strip()
        safe = (
            base.lower()
            .replace(" ", "")
            .replace("-", "")
            .replace(".", "")
            .replace("_", "")
        )
        candidates.append(f"{safe}.png")

        # version originale (si ton fichier est Visa.png)
        candidates.append(f"{base}.png")

    # -------- ticker --------
    if ticker:
        base = ticker.strip()
        safe = (
            base.lower()
            .replace(" ", "")
            .replace("-", "")
            .replace(".", "")
            .replace("_", "")
        )
        candidates.append(f"{safe}.png")
        candidates.append(f"{base}.png")

    # -------- TEST : logos/<candidate> --------
    for cand in candidates:
        logo_path = os.path.join(LOGO_DIR, cand)
        if os.path.exists(logo_path):
            return logo_path

    return None


def _processed_logo_path(source_path: str) -> str:
    cache_dir = os.path.join(os.path.dirname(source_path), _CACHE_SUBDIR)
    os.makedirs(cache_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(source_path))[0]
    return os.path.join(cache_dir, f"{base}_transparent.png")


def _remove_opaque_background(img: "Image.Image", thresh: int = 28) -> "Image.Image":
    """
    Si l'image n'a pas de vraie transparence (fond uni opaque, cas de la
    majorité des logos du dossier), on retire le fond par un flood fill
    depuis les 4 coins. Les zones claires internes (non connectées au bord,
    ex. un logo blanc sur fond de couleur) ne sont pas touchées.
    """
    img = img.convert("RGBA")
    if img.getchannel("A").getextrema()[0] < 250:
        return img  # a déjà une vraie transparence

    w, h = img.size
    for corner in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
        if img.getpixel(corner)[3] == 0:
            continue
        try:
            ImageDraw.floodfill(img, corner, (0, 0, 0, 0), thresh=thresh)
        except Exception:
            pass
    return img


def _autocrop_to_content(img: "Image.Image", padding: int = 6) -> "Image.Image":
    bbox = img.getchannel("A").getbbox()
    if not bbox:
        return img
    left, top, right, bottom = bbox
    left = max(0, left - padding)
    top = max(0, top - padding)
    right = min(img.width, right + padding)
    bottom = min(img.height, bottom + padding)
    return img.crop((left, top, right, bottom))


def get_display_logo(label: str = None, ticker: str = None) -> str | None:
    """
    Retourne le chemin d'une version du logo prête pour l'affichage en
    filigrane : fond transparent (retiré automatiquement si besoin) et
    recadrée sur son contenu utile. Le résultat est mis en cache sur disque
    (dossier LOGO_DIR/.cache) pour ne traiter chaque logo qu'une seule fois.
    Retourne None si aucun logo local n'est trouvé.
    """
    source_path = find_or_download_logo(label=label, ticker=ticker)
    if not source_path:
        return None

    cache_path = _processed_logo_path(source_path)
    try:
        if (
            os.path.exists(cache_path)
            and os.path.getmtime(cache_path) >= os.path.getmtime(source_path)
        ):
            return cache_path

        img = Image.open(source_path)
        img = _remove_opaque_background(img)
        img = _autocrop_to_content(img)
        img.save(cache_path)
        return cache_path
    except Exception as e:
        print(f"⚠️ Impossible de préparer le logo {source_path} : {e}")
        return source_path
