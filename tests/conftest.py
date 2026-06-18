import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-provider",
        action="store_true",
        default=False,
        help="Run ONLY provider integration tests",
    )
    parser.addoption(
        "--run-repo",
        action="store_true",
        default=False,
        help="Run ONLY repo integration tests",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "provider_integration: marks test as a provider integration test"
    )
    config.addinivalue_line(
        "markers", "repo_integration: marks test as a repo integration test"
    )


def pytest_collection_modifyitems(config, items):
    run_provider = config.getoption("--run-provider")
    run_repo = config.getoption("--run-repo")

    # Determine what should be skipped
    skip_integration = pytest.mark.skip(reason="integration tests skipped by default")
    skip_unit = pytest.mark.skip(
        reason="unit/mock tests skipped when running specific integration tests"
    )
    skip_other_integration = pytest.mark.skip(reason="skipped other integration type")

    for item in items:
        is_provider = "provider_integration" in item.keywords
        is_repo = "repo_integration" in item.keywords
        is_unit = not is_provider and not is_repo

        if not run_provider and not run_repo:
            # Default mode: run unit tests, skip integration tests
            if is_provider or is_repo:
                item.add_marker(skip_integration)
        else:
            # Integration-only mode: skip unit/mock tests
            if is_unit:
                item.add_marker(skip_unit)

            # If specifically looking for provider, skip repo
            if run_provider and not run_repo and is_repo:
                item.add_marker(skip_other_integration)

            # If specifically looking for repo, skip provider
            if run_repo and not run_provider and is_provider:
                item.add_marker(skip_other_integration)
