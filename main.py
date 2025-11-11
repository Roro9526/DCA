# main.py
# Point d'entrée de l'app DCA TikTok
# - Lit tickers depuis arguments CLI et/ou tickers.txt
# - Normalise les lignes (TICKER-Label ou TICKER-Label.csv)
# - Prépare la liste des spécifications
# - Vérifie ou télécharge les logos
# - Lance le rendu single ou battle selon le nombre de tickers

import os
import sys
from typing import List, Tuple, Optional

# Imports internes
from dca.config import (
    TICKERS_FILE,
    DEFAULT_TICKER,
    OUT_DIR,
    LOGO_DIR,
)
from dca.renderer_single import make_video_single
from dca.renderer_battle import make_video_battle
from dca.logo_manager import find_or_download_logo


def parse_ticker_line(line: str) -> Tuple[str, str, Optional[str]]:
    """
    Accepte:
      - 'NVDA-Nvidia'
      - 'BTC-USD-Bitcoin'
      - 'CA.PA-Carrefour,ca.csv'  (peu probable, on évite la virgule)
      - 'AMZN-Amazon.csv' -> CSV dans ./data/Amazon.csv
      - 'AMZN-Jeff.csv'   -> CSV dans ./data/Jeff.csv
      - 'AMZN'            -> label = 'AMZN'
    Retourne (ticker, label, csv_path_or_None)
    """
    raw = (line or "").strip()
    if not raw:
        return "", "", None

    # format CSV explicite à droite: TICKER-QuelqueChose.csv
    if "-" in raw and raw.lower().endswith(".csv"):
        left, right_csv = raw.rsplit("-", 1)
        ticker = left.strip()
        label = os.path.splitext(os.path.basename(right_csv.strip()))[0]
        csv_path = os.path.join("data", right_csv.strip())
        return ticker, label, csv_path

    # format standard TICKER-Label
    if "-" in raw:
        ticker, label = raw.rsplit("-", 1)
        return ticker.strip(), label.strip(), None

    # sinon TICKER seul
    return raw, raw, None


def read_specs_from_file(path: str) -> List[Tuple[str, str, Optional[str]]]:
    if not os.path.exists(path):
        return []
    specs: List[Tuple[str, str, Optional[str]]] = []
    with open(path, "r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            tk, label, csvp = parse_ticker_line(ln)
            if tk:
                specs.append((tk, label, csvp))
    return specs


def read_specs_from_argv(argv: List[str]) -> List[Tuple[str, str, Optional[str]]]:
    """
    Permet de passer des items directement en CLI, même format que tickers.txt
    Exemples:
      py main.py "NVDA-Nvidia" "INTC-Intel"
      py main.py NVDA INTC
      py main.py "AMZN-Amazon.csv"
    """
    specs: List[Tuple[str, str, Optional[str]]] = []
    for raw in argv:
        tk, label, csvp = parse_ticker_line(raw)
        if tk:
            specs.append((tk, label, csvp))
    return specs


def dedupe_preserve_order(items: List[Tuple[str, str, Optional[str]]]) -> List[Tuple[str, str, Optional[str]]]:
    seen = set()
    out = []
    for t in items:
        key = (t[0].upper(), t[1])
        if key not in seen:
            seen.add(key)
            out.append(t)
    return out


def ensure_dirs():
    os.makedirs(OUT_DIR, exist_ok=True)
    if LOGO_DIR:
        os.makedirs(LOGO_DIR, exist_ok=True)
    os.makedirs("data", exist_ok=True)


def ensure_logos(specs: List[Tuple[str, str, Optional[str]]]) -> None:
    """
    Tente de trouver un logo local pour chaque label, sinon le télécharge.
    Ne lève pas d'exception si échec, le rendu tombera en mode texte.
    """
    for tk, label, _ in specs:
        try:
            _ = find_or_download_logo(label=label, ticker=tk)
        except Exception as e:
            print(f"⚠️ Logo manquant pour {label} ({tk}) : {e}")


def main():
    ensure_dirs()

    # 1) lecture depuis CLI
    cli_specs = read_specs_from_argv(sys.argv[1:])

    # 2) lecture depuis fichier si pas d’arguments explicites
    file_specs = read_specs_from_file(TICKERS_FILE) if not cli_specs else []

    # 3) fallback DEFAULT_TICKER
    if cli_specs:
        specs = cli_specs
    elif file_specs:
        specs = file_specs
    else:
        specs = [(DEFAULT_TICKER, DEFAULT_TICKER, None)]

    # nettoyage doublons
    specs = dedupe_preserve_order(specs)

    # Sécurité, on limite volontairement le mode battle à 4
    # Si plus de 4, on rendra en lots successifs de 4
    if len(specs) == 0:
        print("❌ Aucun ticker valide.")
        return

    # Téléchargement des logos si besoin
    ensure_logos(specs)

    # Dispatch
    if len(specs) == 1:
        tk, label, csvp = specs[0]
        print(f"🎯 Mode simple, 1 ticker → {tk} | {label}")
        make_video_single((tk, label, csvp))
        return

    # Si plus de 4 tickers, on segmente en groupes de 4
    if len(specs) > 4:
        print(f"⚠️ {len(specs)} tickers fournis, segmentation en groupes de 4 pour le mode battle.")
        chunk = []
        for item in specs:
            chunk.append(item)
            if len(chunk) == 4:
                make_video_battle(chunk)
                chunk = []
        if chunk:
            make_video_battle(chunk)
        return

    # 2 à 4 tickers, battle direct
    print(f"🏁 Mode battle, {len(specs)} tickers.")
    make_video_battle(specs)


if __name__ == "__main__":
    main()
