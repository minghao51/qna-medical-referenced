from pathlib import Path

from src.evals.artifacts import ArtifactStore


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
