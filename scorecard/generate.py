"""Generate a markdown reliability scorecard for TrustPipe.

The scorecard is intentionally based on local project configuration so it can run
in CI before Snowflake, Kafka, or external APIs are available.
"""
from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from config.settings import CONTRACTS_PATH, REPO_ROOT, load_contracts

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScoreComponent:
    name: str
    score: int
    weight: int
    detail: str

    @property
    def weighted_points(self) -> float:
        return self.score * self.weight / 100


def _contract_score() -> ScoreComponent:
    contracts = load_contracts()
    sources = len(contracts)
    columns = sum(len(spec.get("columns", {})) for spec in contracts.values())
    primary_keys = sum(1 for spec in contracts.values() if spec.get("primary_keys"))
    constrained_columns = sum(
        1
        for spec in contracts.values()
        for rules in spec.get("columns", {}).values()
        if {"min", "max", "allowed"} & set(rules)
    )

    checks = [
        sources >= 3,
        columns >= 10,
        primary_keys == sources,
        constrained_columns >= 5,
    ]
    score = round(100 * sum(checks) / len(checks))
    return ScoreComponent(
        name="Data Contracts",
        score=score,
        weight=35,
        detail=(
            f"{sources} sources, {columns} columns, {primary_keys} primary-key "
            f"definitions, {constrained_columns} constrained columns"
        ),
    )


def _dbt_score() -> ScoreComponent:
    marts_yml = REPO_ROOT / "dbt" / "models" / "marts" / "marts.yml"
    custom_tests = list((REPO_ROOT / "dbt" / "tests").glob("*.sql"))
    mart_models = list((REPO_ROOT / "dbt" / "models" / "marts").glob("*.sql"))
    staging_models = list((REPO_ROOT / "dbt" / "models" / "staging").glob("*.sql"))

    checks = [
        marts_yml.exists(),
        bool(custom_tests),
        len(mart_models) >= 3,
        len(staging_models) >= 3,
    ]
    score = round(100 * sum(checks) / len(checks))
    return ScoreComponent(
        name="dbt Quality Gates",
        score=score,
        weight=25,
        detail=(
            f"{len(staging_models)} staging models, {len(mart_models)} mart models, "
            f"{len(custom_tests)} custom SQL tests"
        ),
    )


def _runtime_quality_score() -> ScoreComponent:
    expected_files = [
        REPO_ROOT / "quality" / "expectations" / "run_suite.py",
        REPO_ROOT / "quality" / "anomaly" / "detectors.py",
        REPO_ROOT / "quality" / "monitors" / "checks.py",
    ]
    present = [path for path in expected_files if path.exists()]
    score = round(100 * len(present) / len(expected_files))
    return ScoreComponent(
        name="Runtime Quality",
        score=score,
        weight=25,
        detail=f"{len(present)}/{len(expected_files)} quality modules present",
    )


def _automation_score() -> ScoreComponent:
    expected_paths = [
        REPO_ROOT / "Makefile",
        REPO_ROOT / "requirements.txt",
        REPO_ROOT / "docker-compose.yml",
        REPO_ROOT / "tests",
    ]
    present = [path for path in expected_paths if path.exists()]
    score = round(100 * len(present) / len(expected_paths))
    return ScoreComponent(
        name="Automation",
        score=score,
        weight=15,
        detail=f"{len(present)}/{len(expected_paths)} local automation assets present",
    )


def build_components() -> list[ScoreComponent]:
    return [
        _contract_score(),
        _dbt_score(),
        _runtime_quality_score(),
        _automation_score(),
    ]


def total_score(components: list[ScoreComponent]) -> int:
    return round(sum(component.weighted_points for component in components))


def render_markdown(components: list[ScoreComponent]) -> str:
    score = total_score(components)
    rows = "\n".join(
        "| {name} | {score} | {weight}% | {detail} |".format(
            name=component.name,
            score=component.score,
            weight=component.weight,
            detail=component.detail,
        )
        for component in components
    )
    return f"""# TrustPipe Reliability Scorecard

Overall score: **{score}/100**

| Component | Score | Weight | Detail |
|---|---:|---:|---|
{rows}

Source: `{CONTRACTS_PATH.relative_to(REPO_ROOT)}` and local project assets.
"""


def write_scorecard(out_path: Path) -> int:
    components = build_components()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_markdown(components), encoding="utf-8")
    return total_score(components)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "scorecard" / "SCORECARD.md")
    parser.add_argument("--min-score", type=int, default=0)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    score = write_scorecard(args.out)
    log.info("Wrote reliability scorecard to %s (score=%s)", args.out, score)
    if score < args.min_score:
        log.error("Reliability score %s is below required minimum %s", score, args.min_score)
        sys.exit(1)


if __name__ == "__main__":
    main()
