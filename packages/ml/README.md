# Machine Learning Package (`packages/ml`)

Standalone, reproducible Python package for defect risk prediction and model evaluation.

## Responsibilities
- **Data Loading & Preprocessing**:
  - **Track A (Baseline)**: NASA/PROMISE benchmark datasets (CM1, KC1) with stratified cross-validation and strict train/test isolation.
  - **Track B (Production)**: Mined Python repositories using PyDriller and SZZ issue-fixing commit labelling, with radon metric extraction and project-wise splitting.
- **Model Training**:
  - Scikit-learn and XGBoost pipelines (Dummy baseline, Logistic Regression, Decision Tree, Random Forest, XGBoost).
  - Hyperparameter tuning conducted strictly on training splits.
- **Evaluation & Explainability**:
  - Performance reporting: Precision, Recall, F1, ROC-AUC, PR-AUC, Confusion Matrices.
  - Interpretability via SHAP values for top contributing risk features.
- **Artifact Export**:
  - Serialization to `joblib` artifacts accompanied by `model_card.json` documenting training data, hyperparameters, metrics, and limitations.

