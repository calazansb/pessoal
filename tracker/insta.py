"""Acesso ao Instagram via instagrapi (API privada, mesma que o app usa).

A sessão de login é salva em disco (data/session.json) para que as próximas
execuções reaproveitem o login — isso evita pedir senha toda vez e reduz o
risco de o Instagram sinalizar a conta por logins repetidos.
"""

from __future__ import annotations

import os
from getpass import getpass
from pathlib import Path

from tracker.db import User


def _ask_verification_code(username: str, choice=None) -> str:
    return input(f"Código de verificação (2FA/desafio) para @{username}: ").strip()


def get_client(data_dir: Path, username: str | None = None, password: str | None = None):
    """Retorna um Client logado, reaproveitando a sessão salva se existir."""
    from instagrapi import Client

    username = username or os.environ.get("IG_USERNAME") or input("Usuário do Instagram: ").strip()
    password = password or os.environ.get("IG_PASSWORD")

    session_file = data_dir / "session.json"
    cl = Client()
    cl.delay_range = [1, 3]  # pausa entre requisições, comportamento mais "humano"
    cl.challenge_code_handler = _ask_verification_code

    if session_file.exists():
        try:
            cl.load_settings(session_file)
            cl.login(username, password or "")
            cl.get_timeline_feed()  # valida se a sessão ainda serve
            return cl
        except Exception:
            print("Sessão salva expirou, fazendo login novamente...")
            cl = Client()
            cl.delay_range = [1, 3]
            cl.challenge_code_handler = _ask_verification_code

    if not password:
        password = getpass(f"Senha de @{username}: ")

    try:
        cl.login(username, password)
    except Exception as exc:
        if "two_factor" in str(exc).lower() or "two factor" in str(exc).lower():
            code = _ask_verification_code(username)
            cl.login(username, password, verification_code=code)
        else:
            raise

    data_dir.mkdir(parents=True, exist_ok=True)
    cl.dump_settings(session_file)
    return cl


def fetch_relationships(cl) -> tuple[dict[str, User], dict[str, User]]:
    """Baixa a lista completa de seguidores e de quem você segue."""
    me = cl.user_id

    print("Baixando seguidores...")
    raw_followers = cl.user_followers(me)
    print(f"  {len(raw_followers)} seguidores.")

    print("Baixando quem você segue...")
    raw_following = cl.user_following(me)
    print(f"  {len(raw_following)} seguindo.")

    followers = {
        str(pk): User(str(pk), u.username, u.full_name or "")
        for pk, u in raw_followers.items()
    }
    following = {
        str(pk): User(str(pk), u.username, u.full_name or "")
        for pk, u in raw_following.items()
    }
    return followers, following
