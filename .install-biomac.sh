#!/usr/bin/env bash
# BIOMAC - instalador local de herramientas (Docker, make, git)
#
# Uso:
#   Linux / WSL (Ubuntu):  bash .install-biomac.sh
#   macOS:                 bash .install-biomac.sh
#
# Windows: primero instala WSL2 a mano (ver local-deployment.md, seccion 2.A) --
# eso requiere reiniciar el computador y no se puede automatizar desde un script.
# NO instales Docker Desktop para Windows. Despues de la seccion 2.A, ejecuta
# este script DENTRO de la terminal "Ubuntu" -- ahi lo detecta como Linux y este
# mismo script instala Docker adentro de WSL.
#
# El script es seguro de correr varias veces: si algo ya esta instalado, lo
# detecta y no hace nada.

set -euo pipefail

info() { printf '\033[1;34m[info]\033[0m %s\n' "$1"; }
ok()   { printf '\033[1;32m[ok]\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m[atencion]\033[0m %s\n' "$1"; }
err()  { printf '\033[1;31m[error]\033[0m %s\n' "$1"; }

have() { command -v "$1" >/dev/null 2>&1; }

NEEDS_RELOGIN=0

install_linux_pkg_prereqs() {
  local missing=()
  have curl || missing+=("curl")
  have git  || missing+=("git")
  have make || missing+=("make")

  if [ "${#missing[@]}" -eq 0 ]; then
    ok "curl, git y make ya estan instalados."
    return
  fi

  info "Instalando: ${missing[*]}..."
  if have apt-get; then
    sudo apt-get update -y
    sudo apt-get install -y "${missing[@]}"
  elif have dnf; then
    sudo dnf install -y "${missing[@]}"
  elif have pacman; then
    sudo pacman -Sy --noconfirm "${missing[@]}"
  else
    warn "No reconoci tu gestor de paquetes. Instala manualmente: ${missing[*]}"
  fi
}

install_docker_linux() {
  if have docker; then
    ok "Docker ya esta instalado ($(docker --version))."
    return
  fi
  info "Instalando Docker..."
  curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
  sudo sh /tmp/get-docker.sh
  rm -f /tmp/get-docker.sh
  sudo usermod -aG docker "$USER"
  warn "Se agrego tu usuario al grupo docker. Debes CERRAR SESION (o reiniciar) para que tome efecto."
  NEEDS_RELOGIN=1
}

install_macos() {
  if ! have brew; then
    info "Instalando Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    if [ -x /opt/homebrew/bin/brew ]; then
      eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [ -x /usr/local/bin/brew ]; then
      eval "$(/usr/local/bin/brew shellenv)"
    fi
  else
    ok "Homebrew ya esta instalado."
  fi

  if ! xcode-select -p >/dev/null 2>&1; then
    warn "Se va a abrir una ventana para instalar las herramientas de Apple (Xcode Command Line Tools)."
    warn "Haz clic en 'Instalar', espera a que termine, y vuelve a ejecutar este script."
    xcode-select --install || true
    exit 0
  else
    ok "Xcode Command Line Tools ya estan instaladas."
  fi

  have docker || brew install --cask docker

  warn "Abre la aplicacion 'Docker' desde Aplicaciones y espera a que la ballena quede fija antes de continuar."
}

OS="$(uname -s)"
case "$OS" in
  Linux*)
    install_linux_pkg_prereqs
    install_docker_linux
    ;;
  Darwin*)
    install_macos
    ;;
  *)
    err "Sistema operativo no reconocido: $OS"
    err "Si estas en Windows: abre PowerShell como administrador y ejecuta 'wsl --install',"
    err "reinicia, crea tu usuario de Ubuntu, y luego ejecuta este mismo script DENTRO de esa"
    err "terminal Ubuntu (instalara Docker por ti ahi adentro -- no instales Docker Desktop)."
    exit 1
    ;;
esac

echo
ok "Listo. Versiones instaladas:"
docker --version 2>/dev/null || true
make --version 2>/dev/null | head -1 || true

echo
if [ "$NEEDS_RELOGIN" = "1" ]; then
  warn "IMPORTANTE: cierra sesion (o reinicia) para que los permisos de Docker tomen efecto."
  warn "Despues de volver a entrar, continua con local-deployment.md (Paso 3: make up)."
else
  info "Ya puedes continuar con local-deployment.md, Paso 3 (make up)."
fi
