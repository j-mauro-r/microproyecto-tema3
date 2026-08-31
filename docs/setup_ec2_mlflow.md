# Setup MLflow en AWS EC2

Instrucciones para montar el servidor MLflow en EC2 (requerido para Entrega 2).

## 1. Lanzar instancia EC2

- AMI: Ubuntu 22.04 LTS
- Tipo: t2.micro (gratis) o t2.small
- Security Group: abrir puerto **5000** (TCP, inbound) ademas de 22 (SSH)
- Key pair: descargar .pem

## 2. Conectar y configurar

```bash
# Conectar (reemplaza con tu IP y .pem)
ssh -i "tu_key.pem" ubuntu@<PUBLIC_IP>

# Instalar Python y pip
sudo apt-get update -y
sudo apt-get install python3-pip -y

# Instalar MLflow
pip3 install mlflow

# Agregar al PATH
echo 'export PATH=$PATH:/home/ubuntu/.local/bin' >> ~/.bashrc
source ~/.bashrc

# Verificar
mlflow --version
```

## 3. Iniciar servidor MLflow

```bash
# En background (persiste si cierras SSH)
nohup mlflow server \
  --host 0.0.0.0 \
  --port 5000 \
  --backend-store-uri sqlite:///mlflow.db \
  --default-artifact-root ./mlruns \
  > mlflow.log 2>&1 &

echo "MLflow corriendo en http://<PUBLIC_IP>:5000"
```

## 4. Apuntar el notebook a EC2

En `notebooks/10_Modelo_XGBoost.ipynb`, celda de configuracion:

```python
MLFLOW_TRACKING_URI = "http://<PUBLIC_IP>:5000"
```

## 5. Pantallazos requeridos para la entrega

El profesor pide:
1. Pantallazo del terminal SSH mostrando usuario + IP de la instancia
2. Pantallazo de la UI de MLflow en el navegador con esa IP visible en la URL

Para el pantallazo del terminal, el siguiente comando muestra la IP publica:
```bash
curl -s ifconfig.me
```

## 6. Detener (no terminar) la instancia tras la entrega

En la consola de AWS EC2: Actions → Instance State → **Stop** (NO Terminate).
El profesor requiere que la instancia se pueda revisar.
