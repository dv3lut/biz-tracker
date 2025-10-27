PYTHON ?= python

install:
	$(PYTHON) -m pip install -r requirements.txt

lint:
	$(PYTHON) -m compileall app

sync-full:
	$(PYTHON) -m app sync-full

sync-incremental:
	$(PYTHON) -m app sync-incremental

init-db:
	$(PYTHON) -m app init-db

serve:
	$(PYTHON) -m app serve

.PHONY: install lint sync-full sync-incremental init-db serve
