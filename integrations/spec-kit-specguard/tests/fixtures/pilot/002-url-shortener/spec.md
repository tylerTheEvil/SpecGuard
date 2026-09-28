# Feature Specification: URL Shortener Service

**Feature Branch**: `002-url-shortener`

**Created**: 2026-07-18

**Status**: Draft

**Input**: User description: "Build a URL shortener service where users can create short links, optionally with custom aliases, see click statistics for their links, and set expiration dates on links."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Create and Use a Short Link (Priority: P1)

A registered user submits a long URL and receives a short link. Anyone who visits the short link is redirected to the original destination URL.

**Why this priority**: This is the core value proposition of the service. Without link creation and redirection, no other capability (aliases, statistics, expiration) has meaning. Implementing only this story still yields a usable product.

**Independent Test**: Can be fully tested by submitting a long URL, receiving a generated short link, and confirming that visiting the short link redirects to the original URL.

**Acceptance Scenarios**:

1. **Given** a signed-in user with a valid long URL, **When** they submit it for shortening, **Then** the system returns a unique short link associated with their account.
2. **Given** an existing short link, **When** any visitor (signed in or not) opens it, **Then** they are redirected to the original destination URL.
3. **Given** a user submits a malformed or empty URL, **When** they attempt to create a short link, **Then** the system rejects the request with a clear error message explaining what is wrong.
4. **Given** a visitor opens a short link that does not exist, **When** the system looks it up, **Then** the visitor sees a "link not found" page rather than a redirect or a generic error.

---

### User Story 2 - Choose a Custom Alias (Priority: P2)

A user creating a short link optionally provides their own memorable alias (e.g., `myshop-sale`) instead of accepting a system-generated code, so the link is recognizable and brandable.

**Why this priority**: Custom aliases are a common differentiator for marketing and sharing use cases, but the service is fully functional without them. They build directly on the P1 creation flow.

**Independent Test**: Can be tested independently by creating a link with a chosen alias, verifying the alias resolves to the destination, and verifying that a duplicate alias is rejected.

**Acceptance Scenarios**:

1. **Given** a user creating a short link, **When** they provide an available custom alias, **Then** the short link uses that alias instead of a generated code.
2. **Given** an alias already in use, **When** a user requests it, **Then** the system rejects the request, tells the user the alias is taken, and preserves their other input so they can retry.
3. **Given** a user provides an alias with disallowed characters or reserved words, **When** they submit it, **Then** the system rejects it and explains the allowed alias format.

---

### User Story 3 - View Click Statistics (Priority: P2)

A user opens a dashboard of their links and sees how many times each link has been clicked, including click counts over time, so they can measure engagement with what they shared.

**Why this priority**: Statistics are the main reason users prefer a shortener with accounts over an anonymous one, but they depend on links existing first (P1). The service delivers value without them, so they rank below core creation.

**Independent Test**: Can be tested by creating a link, visiting it a known number of times, and verifying the owner's dashboard shows the matching click count while another user cannot see it.

**Acceptance Scenarios**:

1. **Given** a link that has been clicked several times, **When** its owner views their dashboard, **Then** they see the total click count for that link.
2. **Given** a link owner viewing a link's statistics, **When** they select a time range, **Then** they see click counts broken down over that period.
3. **Given** a user viewing their dashboard, **When** they look at the list of links, **Then** only links they own are shown — statistics for other users' links are not accessible.
4. **Given** a link with zero clicks, **When** the owner views its statistics, **Then** the count displays as zero rather than an error or missing entry.

---

### User Story 4 - Set an Expiration Date (Priority: P3)

A user sets an expiration date when creating (or editing) a link, after which the short link stops redirecting — useful for time-limited promotions or temporary shares.

**Why this priority**: Expiration is a convenience/control feature that a minority of links will use. It layers cleanly on top of the P1 redirect flow without affecting links that never set it.

**Independent Test**: Can be tested by creating a link with an expiration in the near future, confirming it redirects before that time, and confirming it no longer redirects after the time passes.

**Acceptance Scenarios**:

1. **Given** a user creating a link, **When** they set a future expiration date, **Then** the link is created and redirects normally until that date.
2. **Given** a link whose expiration date has passed, **When** a visitor opens it, **Then** they see an "expired link" page instead of being redirected.
3. **Given** a user creating a link, **When** they set an expiration date in the past, **Then** the system rejects it with a clear message.
4. **Given** an expired link, **When** the owner views their dashboard, **Then** the link is visibly marked as expired and its accumulated statistics remain viewable.

---

### Edge Cases

- What happens when two users submit a custom alias request for the same alias at nearly the same moment? Exactly one must succeed.
- How does the system handle a destination URL that itself points to the shortener (self-referencing or redirect loops)?
- What happens when a visitor opens a link at the exact moment it expires?
- How are extremely long destination URLs (thousands of characters) handled?
- What happens to click statistics recording during a burst of traffic (e.g., a link goes viral) — are counts lost or delayed?
- How does the system respond to case variations of an alias (e.g., `MyLink` vs `mylink`)?
- What happens when a user deletes their account — do their short links keep redirecting?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow a registered user to create a short link from a valid destination URL.
- **FR-002**: System MUST validate submitted destination URLs and reject malformed or unsupported ones with a descriptive error message.
- **FR-003**: System MUST generate a unique short code for each link when no custom alias is provided.
- **FR-004**: System MUST redirect any visitor of an active short link to its destination URL without requiring the visitor to sign in.
- **FR-005**: Users MUST be able to optionally specify a custom alias when creating a link, subject to an allowed character set and length limits.
- **FR-006**: System MUST reject a custom alias that is already in use or matches a reserved word, and MUST inform the user why.
- **FR-007**: System MUST record each click on a short link, including at minimum the time of the click.
- **FR-008**: Users MUST be able to view the total click count and clicks-over-time breakdown for each link they own.
- **FR-009**: System MUST restrict link management and statistics visibility to the link's owner — no user may view or modify another user's links.
- **FR-010**: Users MUST be able to set an optional expiration date/time on a link at creation, and to add, change, or remove it later.
- **FR-011**: System MUST stop redirecting an expired link and instead show visitors a page explaining that the link has expired.
- **FR-012**: Users MUST be able to list, deactivate, and delete their own links; a deactivated or deleted link MUST stop redirecting.
- **FR-013**: System MUST show a "not found" page for short codes that do not exist, without revealing whether a code ever existed.
- **FR-014**: System MUST retain a link's accumulated statistics after the link expires or is deactivated, until the link is deleted by its owner.

### Key Entities

- **User**: A registered account that owns links; identified uniquely; is the only party able to manage its links and view their statistics.
- **Short Link**: The central entity; has a destination URL, a short code (generated or custom alias), an owner, a creation time, an optional expiration date/time, and a status (active, expired, deactivated).
- **Click Event**: A record of a single visit to a short link; belongs to one short link; carries at minimum a timestamp; aggregated to produce statistics.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can go from submitting a long URL to having a working short link in under 30 seconds.
- **SC-002**: Visitors following an active short link reach the destination in under 1 second in 95% of cases.
- **SC-003**: Click statistics visible to the owner reflect at least 99% of actual clicks, and appear in the dashboard within 1 minute of the click.
- **SC-004**: Expired links stop redirecting within 1 minute of their expiration time in 100% of cases.
- **SC-005**: 90% of first-time users successfully create a short link (with or without a custom alias) on their first attempt without external help.
- **SC-006**: The service sustains 1,000 concurrent redirect requests without visitor-facing errors or degradation.

## Assumptions

- Creating and managing links requires a registered account, since statistics and management are described per-user ("their links"); anonymous visitors only follow links. Anonymous link creation is out of scope for this version.
- A standard account registration/sign-in capability exists or will be provided; its details are not part of this feature's scope.
- Click statistics are aggregate counts and time-series only; per-visitor details such as geography, referrer, or device breakdowns are out of scope for this version.
- Aliases and generated codes are treated case-insensitively to avoid near-duplicate confusing links, and a small set of reserved words (e.g., system page names) is excluded from use.
- Expiration means the link stops redirecting but is not deleted; the owner retains the record and its statistics and may delete it explicitly.
- Links without an expiration date remain active indefinitely.
- Destination URLs are limited to web URLs (http/https-style web addresses); other schemes are rejected.
- Malicious-URL screening (phishing/malware blocklists) is desirable but out of scope for this version; abuse handling is manual.
