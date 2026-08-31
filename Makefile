VENV = .venv

init:
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install -r requirements.txt

download: init
	$(VENV)/bin/python data/download_datasets.py
