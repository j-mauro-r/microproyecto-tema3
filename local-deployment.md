# Despliegue local de BIOMAC — Guía paso a paso (sin experiencia previa)

Esta guía explica, desde cero, cómo hacer funcionar BIOMAC (la API + el dashboard) **en tu propio computador**, sin necesidad de ninguna cuenta de AWS ni de pagar nada. Está escrita asumiendo que nunca has usado una terminal ni instalado herramientas de desarrollo.

No necesitas entender de programación para seguir esta guía. Solo tres comandos: `make up`, `make down` y `make delete`. Casi todo lo demás lo instala uno de ellos automáticamente por ti.

---

## 0. Conceptos básicos (léelo, toma 2 minutos)

- **La terminal**: es una ventana donde escribes comandos de texto en vez de hacer clic. Todos los "bloques de código" de esta guía son comandos que debes **copiar completos y pegarlos en la terminal**, y luego presionar `Enter`.
- **Docker**: es un programa que empaqueta la aplicación (la API y el dashboard) en "cajas" llamadas *contenedores*, para que funcionen igual en cualquier computador sin que tengas que instalar Python, Node, etc. manualmente.
- **No necesitas instalar Docker a mano** (salvo un paso obligatorio en Windows): el comando `make up` revisa si Docker falta en tu computador y lo instala automáticamente por ti la primera vez.

### Requisitos mínimos de tu computador

- Windows 10/11, macOS, o Linux, de 64 bits.
- Al menos 8 GB de RAM.
- Al menos 10 GB de espacio libre en disco.
- Conexión a internet (solo para instalar las herramientas la primera vez).

---

## 1. Obtener el proyecto

Si ya tienes la carpeta del proyecto, solo abre una terminal dentro de ella y sigue al Paso 2.

Si todavía no la tienes: necesitas una terminal para descargarla. Si usas Windows y todavía no tienes una, ve primero a la sección **2.A** de este documento y luego vuelve aquí. Si usas macOS o Linux, abre tu terminal y copia y pega:

```bash
git clone https://github.com/j-mauro-r/microproyecto-tema3.git
cd microproyecto-tema3
```

---

## 2. Preparar tu sistema operativo

Sigue **solo la sección de tu sistema operativo**.

### 2.A — Si usas Windows

En Windows **no vamos a instalar nada directamente sobre Windows** (nada de Docker Desktop). Vamos a instalar "WSL" (un Linux real que corre dentro de Windows) y, de ahí en adelante, vas a trabajar **exactamente igual que un usuario de Linux**, dentro de una terminal de Ubuntu — todo lo demás (Docker incluido) lo instala automáticamente el comando del Paso 3.

1. Abre el menú de inicio, escribe `PowerShell`, haz clic derecho sobre "Windows PowerShell" y elige **"Ejecutar como administrador"**.
2. Copia y pega este comando, presiona `Enter`, y espera (puede tardar varios minutos):
   ```powershell
   wsl --install
   ```
3. Cuando termine, abre el menú de inicio, busca **"Ubuntu"** y ábrelo. La primera vez te va a pedir crear un usuario y una contraseña para tu Linux (puedes usar cualquier nombre y contraseña, solo recuérdalos).
4. Esa ventana de Ubuntu es tu terminal de ahora en adelante — **todos los comandos del resto de esta guía los vas a escribir aquí**, nunca en PowerShell ni en CMD.

Ahora vuelve al **Paso 1** para descargar el proyecto dentro de esta terminal, y luego continúa con el **Paso 3**.

> Consejo: guarda el proyecto dentro de tu carpeta de Linux (por ejemplo `~/proyectos/`), no dentro de `/mnt/c/...`. Va a funcionar mucho más rápido.

### 2.B — Si usas macOS

No necesitas instalar nada todavía. Abre la aplicación **Terminal** (`Cmd + Espacio`, escribe "Terminal", presiona Enter) y sigue directo al **Paso 3** — el comando `make up` se encarga de instalar lo que falte.

### 2.C — Si usas Linux

No necesitas instalar nada todavía. Abre tu terminal (en la mayoría de distribuciones: `Ctrl + Alt + T`) y sigue directo al **Paso 3**.

---

## 3. Levantar la aplicación

```bash
make up
```

**La primera vez**, si a tu computador le falta Docker, vas a ver un mensaje como:

```
Falta Docker. Instalando automaticamente...
```

Espera a que termine — instala todo por ti — y al final te va a pedir **volver a ejecutar `make up`** (a veces, después de instalar Docker por primera vez en Linux, también te pedirá cerrar sesión o reiniciar antes de reintentar). Simplemente sigue esa instrucción.

Cuando termine, vas a ver algo como:

```
✅ Contenedores construidos y corriendo
✅ API:       http://localhost:8001/api/v2/health
✅ Dashboard: http://localhost:3000
```

Abre tu navegador y entra a **http://localhost:3000** — ahí está el dashboard.

Cuando quieras apagarlo:
```bash
make down
```

Si además quieres borrar las imágenes y volúmenes locales que se construyeron (para empezar completamente limpio la próxima vez):
```bash
make delete
```

---

## 4. Usar la aplicación por primera vez

La primera vez que abras el dashboard, vas a ver un mensaje diciendo que no hay datos todavía — **esto es normal**, la aplicación empieza sin información y hay que cargarle el primer archivo:

1. Haz clic en el botón **"Actualizar datos"**.
2. En "Archivo mensual CSV", selecciona el archivo de ejemplo que ya viene en el proyecto: `runtime/carga_mensual_2025-12.csv`.
3. En "Mes de referencia", elige **diciembre de 2025** (`2025-12`).
4. Haz clic en **"Confirmar actualización"**.
5. Espera unos segundos — el dashboard ahora debería mostrar las predicciones para Bucaramanga y Cali.

---

## 5. Problemas comunes

- **Docker no responde / "Cannot connect to the Docker daemon"**: en macOS, abre la aplicación **Docker** y espera a que la ballena 🐳 quede fija. En Linux (y en Windows, dentro de tu terminal Ubuntu), ejecuta `sudo systemctl enable --now docker`.
- **Mensaje sobre "virtualización desactivada"**: tu computador tiene esa función apagada. Pide ayuda a alguien con más experiencia técnica para activarla — el proceso varía según la marca y modelo del computador.
- **Windows/WSL: `systemctl` dice "System has not been booted with systemd"**: dentro de tu terminal Ubuntu ejecuta `printf '[boot]\nsystemd=true\n' | sudo tee -a /etc/wsl.conf`, luego abre **PowerShell** (normal, sin administrador) y ejecuta `wsl --shutdown`, y por último vuelve a abrir **"Ubuntu"**.
- **El puerto ya está en uso** (`port is already allocated`): ejecuta `make down` y vuelve a intentar con `make up`.
- **Windows: los comandos no funcionan**: asegúrate de estar escribiéndolos dentro de la ventana **"Ubuntu"**, no en PowerShell ni en CMD.
- **`make up` sigue pidiendo instalar Docker y no se resuelve solo**: revisa el apéndice "Instalación manual" más abajo.
- **Todo esto es 100% local**: nada de lo que hagas en esta guía crea recursos en AWS ni genera ningún costo — puedes repetir los pasos las veces que quieras.

---

## Apéndice: instalación manual (por si la instalación automática falla en algo)

Detrás de escena, `make up` ejecuta `.install-biomac.sh`, que automatiza exactamente estos comandos. Si por algún motivo falla en un paso puntual, puedes copiar y pegar solo esa parte a mano.

**Linux (Ubuntu/Debian, incluye Windows dentro de WSL):**
```bash
sudo apt update
sudo apt install -y git make curl

curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
# cierra sesión y vuelve a entrar después de este paso
```
(Cambia `apt` por `dnf` en Fedora, o por `pacman -S` en Arch.)

**macOS:**
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
xcode-select --install
brew install --cask docker
```

**Windows:** instalar WSL y abrir Ubuntu por primera vez (sección 2.A) ya es manual por naturaleza. Una vez estás dentro de tu terminal Ubuntu, usa exactamente la instalación manual de Linux de arriba.
