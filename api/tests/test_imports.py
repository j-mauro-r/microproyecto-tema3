import json
import subprocess
import sys


def test_import_does_not_initialize_ml_or_data_modules() -> None:
    script = """
import json
import sys
import api.app.main
forbidden = ('mlflow', 'dvc', 'boto3', 'xgboost', 'lightgbm', 'pandas', 'numpy')
print(json.dumps(sorted(name for name in sys.modules if name.split('.')[0] in forbidden)))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout) == []
