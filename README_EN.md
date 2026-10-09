# 💪 McMuscle AI · 麦麦肌肉大王

**Fuel Your Gains. Save Your Wallet.**

A runnable Codex Skill that combines McDonald's China official MCP nutrition, current store menus, official price calculation, and deterministic Python meal optimization.

[中文](README.md) · [Installation](docs/INSTALL.md) · [Live read-only demo](docs/LIVE_DEMO.md) · [Synthetic demo](examples/MOCK_DEMO.md)

Independent third-party open-source project, not an official McDonald's product or endorsement. General adult fitness meal comparison, not medical diagnosis or treatment.

## What it does

- Parses natural language through Codex, with a conservative Chinese/English convenience CLI parser and validated structured profiles.
- Computes estimated resting energy, TDEE, configurable gain/cut/maintenance targets, and separate daily versus meal macros when enough information is provided.
- Reads official JSON/TOON nutrition, normalizes names/units, rejects missing or conflicting data, and intersects the catalog with a selected store's actual menu.
- Searches a bounded integer quantity space. Protein Max, Best Protein Value, and Calorie Smart optimize different explicit criteria. Hard budget, exclusion, allergy and nutrient constraints take precedence over preferences.
- Uses integer fen for money and official `calculate-price` results for verified recommendations. Never assumes coupons stack; claiming coupons requires separate permission.
- Prepares a fresh order preview and binds confirmation to all parameters and a quote. Durable attempt tracking prevents accidental replay; no blind mutation retries and no automated payment.

Incomplete body data never produces a fake precise TDEE. Unknown allergen information excludes the product whenever allergies are supplied. Current official nutrition has no complete allergen or cross-contact data.

## Quick start

Python 3.11+ required. On macOS download and extract the repo, double-click `Install.command`, then `Setup Token.command`. Get your own new token at https://open.mcd.cn/mcp and enter it only in the local hidden dialog. It is stored in macOS Keychain. Open the repository in Codex and ask:

> Use $mcmuscle. I am 75kg, gaining muscle, with a 40 yuan budget. Compare protein and price before ordering.

```bash
python3 scripts/install.py
.venv/bin/mcmuscle demo
.venv/bin/mcmuscle probe
```

macOS Codex uses `http_headers_helper`, avoiding GUI environment inheritance problems. Other systems use `MCD_MCP_TOKEN` in the process environment. The JSON example uses a client-dependent placeholder; it is not a universal environment-expansion standard. See [installation and troubleshooting](docs/INSTALL.md).

The project Skill needs the Python package and references; copying only SKILL.md does not install the application.

## How it works

User → validated profile → Python nutrition targets → official nutrition/menu/detail → bounded combination search → limited official price checks → three explained options → fresh quote and full preview → explicit confirmation → unpaid order/payment link.

The default search includes up to four units, item-specific limits, and 80,000 visited nodes. Truncated search is clearly reported. Even exhaustive enumeration only covers the stated candidate space; no claim of global optimality across all coupons, stores, or menu variants.

Mifflin–St Jeor and ISSN protein guidance inform estimates. Activity multipliers, ±energy adjustments and meal allocation are configurable planning assumptions. [Methods and limitations](docs/ALGORITHMS.md).

## Verification status

Official authentication, 160 nutrition rows (158 unique), public sample stores, menu, product detail, available/owned/store coupon queries, and regular price calculation were exercised read-only on 2026-10-09. A live bounded recommendation checked 15 products and 6 candidate prices; no orders were created.

No applicable owned coupons were returned in the test account. Delivery addresses, stores, menus and delivery/packing-fee quotes also passed read-only checks without disclosing private locations. Actual discounted checkout, coupon claiming, order creation and payment were not live-tested. Their supported logic uses mock tests; unknown delivery fee formats fail closed. Standard single products are automated; configurable bundles require complete explicit component selection. See [validation](docs/VALIDATION.md) and [MCP integration](MCP_INTEGRATION.md).

## Tests and privacy

```bash
.venv/bin/python -m pip install -e '.[live,dev]'
.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/mypy src
.venv/bin/pip-audit
```

Tests block network access and do not require tokens. CI never creates orders. Personal profiles, addresses, coupons, tokens, and raw account responses must stay outside Git in `private/`. Demo fixtures are clearly labeled **MOCK DEMO**.

MIT applies to original code; official contest declaration, third-party data and trademarks retain their rights. Original official declaration is copied unchanged. This entry does not participate in WorkBuddy bonuses. Publication alone does not establish contest registration: only an explicit official success reply does. See [progress](docs/PROGRESS.md).
