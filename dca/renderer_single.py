# dca/renderer_single.py
# Rendu vidéo d'un seul actif en animation DCA TikTok

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, FFMpegWriter
from matplotlib.patches import Rectangle
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from matplotlib.image import imread
from tqdm import tqdm

from dca import config as CFG
from dca.data_loader import load_price_series, get_dividends_on_price_index
from dca.dca_simulator import simulate_dca
from dca.logo_manager import get_display_logo
from dca.visual_utils import (
    ease_numeric,
    ease_timestamp,
    fmt_currency,
    choose_time_axis,
    build_sampling_index,
    apply_dark_style,
)
from dca.crises import load_crises, CrisisOverlay


# --------- Paramètres visuels ----------
POV_Y = float(getattr(CFG, "POV_Y", 0.91))
GAIN_Y = float(getattr(CFG, "GAIN_Y", 0.13))
TOP_FRAC = float(getattr(CFG, "TOP_FRAC", 0.86))
BOT_FRAC = float(getattr(CFG, "BOT_FRAC", 0.20))
LEFT_FRAC = float(getattr(CFG, "LEFT_FRAC", 0.18))
RIGHT_FRAC = float(getattr(CFG, "RIGHT_FRAC", 0.80))

SMOOTH_SPAN = getattr(CFG, "SMOOTH_SPAN", 50)
RIGHT_MARGIN_PCT = float(getattr(CFG, "RIGHT_MARGIN_PCT", 0.22))

# Largeur cible d'affichage du logo en filigrane, en points (1/72 pouce).
# Le zoom appliqué à l'image est recalculé à partir de sa largeur réelle en
# pixels pour que tous les logos apparaissent à la même taille malgré des
# résolutions sources très différentes (128px à plus de 2500px).
LOGO_TARGET_WIDTH_PT = float(getattr(CFG, "LOGO_TARGET_WIDTH_PT", 200))

MONTHLY_INVEST = CFG.MONTHLY_INVEST
FPS = CFG.FPS
VIDEO_DURATION = CFG.VIDEO_DURATION
STEP_DAYS_CONF = CFG.STEP_DAYS_CONF
OUT_DIR = CFG.OUT_DIR

COLOR_BACKGROUND = CFG.COLOR_BACKGROUND
COLOR_INVEST = CFG.COLOR_INVEST
COLOR_VALUE = CFG.COLOR_VALUE
COLOR_DIVIDEND = CFG.COLOR_DIVIDEND


# --------- Lissage ---------
def _smooth_series(s: pd.Series, span: int = 50) -> pd.Series:
    s = s.astype(float)
    if len(s) < 10:
        return s
    if len(s) >= 5:
        s = s.rolling(window=5, center=True, min_periods=1).median()
    s = s.ewm(span=max(5, int(span)), adjust=False).mean()
    s = s.ewm(span=max(3, int(span * 0.6)), adjust=False).mean()
    return s


# --------- Rendu vidéo ---------
def make_video_single(spec):
    ticker, label_short, csv_path = spec
    print(f"🎬 Rendu → {ticker} ({label_short})")

    price, can_use_dividends = load_price_series(ticker, label_short, csv_path)
    if price is None or price.empty:
        print(f"❌ Aucune donnée exploitable pour {ticker}")
        return

    div = get_dividends_on_price_index(ticker, price.index) if can_use_dividends else pd.Series(0.0, index=price.index)

    invested_raw, portfolio_raw, portfolio_reinvest_raw = simulate_dca(
        price, MONTHLY_INVEST, div, reinvest=CFG.REINVEST_DIVIDENDS
    )

    span = int(SMOOTH_SPAN)
    portfolio = _smooth_series(portfolio_raw, span)
    portfolio_reinvest = _smooth_series(portfolio_reinvest_raw, span)
    price_smooth = _smooth_series(price, span)
    invested = invested_raw

    target_frames = FPS * VIDEO_DURATION
    idx = build_sampling_index(price_smooth.index, target_frames, STEP_DAYS_CONF)
    invested = invested.reindex(idx).ffill()
    portfolio = portfolio.reindex(idx)
    portfolio_reinvest = portfolio_reinvest.reindex(idx)
    price_smooth = price_smooth.reindex(idx)

    plt.rcParams["font.family"] = CFG.FONT_FAMILY

    fig, ax = plt.subplots(figsize=(9, 16), dpi=160)
    fig.patch.set_facecolor(COLOR_BACKGROUND)
    apply_dark_style(ax)

    # marges
    plt.subplots_adjust(left=LEFT_FRAC, right=RIGHT_FRAC, top=TOP_FRAC, bottom=BOT_FRAC)

    # enlever bordures haut + droite
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)

    # --- FOND NOIR AVANT LE LOGO ---
    dynamic_bg = Rectangle(
        (0, 0),
        1,
        1,
        transform=ax.transAxes,
        facecolor=COLOR_BACKGROUND,
        alpha=1.0,
        zorder=0,
    )
    ax.add_patch(dynamic_bg)

    # --- LOGO PAR-DESSUS (fond retiré + taille normalisée) ---
    try:
        logo_path = get_display_logo(label_short, ticker)
        if logo_path and os.path.exists(logo_path):
            logo_img = imread(logo_path)
            logo_width_px = max(1, logo_img.shape[1])
            zoom = LOGO_TARGET_WIDTH_PT / logo_width_px
            ab = AnnotationBbox(
                OffsetImage(logo_img, zoom=zoom, alpha=0.12),
                (0.5, 0.56),
                frameon=False,
                xycoords="axes fraction",
                zorder=1,  # TRÈS IMPORTANT
            )
            ax.add_artist(ab)
    except Exception:
        pass

    # crises
    overlay = CrisisOverlay(ax, load_crises())

    # POV texte
    fig.text(
        0.5,
        POV_Y,
        f"POV : Tu investis {int(MONTHLY_INVEST)}€/mois\nsur {label_short}",
        ha="center",
        va="center",
        fontsize=20,
        fontweight="bold",
        color="black",
        linespacing=1.3,
        bbox=dict(boxstyle="round,pad=0.5", facecolor="white", edgecolor="none"),
    )

    # courbes
    (inv_line,) = ax.plot([], [], lw=2.5, color=COLOR_INVEST, linestyle="--", zorder=3)
    (port_line,) = ax.plot([], [], lw=3.2, color=COLOR_VALUE, zorder=4)
    (div_line,) = ax.plot([], [], lw=3.2, color=COLOR_DIVIDEND, alpha=0.95, zorder=5)

    # points pulsants
    point_main = ax.scatter([], [], s=80, color=COLOR_VALUE, zorder=6)
    point_halo = ax.scatter([], [], s=300, color=COLOR_VALUE, alpha=0.25, zorder=5)

    point_inv_main = ax.scatter([], [], s=55, color=COLOR_INVEST, zorder=6)
    point_inv_halo = ax.scatter([], [], s=220, color=COLOR_INVEST, alpha=0.22, zorder=5)

    point_div_main = ax.scatter([], [], s=55, color=COLOR_DIVIDEND, zorder=6)
    point_div_halo = ax.scatter([], [], s=220, color=COLOR_DIVIDEND, alpha=0.22, zorder=5)

    inv_text = ax.text(0, 0, "", color="#9ef7b3", fontsize=12, weight="bold")
    port_text = ax.text(0, 0, "", color="#ffb3b3", fontsize=12, weight="bold")
    div_text = ax.text(0, 0, "", color="#ffd54f", fontsize=12, weight="bold")

    if not CFG.SHOW_INVEST_LINE:
        inv_line.set_alpha(0.0)
        point_inv_main.set_alpha(0.0)
        point_inv_halo.set_alpha(0.0)
        inv_text.set_alpha(0.0)

    gain_text = fig.text(
        0.5,
        GAIN_Y,
        "",
        ha="center",
        va="bottom",
        fontsize=30,
        fontweight="bold",
        color="#00e676",
        family="monospace",
    )

    choose_time_axis(ax, price_smooth.index)

    x_all = price_smooth.index
    y_inv_all = invested.values
    y_port_all = portfolio.values
    y_portdiv_all = portfolio_reinvest.values

    ax.set_xlim(x_all[0], x_all[min(max(5, len(x_all) // 30), len(x_all) - 1)])
    ymax_init = float(np.nanmax([
        y_inv_all[:50].max(),
        y_port_all[:50].max(),
        y_portdiv_all[:50].max(),
    ]))
    ax.set_ylim(0, ymax_init * 1.35)

    current_ymax = ax.get_ylim()[1]
    current_ymin = ax.get_ylim()[0]
    current_xmax = ax.get_xlim()[1]
    display_gain = 0.0

    frames_total = FPS * VIDEO_DURATION
    data_len = len(x_all)

    def frame_to_index(frame):
        if data_len <= 1:
            return 0
        progress = frame / max(1, frames_total - 1)
        return min(int(progress * (data_len - 1)), data_len - 1)

    def update(frame):
        nonlocal current_ymax, current_ymin, current_xmax, display_gain

        i = frame_to_index(frame)

        x = x_all[: i + 1]
        y_inv = y_inv_all[: i + 1]
        y_port = y_port_all[: i + 1]
        y_portdiv = y_portdiv_all[: i + 1]

        inv_line.set_data(x, y_inv)
        port_line.set_data(x, y_port)
        div_line.set_data(x, y_portdiv)

        offset_y = (current_ymax - current_ymin) * 0.015

        inv_text.set_position((x[-1], y_inv[-1] - offset_y))
        inv_text.set_text(f"Investi : {fmt_currency(y_inv[-1])}")

        port_text.set_position((x[-1], y_port[-1] + offset_y))
        port_text.set_text(f"Valeur : {fmt_currency(y_port[-1])}")

        if abs(y_portdiv[-1] - y_port[-1]) <= 0.50:
            div_text.set_alpha(0.0)
        else:
            div_text.set_alpha(1.0)
            div_text.set_position((x[-1], y_portdiv[-1] + 2 * offset_y))
            div_text.set_text(f"Réinvestis : {fmt_currency(y_portdiv[-1])}")

        target_gain = y_portdiv[-1] - y_inv[-1]
        display_gain = ease_numeric(display_gain, float(target_gain), base_alpha=0.10)
        gain_text.set_text(f"Gain : {fmt_currency(display_gain)}")
        gain_text.set_color("#00e676" if display_gain >= 0 else "#ff5252")

        dynamic_bg.set_facecolor(COLOR_BACKGROUND)

        max_y = float(np.nanmax([y_inv.max(), y_port.max(), y_portdiv.max()]))
        min_y = float(np.nanmin([y_inv.min(), y_port.min(), y_portdiv.min()]))

        vertical_margin = ((max_y - min_y) * 0.22 if max_y != min_y else max(1.0, max_y * 0.22))
        target_ymax = max_y + vertical_margin
        target_ymin = max(0, min_y - vertical_margin * 0.25)

        total_days = max(1, (x_all[-1] - x_all[0]).days)
        right_margin = pd.Timedelta(days=max(1, int(total_days * RIGHT_MARGIN_PCT)))
        target_xmax = x[-1] + right_margin

        current_ymax = ease_numeric(current_ymax, target_ymax, base_alpha=0.16)
        current_ymin = ease_numeric(current_ymin, target_ymin, base_alpha=0.16)
        current_xmax = ease_timestamp(current_xmax, target_xmax, base_alpha=0.18)

        if current_ymax <= current_ymin:
            current_ymax = current_ymin + 1

        ax.set_xlim(x_all[0], current_xmax)
        ax.set_ylim(current_ymin, current_ymax)

        overlay.update(x_left=x_all[0], x_right=current_xmax)

        pulse = 1 + 0.25 * np.sin(frame * 0.15)

        point_main.set_offsets([x[-1], y_port[-1]])
        point_halo.set_offsets([x[-1], y_port[-1]])
        point_main.set_sizes([80 * pulse])
        point_halo.set_sizes([300 * pulse])

        point_inv_main.set_offsets([x[-1], y_inv[-1]])
        point_inv_halo.set_offsets([x[-1], y_inv[-1]])
        point_inv_main.set_sizes([55 * pulse])
        point_inv_halo.set_sizes([220 * pulse])

        point_div_main.set_offsets([x[-1], y_portdiv[-1]])
        point_div_halo.set_offsets([x[-1], y_portdiv[-1]])
        point_div_main.set_sizes([55 * pulse])
        point_div_halo.set_sizes([220 * pulse])

        return (
            inv_line,
            port_line,
            div_line,
            inv_text,
            port_text,
            div_text,
            gain_text,
            dynamic_bg,
            point_main,
            point_halo,
            point_inv_main,
            point_inv_halo,
            point_div_main,
            point_div_halo,
        )

    os.makedirs(OUT_DIR, exist_ok=True)
    safe_label = label_short.replace(" ", "_").lower()
    out_path = os.path.join(OUT_DIR, f"dca_{safe_label}_{int(MONTHLY_INVEST)}eur.mp4")

    writer = FFMpegWriter(
        fps=FPS,
        bitrate=getattr(CFG, "BITRATE", 8000),
        codec=getattr(CFG, "CODEC", "libx264"),
        extra_args=["-pix_fmt", "yuv420p", "-preset", "faster", "-movflags", "+faststart"],
    )

    print(f"📦 Export → {out_path}")

    with tqdm(total=frames_total, desc=f"🎥 Rendu {label_short}", unit="frame") as pbar:
        def _update(frame):
            pbar.update(1)
            return update(frame)

        ani = FuncAnimation(fig, _update, frames=frames_total, interval=1000 / FPS, blit=False)
        ani.save(out_path, writer=writer)

    plt.close(fig)
    print(f"✅ OK : {out_path}")
