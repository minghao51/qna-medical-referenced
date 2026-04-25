from src.rag import production_profile


def test_register_builtin_profiles_includes_baseline_and_optimal(monkeypatch):
    production_profile._PROFILE_REGISTRY.clear()

    def fake_loader(config_path: str, variant_name: str):
        return {"metadata": {"name": variant_name}, "config_path": config_path}

    monkeypatch.setattr(production_profile, "_load_profile_from_experiment", fake_loader)

    production_profile.register_builtin_profiles()

    assert "baseline" in production_profile._PROFILE_REGISTRY
    assert "pymupdf_semantic_hybrid" in production_profile._PROFILE_REGISTRY


def test_apply_production_profile_returns_false_for_unknown_profile(monkeypatch):
    production_profile._PROFILE_REGISTRY.clear()
    monkeypatch.setattr(production_profile, "register_builtin_profiles", lambda: None)

    configured_profiles: list[dict] = []

    def fake_configure(profile):
        configured_profiles.append(profile)

    monkeypatch.setattr("src.rag.runtime.configure_runtime_for_experiment", fake_configure)

    applied = production_profile.apply_production_profile("does-not-exist")

    assert applied is False
    assert configured_profiles == []
