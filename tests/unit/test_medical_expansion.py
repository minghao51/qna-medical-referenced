from src.rag import production_profile
from src.rag.production_profile import (
    apply_production_profile,
    get_production_profile,
    register_builtin_profiles,
)


class TestRegisterBuiltinProfiles:
    def setup_method(self):
        production_profile._PROFILE_REGISTRY.clear()

    def test_register_with_fake_loader(self, monkeypatch):
        def fake_loader(config_path, variant_name):
            return {"metadata": {"name": variant_name}, "config_path": config_path}

        monkeypatch.setattr(production_profile, "_load_profile_from_experiment", fake_loader)
        register_builtin_profiles()
        assert "baseline" in production_profile._PROFILE_REGISTRY
        assert "pymupdf_semantic_hybrid" in production_profile._PROFILE_REGISTRY
        assert "baseline_cross_encoder" in production_profile._PROFILE_REGISTRY

    def test_register_idempotent(self, monkeypatch):
        call_count = 0

        def fake_loader(config_path, variant_name):
            nonlocal call_count
            call_count += 1
            return {"name": variant_name}

        monkeypatch.setattr(production_profile, "_load_profile_from_experiment", fake_loader)
        register_builtin_profiles()
        register_builtin_profiles()
        assert call_count == 2

    def test_register_handles_load_failure(self, monkeypatch):
        monkeypatch.setattr(
            production_profile, "_load_profile_from_experiment", lambda *a, **k: None
        )
        register_builtin_profiles()
        assert len(production_profile._PROFILE_REGISTRY) == 0

    def test_baseline_cross_encoder_has_reranking(self, monkeypatch):
        def fake_loader(config_path, variant_name):
            return {"metadata": {"name": variant_name}, "retrieval": {"base": True}}

        monkeypatch.setattr(production_profile, "_load_profile_from_experiment", fake_loader)
        register_builtin_profiles()
        ce = production_profile._PROFILE_REGISTRY["baseline_cross_encoder"]
        assert ce["retrieval"]["enable_reranking"] is True
        assert ce["retrieval"]["reranking_mode"] == "cross_encoder"


class TestGetProductionProfile:
    def setup_method(self):
        production_profile._PROFILE_REGISTRY.clear()

    def test_returns_none_for_none_name(self):
        assert get_production_profile(None) is None

    def test_returns_none_for_empty_name(self):
        assert get_production_profile("") is None

    def test_returns_none_for_unknown_name(self, monkeypatch):
        monkeypatch.setattr(production_profile, "register_builtin_profiles", lambda: None)
        assert get_production_profile("nonexistent") is None

    def test_returns_profile_when_registered(self, monkeypatch):
        production_profile._PROFILE_REGISTRY["test"] = {"key": "value"}
        monkeypatch.setattr(production_profile, "register_builtin_profiles", lambda: None)
        assert get_production_profile("test") == {"key": "value"}


class TestApplyProductionProfile:
    def setup_method(self):
        production_profile._PROFILE_REGISTRY.clear()

    def test_returns_false_for_none(self):
        assert apply_production_profile(None) is False

    def test_returns_false_for_unknown(self, monkeypatch):
        monkeypatch.setattr(production_profile, "register_builtin_profiles", lambda: None)
        assert apply_production_profile("nope") is False

    def test_applies_known_profile(self, monkeypatch):
        production_profile._PROFILE_REGISTRY["myprofile"] = {"test": True}
        monkeypatch.setattr(production_profile, "register_builtin_profiles", lambda: None)

        configured = []
        monkeypatch.setattr(
            "src.rag.index.configure_runtime_for_experiment",
            lambda p: configured.append(p),
        )

        result = apply_production_profile("myprofile")
        assert result is True
        assert len(configured) == 1
