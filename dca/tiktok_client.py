# dca/tiktok_client.py
# Intégration TikTok Content Posting API, mode "brouillon" (scope video.upload).
# La vidéo est envoyée dans la boîte de réception TikTok du compte autorisé ;
# il faut ensuite ouvrir l'appli TikTok et valider la publication à la main
# (ajouter légende, choisir la confidentialité, etc.) — ce mode ne nécessite
# pas d'audit TikTok, contrairement à la publication directe (video.publish).
#
# N'utilise que la bibliothèque standard (urllib) pour éviter une dépendance
# supplémentaire au projet.

import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request

from dca.config import (
    TIKTOK_CLIENT_KEY,
    TIKTOK_CLIENT_SECRET,
    TIKTOK_REDIRECT_URI,
    TIKTOK_TOKENS_PATH,
)

AUTHORIZE_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
INBOX_INIT_URL = "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/"
SCOPE = "video.upload"

# Envoi en un seul morceau : simple et suffisant pour les vidéos de ce projet
# (quelques dizaines de Mo). Au-delà, TikTok exige un envoi découpé en
# plusieurs morceaux, non géré ici.
MAX_SINGLE_CHUNK_BYTES = 60 * 1024 * 1024


class TikTokAuthError(RuntimeError):
    pass


def _post_form(url: str, fields: dict) -> dict:
    data = urllib.parse.urlencode(fields).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Cache-Control": "no-cache",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise TikTokAuthError(f"Erreur HTTP {e.code} sur {url} : {body}") from e


def _post_json(url: str, payload: dict, access_token: str) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json; charset=UTF-8",
            "Authorization": f"Bearer {access_token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise TikTokAuthError(f"Erreur HTTP {e.code} sur {url} : {body}") from e


def build_authorize_url() -> str:
    if not TIKTOK_CLIENT_KEY:
        raise TikTokAuthError(
            "TIKTOK_CLIENT_KEY manquant dans .env — crée d'abord une app sur "
            "developers.tiktok.com."
        )
    state = secrets.token_urlsafe(16)
    params = {
        "client_key": TIKTOK_CLIENT_KEY,
        "response_type": "code",
        "scope": SCOPE,
        "redirect_uri": TIKTOK_REDIRECT_URI,
        "state": state,
    }
    return f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}", state


def _extract_code_from_input(raw: str) -> str:
    """Accepte soit le code brut, soit l'URL complète de redirection collée par l'utilisateur."""
    raw = raw.strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        parsed = urllib.parse.urlparse(raw)
        qs = urllib.parse.parse_qs(parsed.query)
        code = qs.get("code", [None])[0]
        if not code:
            raise TikTokAuthError("Aucun paramètre 'code' trouvé dans l'URL collée.")
        return code
    return raw


def exchange_code_for_tokens(code: str) -> dict:
    fields = {
        "client_key": TIKTOK_CLIENT_KEY,
        "client_secret": TIKTOK_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": TIKTOK_REDIRECT_URI,
    }
    tokens = _post_form(TOKEN_URL, fields)
    if "access_token" not in tokens:
        raise TikTokAuthError(f"Échange du code impossible : {tokens}")
    return _with_expiry(tokens)


def refresh_tokens(refresh_token: str) -> dict:
    fields = {
        "client_key": TIKTOK_CLIENT_KEY,
        "client_secret": TIKTOK_CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    tokens = _post_form(TOKEN_URL, fields)
    if "access_token" not in tokens:
        raise TikTokAuthError(f"Rafraîchissement du token impossible : {tokens}")
    return _with_expiry(tokens)


def _with_expiry(tokens: dict) -> dict:
    now = time.time()
    tokens["obtained_at"] = now
    tokens["expires_at"] = now + float(tokens.get("expires_in", 0))
    return tokens


def load_saved_tokens() -> dict | None:
    if not os.path.exists(TIKTOK_TOKENS_PATH):
        return None
    with open(TIKTOK_TOKENS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_tokens(tokens: dict) -> None:
    with open(TIKTOK_TOKENS_PATH, "w", encoding="utf-8") as f:
        json.dump(tokens, f, indent=2)


def run_interactive_authorization() -> dict:
    """
    Flux OAuth pensé pour un usage en ligne de commande, sans serveur local :
    TikTok exige une redirect_uri en HTTPS, donc on n'essaie pas d'écouter en
    local. On affiche l'URL d'autorisation, l'utilisateur se connecte dans son
    navigateur, puis colle ici l'URL vers laquelle il a été redirigé (même si
    la page ne charge pas, le code est visible dans la barre d'adresse).
    """
    url, expected_state = build_authorize_url()
    print("\n🔗 Ouvre cette URL dans ton navigateur, connecte-toi et autorise l'app :")
    print(f"   {url}\n")
    print(
        "Après connexion, TikTok te redirige vers une page qui ne chargera "
        "probablement pas (normal, c'est une adresse locale). Copie l'URL "
        "complète depuis la barre d'adresse de ton navigateur et colle-la ici."
    )
    raw = input("URL de redirection (ou juste le code) : ")
    code = _extract_code_from_input(raw)
    tokens = exchange_code_for_tokens(code)
    save_tokens(tokens)
    print("✅ Autorisation TikTok enregistrée.")
    return tokens


def get_valid_access_token() -> str:
    tokens = load_saved_tokens()
    if tokens is None:
        tokens = run_interactive_authorization()

    if time.time() >= tokens.get("expires_at", 0) - 60:
        refresh_token = tokens.get("refresh_token")
        if not refresh_token:
            tokens = run_interactive_authorization()
        else:
            try:
                tokens = refresh_tokens(refresh_token)
                save_tokens(tokens)
            except TikTokAuthError:
                tokens = run_interactive_authorization()

    return tokens["access_token"]


def upload_draft(video_path: str) -> dict:
    """
    Envoie la vidéo dans la boîte de réception TikTok du compte autorisé
    (brouillon à finaliser manuellement dans l'appli). Retourne la réponse
    d'initialisation TikTok (contient notamment publish_id).
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(video_path)

    video_size = os.path.getsize(video_path)
    if video_size > MAX_SINGLE_CHUNK_BYTES:
        raise TikTokAuthError(
            f"Vidéo trop volumineuse ({video_size / 1_000_000:.1f} Mo) pour "
            "l'envoi en un seul morceau géré par ce script (limite "
            f"{MAX_SINGLE_CHUNK_BYTES / 1_000_000:.0f} Mo)."
        )

    access_token = get_valid_access_token()

    init_payload = {
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": video_size,
            "chunk_size": video_size,
            "total_chunk_count": 1,
        }
    }
    init_resp = _post_json(INBOX_INIT_URL, init_payload, access_token)
    data = init_resp.get("data") or {}
    upload_url = data.get("upload_url")
    publish_id = data.get("publish_id")
    if not upload_url:
        raise TikTokAuthError(f"Initialisation de l'envoi impossible : {init_resp}")

    with open(video_path, "rb") as f:
        video_bytes = f.read()

    put_req = urllib.request.Request(
        upload_url,
        data=video_bytes,
        headers={
            "Content-Type": "video/mp4",
            "Content-Range": f"bytes 0-{video_size - 1}/{video_size}",
        },
        method="PUT",
    )
    try:
        with urllib.request.urlopen(put_req) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise TikTokAuthError(f"Envoi de la vidéo échoué ({e.code}) : {body}") from e

    print(f"📥 Vidéo envoyée dans la boîte de réception TikTok (publish_id={publish_id}).")
    print("👉 Ouvre l'appli TikTok pour finaliser la publication (légende, visibilité...).")
    return init_resp
