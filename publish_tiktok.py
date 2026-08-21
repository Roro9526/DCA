# publish_tiktok.py
# Envoie une vidéo déjà générée (dossier publier/) vers la boîte de réception
# TikTok du compte autorisé, en mode brouillon.
#
# Usage :
#   py publish_tiktok.py publier/dca_tesla_100eur.mp4
#
# Première utilisation : une URL d'autorisation TikTok s'affiche, à ouvrir
# dans le navigateur. Les fois suivantes réutilisent le token sauvegardé
# (tiktok_tokens.json) et se rafraîchissent automatiquement.

import sys

from dca.tiktok_client import upload_draft, TikTokAuthError


def main():
    if len(sys.argv) != 2:
        print("Usage : py publish_tiktok.py <chemin_vers_la_video.mp4>")
        sys.exit(1)

    video_path = sys.argv[1]
    try:
        upload_draft(video_path)
    except TikTokAuthError as e:
        print(f"❌ {e}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"❌ Fichier introuvable : {video_path}")
        sys.exit(1)


if __name__ == "__main__":
    main()
