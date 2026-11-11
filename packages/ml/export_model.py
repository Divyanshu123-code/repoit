#!/usr/bin/env python3
"""CLI script to train and export the champion defect prediction artifact and model card (P3-04).

Usage:
    python packages/ml/export_model.py
"""

from packages.ml.dataset import load_kc1
from packages.ml.export import (
    DEFAULT_ARTIFACTS_DIR,
    export_champion_artifact,
    load_model_artifact,
    predict_defect_risk,
)


def main() -> None:
    print("=" * 80)
    print("RepoPilot AI — Champion Model Artifact & Model Card Export (P3-04)")
    print("=" * 80)

    print("\nLoading KC1 benchmark dataset...")
    kc1 = load_kc1()
    print(f"Loaded {len(kc1)} modules with 21 static code metric features.")

    print("\nTraining and serializing Random Forest champion pipeline...")
    model_path, card_path = export_champion_artifact(
        df=kc1,
        dataset_name="kc1",
        model_type="random_forest",
        version="1.0.0",
        output_dir=DEFAULT_ARTIFACTS_DIR,
    )
    print(
        f"  Artifact saved to: {model_path} ({model_path.stat().st_size / 1024:.1f} KB)"
    )
    print(f"  Model card saved to: {card_path}")

    print("\nVerifying model artifact reload and test prediction...")
    pipeline, model_card = load_model_artifact(DEFAULT_ARTIFACTS_DIR)
    print(
        f"  Successfully loaded model '{model_card['model_name']}' v{model_card['model_version']}"
    )

    # Sample inference verification with representative metric profile
    sample_metrics = {
        "loc": 45.0,
        "v(g)": 8.0,
        "ev(g)": 4.0,
        "iv(g)": 6.0,
        "n": 140.0,
        "v": 780.0,
        "l": 0.05,
        "d": 18.0,
        "i": 42.0,
        "e": 14000.0,
        "b": 0.26,
        "t": 780.0,
        "lOCode": 35.0,
        "lOComment": 2.0,
        "lOBlank": 6.0,
        "locCodeAndComment": 0.0,
        "uniq_Op": 18.0,
        "uniq_Opnd": 24.0,
        "total_Op": 88.0,
        "total_Opnd": 52.0,
        "branchCount": 15.0,
    }

    prediction = predict_defect_risk(
        pipeline=pipeline,
        features=sample_metrics,
        model_version=model_card["model_version"],
    )

    print("\nSample Risk Prediction Output:")
    print(f"  Risk Probability: {prediction['risk_probability'] * 100:.1f}%")
    print(f"  Risk Band: {prediction['risk_band'].upper()}")
    print(f"  Model Version: {prediction['model_version']}")
    print(f"  Source Attribution: {prediction['source']}")
    print(f"  Disclaimer: {prediction['disclaimer']}")
    print("  Top Contributing Complexity Drivers:")
    for driver in prediction["top_features"]:
        print(f"    - {driver['feature']}: {driver['value']} ({driver['description']})")

    print("\n[OK] Artifact export successfully verified.")


if __name__ == "__main__":
    main()
