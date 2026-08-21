# dca/visual_utils.py
# Ensemble de fonctions utilitaires pour la partie visuelle du projet DCA TikTok

import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.dates as mdates
from matplotlib.dates import YearLocator, MonthLocator, DateFormatter
from matplotlib.colors import to_rgba


# ========= FORMATTAGE =========
def fmt_currency(x) -> str:
    """Affiche les valeurs avec séparateur de milliers et symbole €."""
    try:
        return f"{float(x):,.0f} €".replace(",", " ")
    except Exception:
        return f"{x} €"


def safe_name(name: str) -> str:
    """Crée une version sûre d’un nom (pour fichiers)."""
    return (
        name.lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace(".", "")
        .replace("/", "_")
        .strip()
    )


# ========= EASING / TRANSITIONS =========
def ease_numeric(current, target, base_alpha=0.2):
    """Transition fluide entre deux nombres (pour les animations)."""
    c = float(current)
    t = float(target)
    delta = abs(t - c)
    if delta == 0:
        return c
    alpha = min(0.5, base_alpha + 0.6 * (delta / (delta + 1e-9)))
    return c + alpha * (t - c)


def ease_timestamp(current, target, base_alpha=0.2):
    """Transition fluide entre deux dates (pour les animations temporelles)."""
    if isinstance(current, pd.Timestamp) and isinstance(target, pd.Timestamp):
        diff = (target - current).total_seconds()
        alpha = min(0.5, base_alpha + 0.6 * (abs(diff) / (abs(diff) + 1)))
        return current + pd.Timedelta(seconds=diff * alpha)
    return target


# ========= AXES & TEMPS =========
def choose_time_axis(ax, index: pd.DatetimeIndex):
    """Choisit automatiquement les intervalles d'axe X selon la durée totale."""
    if len(index) < 2:
        ax.xaxis.set_major_locator(YearLocator(1))
        ax.xaxis.set_major_formatter(DateFormatter("%Y"))
        return

    total_years = (index[-1] - index[0]).days / 365.25
    if total_years <= 3:
        ax.xaxis.set_major_locator(MonthLocator(interval=1))
        ax.xaxis.set_major_formatter(DateFormatter("%b %Y"))
    elif total_years <= 7:
        ax.xaxis.set_major_locator(MonthLocator(interval=3))
        ax.xaxis.set_major_formatter(DateFormatter("%b %Y"))
    elif total_years <= 15:
        ax.xaxis.set_major_locator(YearLocator(1))
        ax.xaxis.set_major_formatter(DateFormatter("%Y"))
    else:
        ax.xaxis.set_major_locator(YearLocator(2))
        ax.xaxis.set_major_formatter(DateFormatter("%Y"))

    ax.figure.autofmt_xdate(rotation=20, ha="right")


def build_sampling_index(index: pd.DatetimeIndex, target_frames: int, fallback_step: int) -> pd.DatetimeIndex:
    """Échantillonne une série temporelle selon la durée cible de la vidéo."""
    if len(index) <= 2:
        return index

    total_days = max(1, (index[-1] - index[0]).days)
    total_years = total_days / 365.25

    if total_years <= 6:
        step_days = 1
    elif total_years <= 12:
        step_days = 2
    else:
        est_step = max(1, int(round(total_days / max(1, int(target_frames * 0.95)))))
        step_days = min(max(est_step, 1), max(fallback_step, 2))

    idx = index[::step_days]
    if len(idx) < 2:
        idx = index[[0, -1]]
    return idx


# ========= COULEURS / STYLE =========
def color_with_alpha(hex_color: str, alpha: float):
    """Convertit une couleur hex en RGBA avec transparence."""
    return to_rgba(hex_color, alpha)


def apply_dark_style(ax):
    """Applique un style sombre cohérent à un graphe."""
    ax.set_facecolor("#0b0f17")
    for spine in ax.spines.values():
        spine.set_color("#37474f")
    ax.tick_params(colors="#b0bec5")
    ax.grid(True, color="white", alpha=0.08, linewidth=0.8)
    ax.yaxis.set_major_formatter(mticker.StrMethodFormatter("{x:,.0f} €"))


# ========= TEXTE / TITRES =========
def fit_fontsize(text: str, base: int = 20) -> int:
    """Ajuste automatiquement la taille de police selon la longueur du texte."""
    n = len(text)
    if n <= 36:
        return base
    if n <= 48:
        return base - 2
    if n <= 60:
        return base - 4
    return max(12, base - 6)


def draw_title(fig, main_line: str, sub_line: str, base_fontsize=20):
    """Affiche un titre stylisé à deux lignes avec cartouche arrondie."""
    from matplotlib.patches import FancyBboxPatch
    from matplotlib import patheffects

    fs_main = fit_fontsize(main_line, base=base_fontsize)
    fs_sub = max(11, fs_main - 4)

    bbox = FancyBboxPatch(
        (0.05, 0.83),
        0.90,
        0.09,
        transform=fig.transFigure,
        boxstyle="round,pad=0.02,rounding_size=0.03",
        facecolor=to_rgba("#ffffff", 0.12),
        edgecolor=to_rgba("#00e676", 0.7),
        linewidth=2,
        zorder=10,
    )
    fig.patches.append(bbox)

    fig.text(
        0.5,
        0.885,
        main_line,
        ha="center",
        va="center",
        fontsize=fs_main,
        fontweight="bold",
        color="#e0f7fa",
        zorder=11,
        path_effects=[patheffects.withStroke(linewidth=3, foreground="black", alpha=0.6)],
    )
    fig.text(
        0.5,
        0.855,
        sub_line,
        ha="center",
        va="center",
        fontsize=fs_sub,
        fontweight="bold",
        color="#b2ebf2",
        zorder=11,
        path_effects=[patheffects.withStroke(linewidth=2, foreground="black", alpha=0.45)],
    )


# ========= TEST LOCAL =========
if __name__ == "__main__":
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd

    # mini test de rendu
    dates = pd.date_range("2020-01-01", "2023-12-31", freq="B")
    y = np.cumsum(np.random.randn(len(dates))) + 100
    fig, ax = plt.subplots(figsize=(9, 5), dpi=120)
    apply_dark_style(ax)
    ax.plot(dates, y, color="#00e676")
    choose_time_axis(ax, dates)
    draw_title(fig, "POV : tu investis 100€ / mois sur Tesla", "depuis 2010")
    plt.show()
