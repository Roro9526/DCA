# dca/__init__.py
# Package du projet DCA TikTok
# Contient les outils de simulation, chargement, rendu et configuration

__version__ = "2025.11.10"

from dca import config
from dca import data_loader
from dca import dca_simulator
from dca import logo_manager
from dca import visual_utils
from dca import crises
from dca import renderer_single
from dca import renderer_battle


def about():
    """Affiche un résumé rapide du package DCA TikTok."""
    print(f"DCA TikTok v{__version__}")
    print("Modules disponibles :")
    print(" - config              → variables globales et .env")
    print(" - data_loader         → chargement des prix et dividendes")
    print(" - dca_simulator       → logique DCA et réinvestissement")
    print(" - logo_manager        → gestion et téléchargement des logos")
    print(" - crises              → gestion des crises économiques")
    print(" - visual_utils        → outils visuels (style, easing, titres)")
    print(" - renderer_single     → rendu d’un actif unique")
    print(" - renderer_battle     → rendu compétition multi-actifs")
    print("")


if __name__ == "__main__":
    about()
