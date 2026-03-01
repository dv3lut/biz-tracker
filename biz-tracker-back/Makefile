PYTHON ?= python

install:
	$(PYTHON) -m pip install -r requirements.txt

install-dev:
	$(PYTHON) -m pip install -r requirements-dev.txt

lint:
	$(PYTHON) -m compileall app

sync:
	$(PYTHON) -m app sync --check-for-updates

sync-force:
	$(PYTHON) -m app sync --no-check-for-updates

sync-full: sync-force

sync-incremental: sync

init-db:
	$(PYTHON) -m app init-db

serve:
	$(PYTHON) -m app serve

test:
	$(PYTHON) -m pytest

.PHONY: install install-dev lint sync sync-force sync-full sync-incremental init-db serve test
