.PHONY: all setup build-ui test heal run clean docker-build docker-run

VENV = .venv
PYTHON = $(VENV)/bin/python3
PIP = $(VENV)/bin/pip
SOPHIA = $(VENV)/bin/sophia

all: setup build-ui test

setup:
	@echo "==> Setting up Python virtual environment..."
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e .

build-ui:
	@echo "==> Compiling Native macOS Dynamic Island Overlay (Swift)..."
	swift build --package-path sophia/ui/swift -c release

test:
	@echo "==> Running Automated Self-Testing Suite..."
	$(SOPHIA) test

heal:
	@echo "==> Running Recursive Self-Healing Loop..."
	$(SOPHIA) test --heal

run:
	@echo "==> Starting Sophia Assistant Daemon & Dynamic Island..."
	$(SOPHIA) start

clean:
	@echo "==> Cleaning build artifacts and caches..."
	rm -rf sophia/ui/swift/.build
	rm -rf *.egg-info build dist
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

docker-build:
	@echo "==> Building Docker container image..."
	docker build -t sophia-assistant:latest .

docker-run:
	@echo "==> Running Sophia in Docker..."
	docker run --rm -it sophia-assistant:latest test
