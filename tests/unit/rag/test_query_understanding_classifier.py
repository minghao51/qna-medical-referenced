from src.rag.query_understanding.classifier import QueryType, classify_query


def test_definition_query_classification() -> None:
    classification = classify_query("What is LDL cholesterol?")
    assert classification.query_type == QueryType.DEFINITION


def test_symptom_query_classification() -> None:
    classification = classify_query("Symptoms of anemia?")
    assert classification.query_type == QueryType.SYMPTOM_QUERY


def test_treatment_query_classification() -> None:
    classification = classify_query("Treatment for hypertension?")
    assert classification.query_type == QueryType.TREATMENT


def test_comparison_query_classification() -> None:
    classification = classify_query("LDL vs HDL?")
    assert classification.query_type == QueryType.COMPARISON


def test_reference_range_query_classification() -> None:
    classification = classify_query("What is the normal blood glucose range?")
    assert classification.query_type == QueryType.REFERENCE_RANGE
