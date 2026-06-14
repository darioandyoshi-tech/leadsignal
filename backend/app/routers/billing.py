
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import get_settings
from app.dependencies import get_current_user
from app.models import User, Subscription, Tier, SubscriptionStatus
from app.schemas import SubscriptionCreate, SubscriptionRead, CheckoutSessionRequest

router = APIRouter(prefix="/billing", tags=["billing"])
settings = get_settings()
stripe.api_key = settings.stripe_secret_key


TIER_PRICES = {
    Tier.starter: settings.stripe_price_starter,
    Tier.pro: settings.stripe_price_pro,
    Tier.growth: settings.stripe_price_growth,
}


@router.post("/checkout")
async def create_checkout(payload: CheckoutSessionRequest, user: User = Depends(get_current_user)):
    price_id = TIER_PRICES.get(payload.tier)
    if not price_id:
        raise HTTPException(status_code=400, detail="Invalid tier for checkout")
    customer_id = None
    subs = [s for s in user.subscriptions if s.stripe_customer_id]
    if subs:
        customer_id = subs[0].stripe_customer_id
    session_kwargs = {
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": payload.success_url,
        "cancel_url": payload.cancel_url,
        "metadata": {"user_id": str(user.id), "tier": payload.tier.value},
    }
    if customer_id:
        session_kwargs["customer"] = customer_id
    else:
        session_kwargs["customer_email"] = user.email
    session = stripe.checkout.Session.create(**session_kwargs)
    return {"checkout_url": session.url, "session_id": session.id}


@router.get("/subscription", response_model=SubscriptionRead)
async def get_active_subscription(user: User = Depends(get_current_user)):
    active = [s for s in user.subscriptions if s.status in (SubscriptionStatus.active, SubscriptionStatus.trialing)]
    if not active:
        raise HTTPException(status_code=404, detail="No active subscription")
    return active[0]


@router.post("/portal")
async def customer_portal(user: User = Depends(get_current_user)):
    subs = [s for s in user.subscriptions if s.stripe_customer_id]
    if not subs:
        raise HTTPException(status_code=400, detail="No Stripe customer found")
    session = stripe.billing_portal.Session.create(
        customer=subs[0].stripe_customer_id,
        return_url=settings.frontend_url + "/dashboard/billing",
    )
    return {"portal_url": session.url}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, settings.stripe_webhook_secret)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Webhook error: {e}")

    data = event["data"]["object"]
    if event["type"] == "checkout.session.completed":
        user_id = data.get("metadata", {}).get("user_id")
        tier = data.get("metadata", {}).get("tier")
        if not user_id or not tier:
            raise HTTPException(status_code=400, detail="Missing metadata")
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        subscription = Subscription(
            user_id=user.id,
            tier=tier,
            stripe_customer_id=data.get("customer"),
            stripe_subscription_id=data.get("subscription"),
            status=SubscriptionStatus.active,
        )
        db.add(subscription)
        await db.commit()
    elif event["type"] in ("invoice.payment_failed", "customer.subscription.deleted"):
        sub_id = data.get("subscription") or data.get("id")
        result = await db.execute(select(Subscription).where(Subscription.stripe_subscription_id == sub_id))
        sub = result.scalar_one_or_none()
        if sub:
            sub.status = SubscriptionStatus.canceled if event["type"] == "customer.subscription.deleted" else SubscriptionStatus.past_due
            await db.commit()
    elif event["type"] == "customer.subscription.updated":
        sub_id = data.get("id")
        result = await db.execute(select(Subscription).where(Subscription.stripe_subscription_id == sub_id))
        sub = result.scalar_one_or_none()
        if sub:
            sub.status = data.get("status", "active")
            sub.current_period_start = _ts(data.get("current_period_start"))
            sub.current_period_end = _ts(data.get("current_period_end"))
            await db.commit()
    return {"status": "ok"}


def _ts(epoch: int | None):
    from datetime import datetime
    if epoch:
        return datetime.utcfromtimestamp(epoch)
    return None
