# dca/crises.py
# Gestion et affichage des zones de crises économiques sur les graphiques.

import pandas as pd
import csv
import json
import re
import matplotlib.patheffects as patheffects
from matplotlib.patches import Rectangle
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
    ]
    print("🧱 Crises par défaut chargées")
    return defaults


# ========= AFFICHAGE =========

class CrisisOverlay:
    """
    Affiche toutes les crises sous forme de bandes colorées pleine hauteur.
    CORRECTION: le texte n'apparait que lorsque le centre de la période est dans la fenêtre visible
    et il est clipé au graphe et recentré pour ne jamais sortir de l'axe.
    """

    def __init__(self, ax, crises, alpha=0.15, text_alpha=0.95):
        self.ax = ax
        self.crises = crises
        self.alpha = alpha
        self.text_alpha = text_alpha
        self._trans = mtransforms.blended_transform_factory(ax.transData, ax.transAxes)
        self._items = []

        for c in self.crises:
            color = c.get("color", "#ffa726")
            start = pd.Timestamp(c["start"])
            end = pd.Timestamp(c["end"])

            # Bande colorée sur toute la hauteur
            rect = Rectangle(
                (mdates.date2num(start.to_pydatetime()), 0),
                mdates.date2num(end.to_pydatetime()) - mdates.date2num(start.to_pydatetime()),
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

            # Position x centrale de la crise en coordonnées data
            mid_x = mdates.date2num(start.to_pydatetime()) + (
                (mdates.date2num(end.to_pydatetime()) - mdates.date2num(start.to_pydatetime())) / 2
            )

            # Texte en haut du graphe, invisible au départ
            txt = self.ax.text(
                mid_x,
                0.97,  # haut du graphe
                self._shorten(c["name"]),
                transform=self._trans,
                ha="center",
                va="top",
                fontsize=11,
                color="#ffffff",  # blanc pur
                alpha=0.0,  # affiché dynamiquement
                fontweight="bold",
                zorder=20,
                path_effects=[
                    patheffects.withStroke(linewidth=3, foreground="black", alpha=0.7)
                ],
            )


            txt.set_clip_on(True)
            txt.set_clip_path(self.ax.patch)

            self._items.append((rect, txt, start, end, mid_x))

    def update(self, current_time=None, x_left=None, x_right=None):
        """
        Affiche le texte uniquement si le centre de la période est dans la fenêtre [x_left, x_right].
        Recale la position X du texte pour rester à l'intérieur des bords visibles.
        """
        if x_left is None or x_right is None:
            return

        # Convertit en nombres Matplotlib pour comparer proprement
        x_left_num = mdates.date2num(pd.to_datetime(x_left).to_pydatetime())
        x_right_num = mdates.date2num(pd.to_datetime(x_right).to_pydatetime())
        if x_right_num < x_left_num:
            x_left_num, x_right_num = x_right_num, x_left_num

        # petit padding interne pour éviter que le texte colle aux bords
        pad = (x_right_num - x_left_num) * 0.02

        for rect, txt, start, end, mid_x in self._items:
            center_visible = (mid_x >= x_left_num) and (mid_x <= x_right_num)
            # alpha du texte
            txt.set_alpha(self.text_alpha if center_visible else 0.0)

            # clamp x du texte dans la fenêtre visible pour éviter toute sortie
            clamped_x = min(max(mid_x, x_left_num + pad), x_right_num - pad)
            # remet la position, y restant en fraction d'axes via blended transform
            txt.set_position((clamped_x, 0.97))

    @staticmethod
    def _shorten(label: str, max_len=22):
        return label if len(label) <= max_len else (label[:max_len - 1] + "…")
