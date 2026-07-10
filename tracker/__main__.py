"""Ponto de entrada da linha de comando.

Uso:
    python -m tracker sync                     # baixa dados do Instagram e atualiza a base
    python -m tracker report [--completo]      # mostra a situação atual sem baixar nada
    python -m tracker history                  # lista todas as execuções
    python -m tracker events [--tipo T] [-n N] # histórico de mudanças
    python -m tracker import-export CAMINHO    # importa o export oficial (ZIP ou pasta)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tracker import report
from tracker.db import EVENT_TYPES, Database


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tracker",
        description="Rastreador de seguidores do Instagram com histórico local.",
    )
    parser.add_argument(
        "--data-dir",
        default="data",
        help="Pasta onde ficam a base de dados e a sessão (padrão: ./data)",
    )
    sub = parser.add_subparsers(dest="command")

    p_sync = sub.add_parser("sync", help="Baixa seguidores/seguindo e atualiza a base")
    p_sync.add_argument("--usuario", help="Usuário do Instagram (ou variável IG_USERNAME)")
    p_sync.add_argument("--completo", action="store_true", help="Lista também quem você não segue de volta")

    p_report = sub.add_parser("report", help="Mostra a situação atual (sem acessar o Instagram)")
    p_report.add_argument("--completo", action="store_true", help="Lista também quem você não segue de volta")

    sub.add_parser("history", help="Lista todas as execuções (snapshots)")

    p_events = sub.add_parser("events", help="Histórico de mudanças")
    p_events.add_argument("--tipo", choices=EVENT_TYPES, help="Filtra por tipo de evento")
    p_events.add_argument("-n", "--limite", type=int, default=50, help="Quantidade (padrão: 50)")

    p_imp = sub.add_parser(
        "import-export",
        help="Importa o export oficial de dados do Instagram (ZIP ou pasta, formato JSON)",
    )
    p_imp.add_argument("caminho", help="Caminho do ZIP ou da pasta extraída")
    p_imp.add_argument("--completo", action="store_true", help="Lista também quem você não segue de volta")

    args = parser.parse_args(argv)
    if not args.command:
        args.command = "sync"
        args.usuario = None
        args.completo = False

    data_dir = Path(args.data_dir)
    db = Database(data_dir / "tracker.db")

    try:
        if args.command == "sync":
            from tracker.insta import fetch_relationships, get_client

            cl = get_client(data_dir, username=getattr(args, "usuario", None))
            followers, following = fetch_relationships(cl)
            diff = db.save_snapshot(followers, following, source="api")
            report.show_diff(diff)
            report.show_status(db, diff.snapshot_id, full=args.completo)

        elif args.command == "import-export":
            from tracker.importer import load_export

            followers, following = load_export(Path(args.caminho))
            print(f"Importado: {len(followers)} seguidores, {len(following)} seguindo.")
            diff = db.save_snapshot(followers, following, source="export")
            report.show_diff(diff)
            report.show_status(db, diff.snapshot_id, full=args.completo)

        elif args.command == "report":
            snap = db.latest_snapshot_id()
            if snap is None:
                print("Nenhum dado ainda. Rode 'python -m tracker sync' primeiro.")
                return 1
            report.show_status(db, snap, full=args.completo)

        elif args.command == "history":
            report.show_history(db)

        elif args.command == "events":
            report.show_events(db, limit=args.limite, etype=args.tipo)

    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
