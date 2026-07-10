"""Testes da lógica de snapshots, diffs e importação (sem acessar o Instagram).

Rodar com: python tests/test_tracker.py
"""

from __future__ import annotations

import json
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tracker.db import Database, User
from tracker.importer import load_export


def users(*names: str) -> dict[str, User]:
    return {f"pk_{n}": User(f"pk_{n}", n) for n in names}


def test_snapshots_and_events():
    tmp = Path(tempfile.mkdtemp())
    db = Database(tmp / "t.db")

    # Execução 1: base inicial
    diff1 = db.save_snapshot(
        followers=users("ana", "bruno", "carla"),
        following=users("ana", "bruno", "diego"),
        source="api",
    )
    assert diff1.is_first
    assert db.mutuals_count(diff1.snapshot_id) == 2  # ana, bruno

    nb = db.not_following_back(diff1.snapshot_id)
    assert [u.username for u in nb] == ["diego"]

    fans = db.fans(diff1.snapshot_id)
    assert [u.username for u in fans] == ["carla"]

    # Execução 2: carla saiu, eva entrou; parei de seguir diego, comecei a seguir eva
    diff2 = db.save_snapshot(
        followers=users("ana", "bruno", "eva"),
        following=users("ana", "bruno", "eva"),
        source="api",
    )
    assert not diff2.is_first
    assert [u.username for u in diff2.new_followers] == ["eva"]
    assert [u.username for u in diff2.lost_followers] == ["carla"]
    assert [u.username for u in diff2.started_following] == ["eva"]
    assert [u.username for u in diff2.stopped_following] == ["diego"]
    assert db.not_following_back(diff2.snapshot_id) == []

    # Histórico
    snaps = db.list_snapshots()
    assert len(snaps) == 2
    assert snaps[0]["event_count"] == 0
    assert snaps[1]["event_count"] == 4

    events = db.list_events()
    assert len(events) == 4
    lost = db.list_events(etype="lost_follower")
    assert len(lost) == 1 and lost[0]["username"] == "carla"

    # Execução 3: nada mudou
    diff3 = db.save_snapshot(
        followers=users("ana", "bruno", "eva"),
        following=users("ana", "bruno", "eva"),
        source="api",
    )
    assert not any(
        [diff3.new_followers, diff3.lost_followers,
         diff3.started_following, diff3.stopped_following]
    )
    db.close()
    print("test_snapshots_and_events OK")


def test_import_export_zip():
    tmp = Path(tempfile.mkdtemp())

    followers_json = [
        {"string_list_data": [{"href": "https://www.instagram.com/ana", "value": "ana", "timestamp": 1}]},
        {"string_list_data": [{"href": "https://www.instagram.com/bruno", "value": "bruno", "timestamp": 2}]},
    ]
    following_json = {
        "relationships_following": [
            {"string_list_data": [{"href": "https://www.instagram.com/ana", "value": "ana", "timestamp": 3}]},
            {"string_list_data": [{"href": "https://www.instagram.com/diego", "value": "diego", "timestamp": 4}]},
        ]
    }

    zip_path = tmp / "export.zip"
    base = "meta/connections/followers_and_following"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(f"{base}/followers_1.json", json.dumps(followers_json))
        zf.writestr(f"{base}/following.json", json.dumps(following_json))

    followers, following = load_export(zip_path)
    assert sorted(u.username for u in followers.values()) == ["ana", "bruno"]
    assert sorted(u.username for u in following.values()) == ["ana", "diego"]

    db = Database(tmp / "t.db")
    diff = db.save_snapshot(followers, following, source="export")
    nb = db.not_following_back(diff.snapshot_id)
    assert [u.username for u in nb] == ["diego"]
    db.close()
    print("test_import_export_zip OK")


def test_cli_report_flow():
    """Roda os comandos report/history/events com uma base pré-populada."""
    from tracker.__main__ import main

    tmp = Path(tempfile.mkdtemp())
    db = Database(tmp / "tracker.db")
    db.save_snapshot(users("ana"), users("ana", "diego"), source="api")
    db.save_snapshot(users("ana", "eva"), users("ana"), source="api")
    db.close()

    assert main(["--data-dir", str(tmp), "report", "--completo"]) == 0
    assert main(["--data-dir", str(tmp), "history"]) == 0
    assert main(["--data-dir", str(tmp), "events"]) == 0
    print("test_cli_report_flow OK")


if __name__ == "__main__":
    test_snapshots_and_events()
    test_import_export_zip()
    test_cli_report_flow()
    print("\nTodos os testes passaram.")
