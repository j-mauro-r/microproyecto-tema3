# Manual de instalación local de BIOMAC

Este manual explica cómo instalar y levantar **BIOMAC** en un computador local usando Docker Compose. El proceso inicia la API y el dashboard en contenedores Docker y no requiere AWS, S3 ni credenciales en la nube.

## 1. Requisitos

Antes de comenzar, asegúrate de contar con:

- Windows 10/11, macOS o Linux de 64 bits.
- Al menos 8 GB de memoria RAM.
- Al menos 10 GB de espacio libre.
- Conexión a internet para descargar el proyecto, Docker y las imágenes necesarias.
- Git instalado o disponible para clonar el repositorio.

> La configuración actual de Docker Compose está orientada principalmente a Linux. En Windows se recomienda usar WSL2. En macOS la instalación automática de Docker está soportada, aunque la configuración de red del Compose puede requerir ajustes adicionales.

## 2. Descargar el proyecto

Abre una terminal y ejecuta:

```bash
git clone https://github.com/j-mauro-r/microproyecto-tema3.git
cd microproyecto-tema3
```

Si necesitas instalar una rama específica antes de integrarla a `main`, cámbiate a ella con:

```bash
git switch <nombre-rama>
```

## 3. Preparar el sistema operativo

### Windows

La instalación local se realiza dentro de WSL2.

Abre PowerShell como administrador y ejecuta:

```powershell
wsl --install
```

Reinicia el computador si Windows lo solicita. Luego abre **Ubuntu** desde el menú Inicio y continúa desde esa terminal.

Se recomienda guardar el proyecto dentro del sistema de archivos de Linux, por ejemplo:

```bash
~/proyectos/
```

### macOS y Linux

Abre la aplicación de terminal y continúa con el siguiente paso. No necesitas instalar Docker manualmente antes de ejecutar el proyecto.

## 4. Instalar dependencias y levantar BIOMAC

Desde la carpeta raíz del repositorio ejecuta:

```bash
make up
```

Este comando verifica si Docker está disponible.

Si Docker no está instalado, ejecuta automáticamente el instalador `.install-biomac.sh`, que prepara las herramientas necesarias para el sistema operativo.

En Linux o WSL, después de una primera instalación de Docker puede ser necesario cerrar sesión o reiniciar. Luego vuelve a la carpeta del proyecto y ejecuta nuevamente:

```bash
make up
```

El comando construye las imágenes y levanta los servicios con Docker Compose.

## 5. Verificar la instalación

Verifica primero las herramientas instaladas:

```bash
docker --version
docker compose version
```

Luego confirma que los servicios estén activos:

```bash
docker compose ps
```

La instalación es correcta si los contenedores de la API y del dashboard aparecen en ejecución.

También puedes validar la API localmente:

```bash
curl http://localhost:8001/api/v2/health
```

La respuesta debe indicar que el servicio está disponible.

## 6. Detener o eliminar la instalación local

Para detener los contenedores sin borrar las imágenes:

```bash
make down
```

Para detener los servicios y eliminar imágenes y volúmenes locales creados por el proyecto:

```bash
make delete
```

## 7. Posibles problemas durante la instalación

### Docker no responde

Si aparece un mensaje similar a:

```text
Cannot connect to the Docker daemon
```

En Linux o WSL ejecuta:

```bash
sudo systemctl enable --now docker
```

En macOS abre la aplicación **Docker** y espera a que termine de iniciar.

### WSL no tiene systemd habilitado

Si `systemctl` muestra un error indicando que el sistema no fue iniciado con systemd, ejecuta dentro de Ubuntu:

```bash
printf '[boot]\nsystemd=true\n' | sudo tee -a /etc/wsl.conf
```

Luego, desde PowerShell:

```powershell
wsl --shutdown
```

Vuelve a abrir Ubuntu y repite `make up`.

### El puerto ya está ocupado

Si Docker informa que un puerto ya está asignado:

```bash
make down
make up
```

### La instalación automática de Docker falla

Ejecuta manualmente el instalador incluido en el repositorio:

```bash
bash .install-biomac.sh
```

Cuando termine, sigue las instrucciones mostradas en pantalla y vuelve a ejecutar:

```bash
make up
```

### Revisar logs

Si los contenedores inician pero alguno presenta errores:

```bash
docker compose logs --tail=100
```

Para revisar cada servicio por separado:

```bash
docker compose logs api --tail=100
docker compose logs dashboard --tail=100
```
