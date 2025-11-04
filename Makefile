PYTHON ?= python

install:
	$(PYTHON) -m pip install -r requirements.txt

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

.PHONY: install lint sync sync-force sync-full sync-incremental init-db serve
