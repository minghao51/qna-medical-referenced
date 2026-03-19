import json
from pathlib import Path

from src.evals.artifacts import ArtifactStore, find_reusable_run, update_run_index


def test_artifact_store_writes_json_jsonl_text(tmp_path: Path):
    store = ArtifactStore(tmp_path, "my run")
    store.write_json("a.json", {"x": 1})
    store.write_jsonl("b.jsonl", [{"n": 1}, {"n": 2}])
    store.write_text("c.txt", "hello")
    pointer = store.write_latest_pointer()

    assert (store.run_dir / "a.json").exists()
    assert (store.run_dir / "b.jsonl").exists()
    assert (store.run_dir / "c.txt").read_text(encoding="utf-8") == "hello"
    assert Path(pointer).read_text(encoding="utf-8").strip() == str(store.run_dir)


def test_run_index_reuses_indexed_run(tmp_path: Path):
    run_dir = tmp_path / "20260319T000000.000000Z_demo"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(
        json.dumps({"run_identity": "abc123", "config": {}, "git_head": "deadbeef"}),
        encoding="utf-8",
    )
    (run_dir / "summary.json").write_text(json.dumps({"status": "ok"}), encoding="utf-8")

    update_run_index(tmp_path, run_identity="abc123", run_dir=run_dir)

    assert find_reusable_run(tmp_path, "abc123") == run_dir
