VENV := $(shell git rev-parse --show-toplevel 2>/dev/null || echo ..)/.venv
PYTHON := $(VENV)/Scripts/python

check-env:
	@echo "Checking Python environment..."
	@$(PYTHON) "$(VENV)/verify.py"

install: $(VENV)
$(VENV):
	python -m venv $(VENV)
	$(PYTHON) -m pip install -r requirements.txt

.PHONY: check-env install
