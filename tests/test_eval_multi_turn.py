"""DeepEval integration tests for multi-turn conversation evaluation."""

import pytest

from src.evals.deepeval_models import get_light_model

pytestmark = [pytest.mark.deepeval, pytest.mark.slow, pytest.mark.live_api]


class TestConversationalTestCaseCreation:
    """Test ConversationalTestCase creation from golden conversations."""

    def test_conversational_test_case_from_golden(self, golden_conversations_fixture):
        """Verify we can create ConversationalTestCase from normalized golden data."""
        from deepeval.test_case import ConversationalTestCase, Turn

        conversation = golden_conversations_fixture[0]
        assert conversation["conversation_id"] == "mt_001"
        assert len(conversation["turns"]) == 2

        turns = [Turn(role=t["role"], content=t["content"]) for t in conversation["turns"]]

        test_case = ConversationalTestCase(
            scenario=conversation["scenario"],
            expected_outcome=conversation["expected_outcome"],
            turns=turns,
        )

        assert len(test_case.turns) == 2
        assert test_case.turns[0].role == "user"
        assert "LDL-C" in test_case.turns[0].content

    def test_conversational_test_case_all_categories(
        self, golden_conversations_fixture, multi_turn_categories
    ):
        """Verify all conversation categories can create valid test cases."""
        from deepeval.test_case import ConversationalTestCase, Turn

        for conv in golden_conversations_fixture:
            assert conv["conversation_category"] in multi_turn_categories

            turns = [Turn(role=t["role"], content=t["content"]) for t in conv["turns"]]
            test_case = ConversationalTestCase(
                scenario=conv["scenario"],
                expected_outcome=conv["expected_outcome"],
                turns=turns,
            )

            assert len(test_case.turns) == len(conv["turns"])

    def test_conversational_test_case_turn_level_keywords(self, golden_conversations_fixture):
        """Verify turn-level expected keywords are preserved in test case metadata."""
        from deepeval.test_case import ConversationalTestCase, Turn

        conversation = golden_conversations_fixture[0]
        expected_keywords = conversation["turn_level_expected_keywords"]

        turns = [Turn(role=t["role"], content=t["content"]) for t in conversation["turns"]]
        test_case = ConversationalTestCase(
            scenario=conversation["scenario"],
            expected_outcome=conversation["expected_outcome"],
            turns=turns,
        )

        assert len(expected_keywords) == len(test_case.turns)


class TestConversationalGEval:
    """Test ConversationalGEval metric for multi-turn evaluation."""

    def test_conversational_g_eval_contextual_followup(self):
        """Test ConversationalGEval with contextual follow-up scenario."""
        from deepeval import assert_test
        from deepeval.metrics import ConversationalGEval
        from deepeval.test_case import ConversationalTestCase, Turn

        test_case = ConversationalTestCase(
            scenario="User asks about LDL targets then asks about diabetes patients",
            expected_outcome="Assistant maintains context about LDL targets when answering diabetes question",
            turns=[
                Turn(
                    role="user",
                    content="What is the LDL-C target for secondary prevention?",
                ),
                Turn(
                    role="assistant",
                    content="The LDL-C target for secondary prevention is less than 1.8 mmol/L.",
                ),
                Turn(
                    role="user",
                    content="And what if the patient has diabetes?",
                ),
                Turn(
                    role="assistant",
                    content="For patients with diabetes and ASCVD, the LDL-C target may be even lower, often less than 1.4 mmol/L, as diabetes is a cardiovascular risk enhancer.",
                ),
            ],
        )

        metric = ConversationalGEval(
            name="Medical Context Retention",
            criteria="The assistant correctly maintains context about LDL-C targets and appropriately addresses how diabetes affects cardiovascular risk management.",
            evaluation_steps=[
                "Check if assistant acknowledges the previous LDL-C target information",
                "Verify assistant correctly identifies diabetes as a risk enhancer",
                "Confirm assistant provides appropriate lipid management guidance for diabetic patients",
            ],
            threshold=0.5,
        )

        assert_test(test_case, [metric])

    def test_conversational_g_eval_clarification(self):
        """Test ConversationalGEval with clarification scenario."""
        from deepeval import assert_test
        from deepeval.metrics import ConversationalGEval
        from deepeval.test_case import ConversationalTestCase, Turn

        test_case = ConversationalTestCase(
            scenario="User asks about FH then asks for clarification on genetic testing",
            expected_outcome="Assistant clearly explains when genetic testing for FH is appropriate",
            turns=[
                Turn(
                    role="user",
                    content="What is FH?",
                ),
                Turn(
                    role="assistant",
                    content="FH stands for Familial Hypercholesterolemia, an inherited genetic condition that causes severely elevated LDL-C levels from birth.",
                ),
                Turn(
                    role="user",
                    content="When should genetic testing be considered for FH?",
                ),
                Turn(
                    role="assistant",
                    content="Genetic testing for FH should be considered when LDL-C is 4.9 mmol/L (190 mg/dL) or higher, or when there is a family history of early heart disease.",
                ),
            ],
        )

        metric = ConversationalGEval(
            name="Clarification Accuracy",
            criteria="The assistant provides clear, accurate clarification about FH genetic testing criteria.",
            evaluation_steps=[
                "Verify assistant provides correct LDL-C threshold (4.9 mmol/L)",
                "Check if assistant mentions family history as additional indicator",
                "Confirm explanation is clear and medically accurate",
            ],
            threshold=0.5,
        )

        assert_test(test_case, [metric])

    def test_conversational_g_eval_with_qwen_judge(self):
        """Test ConversationalGEval using Qwen as judge model."""
        from deepeval.metrics import ConversationalGEval
        from deepeval.test_case import ConversationalTestCase, Turn

        test_case = ConversationalTestCase(
            scenario="User asks about pre-diabetes then follows up on metformin",
            expected_outcome="Assistant maintains context about pre-diabetes management",
            turns=[
                Turn(role="user", content="When should metformin be considered for pre-diabetes?"),
                Turn(
                    role="assistant",
                    content="Metformin may be considered for pre-diabetes when BMI is 23 or higher and lifestyle modifications have not been sufficient.",
                ),
                Turn(role="user", content="What BMI threshold makes it more strongly indicated?"),
                Turn(
                    role="assistant",
                    content="BMI of 23 kg/m2 is the threshold, particularly for individuals with higher metabolic risk.",
                ),
            ],
        )

        metric = ConversationalGEval(
            name="Medical Follow-up Accuracy",
            criteria="The assistant correctly addresses the follow-up question about BMI thresholds for metformin in pre-diabetes.",
            evaluation_steps=[
                "Check if assistant mentions BMI 23 threshold",
                "Verify context about pre-diabetes is maintained",
                "Confirm medical accuracy of the response",
            ],
            threshold=0.5,
            model=get_light_model(),
        )

        metric.measure(test_case)
        assert metric.score is not None


class TestConversationalMetricsIntegration:
    """Test integration of multi-turn conversations with DeepEval metrics."""

    def test_conversational_test_case_with_g_eval(self):
        """Test that ConversationalTestCase can be evaluated with GEval metric."""
        from deepeval import assert_test
        from deepeval.metrics import GEval
        from deepeval.test_case import ConversationalTestCase, LLMTestCaseParams, Turn

        test_case = ConversationalTestCase(
            scenario="User asks multi-part question about lipid management",
            turns=[
                Turn(role="user", content="What is the LDL-C target for secondary prevention?"),
                Turn(
                    role="assistant",
                    content="The LDL-C target for secondary prevention is less than 1.8 mmol/L (< 70 mg/dL).",
                ),
                Turn(role="user", content="And what about triglycerides?"),
                Turn(
                    role="assistant",
                    content="For triglycerides, the target is less than 1.7 mmol/L (< 150 mg/dL) for normal levels.",
                ),
            ],
        )

        metric = GEval(
            name="Multi-Turn Medical Accuracy",
            criteria="The assistant maintains accurate medical information across turns and provides consistent, clinically relevant responses.",
            evaluation_params=[
                LLMTestCaseParams.INPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            threshold=0.5,
        )
        assert_test(test_case, [metric])


class TestMultiTurnDatasetSplit:
    """Test dataset splits for multi-turn conversations."""

    def test_split_distribution(self, golden_conversations_fixture, multi_turn_splits):
        """Verify conversations are distributed across splits."""
        splits = {}
        for conv in golden_conversations_fixture:
            split = conv["dataset_split"]
            splits[split] = splits.get(split, 0) + 1

        for split in multi_turn_splits:
            assert split in splits
            assert splits[split] > 0

    def test_regression_conversations_exist(self, golden_conversations_fixture):
        """Verify regression split has sufficient conversations."""
        regression = [c for c in golden_conversations_fixture if c["dataset_split"] == "regression"]
        assert len(regression) >= 4

    def test_all_difficulties_present(self, golden_conversations_fixture, multi_turn_difficulties):
        """Verify all difficulty levels are represented."""
        difficulties = set(c["difficulty"] for c in golden_conversations_fixture)
        assert difficulties == set(multi_turn_difficulties)


class TestConversationSimulatorIntegration:
    """Test integration with DeepEval's ConversationSimulator for synthetic data."""

    def test_conversation_simulator_import(self):
        """Verify ConversationSimulator can be imported from DeepEval."""
        try:
            from deepeval.simulator import ConversationSimulator

            assert ConversationSimulator is not None
        except ImportError:
            pytest.skip("ConversationSimulator not available in installed DeepEval version")


class TestMultiTurnEndToEnd:
    """End-to-end tests for multi-turn evaluation workflow."""

    def test_full_evaluation_workflow(self, golden_conversations_fixture):
        """Test the complete workflow from golden data to evaluation."""
        from deepeval import evaluate
        from deepeval.metrics import ConversationalGEval
        from deepeval.test_case import ConversationalTestCase, Turn

        conversation = golden_conversations_fixture[0]
        turns = [Turn(role=t["role"], content=t["content"]) for t in conversation["turns"]]

        test_case = ConversationalTestCase(
            scenario=conversation["scenario"],
            expected_outcome=conversation["expected_outcome"],
            turns=turns,
        )

        metric = ConversationalGEval(
            name="Contextual Follow-up Quality",
            criteria="The assistant appropriately follows up on the initial question about LDL-C targets and correctly addresses the diabetes context.",
            threshold=0.5,
        )

        results = evaluate(test_cases=[test_case], metrics=[metric])
        assert results is not None

    def test_multiple_conversations_evaluation(self, golden_conversations_fixture):
        """Test evaluating multiple conversations in batch."""
        from deepeval.metrics import ConversationalGEval
        from deepeval.test_case import ConversationalTestCase, Turn

        conversations_to_test = golden_conversations_fixture[:3]

        test_cases = []
        for conv in conversations_to_test:
            turns = [Turn(role=t["role"], content=t["content"]) for t in conv["turns"]]
            test_case = ConversationalTestCase(
                scenario=conv["scenario"],
                expected_outcome=conv["expected_outcome"],
                turns=turns,
            )
            test_cases.append(test_case)

        assert len(test_cases) == 3

        metric = ConversationalGEval(
            name="Multi-turn Quality",
            criteria="The assistant maintains coherent medical context throughout the conversation.",
            threshold=0.5,
        )

        for tc in test_cases:
            metric.measure(tc)
            assert tc.turns is not None
