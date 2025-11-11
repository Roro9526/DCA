# dca/logo_manager.py
# Gestion automatique des logos (locaux ou téléchargés)
# Utilise Clearbit pour les entreprises et CryptoLogos pour les cryptos

import os
import re
import requests
from typing import Optional
from dca.config import LOGO_DIR


# ========= OUTILS =========
def _safe_name(name: str) -> str:
    """Nettoie le nom pour générer un nom de fichier sûr."""
    return (
        name.lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace(".", "")
        .replace("/", "_")
        .strip()
    )


def _is_crypto(label: str, ticker: str) -> bool:
    """Détecte si c’est probablement une crypto."""
    return (
        "-USD" in ticker.upper()
        or ticker.upper() in {"BTC", "ETH", "SOL", "ADA", "BNB", "XRP", "DOGE", "AVAX", "DOT", "MATIC", "SHIB"}
    )


def _crypto_logo_url(label: str, ticker: str) -> str:
    """Construit l’URL du logo crypto sur cryptologos.cc."""
    base = ticker.split("-")[0].lower()
    return f"https://cryptologos.cc/logos/{base}-{base}-logo.png"


def _company_domain(label: str, ticker: str) -> str:
    """Retourne un domaine plausible pour une entreprise."""
    label = label.lower()
    t = ticker.lower()

    if t.endswith(".pa"):  # société française
        base = label.replace(" ", "").replace(".", "")
        return f"{base}.fr"
    if t.endswith(".de"):
        base = label.replace(" ", "").replace(".", "")
        return f"{base}.de"
    if t.endswith(".co.uk"):
        base = label.replace(" ", "").replace(".", "")
        return f"{base}.co.uk"

    # Cas général
    base = label.replace(" ", "").replace(".", "")
    return f"{base}.com"


def _clearbit_logo_url(domain: str) -> str:
    """URL d’un logo Clearbit à partir du domaine."""
    return f"https://logo.clearbit.com/{domain}"


def _download_image(url: str, dest_path: str) -> bool:
    """Télécharge un fichier image et le sauvegarde localement."""
    try:
        r = requests.get(url, timeout=8)
        if r.status_code == 200 and r.content:
            with open(dest_path, "wb") as f:
                f.write(r.content)
            return True
    except Exception:
        pass
    return False


# ========= RECHERCHE / TÉLÉCHARGEMENT =========
def find_local_logo(label: str) -> Optional[str]:
    """Vérifie si un logo local existe déjà."""
    if not LOGO_DIR or not os.path.isdir(LOGO_DIR):
        return None

    base = _safe_name(label)
    for ext in [".png", ".jpg", ".jpeg", ".webp"]:
        path = os.path.join(LOGO_DIR, base + ext)
        if os.path.exists(path):
            return path
    return None


def find_or_download_logo(label: str, ticker: str = "") -> Optional[str]:
    """
    Retourne le chemin du logo (local ou téléchargé).
    Si le logo n'existe pas, il est téléchargé automatiquement.
    """
    os.makedirs(LOGO_DIR, exist_ok=True)

    # 1) Logo local déjà présent
    local_path = find_local_logo(label)
    if local_path:
        return local_path

    # 2) Construction du nom
    safe = _safe_name(label)
    target_path = os.path.join(LOGO_DIR, f"{safe}.png")

    # 3) Détection crypto ou société
    if _is_crypto(label, ticker):
        url = _crypto_logo_url(label, ticker)
        if _download_image(url, target_path):
            print(f"🪙 Logo crypto téléchargé : {label}")
            return target_path
        else:
            print(f"⚠️ Logo crypto introuvable : {label}")
            return None

    # 4) Logo entreprise via Clearbit
    domain = _company_domain(label, ticker)
    url = _clearbit_logo_url(domain)
    if _download_image(url, target_path):
        print(f"🏢 Logo téléchargé : {label} ({domain})")
        return target_path

    print(f"⚠️ Aucun logo trouvé pour {label}")
    return None


# ========= TEST =========
if __name__ == "__main__":
    print("🔍 Test téléchargement de logos...")
    samples = [
        ("Apple", "AAPL"),
        ("Tesla", "TSLA"),
        ("Nvidia", "NVDA"),
        ("Bitcoin", "BTC-USD"),
        ("Ethereum", "ETH-USD"),
        ("LVMH", "MC.PA"),
    ]
    for label, ticker in samples:
        path = find_or_download_logo(label, ticker)
        print(f"{label} → {path}")
