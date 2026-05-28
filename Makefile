PATH := /usr/bin:/bin:$(PATH)

.PHONY: setup dev-server clean

setup:
	python3 -m venv .venv
	.venv/bin/python -m pip install -e .

dev-server:
	.venv/bin/uvicorn quiz_relay.web:app --reload --host 0.0.0.0 --port 8001

clean:
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	find . -type f \( -name '*.pyc' -o -name '*.pyo' -o -name '*.pyd' \) -delete
	find . -type d -name '*.egg-info' -prune -exec rm -rf {} +
	rm -rf .pytest_cache .mypy_cache .ruff_cache .hypothesis .tox .nox
	rm -rf build dist htmlcov site runtime
	rm -f .coverage coverage.xml

