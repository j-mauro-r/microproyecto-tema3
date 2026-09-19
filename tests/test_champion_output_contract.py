"""Focused checks for the BIOMAC Champion output contract."""

from __future__ import annotations

import hashlib
import json
import pickle
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import generate_champion_output as generator


EXPECTED_PREDICTIONS = [
    ("68001", "Bucaramanga", "T+1", "2026-01", 0.7347, 0.34, "EXCESO"),
    ("68001", "Bucaramanga", "T+2", "2026-02", 0.6724, 0.27, "EXCESO"),
    ("76001", "Cali", "T+1", "2026-01", 0.0132, 0.34, "NO_EXCESO"),
    ("76001", "Cali", "T+2", "2026-02", 0.0150, 0.27, "NO_EXCESO"),
]


def _artifact_features(filename: str) -> list[str]:
    with (ROOT / "model" / filename).open("rb") as fh:
        return pickle.load(fh)["features"]


class ChampionOutputContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.f1 = _artifact_features("xgb_clasico_calibrated.pkl")
        cls.f2 = _artifact_features("xgb_clasico_T2_calibrated.pkl")

    def test_real_artifacts_share_the_approved_39_feature_contract(self) -> None:
        self.assertEqual(self.f1, self.f2)
        self.assertEqual(len(self.f1), 39)
        self.assertEqual(
            generator._validate_feature_contract(self.f1, self.f2),
            generator.FEATURE_CONTRACT_SHA256,
        )

    def test_different_horizon_features_fail(self) -> None:
        with self.assertRaises(ValueError):
            generator._validate_feature_contract(self.f1, self.f2[:-1])

    def test_feature_order_change_changes_sha_and_fails(self) -> None:
        reordered = [self.f1[1], self.f1[0], *self.f1[2:]]
        reordered_sha = hashlib.sha256(
            "\n".join(reordered).encode("utf-8")
        ).hexdigest()
        self.assertNotEqual(reordered_sha, generator.FEATURE_CONTRACT_SHA256)
        with self.assertRaises(ValueError):
            generator._validate_feature_contract(reordered, reordered)

    def test_model_and_feature_contract_versions_are_independent(self) -> None:
        self.assertEqual(generator.MODEL_VERSION, "pr12-f5a2d39")
        self.assertEqual(generator.FEATURE_CONTRACT_VERSION, "pr12-74e385c3")
        self.assertNotEqual(generator.MODEL_VERSION, generator.FEATURE_CONTRACT_VERSION)

    def test_generated_output_preserves_real_predictions(self) -> None:
        output = json.loads((ROOT / "champion_output.json").read_text(encoding="utf-8"))
        actual = [
            (
                p["divipola"], p["municipality"], p["horizon"], p["target_month"],
                p["probability"], p["threshold"], p["label"],
            )
            for p in output["predictions"]
        ]
        self.assertEqual(actual, EXPECTED_PREDICTIONS)


if __name__ == "__main__":
    unittest.main()
