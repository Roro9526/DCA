# dca/renderer_battle.py
# Mode "battle" fluide (identique au single) avec la courbe Investi commune
# Supporte jusqu’à 4 entreprises + 1 courbe d’investissement de référence
# Corrections :
#  - Les noms de crises n'apparaissent que quand la période est visible
#  - Démarrage synchronisé : on (re)simule le DCA à partir de la date commune MAX
#    (incluant START_DATE/START_YEAR du .env si présents)

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patheffects as patheffects
from matplotlib.animation import FuncAnimation, FFMpegWriter
from matplotlib.patches import Rectangle
from tqdm import tqdm

from dca import config as CFG
from dca.config import MONTHLY_INVEST, FPS, VIDEO_DURATION, STEP_DAYS_CONF, OUT_DIR
from dca.visual_utils import (
    ease_numeric,
    ease_timestamp,
    fmt_currency,
    choose_time_axis,
    build_sampling_index,
    apply_dark_style,
)
from dca.crises import load_crises, CrisisOverlay
from dca.data_loader import load_price_series
from dca.dca_simulator import simulate_dca

# --------- Paramètres visuels identiques au mode single ----------
POV_Y = 0.91
GAIN_Y = 0.13
TOP_FRAC = 0.86
BOT_FRAC = 0.20
LEFT_FRAC = 0.10
RIGHT_FRAC = 0.96

# --------- Date de départ commune imposée par le .env (START), si présente ----------
_ENV_START = pd.Timestamp(CFG.ENV_START) if CFG.ENV_START else None


def make_video_battle(tickers_info):
    if len(tickers_info) < 2:
        print("⚠️ Le mode battle nécessite au moins 2 tickers.")
        return

    print(f"🏁 Mode battle avec {len(tickers_info)} tickers")

    # 1) On charge d'abord TOUTES les séries de prix pour déterminer la date de départ commune
    raw_prices = []  # [(label, price_series)]
    starts = []

    for ticker, label, csv_path in tickers_info:
        print(f"📊 Chargement → {label} ({ticker})")
        price, _ = load_price_series(ticker, label, csv_path)
        if price is None or price.empty:
            print(f"⚠️ Données manquantes pour {label}")
            continue
        raw_prices.append((label, ticker, price))
        starts.append(price.index.min())

    if len(raw_prices) < 2:
        print("❌ Aucune donnée exploitable pour le mode battle.")
        return

    # Date de départ commune = max(des dates de début) et contrainte .env si présente
    latest_common_start = max(starts)
    if _ENV_START is not None:
        latest_common_start = max(latest_common_start, _ENV_START)
    print(f"📆 Démarrage commun (re-simulation) à partir de : {latest_common_start.date()}")

    # 2) Maintenant qu'on a la date commune, on TRIM les prix et on SIMULE le DCA à partir de cette date
    all_series = []       # [(label, invested, portfolio_reinvest)]
    aligned_index = None  # intersection des index simulés (après trim)

    for label, ticker, full_price in raw_prices:
        price = full_price[full_price.index >= latest_common_start]
        if price.empty:
            print(f"⚠️ Aucune donnée après {latest_common_start.date()} pour {label}")
            continue

        # simulate_dca uniquement sur la fenêtre coupée → tout part de 0
        invested, _, portfolio_reinvest = simulate_dca(
            price, MONTHLY_INVEST, reinvest=CFG.REINVEST_DIVIDENDS
        )

        # Lissage léger sur la valeur seulement (on garde Investi exact)
        span = 50
        portfolio_reinvest = portfolio_reinvest.ewm(span=span, adjust=False).mean()

        # Sécurité : premier point à 0
        if len(invested) > 0:
            invested.iloc[0] = 0.0
        if len(portfolio_reinvest) > 0:
            portfolio_reinvest.iloc[0] = 0.0

        all_series.append((label, invested, portfolio_reinvest))

        aligned_index = portfolio_reinvest.index if aligned_index is None else aligned_index.intersection(portfolio_reinvest.index)

    if len(all_series) < 2:
        print("❌ Pas assez de séries après alignement commun.")
        return

    # 3) Échantillonnage temporel commun
    target_frames = FPS * VIDEO_DURATION
    idx = build_sampling_index(aligned_index, target_frames, STEP_DAYS_CONF)

    for i, (label, invested, port_re) in enumerate(all_series):
        invested = invested.reindex(idx).interpolate("time").bfill().ffill()
        port_re = port_re.reindex(idx).interpolate("time").bfill().ffill()
        # re-garantie départ à 0
        if len(invested) > 0:
            invested.iloc[0] = 0.0
        if len(port_re) > 0:
            port_re.iloc[0] = 0.0
        all_series[i] = (label, invested, port_re)

    print(f"🕒 Index échantillonné : {len(idx)} points")

    # --- Figure ---
    plt.rcParams["font.family"] = CFG.FONT_FAMILY
    fig, ax = plt.subplots(figsize=(9, 16), dpi=160)
    fig.patch.set_facecolor(CFG.COLOR_BACKGROUND)
    apply_dark_style(ax)
    plt.subplots_adjust(top=TOP_FRAC, bottom=BOT_FRAC, left=LEFT_FRAC, right=RIGHT_FRAC)

    # --- Fond dynamique ---
    dynamic_bg = Rectangle((0, 0), 1, 1, transform=ax.transAxes, facecolor="#00ff00", alpha=0.05, zorder=0)
    ax.add_patch(dynamic_bg)

    # --- Crises (zones + liserés + étiquettes) ---
    crisis_overlay = CrisisOverlay(ax, load_crises())

    # --- Axes ---
    choose_time_axis(ax, idx)

    # --- Lignes et couleurs ---
    colors = ["#ff5252", "#42a5f5", "#ffa726", "#ab47bc"]
    lines, dots, texts = [], [], []

    (inv_glow,) = ax.plot([], [], lw=6, color="#00c853", alpha=0.10, zorder=2)
    (inv_line,) = ax.plot([], [], lw=2.2, color="#00e676", linestyle="--", zorder=3)
    (inv_dot,) = ax.plot([], [], "o", color="#00e676", markersize=7, markeredgecolor="white", markeredgewidth=1.2, zorder=4)
    inv_text = ax.text(
        0, 0, "", color="#9ef7b3", fontsize=13, weight="bold",
        va="bottom", ha="left",
        path_effects=[patheffects.withStroke(linewidth=2, foreground="black", alpha=0.45)]
    )

    if not CFG.SHOW_INVEST_LINE:
        inv_glow.set_alpha(0.0)
        inv_line.set_alpha(0.0)
        inv_dot.set_alpha(0.0)
        inv_text.set_alpha(0.0)

    for i, (label, _, port_re) in enumerate(all_series):
        color = colors[i % len(colors)]
        (glow,) = ax.plot([], [], lw=7, color=color, alpha=0.10, solid_capstyle="round", zorder=2)
        if not CFG.GLOW:
            glow.set_alpha(0.0)
        (line,) = ax.plot([], [], lw=3, color=color, solid_capstyle="round", zorder=3)
        (dot,) = ax.plot([], [], "o", color=color, markersize=8, markeredgecolor="white", markeredgewidth=1.2, zorder=5)
        txt = ax.text(
            0, 0, "", color=color, fontsize=13, weight="bold",
            va="bottom", ha="left",
            path_effects=[patheffects.withStroke(linewidth=2, foreground="black", alpha=0.45)]
        )
        lines.append((label, line, glow))
        dots.append(dot)
        texts.append(txt)

    # --- POV ---
    label_names = " vs ".join([lbl for lbl, _, _ in all_series])
    pov_text = f"POV : Tu investis {int(MONTHLY_INVEST)}€/mois\nsur {label_names}"
    fig.text(
        0.5, POV_Y, pov_text,
        ha="center", va="center",
        fontsize=20, fontweight="bold",
        color="black",
        linespacing=1.3,
        bbox=dict(boxstyle="round,pad=0.5", facecolor="white", edgecolor="none")
    )

    # --- Gain ---
    gain_text = fig.text(
        0.5, GAIN_Y, "",
        ha="center", va="bottom",
        fontsize=30, fontweight="bold",
        color="#00e676",
        family="monospace"
    )

    # --- Animation ---
    frames_total = FPS * VIDEO_DURATION
    x_all = idx
    current_ymax, current_xmax = None, x_all[0]

    def frame_to_index(frame):
        progress = frame / max(1, frames_total - 1)
        return min(int(progress * (len(x_all) - 1)), len(x_all) - 1)

    def update(frame):
        nonlocal current_ymax, current_xmax
        i = frame_to_index(frame)
        x = x_all[:i + 1]
        all_y_values = []

        # Investi (commun) — déjà recalculé depuis la date commune
        invested_ref = all_series[0][1]
        y_inv = invested_ref.iloc[:i + 1].values
        inv_glow.set_data(x, y_inv)
        inv_line.set_data(x, y_inv)
        inv_dot.set_data([x[-1]], [y_inv[-1]])
        inv_text.set_position((x[-1], y_inv[-1] * 1.01))
        inv_text.set_text(f"Investi\n{fmt_currency(y_inv[-1])}")
        all_y_values.extend(y_inv)

        # Entreprises
        for (label, _, s), (_, line, glow), dot, txt in zip(all_series, lines, dots, texts):
            y = s.iloc[:i + 1].values
            all_y_values.extend(y)
            line.set_data(x, y)
            glow.set_data(x, y)
            dot.set_data([x[-1]], [y[-1]])
            offset_y = (max(y) * 0.015) if len(y) > 0 else 1
            txt.set_position((x[-1], y[-1] + offset_y))
            txt.set_text(f"{label}\n{fmt_currency(y[-1])}")

        if not all_y_values:
            return []

        max_y = float(np.nanmax(all_y_values))
        current_ymax = ease_numeric(current_ymax or max_y, max_y * 1.3, 0.18)
        right_margin = pd.Timedelta(days=max(1, int((x_all[-1] - x_all[0]).days * 0.15)))
        target_xmax = x[-1] + right_margin
        current_xmax = ease_timestamp(current_xmax, target_xmax, base_alpha=0.22)
        ax.set_xlim(x_all[0], current_xmax)
        ax.set_ylim(0, current_ymax)

        crisis_overlay.update(x_left=x_all[0], x_right=current_xmax)

        # Gagnant
        total_end = {lbl: s.iloc[i] for lbl, _, s in all_series if not pd.isna(s.iloc[i])}
        if total_end:
            best = max(total_end.items(), key=lambda x: x[1])
            gain_text.set_text(f" {best[0]} en tête : {fmt_currency(best[1])}")
            dynamic_bg.set_facecolor("#00ff00" if best[1] >= y_inv[-1] else "#ff0000")

        return [inv_line, inv_glow, inv_dot, inv_text] + [l for _, l, _ in lines] + dots + texts + [gain_text, dynamic_bg]

    # --- Export ---
    os.makedirs(OUT_DIR, exist_ok=True)
    safe = "_".join(lbl.lower().replace(" ", "_") for lbl, _, _ in all_series)
    out_path = os.path.join(OUT_DIR, f"battle_{safe}_{int(MONTHLY_INVEST)}eur.mp4")
    print(f"📦 Export → {out_path}")

    writer = FFMpegWriter(
        fps=FPS,
        bitrate=8000,
        codec="libx264",
        extra_args=["-pix_fmt", "yuv420p", "-preset", "faster", "-crf", "18"]
    )

    with tqdm(total=frames_total, desc="🏁 Battle", unit="frame") as pbar:
        def _update(frame):
            pbar.update(1)
            return update(frame)
        ani = FuncAnimation(fig, _update, frames=frames_total, interval=1000 / FPS, blit=False)
        ani.save(out_path, writer=writer)

    plt.close(fig)
    print(f"✅ Vidéo enregistrée : {out_path}")
