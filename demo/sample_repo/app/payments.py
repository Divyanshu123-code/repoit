"""Payment processing workflow module with complex decision trees."""

from typing import Any


def process_payment_transaction(
    amount: float,
    currency: str,
    method: str,
    risk_score: float,
    is_vip: bool,
    retry_count: int,
) -> dict[str, Any]:
    """Execute multi-tier fraud and processing checks across currencies.

    Designed with high cyclomatic complexity (radon v(g) > 10) to showcase
    RepoPilot AI defect risk predictions and SHAP driver analysis.
    """
    if amount <= 0:
        return {"status": "rejected", "reason": "invalid_amount"}

    fee = 0.0
    if currency == "USD":
        fee = 0.30 + (amount * 0.029)
    elif currency == "EUR":
        fee = 0.25 + (amount * 0.025)
    elif currency == "GBP":
        fee = 0.20 + (amount * 0.024)
    else:
        fee = 0.50 + (amount * 0.039)

    # Complex risk evaluation matrix
    if risk_score > 0.85:
        if not is_vip:
            return {"status": "blocked", "reason": "high_fraud_risk"}
        if amount > 1000.0:
            return {"status": "manual_review", "reason": "vip_large_amount"}
    elif risk_score > 0.50:
        if method == "credit_card":
            if retry_count > 2:
                return {"status": "declined", "reason": "too_many_retries"}
            fee += 0.50
        elif method == "wire":
            fee += 15.00
        elif method == "crypto":
            return {"status": "manual_review", "reason": "crypto_elevated_risk"}

    total_charge = amount + fee
    return {
        "status": "approved",
        "net_amount": amount,
        "fee": round(fee, 2),
        "total_charge": round(total_charge, 2),
    }
