#!/usr/bin/env python3
"""seed_shop.py — ONE-TIME script.

1) Adds the requested products to the shop.
2) Locks payment to USDT BEP-20 only, with the new receiving address.

Run this ONCE in the same environment as your bots (so it uses the same
DB_PATH / persistent volume), e.g. on Railway:

    railway run python seed_shop.py

or via a one-off shell on your host:

    python seed_shop.py

Re-running this will add duplicate product rows, so run it only once.
After running, use the Admin Panel bot to fix up:
  - real prices for the 3 "(DM for price)" items
  - stock counts (default set to 10)
  - delivery_content per product (default is a placeholder note)
"""

import shared_db as db

db.init_db()

# ── Products: (name, price, stock, delivery_type, delivery_content) ──
PLACEHOLDER = "Contact admin — delivered manually after purchase."

PRODUCTS = [
    ("Adobe Pro 1M",                        4.0, 10, "text", PLACEHOLDER),
    ("Canva Edu 1Y (DM for price)",         0.0, 10, "text", PLACEHOLDER),
    ("Canva Pro 1Y (DM for price)",         0.0, 10, "text", PLACEHOLDER),
    ("CapCut 1M",                           5.0, 10, "text", PLACEHOLDER),
    ("Claude Team Max 5 Slot",             65.0, 10, "text", PLACEHOLDER),
    ("Claude Team Pro Slot 1M (Option 1)", 16.0, 10, "text", PLACEHOLDER),
    ("Claude Team Pro Slot 1M (Option 2)", 17.0, 10, "text", PLACEHOLDER),
    ("Cursor Pro 1M",                      16.0, 10, "text", PLACEHOLDER),
    ("Cursor Pro Plus",                    60.0, 10, "text", PLACEHOLDER),
    ("ElevenLabs 1M",                      10.0, 10, "text", PLACEHOLDER),
    ("ExpressVPN / NordVPN",                2.0, 10, "text", PLACEHOLDER),
    ("Figma Pro 1Y",                       16.0, 10, "text", PLACEHOLDER),
    ("Gemini Pro 18M",                     10.0, 10, "text", PLACEHOLDER),
    ("Gemini Ultra 1M (DM for price)",      0.0, 10, "text", PLACEHOLDER),
    ("GPT Plus",                           10.0, 10, "text", PLACEHOLDER),
    ("Grok Super 7 Days",                   3.0, 10, "text", PLACEHOLDER),
    ("Grok Super 1M",                       5.0, 10, "text", PLACEHOLDER),
    ("Grok Super 3 Months",                16.0, 10, "text", PLACEHOLDER),
    ("HeyGen Creator 1M",                  25.0, 10, "text", PLACEHOLDER),
    ("Highsfield Ultra 1M",                60.0, 10, "text", PLACEHOLDER),
    ("Kiro Pro Max 1M",                     8.0, 10, "text", PLACEHOLDER),
    ("Kling Ultra 26K Credits",            80.0, 10, "text", PLACEHOLDER),
    ("Lovable AI Pro 1M",                  20.0, 10, "text", PLACEHOLDER),
    ("Microsoft Office Slot 1Y",            8.0, 10, "text", PLACEHOLDER),
    ("Suno Premium 1M",                    25.0, 10, "text", PLACEHOLDER),
    ("Xbox Game Pass Ultimate 1Y",         25.0, 10, "text", PLACEHOLDER),
    ("Xbox Game Pass Ultimate 1M",         12.0, 10, "text", PLACEHOLDER),
]

added = 0
for name, price, stock, dtype, dcontent in PRODUCTS:
    db.add_product(name, price, stock, dtype, dcontent)
    added += 1
print(f"✅ Added {added} products.")

# ── Wallets: keep ONLY USDT BEP-20 active, set its address ──────────
NEW_BEP20_ADDRESS = "0x4C7894610C455d6381aCe22dce2468ccf95D2875"

db.update_wallet("usdt_bep20", NEW_BEP20_ADDRESS)

for w in db.get_all_wallets():
    if w["key"] == "usdt_bep20":
        if not w["active"]:
            db.toggle_wallet("usdt_bep20")
    else:
        if w["active"]:
            db.toggle_wallet(w["key"])

print("✅ Wallets updated — only USDT BEP-20 is active now.")
print(f"   Address set to: {NEW_BEP20_ADDRESS}")
