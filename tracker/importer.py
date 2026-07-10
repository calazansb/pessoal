"""Importa o export oficial de dados do Instagram (formato JSON).

Alternativa segura ao login automatizado: no app do Instagram, vá em
Configurações > Central de Contas > Suas informações e permissões >
Baixar suas informações, escolha o formato **JSON** e selecione
"Seguidores e seguindo". O Instagram envia um ZIP; passe o caminho do ZIP
(ou da pasta extraída) para o comando `import-export`.

Como o export não traz o id numérico dos perfis, os usuários são
identificados por "u:<username>". Por isso, evite misturar snapshots de
importação com snapshots baixados via API na mesma base de dados.
"""

from __future__ import annotations

import json
import tempfile
import zipfile
from pathlib import Path

from tracker.db import User


def _extract_usernames(data) -> dict[str, User]:
    """Extrai usernames da estrutura do export (lista de relationship entries)."""
    users: dict[str, User] = {}
    if isinstance(data, dict):
        # following.json usa {"relationships_following": [...]}
        for value in data.values():
            users.update(_extract_usernames(value))
        return users
    for entry in data or []:
        for item in entry.get("string_list_data", []):
            username = item.get("value") or ""
            if not username and item.get("href"):
                username = item["href"].rstrip("/").rsplit("/", 1)[-1]
            if username:
                pk = f"u:{username}"
                users[pk] = User(pk, username)
    return users


def load_export(path: Path) -> tuple[dict[str, User], dict[str, User]]:
    """Lê o ZIP ou a pasta do export e retorna (seguidores, seguindo)."""
    path = Path(path)

    if path.is_file() and path.suffix.lower() == ".zip":
        tmp = Path(tempfile.mkdtemp(prefix="ig-export-"))
        with zipfile.ZipFile(path) as zf:
            members = [
                m for m in zf.namelist()
                if "followers_and_following" in m and m.endswith(".json")
            ]
            if not members:
                raise SystemExit(
                    "O ZIP não contém a pasta 'followers_and_following'. "
                    "Confira se o export foi pedido em formato JSON e inclui "
                    "'Seguidores e seguindo'."
                )
            zf.extractall(tmp, members)
        path = tmp

    followers: dict[str, User] = {}
    following: dict[str, User] = {}
    follower_files = sorted(path.rglob("followers_*.json")) or sorted(path.rglob("followers.json"))
    following_files = sorted(path.rglob("following.json"))

    if not follower_files or not following_files:
        raise SystemExit(
            f"Não encontrei followers_*.json / following.json em {path}. "
            "Confira se o export está em formato JSON."
        )

    for f in follower_files:
        followers.update(_extract_usernames(json.loads(f.read_text(encoding="utf-8"))))
    for f in following_files:
        following.update(_extract_usernames(json.loads(f.read_text(encoding="utf-8"))))

    return followers, following
