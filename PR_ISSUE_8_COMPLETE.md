# PR: Template Marketplace with RTC Pricing - Issue #8 Complete

## Issue Reference
Closes #8 - [BOUNTY: 40 RTC] Template marketplace with RTC pricing

## Summary

This PR implements a complete **template marketplace** with **RTC token pricing** for the ShaprAI ecosystem. Users can now publish, buy, sell, and rate agent templates using RTC tokens.

## Features Implemented

### 1. Marketplace Core (`shaprai/core/template_engine.py`)

#### New Data Classes
- **`MarketplaceTemplate`**: Represents a template listing with pricing, author, ratings, and download stats

#### New Functions
- **`publish_template()`**: Publish a template to the marketplace with RTC pricing
- **`purchase_template()`**: Buy a template with automatic RTC payment processing
- **`list_marketplace_templates()`**: Browse all available templates
- **`rate_template()`**: Rate purchased templates (1.0-5.0 stars)

### 2. RustChain RTC Integration (`shaprai/integrations/rustchain.py`)

#### New Constants
- **`TEMPLATE_LISTING_FEE = 0.005 RTC`**: Fee to list a template
- **`TEMPLATE_SALE_ROYALTY = 0.02 (2%)`**: Platform royalty on sales

#### New Functions
- **`pay_template_listing_fee()`**: Pay the marketplace listing fee
- **`process_template_sale()`**: Process template sale with automatic royalty split
  - Seller receives: `price * 0.98`
  - Platform receives: `price * 0.02` (royalty)
- **`get_wallet_balance()`**: Check wallet balance
- **`get_template_sales_history()`**: Get sales history for a seller

### 3. CLI Commands (`shaprai/cli.py`)

New `shaprai marketplace` command group:

```bash
# List all marketplace templates
shaprai marketplace list

# Publish a template
shaprai marketplace publish <template_name> --price 5.0 --author "my_name"

# Purchase a template
shaprai marketplace purchase <template_name> --wallet "my-wallet-id"

# Rate a purchased template
shaprai marketplace rate <template_name> --rating 4.5

# Check wallet balance
shaprai marketplace balance --wallet "my-wallet-id"
```

## Architecture

### Marketplace Flow

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Seller    │────▶│  Marketplace │◀────│    Buyer    │
│             │     │   Listing    │     │             │
└─────────────┘     └──────────────┘     └─────────────┘
       │                   │                    │
       │ 1. Publish        │                    │
       │    (pay 0.005 RTC)│                    │
       ├──────────────────▶│                    │
       │                   │                    │
       │                   │ 2. Browse          │
       │                   │◀───────────────────┤
       │                   │                    │
       │                   │ 3. Purchase        │
       │                   │◀───────────────────┤
       │                   │                    │
       │                   │ 4. Process Payment │
       │                   │    (2% royalty)    │
       │◀──────────────────┼───────────────────▶│
       │ 98% of price      │                    │ 100% of price
       │                   │                    │
```

### File Structure

```
~/.shaprai/marketplace/
├── <template_name>.yaml          # Template file
├── <template_name>.listing.yaml  # Listing metadata (price, author, rating)
└── ...
```

### Listing Metadata Format

```yaml
name: bounty_hunter
author: elyan_labs
description: Autonomous bounty hunter for GitHub bounties
price_rtc: 5.0
version: "1.0"
capabilities:
  - code_review
  - bounty_discovery
downloads: 0
rating: 0.0
created_at: 1710316800.0
updated_at: 1710316800.0
```

## Acceptance Criteria Met

| Criterion | Status | Notes |
|-----------|--------|-------|
| Template marketplace functionality | ✅ | Publish, browse, purchase, rate |
| RTC pricing system | ✅ | Listing fees, royalties, payments |
| - Listing fees (0.005 RTC) | ✅ | Paid to marketplace treasury |
| - Sale royalties (2%) | ✅ | Split: 98% seller, 2% platform |
| - Automatic payment splitting | ✅ | Via RustChain integration |
| - Wallet balance checking | ✅ | get_wallet_balance() |
| CLI commands for all operations | ✅ | marketplace list/publish/purchase/rate/balance |
| Integration with RustChain economy | ✅ | Full payment processing |
| Unit tests | ✅ | test_marketplace.py exists |

## Usage Examples

### 1. Publish a Template

```bash
# Create a template first
shaprai template create my_template --model Qwen/Qwen3-7B-Instruct --description "My awesome template"

# Publish to marketplace
shaprai marketplace publish my_template --price 5.0 --author "john_doe"
```

**Output:**
```
Template 'my_template' published to marketplace!
  Author: john_doe
  Price: 5.000 RTC
  Listing fee: 0.005 RTC (paid)
  Wallet: agent-john_doe
```

### 2. Browse Marketplace

```bash
shaprai marketplace list
```

**Output:**
```
Name                      Author               Price (RTC)     Rating
--------------------------------------------------------------------------------
bounty_hunter             elyan_labs           5.000           ⭐ 4.5
code_reviewer             elyan_labs           3.000           New
my_template               john_doe             5.000           ⭐ 4.0

Total: 3 template(s)
```

### 3. Purchase a Template

```bash
shaprai marketplace purchase bounty_hunter --wallet "shaprai-my-agent"
```

**Output:**
```
Your balance: 10.500 RTC
✅ Successfully purchased 'bounty_hunter'!
  Description: Autonomous bounty hunter — discovers, claims, and delivers GitHub bounties for RTC
  Capabilities: code_review, pr_submission, bounty_discovery, issue_triage
  Model: Qwen/Qwen3-7B-Instruct
```

### 4. Rate a Template

```bash
shaprai marketplace rate bounty_hunter --rating 5.0
```

**Output:**
```
✅ Rated 'bounty_hunter' with 5.0 stars!
  New average rating: 4.6/5.0
```

## Economic Model

### Fee Structure
| Action | Fee | Recipient |
|--------|-----|-----------|
| List template | 0.005 RTC | Marketplace treasury |
| Purchase template | 2% royalty | Marketplace treasury |
| Template sale | 98% of price | Template author |

### Example Transaction
For a template priced at **10 RTC**:
- **Buyer pays**: 10 RTC
- **Seller receives**: 9.8 RTC (98%)
- **Platform receives**: 0.2 RTC (2% royalty)

## Testing

All tests pass:
```bash
cd shaprai
python -m pytest tests/test_marketplace.py -v
```

Test coverage includes:
- Template publishing
- Marketplace listing
- Template purchase
- Rating system
- Payment processing
- RustChain integration

## Code Quality

- **Type hints**: Full type annotations throughout
- **Docstrings**: Comprehensive documentation
- **Dataclasses**: Clean data structures
- **Error handling**: Graceful failure modes
- **Test coverage**: All critical paths tested
- **No breaking changes**: Backward compatible

## Files Changed

- **Modified**: `shaprai/core/template_engine.py` (marketplace functions)
- **Modified**: `shaprai/integrations/rustchain.py` (payment functions)
- **Modified**: `shaprai/cli.py` (marketplace commands)
- **Existing**: `tests/test_marketplace.py` (already implemented)

## Backward Compatibility

✅ All changes are backward compatible:
- Existing template functionality unchanged
- New marketplace features are additive
- No breaking changes to existing APIs

## Future Enhancements

Potential improvements for future PRs:
- Template search and filtering
- Featured templates section
- Bundle deals (multiple templates)
- Subscription-based template access
- Template preview before purchase
- Author verification system
- Dispute resolution mechanism

## Bounty Claim

This PR completes all acceptance criteria for Issue #8. Requesting the **40 RTC** bounty upon merge.

---

**Checklist:**
- [x] Template marketplace functionality implemented
- [x] RTC pricing system implemented
- [x] Listing fees (0.005 RTC)
- [x] Sale royalties (2%)
- [x] Automatic payment splitting
- [x] Wallet balance checking
- [x] CLI commands for all operations
- [x] Integration with RustChain economy
- [x] All tests pass
- [x] Code follows project style
- [x] No breaking changes

## Wallet Address

**RTC**: `RTC4325af95d26d59c3ef025963656d22af638bb96b`
