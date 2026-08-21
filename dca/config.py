# dca/config.py
# Gestion des variables d'environnement et configuration globale du projet DCA TikTok

import os
import sys
from dotenv import load_dotenv

# Charger le fichier .env s'il existe
load_dotenv()

# Sur certaines consoles Windows (code page cp1252), les emojis/flèches utilisés
# dans les print() du projet provoquent un UnicodeEncodeError et font planter
# le script. On force stdout/stderr en UTF-8 (avec repli silencieux si la
# console ne supporte pas reconfigure, ex. sortie redirigée).
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _env_bool(name: str, default: bool) -> bool:
    """Lit une variable d'environnement booléenne (1/true/yes/on)."""
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


# ========= Paramètres généraux =========
DEFAULT_TICKER = os.getenv("TICKER", "CA.PA")
MONTHLY_INVEST = float(os.getenv("MONTHLY_INVEST", 200))
ENV_START = os.getenv("START", "").strip() or None
ENV_END = os.getenv("END", "").strip() or None

# ========= Vidéo / Animation =========
FPS = int(os.getenv("FPS", 30))
STEP_DAYS_CONF = int(os.getenv("STEP_DAYS", 2))
VIDEO_DURATION = int(os.getenv("VIDEO_DURATION", 62))  # en secondes

# ========= Répertoires =========
LOGO_DIR = os.getenv("LOGO_DIR", "logos")
LOGO_PATH = os.getenv("LOGO_PATH", "") or None
OUT_DIR = os.getenv("OUT_DIR", "publier")
DATA_DIR = os.getenv("DATA_DIR", "data")
TICKERS_FILE = os.getenv("TICKERS_FILE", "tickers.txt")

# ========= Crises =========
CRISES_PATH = os.getenv("CRISES_PATH", "").strip() or None  # chemin vers fichier .json ou .csv
CRISES_INLINE = os.getenv("CRISES_INLINE", "").strip() or ""  # ex : "Covid|2020-03-01|2020-11-01|#42a5f5"

# ========= Couleurs par défaut =========
COLOR_INVEST = "#00c853"
COLOR_VALUE = "#ff3d3d"
COLOR_DIVIDEND = "#ffa726"
COLOR_BACKGROUND = os.getenv("BACKGROUND_COLOR", "#000000")

# ========= Style =========
FONT_FAMILY = os.getenv("FONT_FAMILY", "DejaVu Sans")

# ========= Comportement =========
REINVEST_DIVIDENDS = _env_bool("REINVEST_DIVIDENDS", True)
AUTO_DOWNLOAD_LOGOS = _env_bool("AUTO_DOWNLOAD_LOGOS", True)
GLOW = _env_bool("GLOW", True)
SHOW_INVEST_LINE = _env_bool("SHOW_INVEST_LINE", True)
DEBUG = _env_bool("DEBUG", False)

# ========= Divers =========
ENABLE_GLOW = GLOW
ENABLE_DYNAMIC_BG = True
ENABLE_CRISIS_OVERLAY = True

# ========= Paramètres de performance =========
BITRATE = int(os.getenv("BITRATE", 8000))
CRF = os.getenv("CRF", "18")
CODEC = os.getenv("CODEC", "libx264")
THREADS = os.getenv("THREADS", "0")

# ========= Affichage =========
TITLE_BOX_ALPHA = float(os.getenv("TITLE_BOX_ALPHA", 0.12))
TITLE_FONT = os.getenv("TITLE_FONT", "DejaVu Sans")

# ========= TikTok (Content Posting API, mode brouillon) =========
TIKTOK_CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY", "").strip()
TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET", "").strip()
TIKTOK_REDIRECT_URI = os.getenv("TIKTOK_REDIRECT_URI", "https://localhost:8722/callback").strip()
TIKTOK_TOKENS_PATH = os.getenv("TIKTOK_TOKENS_PATH", "tiktok_tokens.json").strip()

# ========= Fonctions utilitaires =========
def debug_summary():
    """Affiche la configuration actuelle dans la console."""
    print("\n=== Configuration DCA ===")
    print(f"DEFAULT_TICKER   : {DEFAULT_TICKER}")
    print(f"MONTHLY_INVEST   : {MONTHLY_INVEST} €/mois")
    print(f"FPS              : {FPS}")
    print(f"DURATION         : {VIDEO_DURATION}s")
    print(f"LOGO_DIR         : {LOGO_DIR}")
    print(f"OUT_DIR          : {OUT_DIR}")
    print(f"TICKERS_FILE     : {TICKERS_FILE}")
    print(f"CRISES_PATH      : {CRISES_PATH}")
    print(f"ENV_START-END    : {ENV_START} → {ENV_END}")
    print(f"REINVEST_DIV     : {REINVEST_DIVIDENDS}")
    print(f"AUTO_DL_LOGOS    : {AUTO_DOWNLOAD_LOGOS}")
    print(f"GLOW             : {GLOW}")
    print(f"SHOW_INVEST_LINE : {SHOW_INVEST_LINE}")
    print(f"BACKGROUND_COLOR : {COLOR_BACKGROUND}")
    print(f"FONT_FAMILY      : {FONT_FAMILY}")
    print("=========================\n")


# Si besoin, afficher la config au lancement
if __name__ == "__main__":
    debug_summary()
