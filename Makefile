VENV = .venv

init:
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install -r requirements.txt

download: init
	$(VENV)/bin/python data/download_datasets.py

# --- Local container testing (no AWS account needed) --------------------
#   make up      build + start api and dashboard locally (docker compose)
#   make down    stop them
#   make delete  stop them AND remove the local images/volumes
# `up` checks for Docker first and, if it's missing, runs .install-biomac.sh
# automatically -- no need to run it by hand.

check-docker:
	@command -v docker >/dev/null 2>&1 || $(MAKE) _install-then-stop

_install-then-stop:
	@echo "Falta Docker. Instalando automaticamente..."
	@bash .install-biomac.sh
	@echo
	@echo "Instalacion lista. Vuelve a ejecutar 'make up'."
	@echo "(Si era la primera vez que se instalaba Docker en Linux, primero cierra sesion o reinicia.)"
	@exit 1

up: check-docker
	docker compose up --build -d
	@echo "✅ Contenedores construidos y corriendo"
	@echo "✅ API:       http://localhost:8001/api/v2/health"
	@echo "✅ Dashboard: http://localhost:3000"

down:
	docker compose down
	@echo "✅ Contenedores detenidos"

delete:
	docker compose down --rmi local --volumes --remove-orphans
	@echo "✅ Todo eliminado (contenedores, imagenes locales y volumenes)"

.PHONY: init download check-docker _install-then-stop up down delete
