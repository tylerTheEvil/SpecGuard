# Feature Specification: Cart Discount Codes

**Feature Branch**: `004-cart-discounts`

**Created**: 2026-07-18

**Status**: Draft

**Input**: User description: "Add discount code support to our e-commerce checkout: percentage and fixed-amount codes, per-customer usage limits, expiry dates, rules about which codes can be combined, and an admin screen where marketing can create and deactivate codes."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Apply a Discount Code at Checkout (Priority: P1)

A shopper with items in their cart enters a discount code during checkout. The system validates the code (exists, active, not expired, usage limit not reached), applies the discount to the order total, and shows the shopper exactly how much they saved before they pay.

**Why this priority**: This is the core value of the feature — without redemption at checkout, nothing else matters. It is the shopper-facing half of the feature and directly affects conversion and revenue.

**Independent Test**: Can be fully tested by seeding a set of test codes (percentage and fixed-amount, including expired and limit-exhausted ones) and completing checkouts with each. Delivers value on its own: shoppers can redeem codes distributed through any existing channel.

**Acceptance Scenarios**:

1. **Given** a cart with a $100 subtotal and a valid 20% discount code, **When** the shopper applies the code, **Then** the order shows a $20 discount line item and a $80 discounted subtotal before payment.
2. **Given** a cart with a $30 subtotal and a valid $10 fixed-amount code, **When** the shopper applies the code, **Then** the order total is reduced by $10 and the discount is itemized with the code name.
3. **Given** a cart with a $5 subtotal and a valid $10 fixed-amount code, **When** the shopper applies the code, **Then** the merchandise total is reduced to $0 and never goes negative.
4. **Given** a code that expired yesterday, **When** the shopper attempts to apply it, **Then** the code is rejected with a message stating the code has expired.
5. **Given** a code the shopper has already used up to its per-customer limit, **When** they attempt to apply it again, **Then** the code is rejected with a message stating the usage limit has been reached.
6. **Given** an applied discount code, **When** the shopper removes it before paying, **Then** the order total returns to the undiscounted amount.

---

### User Story 2 - Marketing Creates and Deactivates Codes (Priority: P2)

A marketing team member opens the discount code admin screen, creates a new code by specifying its code string, discount type (percentage or fixed amount), value, expiry date, per-customer usage limit, and whether it can be combined with other codes. Later, they deactivate a code that is being abused or was published by mistake, and the code immediately stops working for new orders.

**Why this priority**: Self-service code management is what makes the feature operational — without it, every campaign requires engineering involvement. It is second priority because redemption (Story 1) can initially be validated with seeded codes.

**Independent Test**: Can be tested independently by having a marketing user create a code through the admin screen, verifying it appears in the code list with correct attributes, deactivating it, and verifying its status changes — without needing the checkout flow.

**Acceptance Scenarios**:

1. **Given** a marketing user on the admin screen, **When** they create a 15% code with an expiry date and a per-customer limit of 1, **Then** the code is saved, listed with its attributes and status, and becomes usable at checkout immediately.
2. **Given** an existing active code, **When** a marketing user deactivates it, **Then** the code is rejected for all new checkout applications from that moment, while orders already completed with it are unaffected.
3. **Given** an attempt to create a code whose code string already exists (in any letter casing), **When** the marketing user saves, **Then** the system rejects the duplicate and explains why.
4. **Given** a user without marketing/admin permissions, **When** they attempt to access the discount code admin screen, **Then** access is denied.

---

### User Story 3 - Combining Multiple Codes Under Stacking Rules (Priority: P3)

A shopper attempts to apply more than one discount code to a single order. The system enforces the combination rules defined on each code: codes marked as combinable can stack, while an exclusive code cannot be applied together with any other code.

**Why this priority**: Stacking rules protect margins and prevent abuse, but they only matter once single-code redemption (P1) and code management (P2) exist. The single-code default is a safe interim behavior.

**Independent Test**: Can be tested independently by defining one combinable and one exclusive code and attempting all pairings at checkout, verifying accepted/rejected combinations and the computed total.

**Acceptance Scenarios**:

1. **Given** two codes both marked combinable (10% and $5 off) on a $100 cart, **When** the shopper applies both, **Then** both discounts are applied ($100 → $90 → $85) and each is itemized separately.
2. **Given** an exclusive code already applied to the order, **When** the shopper attempts to add a second code, **Then** the second code is rejected with a message explaining the applied code cannot be combined.
3. **Given** a combinable code already applied, **When** the shopper attempts to add an exclusive code, **Then** the exclusive code is rejected with a message explaining it cannot be combined with other codes.

---

### Edge Cases

- What happens when a fixed-amount discount exceeds the order subtotal? (Discount is capped at the subtotal; the merchandise total is never negative.)
- What happens when a code expires or is deactivated between being applied to a cart and the order being placed? (Final validation at order placement rejects it and prompts the shopper to review the updated total before paying.)
- What happens when the last remaining redemption of a limited code is claimed by another customer while a shopper has it applied in their cart? (Order placement re-checks limits; the later order is rejected with a clear message.)
- How is the per-customer limit enforced for guest checkout, where there is no account? (Tracked by the email address given at checkout — see Assumptions.)
- What happens when the shopper edits the cart after applying a percentage code? (The discount amount is recalculated from the current eligible subtotal.)
- How are code strings matched with respect to casing and surrounding whitespace? (Matching is case-insensitive and input is trimmed.)
- What happens to a code's usage count when an order is cancelled? (Cancellation before fulfillment releases the redemption; refunds after fulfillment do not — see Assumptions.)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow shoppers to enter a discount code during checkout and apply it to the current order after validation.
- **FR-002**: System MUST support percentage discount codes that reduce the eligible order subtotal by a configured percentage (1–100%).
- **FR-003**: System MUST support fixed-amount discount codes that reduce the eligible order subtotal by a configured monetary amount, capped so the merchandise total never falls below zero.
- **FR-004**: System MUST enforce an expiry date per code and reject expired codes at both application time and order placement.
- **FR-005**: System MUST enforce a per-customer usage limit per code, counting completed orders per customer, and reject applications beyond the limit.
- **FR-006**: System MUST support an optional total redemption cap per code across all customers and reject applications once the cap is reached.
- **FR-007**: System MUST enforce combination rules: each code is marked either combinable or exclusive; an exclusive code cannot be applied together with any other code, and only codes marked combinable may stack.
- **FR-008**: System MUST display each applied discount as an itemized line (code and amount saved) and show the updated order total before payment is taken.
- **FR-009**: System MUST re-validate all applied codes (active status, expiry, usage limits, combination rules) at order placement, and reject the order with a clear explanation if any code is no longer valid.
- **FR-010**: Shoppers MUST be able to remove an applied code before payment, restoring the undiscounted total.
- **FR-011**: Marketing users MUST be able to create discount codes via an admin screen, specifying: code string, discount type (percentage or fixed amount), value, expiry date, per-customer usage limit, optional total redemption cap, and combinability.
- **FR-012**: Marketing users MUST be able to deactivate (and reactivate) codes; deactivation takes effect immediately for new applications and does not alter completed orders.
- **FR-013**: System MUST enforce uniqueness of code strings (case-insensitive) and match shopper-entered codes case-insensitively with surrounding whitespace ignored.
- **FR-014**: System MUST record every redemption (code, customer, order, discount amount, timestamp) so that usage limits can be enforced and marketing can review code usage.
- **FR-015**: Access to the discount code admin screen MUST be restricted to authorized marketing/admin roles.
- **FR-016**: System MUST present distinct, shopper-friendly rejection messages for each failure reason: unknown code, expired, deactivated, per-customer limit reached, total cap reached, and not combinable with an applied code.

### Key Entities

- **Discount Code**: A marketing-created promotion definition. Attributes: unique code string, discount type (percentage | fixed amount), value, expiry date, per-customer usage limit, optional total redemption cap, combinability flag (combinable | exclusive), status (active | deactivated), creation metadata.
- **Redemption**: A record that a specific customer used a specific code on a specific order. Attributes: code, customer identity (account or guest email), order, discount amount applied, timestamp. Basis for usage-limit enforcement and reporting.
- **Order / Cart**: The existing purchase context the discounts attach to. Holds zero or more applied codes, itemized discount lines, and the discounted total.
- **Marketing User**: An authorized administrator who creates, reviews, and deactivates discount codes via the admin screen.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A shopper can apply a valid discount code and see the updated order total within 2 seconds, without leaving the checkout flow.
- **SC-002**: 100% of orders placed with a discount reflect a discount amount consistent with the code's definition, and no completed order has a negative merchandise total.
- **SC-003**: Zero orders are completed using a code that was expired, deactivated, or over its usage limit at the moment of order placement.
- **SC-004**: A marketing user can create and publish a new discount code in under 3 minutes without engineering involvement.
- **SC-005**: At least 95% of shoppers who attempt to apply a code either succeed or receive a message identifying the specific reason for rejection on the first attempt.

## Assumptions

- Discounts apply to the merchandise subtotal only; shipping fees and taxes are excluded from the discount calculation.
- Per-customer usage limits are tracked by customer account; for guest checkout, the email address provided at checkout is used as the customer identity.
- Default combination behavior is one code per order; stacking is only possible when all applied codes are explicitly marked combinable. When codes stack, percentage discounts are applied to the subtotal first, then fixed amounts, and the combined discount is capped at the subtotal.
- A code is valid through the end of its expiry date in the store's local time zone.
- Deactivation is reversible; permanent deletion of codes is out of scope, and historical redemption records are always retained.
- Order cancellation before fulfillment releases the redemption back to the customer's limit; refunds after fulfillment do not restore usage counts.
- The store operates in a single currency; fixed-amount codes are denominated in that currency.
- The existing admin authentication and role system is reused for restricting access to the discount admin screen; no new login mechanism is introduced.
- Product/category-restricted codes, minimum-order-value thresholds, automatic (codeless) promotions, and bulk code generation are out of scope for this feature.
