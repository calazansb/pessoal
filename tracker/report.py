"""Exibição dos relatórios no terminal (usa rich, se instalado)."""

from __future__ import annotations

from tracker.db import Database, SnapshotDiff, User

try:
    from rich.console import Console
    from rich.table import Table

    _console = Console()

    def _print(text: str = "", style: str | None = None) -> None:
        _console.print(text, style=style)

    def _user_table(title: str, users: list[User], style: str) -> None:
        if not users:
            return
        table = Table(title=f"{title} ({len(users)})", title_style=style, min_width=50)
        table.add_column("Usuário")
        table.add_column("Nome")
        table.add_column("Perfil")
        for u in users:
            table.add_row(
                f"@{u.username}", u.full_name, f"https://instagram.com/{u.username}"
            )
        _console.print(table)

except ImportError:  # sem rich, saída em texto simples

    def _print(text: str = "", style: str | None = None) -> None:
        print(text)

    def _user_table(title: str, users: list[User], style: str) -> None:
        if not users:
            return
        print(f"\n{title} ({len(users)}):")
        for u in users:
            name = f" — {u.full_name}" if u.full_name else ""
            print(f"  @{u.username}{name}  https://instagram.com/{u.username}")


EVENT_LABELS = {
    "new_follower": "🟢 Novo seguidor",
    "lost_follower": "🔴 Deixou de me seguir",
    "started_following": "➕ Comecei a seguir",
    "stopped_following": "➖ Parei de seguir",
}


def show_diff(diff: SnapshotDiff) -> None:
    """Mostra o que mudou desde a última execução."""
    if diff.is_first:
        _print(
            "\nPrimeira execução: base criada. Nas próximas execuções vou mostrar "
            "quem entrou e quem saiu.",
            style="bold",
        )
        return

    changed = any(
        [diff.new_followers, diff.lost_followers, diff.started_following, diff.stopped_following]
    )
    _print("\n=== Mudanças desde a última execução ===", style="bold")
    if not changed:
        _print("Nenhuma mudança.")
        return
    _user_table("🔴 Deixaram de me seguir", diff.lost_followers, "bold red")
    _user_table("🟢 Novos seguidores", diff.new_followers, "bold green")
    _user_table("➕ Comecei a seguir", diff.started_following, "cyan")
    _user_table("➖ Parei de seguir", diff.stopped_following, "yellow")


def show_status(db: Database, snapshot_id: int, full: bool = False) -> None:
    """Mostra o estado atual: totais e quem não segue de volta."""
    info = db.snapshot_info(snapshot_id)
    not_back = db.not_following_back(snapshot_id)
    fans = db.fans(snapshot_id)

    _print(f"\n=== Situação atual (snapshot #{snapshot_id}, {info['taken_at']}) ===", style="bold")
    _print(f"Seguidores: {info['followers_count']}")
    _print(f"Seguindo:   {info['following_count']}")
    _print(f"Mútuos:     {db.mutuals_count(snapshot_id)}")

    _user_table("😤 Eu sigo e NÃO me seguem de volta", not_back, "bold magenta")
    if full:
        _user_table("🤗 Me seguem e eu não sigo de volta", fans, "bold blue")
    else:
        _print(f"\n🤗 Me seguem e eu não sigo de volta: {len(fans)} "
               "(use --completo para listar)")


def show_history(db: Database) -> None:
    snaps = db.list_snapshots()
    if not snaps:
        _print("Nenhum snapshot ainda. Rode o comando 'sync' primeiro.")
        return
    _print("\n=== Histórico de execuções ===", style="bold")
    for s in snaps:
        _print(
            f"#{s['id']}  {s['taken_at']}  seguidores={s['followers_count']}  "
            f"seguindo={s['following_count']}  mudanças={s['event_count']}  ({s['source']})"
        )


def show_events(db: Database, limit: int | None, etype: str | None) -> None:
    events = db.list_events(limit=limit, etype=etype)
    if not events:
        _print("Nenhum evento registrado ainda.")
        return
    _print("\n=== Histórico de mudanças (mais recentes primeiro) ===", style="bold")
    for e in events:
        label = EVENT_LABELS.get(e["type"], e["type"])
        _print(f"{e['taken_at']}  {label}: @{e['username']}")
