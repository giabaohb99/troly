from worker.jobs.backup import choose_to_delete

W = "backups/weekly/"
P = "backups/premigrate/"


def test_keeps_newest_five_deleting_premigrate_first():
    keys = [
        f"{W}20261101-020000.dump",
        f"{W}20261108-020000.dump",
        f"{P}20261109-100000-a.dump",
        f"{P}20261110-100000-b.dump",
        f"{P}20261111-100000-c.dump",
        f"{P}20261112-100000-d.dump",
    ]
    assert choose_to_delete(keys, 5) == [f"{P}20261109-100000-a.dump"]


def test_many_deploys_never_remove_last_weekly():
    keys = [f"{W}20261101-020000.dump"] + [f"{P}2026111{i}-100000.dump" for i in range(6)]
    removed = choose_to_delete(keys, 5)
    assert f"{W}20261101-020000.dump" not in removed
    assert len(removed) == 2


def test_nothing_removed_when_under_limit():
    assert choose_to_delete([f"{W}20261101-020000.dump"], 5) == []
