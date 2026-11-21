from evals.run import main, run_golden_suite


def test_golden_suite_matches_every_recorded_expectation() -> None:
    passed = run_golden_suite()

    assert passed == (
        "golden-01-resolved-corporate",
        "golden-02-ambiguous-guest-count",
        "golden-03-incomplete-date",
        "golden-04-unknown-venue",
        "golden-05-invalid-extraction",
        "golden-06-preferred-menu-selection",
        "golden-07-unpriced-menu",
    )


def test_golden_cli_runs_structured_mode() -> None:
    assert main(["--suite", "golden", "--mode", "structured"]) == 0
