"""
Verifica la convencion de alcance con la que se registran las metricas.

    sin prefijo    los dos municipios del alcance (68001 y 76001)
    nacional_      todos los municipios
    {divipola}_    cada municipio por separado

Las que van sin prefijo son las que terminan en la misma columna de MLflow que
los baselines y el Poisson, asi que tienen que ser las del alcance del producto
y no las del pais. Esta prueba existe porque ese error no se ve: la columna se
llama igual y el numero es plausible.

No necesita servidor de MLflow: se intercepta log_metrics y se revisa que se
registro, sin abrir ningun run.

Uso:
    python tests/test_registro_alcance.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import model_utils


def caso():
    """
    Datos armados a mano para poder verificar los numeros sin recalcularlos
    con el mismo codigo que se esta probando.

    68001   y=[1,1,1,0,0,0]  pred=[1,1,0,0,1,0]   VP=2 FP=1 FN=1 VN=2
    76001   y=[1,1,0,0,0,0]  pred=[1,0,0,0,0,1]   VP=1 FP=1 FN=1 VN=3
    05001   y=[1]*6+[0]*6    pred= igual          VP=6 FP=0 FN=0 VN=6

    dos ciudades   VP=3 FP=2 FN=2   sens=3/5  prec=3/5  F1=0,600
    nacional       VP=9 FP=2 FN=2   sens=9/11 prec=9/11 F1=0,818
    """
    div  = ["68001"] * 6 + ["76001"] * 6 + ["05001"] * 12
    y    = [1, 1, 1, 0, 0, 0] + [1, 1, 0, 0, 0, 0] + [1] * 6 + [0] * 6
    pred = [1, 1, 0, 0, 1, 0] + [1, 0, 0, 0, 0, 1] + [1] * 6 + [0] * 6
    ini  = [1, 0, 0, 0, 0, 0] + [0, 1, 0, 0, 0, 0] + [0] * 12
    sc   = [0.9, 0.8, 0.3, 0.2, 0.7, 0.1] + [0.9, 0.4, 0.2, 0.1, 0.3, 0.6] + \
           [0.9] * 6 + [0.1] * 6
    return map(np.array, (div, y, pred, ini, sc))


def registrar():
    """Corre registrar_por_alcance interceptando MLflow y devuelve lo registrado."""
    capturado = {}
    original = model_utils.mlflow.log_metrics
    model_utils.mlflow.log_metrics = capturado.update
    try:
        div, y, pred, ini, sc = caso()
        model_utils.registrar_por_alcance(div, y, pred, ini, sc, imprimir=False)
    finally:
        model_utils.mlflow.log_metrics = original
    return capturado


fallos = []


def check(nombre, ok, detalle=""):
    print(f"  {'ok  ' if ok else 'FALLA'}  {nombre}{'  ' + detalle if detalle else ''}")
    if not ok:
        fallos.append(nombre)


def main():
    m = registrar()

    print("\nlas metricas sin prefijo son las de los dos municipios")
    check("f1 sin prefijo = 0,600", round(m["f1"], 3) == 0.600, f"da {m['f1']:.3f}")
    check("sensibilidad sin prefijo = 0,600", round(m["sensibilidad"], 3) == 0.600)
    check("precision sin prefijo = 0,600", round(m["precision"], 3) == 0.600)
    check("n sin prefijo = 12", m["n"] == 12, f"da {m['n']:.0f}")

    print("\nlas nacionales van bajo nacional_ y son distintas")
    check("nacional_f1 = 0,818", round(m["nacional_f1"], 3) == 0.818, f"da {m['nacional_f1']:.3f}")
    check("nacional_n = 24", m["nacional_n"] == 24)
    check("nacional_f1 != f1", m["nacional_f1"] != m["f1"])

    print("\ncada municipio bajo su codigo")
    check("68001_f1 = 0,667", round(m["68001_f1"], 3) == 0.667, f"da {m['68001_f1']:.3f}")
    check("76001_f1 = 0,500", round(m["76001_f1"], 3) == 0.500, f"da {m['76001_f1']:.3f}")
    check("68001_n = 6 y 76001_n = 6", m["68001_n"] == 6 and m["76001_n"] == 6)

    print("\ninicios: 2 en el alcance, 1 detectado")
    check("ini_inicios = 2", m["ini_inicios"] == 2, f"da {m['ini_inicios']:.0f}")
    check("ini_inicios_detectados = 1", m["ini_inicios_detectados"] == 1,
          f"da {m['ini_inicios_detectados']:.0f}")

    print("\nno quedan nombres del esquema viejo")
    viejos = sorted(k for k in m if k.startswith("test_"))
    check("ninguna clave empieza por test_", not viejos, str(viejos))
    check("pr_auc se registra sin prefijo", "pr_auc" in m)

    print(f"\n{len(fallos)} fallas de {len(fallos) + 14}" if fallos else "\ntodo bien")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
