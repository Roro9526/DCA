# dca/data_loader.py
# Chargement des séries de prix (Yahoo Finance ou CSV local) et des dividendes
# Version améliorée
# - lecture CSV tolérante (séparateurs ; , tab, sans header, noms variés)
# - support dates mensuelles YYYY-MM
# - support fichiers 1 colonne "Date;Close" avec valeurs "YYYY-MM;prix"

import os
import re
import pandas as pd
import numpy as np
import yfinance as yf
from typing import Tuple, Optional

from dca.config import ENV_START, ENV_END


# ========= OUTILS =========
def _to_series_from_df(df: pd.DataFrame) -> pd.Series:
    """Essaye d'extraire une colonne de prix exploitable depuis un DataFrame."""
    # Tentative directe sur noms usuels
    for col in ["Adj Close", "Close", "Prix", "Price", "Valeur"]:
        if col in df.columns:
            return df[col].astype(float).dropna()

    # Tolérance pour les noms en minuscules ou variantes
    lower_cols = {c.lower(): c for c in df.columns}
    for col in ["adj close", "close", "prix", "price", "valeur"]:
        if col in lower_cols:
            c = lower_cols[col]
            return df[c].astype(float).dropna()

    # Si aucune colonne connue, on prend la première numérique
    num = df.select_dtypes(include=[np.number])
    if num.shape[1] >= 1:
        return num.iloc[:, 0].astype(float).dropna()

    raise ValueError("Aucune colonne numérique de prix trouvée dans le CSV.")


def _try_read_csv(candidate_path: str) -> Optional[pd.DataFrame]:
    """Lecture robuste d'un CSV (supporte ; , tab, header absent, formats non standard)."""
    if not os.path.exists(candidate_path):
        return None

    try:
        # On essaie plusieurs séparateurs
        df = None
        for sep in [",", ";", "\t", "|"]:
            try:
                tmp = pd.read_csv(candidate_path, sep=sep)
                if tmp.shape[1] >= 1:
                    df = tmp
                    break
            except Exception:
                continue
        if df is None:
            return None

        # Cas spécial pour tes fichiers "Date;Close" dans une seule colonne
        # Exemple
        #   colonne unique "Date;Close"
        #   valeur "1992-01;8.15"
        if df.shape[1] == 1:
            col_name = str(df.columns[0])
            first_val = str(df.iloc[0, 0])
            if ";" in col_name or ";" in first_val:
                splitted = df.iloc[:, 0].astype(str).str.split(";", expand=True)
                if splitted.shape[1] >= 2:
                    df = splitted.iloc[:, :2].copy()
                    df.columns = ["Date", "Close"]

        # Si pas de header "date" reconnu, on en crée un générique
        if not any("date" in str(c).lower() for c in df.columns):
            # Cas sans en-tête deux colonnes supposées (Date, Close)
            if df.shape[1] == 2:
                df.columns = ["Date", "Close"]
            elif df.shape[1] == 1:
                df.columns = ["Close"]
            else:
                df.columns = [f"Col{i}" for i in range(df.shape[1])]
        else:
            # On nettoie les noms de colonnes
            df.columns = [str(c).strip().title() for c in df.columns]

        # ---------- Gestion des dates ----------
        if "Date" in df.columns:
            df["Date"] = (
                df["Date"]
                .astype(str)
                .str.strip()
                # "YYYY-MM" → "YYYY-MM-01"
                .replace(r"^(\d{4})[-/](\d{2})$", r"\1-\2-01", regex=True)
            )
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce", format="%Y-%m-%d")
            df = df.dropna(subset=["Date"]).set_index("Date")
        else:
            # Si pas de colonne Date explicite, on essaie sur la première
            first = df.columns[0]
            df[first] = (
                df[first]
                .astype(str)
                .str.strip()
                .replace(r"^(\d{4})[-/](\d{2})$", r"\1-\2-01", regex=True)
            )
            df[first] = pd.to_datetime(df[first], errors="coerce", format="%Y-%m-%d")
            df = df.dropna(subset=[first]).set_index(first)

        # ---------- Conversion automatique des nombres ----------
        for c in df.columns:
            df[c] = (
                df[c]
                .astype(str)
                .str.replace(",", ".", regex=False)
                .replace("", np.nan)
            )
            df[c] = pd.to_numeric(df[c], errors="coerce")

        df = df.dropna(how="all")
        # Important ne pas appeler sort_index sur un DatetimeIndex directement
        # on passe par .sort_index() du DataFrame
        return df.sort_index()

    except Exception as e:
        print(f"⚠️ Échec lecture CSV {candidate_path}: {e}")
        return None


def _clip_by_env_dates(s: pd.Series) -> pd.Series:
    """Découpe la série selon les bornes définies dans .env (START, END)."""
    out = s.copy()
    if ENV_START:
        out = out[out.index >= pd.to_datetime(ENV_START)]
    if ENV_END:
        out = out[out.index <= pd.to_datetime(ENV_END)]
    return out


def _normalize_ticker_for_yahoo(ticker: str) -> str:
    """Convertit les symboles simplifiés en version Yahoo Finance."""
    t = ticker.upper().strip()
    common_crypto = {
        "BTC": "BTC-USD",
        "ETH": "ETH-USD",
        "SOL": "SOL-USD",
        "ADA": "ADA-USD",
        "BNB": "BNB-USD",
        "XRP": "XRP-USD",
        "DOGE": "DOGE-USD",
    }
    return common_crypto.get(t, t)


# ========= CHARGEMENT PRINCIPAL =========
def load_price_series(
    ticker: str,
    label_short: str,
    csv_override: Optional[str] = None
) -> Tuple[Optional[pd.Series], bool]:
    """
    Retourne (series_prix, can_use_dividends)
    can_use_dividends=False si la source est un CSV sans info complémentaire.
    """

    # 1) CSV explicite fourni
    if csv_override:
        df = _try_read_csv(csv_override)
        if df is not None:
            try:
                s = _to_series_from_df(df)
                s.index = pd.to_datetime(s.index).tz_localize(None)
                s = s.sort_index()
                s = _clip_by_env_dates(s)
                if len(s) < 500:
                    s = s.asfreq("B").interpolate("time").dropna()
                print(
                    f"📂 Données locales CSV utilisées : {csv_override} "
                    f"({len(s)} points) | {s.index.min().date()} → {s.index.max().date()}"
                )
                return s, False
            except Exception as e:
                print(f"⚠️ CSV explicite invalide {csv_override}: {e}")

    # 2) CSV par défaut dans ./data/
    label_file = re.sub(r"[^a-zA-Z0-9]", "_", label_short)
    ticker_file = re.sub(r"[^a-zA-Z0-9]", "_", ticker)

    for path in [
        os.path.join("data", f"{label_file}.csv"),
        os.path.join("data", f"{ticker_file}.csv"),
        f"{label_file}.csv",
        f"{ticker_file}.csv",
    ]:
        df = _try_read_csv(path)
        if df is not None:
            try:
                s = _to_series_from_df(df)
                s.index = pd.to_datetime(s.index).tz_localize(None)
                s = s.sort_index()
                s = _clip_by_env_dates(s)
                if len(s) < 500:
                    s = s.asfreq("B").interpolate("time").dropna()
                print(
                    f"📂 Données locales CSV utilisées : {path} "
                    f"({len(s)} points) | {s.index.min().date()} → {s.index.max().date()}"
                )
                return s, False
            except Exception as e:
                print(f"⚠️ CSV invalide {path}: {e}")

    # 3) Yahoo Finance
    tnorm = _normalize_ticker_for_yahoo(ticker)
    print(f"🌐 Téléchargement Yahoo Finance : {tnorm}")
    try:
        data = yf.download(tnorm, period="max", auto_adjust=True, progress=False)
    except Exception as e:
        print(f"⚠️ Échec du téléchargement pour {tnorm}: {e}")
        return None, False

    if data is None or data.empty:
        print(f"⚠️ Aucune donnée pour {tnorm}")
        return None, False

    if isinstance(data.columns, pd.MultiIndex):
        if tnorm in data.columns.get_level_values(1):
            data = data.xs(tnorm, axis=1, level=1)
        else:
            data = data.droplevel(0, axis=1)

    if "Adj Close" in data.columns:
        price = data["Adj Close"]
    elif "Close" in data.columns:
        price = data["Close"]
    else:
        price = data.iloc[:, 0]

    price = price.dropna().astype(float)
    price.index = pd.to_datetime(price.index).tz_localize(None)
    price = price.sort_index()
    price = _clip_by_env_dates(price)
    if len(price) < 500:
        price = price.asfreq("B").interpolate("time").dropna()

    print(
        f"✅ Données récupérées ({len(price)} points) | "
        f"{price.index.min().date()} → {price.index.max().date()}"
    )
    return price, True


# ========= DIVIDENDES =========
def get_dividends_on_price_index(
    ticker: str,
    price_index: pd.DatetimeIndex
) -> pd.Series:
    """
    Récupère les dividendes depuis Yahoo Finance, alignés sur les dates du prix.
    Retourne une série de même index.
    """
    try:
        tk = yf.Ticker(ticker)
        div = tk.dividends

        if (div is None) or div.empty:
            actions = tk.actions
            if isinstance(actions, pd.DataFrame) and "Dividends" in actions.columns:
                div = actions["Dividends"]

        if div is None or div.empty:
            return pd.Series(0.0, index=price_index)

        div.index = pd.to_datetime(div.index).tz_localize(None)
        div = div[(div.index >= price_index[0]) & (div.index <= price_index[-1])]
        div = div.reindex(price_index).fillna(0.0).astype(float)
        return div

    except Exception:
        return pd.Series(0.0, index=price_index)
