from dataclasses import dataclass, field
from typing import List

from django.db import transaction

from research.services.health_score import (
    calculate_company_health_scores,
)
from research.services.metric_normalizer import (
    normalize_company_metrics,
)
from research.services.ratio_calculator import (
    calculate_company_ratios,
)


@dataclass
class PipelineResult:
    ticker: str
    success: bool = True
    steps: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def add_step(self, message):
        self.steps.append(message)

    def add_error(self, message):
        self.success = False
        self.errors.append(message)


@transaction.atomic
def process_company_financials(company):
    """
    Process financial data already imported for a company.

    Current stages:
        1. Normalize financial metrics
        2. Calculate financial ratios
        3. Calculate financial health scores

    SEC synchronization and Company Facts importing can be added once
    their existing service function names are confirmed.
    """
    result = PipelineResult(ticker=company.ticker)

    try:
        metric_result = normalize_company_metrics(company)

        result.add_step(
            f"Normalized financial metrics: {metric_result}"
        )
    except Exception as exc:
        result.add_error(
            f"Metric normalization failed: {exc}"
        )
        raise

    try:
        ratio_result = calculate_company_ratios(company)

        result.add_step(
            f"Calculated financial ratios: {ratio_result}"
        )
    except Exception as exc:
        result.add_error(
            f"Ratio calculation failed: {exc}"
        )
        raise

    try:
        health_result = calculate_company_health_scores(company)

        result.add_step(
            f"Calculated health scores: {health_result}"
        )
    except Exception as exc:
        result.add_error(
            f"Health-score calculation failed: {exc}"
        )
        raise

    return result