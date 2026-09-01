VENV = .venv

init:
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install -r requirements.txt

download: init
	$(VENV)/bin/python data/download_datasets.py

features: init
	$(VENV)/bin/python src/features/build_features.py
