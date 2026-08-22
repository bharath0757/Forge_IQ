import pytest
from app.evaluation.runner import get_evaluation_runner
from app.evaluation.metrics import calculate_metrics
from app.evaluation.reports import generate_report

def test_evaluation_runner_not_implemented():
    runner = get_evaluation_runner()
    with pytest.raises(NotImplementedError, match="Reference data unavailable"):
        runner.evaluate_dataset()

def test_calculate_metrics_not_implemented():
    with pytest.raises(NotImplementedError, match="Reference data unavailable"):
        calculate_metrics([], [])

def test_generate_report_not_implemented():
    with pytest.raises(NotImplementedError, match="Reference data unavailable"):
        generate_report({})
