.PHONY: install test lint format clean run-backend run-app

# Variables
PYTHON = python
PYTEST = $(PYTHON) -m pytest
UVICORN = $(PYTHON) -m uvicorn

install:
	$(PYTHON) -m pip install -e .[dev]
	pre-commit install

test:
	$(PYTEST) backend/tests/ -v

lint:
	flake8 backend/ SignalCoreAI/
	black --check backend/ SignalCoreAI/
	isort --check-only backend/ SignalCoreAI/

format:
	black backend/ SignalCoreAI/
	isort backend/ SignalCoreAI/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

run-backend:
	$(UVICORN) backend.main:app --host 0.0.0.0 --port 8002 --reload

run-app:
	cd storeops && flutter run
