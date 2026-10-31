"""Static policy: tests must never open the real Chroma corpus implicitly.

``data/chroma-d11`` is a frozen, R2-synced runtime artifact. A test that builds
``ChromaVectorStore`` without an explicit location resolves
``settings.storage.chroma_persist_directory`` and writes the project corpus.
This scan fails fast at review time instead of relying on the runtime mutation
guard in ``tests/conftest.py`` to notice after the fact.
"""

from __future__ import annotations

import ast
from pathlib import Path

TESTS_ROOT = Path(__file__).resolve().parents[1]

# Constructor arguments that pin the store to a temporary/injected location.
ISOLATING_KWARGS = frozenset({"persist_directory", "client", "collection"})
# Fixtures that already patch settings.storage.chroma_persist_directory.
ISOLATING_FIXTURES = frozenset({"fake_chroma_embeddings"})
PERSIST_SETTING = "chroma_persist_directory"


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _arg_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    arguments = node.args
    return {arg.arg for arg in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs)}


def _decorator_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    names: set[str] = set()
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if isinstance(target, ast.Attribute):
            names.add(target.attr)
        elif isinstance(target, ast.Name):
            names.add(target.id)
    return names


def _fixture_dependencies(
    modules: dict[Path, ast.Module],
) -> dict[str, set[str]]:
    dependencies: dict[str, set[str]] = {}
    for tree in modules.values():
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and "fixture" in (
                _decorator_names(node)
            ):
                dependencies[node.name] = _arg_names(node)
    return dependencies


def _reaches_isolating_fixture(
    params: set[str], dependencies: dict[str, set[str]], seen: frozenset[str] = frozenset()
) -> bool:
    if params & ISOLATING_FIXTURES:
        return True
    return any(
        _reaches_isolating_fixture(dependencies.get(name, set()), dependencies, seen | {name})
        for name in params - seen
    )


def _is_autouse_fixture(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call):
            continue
        target = decorator.func
        if not isinstance(target, ast.Attribute) or target.attr != "fixture":
            continue
        if any(
            keyword.arg == "autouse"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value is True
            for keyword in decorator.keywords
        ):
            return True
    return False


def _usefixtures_names(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> set[str]:
    names: set[str] = set()
    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call) or not decorator.args:
            continue
        target = decorator.func
        if not isinstance(target, ast.Attribute) or target.attr != "usefixtures":
            continue
        for argument in decorator.args:
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                names.add(argument.value)
    return names


def _autouse_fixture_names(tree: ast.Module) -> set[str]:
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_autouse_fixture(node)
    }


def _scope_autouse_fixtures(path: Path, root: Path, modules: dict[Path, ast.Module]) -> set[str]:
    """Autouse fixtures that apply to ``path``: its module plus ancestor conftests."""
    autouse = _autouse_fixture_names(modules[path])
    directory = path.parent
    while directory == root or root in directory.parents:
        conftest = modules.get(directory / "conftest.py")
        if conftest is not None:
            autouse |= _autouse_fixture_names(conftest)
        if directory == root:
            break
        directory = directory.parent
    return autouse


def _enclosing_functions(
    node: ast.AST, parents: dict[ast.AST, ast.AST]
) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    enclosing: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    current = parents.get(node)
    while current is not None:
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            enclosing.append(current)
        current = parents.get(current)
    return enclosing


def _enclosing_classes(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> list[ast.ClassDef]:
    enclosing: list[ast.ClassDef] = []
    current = parents.get(node)
    while current is not None:
        if isinstance(current, ast.ClassDef):
            enclosing.append(current)
        current = parents.get(current)
    return enclosing


def _patches_persist_setting(function_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return any(
        isinstance(inner, ast.Constant) and inner.value == PERSIST_SETTING
        for inner in ast.walk(function_node)
    )


def _is_store_call(node: ast.Call) -> bool:
    if not isinstance(node, ast.Call):
        return False
    if isinstance(node.func, ast.Name):
        return node.func.id == "ChromaVectorStore"
    if isinstance(node.func, ast.Attribute):
        return node.func.attr == "ChromaVectorStore"
    return False


def _violations(root: Path) -> list[str]:
    modules = {path: _parse(path) for path in sorted(root.rglob("*.py"))}
    dependencies = _fixture_dependencies(modules)

    found: list[str] = []
    for path, tree in modules.items():
        autouse = _scope_autouse_fixtures(path, root, modules)
        module_isolated = _reaches_isolating_fixture(autouse, dependencies)
        parents = {
            child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)
        }
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not _is_store_call(node):
                continue
            if {keyword.arg for keyword in node.keywords} & ISOLATING_KWARGS:
                continue
            if module_isolated:
                continue
            enclosing = _enclosing_functions(node, parents)
            isolated = any(
                _patches_persist_setting(function)
                or _reaches_isolating_fixture(_arg_names(function), dependencies)
                or _reaches_isolating_fixture(_usefixtures_names(function), dependencies)
                for function in enclosing
            )
            if any(
                _reaches_isolating_fixture(_usefixtures_names(enclosing_class), dependencies)
                for enclosing_class in _enclosing_classes(node, parents)
            ):
                isolated = True
            if isolated:
                continue
            owner = enclosing[0].name if enclosing else "<module>"
            found.append(f"{path.relative_to(root)}:{node.lineno} in {owner}()")
    return found


def test_scanner_detects_unisolated_store(tmp_path: Path):
    """Guard against a vacuous scan: an unisolated construction must be flagged."""
    (tmp_path / "test_probe.py").write_text(
        "def test_probe():\n    ChromaVectorStore(collection_name='probe')\n",
        encoding="utf-8",
    )
    assert _violations(tmp_path) == ["test_probe.py:2 in test_probe()"]

    (tmp_path / "test_probe.py").write_text(
        "def test_probe(tmp_path):\n"
        "    ChromaVectorStore(collection_name='probe', persist_directory=tmp_path / 'chroma')\n",
        encoding="utf-8",
    )
    assert _violations(tmp_path) == []


def test_every_chroma_store_in_tests_is_explicitly_isolated():
    violations = _violations(TESTS_ROOT)
    assert violations == [], (
        "These test constructions would open the real data/chroma-d11 corpus.\n"
        "Pass persist_directory=tmp_path / 'chroma', inject client=/collection=, "
        "or request the fake_chroma_embeddings fixture (it patches "
        "settings.storage.chroma_persist_directory):\n" + "\n".join(violations)
    )


def _load_repo_conftest():
    import importlib.util
    import sys

    conftest_path = TESTS_ROOT / "conftest.py"
    spec = importlib.util.spec_from_file_location("conftest_data_guard", conftest_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_guard_reports_created_removed_and_modified_entries():
    module = _load_repo_conftest()
    changes = module._data_changes({"a": (1, 1), "b": (2, 2)}, {"a": (1, 2), "c": (3, 3)})
    assert changes == ["created c", "removed b", "modified a"]


def test_guard_activation_follows_opt_ins_and_opt_out(monkeypatch):
    import types

    module = _load_repo_conftest()
    serial = types.SimpleNamespace()

    monkeypatch.setenv("QNA_TEST_DATA_GUARD", "0")
    assert module._data_guard_active(serial) is False
    monkeypatch.delenv("QNA_TEST_DATA_GUARD")

    live_enabled = any(
        (module.LIVE_QWEN_ENABLED, module.LIVE_OPENROUTER_ENABLED, module.REAL_API_TESTS_ENABLED)
    )
    assert module._data_guard_active(serial) is (not live_enabled)

    # xdist workers report their peers' writes; the controller owns the check.
    assert module._data_guard_active(types.SimpleNamespace(workerinput={})) is False
