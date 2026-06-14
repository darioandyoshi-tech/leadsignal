#!/usr/bin/env bash
# Bootstrap Stripe product/price setup for LeadSignal tiers.
# Requires STRIPE_SECRET_KEY env var.

set -euo pipefail

: "${STRIPE_SECRET_KEY:?Need STRIPE_SECRET_KEY}"

create_price() {
  local name="$1"
  local amount="$2" # cents
  local interval="$3"

  product_id=$(stripe products create \
    --name="$name" \
    -d "description=LeadSignal $name subscription" \
    | jq -r '.id')

  price_id=$(stripe prices create \
    -d "product=$product_id" \
    -d "unit_amount=$amount" \
    -d "currency=usd" \
    -d "recurring[interval]=$interval" \
    | jq -r '.id')

  echo "$name price ID: $price_id"
}

# Starter $49/mo
create_price "Starter" 4900 month
# Pro $149/mo
create_price "Pro" 14900 month
# Growth $399/mo
create_price "Growth" 39900 month

echo "Add these price IDs to backend/.env as STRIPE_PRICE_STARTER, STRIPE_PRICE_PRO, STRIPE_PRICE_GROWTH"
