# dca/crises.py
# Gestion et affichage des zones de crises économiques sur les graphiques.

import pandas as pd
import csv
import json
import re
import matplotlib.patheffects as patheffects
from matplotlib.patches import Rectangle
from matplotlib.colors import to_rgba
from matplotlib import transforms as mtransforms
import matplotlib.dates as mdates


# ========= UTILITAIRES =========

def hex_or_none(c: str):
    if isinstance(c, str) and re.fullmatch(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})", c):
        return c
    return None


# ========= CHARGEMENT =========

def load_crises_from_json(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        crises = []
        for item in data:
            name = str(item.get("name", "")).strip()
            start = pd.to_datetime(item.get("start", ""), errors="coerce")
            end = pd.to_datetime(item.get("end", ""), errors="coerce")
            color = hex_or_none(str(item.get("color", "#ffa726")))
            if name and pd.notna(start) and pd.notna(end):
                crises.append({
                    "name": name,
                    "start": start,
                    "end": end,
                    "color": color or "#ffa726"
                })
        return crises
    except Exception as e:
        print(f"⚠️ Impossible de lire {path} (JSON) : {e}")
        return []


def load_crises_from_csv(path: str):
    try:
        crises = []
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = str(row.get("name", "")).strip()
                start = pd.to_datetime(row.get("start", ""), errors="coerce")
                end = pd.to_datetime(row.get("end", ""), errors="coerce")
                color = hex_or_none(str(row.get("color", "#ffa726")))
                if name and pd.notna(start) and pd.notna(end):
                    crises.append({
                        "name": name,
                        "start": start,
                        "end": end,
                        "color": color or "#ffa726"
                    })
        return crises
    except Exception as e:
        print(f"⚠️ Impossible de lire {path} (CSV) : {e}")
        return []


def load_crises_from_inline(spec: str):
    if not spec:
        return []
    crises = []
    parts = [p.strip() for p in spec.split(";") if p.strip()]
    for p in parts:
        fields = [x.strip() for x in p.split("|")]
        if len(fields) < 3:
            continue
        name = fields[0]
        start = pd.to_datetime(fields[1], errors="coerce")
        end = pd.to_datetime(fields[2], errors="coerce")
        color = hex_or_none(fields[3]) if len(fields) >= 4 else "#ffa726"
        if name and pd.notna(start) and pd.notna(end):
            crises.append({
                "name": name,
                "start": start,
                "end": end,
                "color": color or "#ffa726"
            })
    return crises


def load_crises(CRISES_PATH=None, CRISES_INLINE=""):
    if CRISES_PATH:
        p = CRISES_PATH
        if p.lower().endswith(".json"):
            crises = load_crises_from_json(p)
        elif p.lower().endswith(".csv"):
            crises = load_crises_from_csv(p)
        else:
            crises = []
        if crises:
            print(f"🧱 {len(crises)} crises chargées depuis {p}")
            return crises

    crises = load_crises_from_inline(CRISES_INLINE)
    if crises:
        print(f"🧱 {len(crises)} crises chargées depuis CRISES_INLINE")
        return crises

    defaults = [
        {
            "name": "Crise financière 2008",
            "start": pd.Timestamp("2007-10-01"),
            "end": pd.Timestamp("2009-06-01"),
            "color": "#ff5252",
        },
        {
            "name": "Covid-19",
            "start": pd.Timestamp("2020-02-15"),
            "end": pd.Timestamp("2020-11-01"),
            "color": "#2979ff",
        },
        {
            "name": "Guerre Ukraine",
            "start": pd.Timestamp("2022-02-01"),
            "end": pd.Timestamp("2023-03-01"),
            "color": "#ff9100",
        },
        {
            "name": "Guerre Israël-Hamas",
            "start": pd.Timestamp("2023-10-07"),
            "end": pd.Timestamp("2024-04-01"),
            "color": "#ab47bc",
        },
        {
            "name": "Guerre Iran-Israël",
            "start": pd.Timestamp("2025-06-13"),
            "end": pd.Timestamp("2025-06-25"),
            "color": "#26c6da",
        },
    ]
    print("🧱 Crises par défaut chargées")
    return defaults


# ========= AFFICHAGE =========

class CrisisOverlay:
    """
    Affiche chaque crise comme une bande colorée pleine hauteur, délimitée par
    deux liserés verticaux (début/fin de la période), avec une étiquette sur
    fond sombre translucide dont le texte reprend la couleur de la crise
    (pas de blanc pur, pour rester lisible sans casser le thème sombre).
    Le texte est visible dès qu'une partie de la période est dans la fenêtre
    visible [x_left, x_right] et reste centré sur la portion visible.
    """

    def __init__(self, ax, crises, alpha=0.20, text_alpha=0.95):
        self.ax = ax
        self.crises = crises
        self.alpha = alpha
        self.text_alpha = text_alpha
        self._trans = mtransforms.blended_transform_factory(ax.transData, ax.transAxes)
        self._items = []

        # Trié par date de début : les crises proches dans le temps (ex. Covid,
        # Ukraine, Israël-Hamas, Iran-Israël) alternent alors de rangée pour ne
        # pas superposer leurs étiquettes quand elles sont visibles ensemble.
        sorted_crises = sorted(self.crises, key=lambda c: pd.Timestamp(c["start"]))
        row_ys = (0.97, 0.895, 0.82)

        for i, c in enumerate(sorted_crises):
            row_y = row_ys[i % len(row_ys)]
            color = c.get("color", "#ffa726")
            start = pd.Timestamp(c["start"])
            end = pd.Timestamp(c["end"])
            start_num = mdates.date2num(start.to_pydatetime())
            end_num = mdates.date2num(end.to_pydatetime())

            # Bande colorée sur toute la hauteur
            rect = Rectangle(
                (start_num, 0),
                end_num - start_num,
                1.0,
                transform=self._trans,
                facecolor=color,
                edgecolor="none",
                alpha=self.alpha,
                zorder=1,
            )
            rect.set_clip_on(True)
            rect.set_clip_path(self.ax.patch)
            self.ax.add_patch(rect)

            # Liserés verticaux marquant le début et la fin de la période
            for x_num in (start_num, end_num):
                (edge,) = self.ax.plot(
                    [x_num, x_num],
                    [0, 1],
                    transform=self._trans,
                    color=color,
                    alpha=0.55,
                    linewidth=1.3,
                    linestyle="--",
                    zorder=2,
                    clip_on=True,
                )
                edge.set_clip_path(self.ax.patch)

            # Position x centrale de la crise en coordonnées data
            mid_x = start_num + (end_num - start_num) / 2

            # Étiquette : fond sombre translucide + texte de la couleur de la crise
            txt = self.ax.text(
                mid_x,
                row_y,
                self._shorten(c["name"]),
                transform=self._trans,
                ha="center",
                va="top",
                fontsize=12,
                color=color,
                alpha=0.0,  # affiché dynamiquement
                fontweight="bold",
                zorder=20,
                bbox=dict(
                    boxstyle="round,pad=0.35,rounding_size=0.3",
                    facecolor=to_rgba("#05070b", 0.72),
                    edgecolor=to_rgba(color, 0.9),
                    linewidth=1.2,
                ),
                path_effects=[
                    patheffects.withStroke(linewidth=1.5, foreground="black", alpha=0.5)
                ],
            )

            txt.set_clip_on(True)
            txt.set_clip_path(self.ax.patch)

            self._items.append((rect, txt, start_num, end_num, row_y))

    def update(self, current_time=None, x_left=None, x_right=None):
        """
        Affiche le texte dès qu'une partie de la période [start, end] recoupe
        la fenêtre visible [x_left, x_right], et centre l'étiquette sur la
        portion visible (recalée pour ne jamais sortir de l'axe).
        """
        if x_left is None or x_right is None:
            return

        # Convertit en nombres Matplotlib pour comparer proprement
        # (on tronque les nanosecondes pour éviter un UserWarning de matplotlib)
        x_left_num = mdates.date2num(pd.to_datetime(x_left).replace(nanosecond=0).to_pydatetime())
        x_right_num = mdates.date2num(pd.to_datetime(x_right).replace(nanosecond=0).to_pydatetime())
        if x_right_num < x_left_num:
            x_left_num, x_right_num = x_right_num, x_left_num

        # petit padding interne pour éviter que le texte colle aux bords
        pad = max((x_right_num - x_left_num) * 0.02, 1e-6)

        for rect, txt, start_num, end_num, row_y in self._items:
            overlap_visible = (start_num <= x_right_num) and (end_num >= x_left_num)
            txt.set_alpha(self.text_alpha if overlap_visible else 0.0)

            if overlap_visible:
                visible_left = max(start_num, x_left_num)
                visible_right = min(end_num, x_right_num)
                center = (visible_left + visible_right) / 2
                clamped_x = min(max(center, x_left_num + pad), x_right_num - pad)
                txt.set_position((clamped_x, row_y))

    @staticmethod
    def _shorten(label: str, max_len=24):
        return label if len(label) <= max_len else (label[:max_len - 1] + "…")
