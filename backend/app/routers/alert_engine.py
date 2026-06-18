
"""Alert delivery engine: email, Slack, Discord, webhook, dashboard."""

import os
import json
import httpx
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import get_settings
from app.dependencies import get_current_user
from app.db import get_db
from app.models import Signal, Subscription, Alert, AlertChannel, User, SubscriptionStatus
from app.schemas import AlertPayload
from app.scoring import SignalScreener

router = APIRouter(prefix="/alerts", tags=["alerts"])
settings = get_settings()


def _score_threshold() -> float:
    """Return the composite score threshold for auto-alerts."""
    try:
        return float(os.environ.get("LEADSIGNAL_ALERT_SCORE_THRESHOLD", "0.65"))
    except ValueError:
        return 0.65


def _email_body(signals: list) -> str:
    lines = ["LeadSignal Daily Alert", "=" * 40, ""]
    for s in signals:
        lines.append(f"[{s.signal_type.value}] {s.headline}")
        lines.append(f"Severity: {s.severity}/5 | Detected: {s.detected_at.strftime('%Y-%m-%d %H:%M UTC')}")
        if s.summary:
            lines.append(s.summary[:500])
        if s.source_url:
            lines.append(f"Source: {s.source_url}")
        lines.append("")
    return "\n".join(lines)


def _markdown_body(signals: list) -> str:
    lines = ["## LeadSignal Alert", ""]
    for s in signals:
        emoji = {"hiring_spike": "💼", "negative_review_cluster": "⭐", "permit_filing": "🏗️"}.get(s.signal_type.value, "📡")
        lines.append(f"### {emoji} {s.headline}")
        lines.append(f"- Severity: {s.severity}/5")
        lines.append(f"- Source: {s.source_url or 'N/A'}")
        if s.summary:
            lines.append(f"> {s.summary[:400]}")
        lines.append("")
    return "\n".join(lines)


async def send_email_alert(to: str, subject: str, body: str):
    if settings.agentmail_api_key:
        async with httpx.AsyncClient() as client:
            await client.post(
                "https://api.agentmail.io/v1/send",
                headers={"Authorization": f"Bearer {settings.agentmail_api_key}"},
                json={"from": settings.agentmail_sender, "to": to, "subject": subject, "text": body},
                timeout=30,
            )
    else:
        # Log for local dev
        print(f"[EMAIL] To: {to}\nSubject: {subject}\n{body}\n")


async def send_slack_alert(webhook_url: str, body: str):
    async with httpx.AsyncClient() as client:
        r = await client.post(webhook_url, json={"text": body}, timeout=30)
        r.raise_for_status()


async def send_discord_alert(webhook_url: str, body: str):
    async with httpx.AsyncClient() as client:
        r = await client.post(webhook_url, json={"content": body[:2000]}, timeout=30)
        r.raise_for_status()


async def send_webhook(target_url: str, payload: dict):
    async with httpx.AsyncClient() as client:
        r = await client.post(target_url, json=payload, timeout=30)
        r.raise_for_status()


@router.post("/send")
async def send_alert(payload: AlertPayload, background: BackgroundTasks,
                     user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Subscription).where(
            Subscription.id == payload.subscription_id,
            Subscription.user_id == user.id,
            Subscription.status.in_([SubscriptionStatus.active, SubscriptionStatus.trialing]),
        )
    )
    subscription = result.scalar_one_or_none()
    if not subscription:
        raise HTTPException(status_code=404, detail="Active subscription not found")

    result = await db.execute(select(Signal).where(Signal.id.in_(payload.signal_ids)))
    signals = result.scalars().all()
    if not signals:
        raise HTTPException(status_code=404, detail="No signals found")

    email_body = _email_body(signals)
    md_body = _markdown_body(signals)

    if payload.channel == AlertChannel.email:
        background.add_task(send_email_alert, user.email, "LeadSignal Alert", email_body)
    elif payload.channel == AlertChannel.slack:
        webhook = subscription.settings.get("slack_webhook")
        if not webhook:
            raise HTTPException(status_code=400, detail="Slack webhook not configured")
        background.add_task(send_slack_alert, webhook, md_body)
    elif payload.channel == AlertChannel.discord:
        webhook = subscription.settings.get("discord_webhook")
        if not webhook:
            raise HTTPException(status_code=400, detail="Discord webhook not configured")
        background.add_task(send_discord_alert, webhook, md_body)
    elif payload.channel == AlertChannel.webhook:
        target = subscription.settings.get("custom_webhook")
        if not target:
            raise HTTPException(status_code=400, detail="Custom webhook not configured")
        background.add_task(send_webhook, target, {
            "subscription_id": str(subscription.id),
            "signals": [{"id": str(s.id), "type": s.signal_type.value, "headline": s.headline} for s in signals],
        })
    else:
        # dashboard-only; just record
        pass

    alert = Alert(
        subscription_id=subscription.id,
        signal_ids=[s.id for s in signals],
        channel=payload.channel,
        status="sent" if payload.channel != AlertChannel.dashboard else "pending",
        content=email_body,
        sent_at=datetime.utcnow() if payload.channel != AlertChannel.dashboard else None,
    )
    db.add(alert)
    for s in signals:
        s.is_alerted = True
    await db.commit()
    return {"alert_id": str(alert.id), "channel": payload.channel.value, "signals_sent": len(signals)}


@router.post("/digest")
async def send_daily_digest(background: BackgroundTasks, user: User = Depends(get_current_user),
                            db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.status.in_([SubscriptionStatus.active, SubscriptionStatus.trialing]),
        )
    )
    subs = result.scalars().all()
    if not subs:
        raise HTTPException(status_code=404, detail="No active subscription")

    cutoff = datetime.utcnow() - timedelta(days=1)
    result = await db.execute(
        select(Signal).where(Signal.detected_at >= cutoff, Signal.is_alerted == False).order_by(Signal.detected_at.desc()).limit(50)
    )
    signals = result.scalars().all()
    if not signals:
        return {"sent": False, "reason": "No new signals in last 24h"}

    body = _email_body(signals)
    background.add_task(send_email_alert, user.email, "LeadSignal Daily Digest", body)

    alert = Alert(
        subscription_id=subs[0].id,
        signal_ids=[s.id for s in signals],
        channel=AlertChannel.email,
        status="sent",
        content=body,
        sent_at=datetime.utcnow(),
    )
    db.add(alert)
    for s in signals:
        s.is_alerted = True
    await db.commit()
    return {"sent": True, "signals": len(signals)}


@router.post("/score-trigger")
async def score_based_alert(
    background: BackgroundTasks,
    threshold: float = Query(default=None),
    channel: AlertChannel = Query(default=AlertChannel.email),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send an alert with signals whose composite score is above the threshold.

    If threshold is not provided, uses LEADSIGNAL_ALERT_SCORE_THRESHOLD env var.
    """
    result = await db.execute(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.status.in_([SubscriptionStatus.active, SubscriptionStatus.trialing]),
        )
    )
    subs = result.scalars().all()
    if not subs:
        raise HTTPException(status_code=404, detail="No active subscription")

    threshold = threshold if threshold is not None else _score_threshold()
    screener = SignalScreener()
    screened = await screener.screen(db, days_back=7, limit=200)
    top = [r for r in screened if r.score >= threshold]
    if not top:
        return {"sent": False, "reason": f"No signals above score threshold {threshold}", "threshold": threshold}

    signal_ids = [r.signal_id for r in top]
    result = await db.execute(select(Signal).where(Signal.id.in_(signal_ids)))
    signals = result.scalars().all()

    body = _email_body(signals)
    md_body = _markdown_body(signals)
    subject = f"LeadSignal High-Score Alert ({len(signals)} signals >= {threshold})"

    if channel == AlertChannel.email:
        background.add_task(send_email_alert, user.email, subject, body)
    elif channel == AlertChannel.slack:
        webhook = subs[0].settings.get("slack_webhook")
        if not webhook:
            raise HTTPException(status_code=400, detail="Slack webhook not configured")
        background.add_task(send_slack_alert, webhook, md_body)
    elif channel == AlertChannel.discord:
        webhook = subs[0].settings.get("discord_webhook")
        if not webhook:
            raise HTTPException(status_code=400, detail="Discord webhook not configured")
        background.add_task(send_discord_alert, webhook, md_body)
    elif channel == AlertChannel.webhook:
        target = subs[0].settings.get("custom_webhook")
        if not target:
            raise HTTPException(status_code=400, detail="Custom webhook not configured")
        background.add_task(send_webhook, target, {
            "subscription_id": str(subs[0].id),
            "threshold": threshold,
            "signals": [{"id": str(s.id), "type": s.signal_type.value, "headline": s.headline} for s in signals],
        })

    alert = Alert(
        subscription_id=subs[0].id,
        signal_ids=[s.id for s in signals],
        channel=channel,
        status="sent" if channel != AlertChannel.dashboard else "pending",
        content=body,
        sent_at=datetime.utcnow() if channel != AlertChannel.dashboard else None,
    )
    db.add(alert)
    for s in signals:
        s.is_alerted = True
    await db.commit()
    return {"sent": True, "channel": channel.value, "threshold": threshold, "signals": len(signals)}
