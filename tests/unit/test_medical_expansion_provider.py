from src.rag.medical_expansion import (
    MedicalExpansion,
    NoopMedicalExpansionProvider,
    get_medical_expansion_provider,
)


class TestMedicalExpansion:
    def test_normalized_collapses_whitespace(self):
        exp = MedicalExpansion(term="  high   blood   pressure  ", source="test")
        assert exp.normalized() == "high blood pressure"

    def test_normalized_preserves_clean_term(self):
        exp = MedicalExpansion(term="hypertension", source="snomed")
        assert exp.normalized() == "hypertension"

    def test_as_trace_payload(self):
        exp = MedicalExpansion(term="diabetes", source="icd10", relation="broader")
        payload = exp.as_trace_payload()
        assert payload["term"] == "diabetes"
        assert payload["source"] == "icd10"
        assert payload["relation"] == "broader"

    def test_as_trace_payload_normalizes_term(self):
        exp = MedicalExpansion(term="  type 2   diabetes  ", source="test")
        payload = exp.as_trace_payload()
        assert payload["term"] == "type 2 diabetes"

    def test_frozen(self):
        exp = MedicalExpansion(term="x", source="y")
        try:
            exp.term = "z"
            raise AssertionError("Should be frozen")
        except AttributeError:
            pass

    def test_default_relation_is_none(self):
        exp = MedicalExpansion(term="x", source="y")
        assert exp.relation is None


class TestNoopMedicalExpansionProvider:
    def test_returns_empty_list(self):
        provider = NoopMedicalExpansionProvider()
        assert provider.expand("any query") == []

    def test_with_base_queries(self):
        provider = NoopMedicalExpansionProvider()
        assert provider.expand("query", base_queries=["q1", "q2"]) == []

    def test_provider_name(self):
        assert NoopMedicalExpansionProvider.provider_name == "noop"


class TestGetMedicalExpansionProvider:
    def test_none_returns_noop(self):
        provider = get_medical_expansion_provider(None)
        assert isinstance(provider, NoopMedicalExpansionProvider)

    def test_empty_string_returns_noop(self):
        provider = get_medical_expansion_provider("")
        assert isinstance(provider, NoopMedicalExpansionProvider)

    def test_noop_name_returns_noop(self):
        provider = get_medical_expansion_provider("noop")
        assert isinstance(provider, NoopMedicalExpansionProvider)

    def test_unknown_name_returns_noop(self):
        provider = get_medical_expansion_provider("unknown_provider")
        assert isinstance(provider, NoopMedicalExpansionProvider)
