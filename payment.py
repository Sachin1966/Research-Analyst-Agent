"""
Razorpay Payment Gateway Integration for Research Paper Agent SaaS.

Handles:
- Razorpay Client initialization with Key ID & Secret
- Order creation for Pro Plan subscriptions (Standard: ₹499/month = 49900 paise)
- HMAC-SHA256 Payment signature verification
- Seamless database upgrade to Pro Member (is_pro = 1)
- Mock/Sandbox fallback when live credentials are not yet set
"""

import os
import time
import hmac
import hashlib
from typing import Dict, Any, Optional

try:
    import razorpay
except ImportError:
    razorpay = None

import database

# Standard Pro Membership pricing
PRO_PLAN_PRICE_INR = 499  # ₹499 / month
PRO_PLAN_AMOUNT_PAISE = PRO_PLAN_PRICE_INR * 100  # 49900 paise
CURRENCY = "INR"

# Environment Variables
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "").strip()
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "").strip()

# Initialize Razorpay Client if credentials are provided
_razorpay_client = None
if razorpay and RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
    try:
        _razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
    except Exception as e:
        print(f"Warning: Razorpay client initialization error: {e}")
        _razorpay_client = None


def is_live_configured() -> bool:
    """Returns True if live Razorpay credentials are actively loaded."""
    return bool(_razorpay_client and RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET)


def get_public_config() -> Dict[str, Any]:
    """Returns public payment configuration for frontend checkout initialization."""
    return {
        "key_id": RAZORPAY_KEY_ID or "rzp_test_demo_veritas2026",
        "currency": CURRENCY,
        "amount": PRO_PLAN_AMOUNT_PAISE,
        "amount_in_rupees": PRO_PLAN_PRICE_INR,
        "plan_name": "VeritasCore Pro Researcher",
        "plan_description": "Unlimited Deep Scholarly Research & Evidence Verification",
        "is_live": is_live_configured()
    }


def create_order(user_id: int, user_email: str, amount_paise: int = PRO_PLAN_AMOUNT_PAISE) -> Dict[str, Any]:
    """
    Creates an order for the user to checkout via Razorpay Standard Checkout.
    If live keys are configured, calls Razorpay Orders API.
    Otherwise, generates a sandbox order to allow seamless staging/testing.
    """
    receipt_id = f"rcpt_{user_id}_{int(time.time())}"
    notes = {
        "user_id": str(user_id),
        "email": user_email,
        "product": "Research Paper Agent Pro Plan"
    }

    if _razorpay_client:
        try:
            order_data = {
                "amount": amount_paise,
                "currency": CURRENCY,
                "receipt": receipt_id,
                "notes": notes,
                "payment_capture": 1
            }
            order = _razorpay_client.order.create(data=order_data)
            return {
                "order_id": order["id"],
                "amount": order["amount"],
                "currency": order["currency"],
                "key_id": RAZORPAY_KEY_ID,
                "receipt": receipt_id,
                "mode": "live"
            }
        except Exception as e:
            print(f"Razorpay API Error, falling back to mock order: {e}")

    # Fallback sandbox order generation (for local testing & development before live keys are entered)
    mock_order_id = f"order_demo_{int(time.time())}_{user_id}"
    return {
        "order_id": mock_order_id,
        "amount": amount_paise,
        "currency": CURRENCY,
        "key_id": RAZORPAY_KEY_ID or "rzp_test_demo_veritas2026",
        "receipt": receipt_id,
        "mode": "sandbox"
    }


def verify_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """
    Validates Razorpay HMAC SHA-256 signature for the completed transaction.
    """
    if not payment_id:
        return False

    # If live client and secret are present, perform cryptographic verification
    if RAZORPAY_KEY_SECRET:
        try:
            msg = f"{order_id}|{payment_id}".encode("utf-8")
            expected_signature = hmac.new(
                RAZORPAY_KEY_SECRET.encode("utf-8"),
                msg,
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(expected_signature, signature)
        except Exception as e:
            print(f"Signature verification error: {e}")
            return False

    # In sandbox/demo mode without live secret, accept test payments
    return bool(payment_id.startswith("pay_") or payment_id.startswith("mock_pay_"))


def upgrade_user_membership(user_id: int, payment_id: str) -> Dict[str, Any]:
    """
    Upgrades user account in SQLite database to Pro Member and returns updated user & trial info.
    """
    success = database.upgrade_user_to_pro(user_id=user_id, payment_id=payment_id)
    if not success:
        raise ValueError(f"Failed to upgrade user #{user_id} in database")

    updated_user = database.get_user_by_id(user_id)
    trial_status = database.get_user_trial_status(updated_user)

    return {
        "success": True,
        "user": updated_user,
        "trial_status": trial_status,
        "payment_id": payment_id
    }
