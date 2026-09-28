# Feature Specification: Team Chat Notification Controls

**Feature Branch**: `006-team-notifications`

**Created**: 2026-07-18

**Status**: Draft

**Input**: User description: "Let users control which team chat notifications they receive: per-channel notification settings, quiet hours, keyword alerts that always come through, and a digest mode that batches non-urgent notifications into a summary."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Per-Channel Notification Settings (Priority: P1)

A user who belongs to many channels wants different notification behavior for each one. They open the notification settings for a channel and choose one of several levels: all messages, mentions only, or muted. From then on, the system only notifies them according to the level they picked for that channel.

**Why this priority**: This is the core control the feature is built around — without per-channel granularity, users receive either everything or nothing, which is the main pain point. Every other capability (quiet hours, keywords, digest) layers on top of this baseline.

**Independent Test**: Can be fully tested by setting different notification levels on two channels, posting messages (with and without mentions) in each, and verifying that notifications arrive only according to the configured level. Delivers immediate value as a standalone noise-reduction tool.

**Acceptance Scenarios**:

1. **Given** a user has set a channel to "mentions only", **When** another member posts a message in that channel without mentioning the user, **Then** the user receives no notification for that message.
2. **Given** a user has set a channel to "mentions only", **When** another member posts a message that @-mentions the user, **Then** the user receives a notification for that message.
3. **Given** a user has muted a channel, **When** any message is posted in that channel, including messages that mention the user, **Then** the user receives no notification from that channel.
4. **Given** a user has not customized a channel's settings, **When** a message is posted there, **Then** the user is notified according to the workspace default notification level.

---

### User Story 2 - Quiet Hours (Priority: P2)

A user does not want to be disturbed outside working hours. They define a daily quiet-hours window (e.g., 19:00–08:00). During that window, notifications are suppressed. When the window ends, they can see what they missed without having been interrupted.

**Why this priority**: Protects users' off-hours time and is the most-requested "do not disturb" behavior in team chat tools, but the product is still usable without it since channels can be muted manually.

**Independent Test**: Can be tested independently by configuring a quiet-hours window, posting messages to the user's channels inside and outside the window, and verifying suppression only during the window.

**Acceptance Scenarios**:

1. **Given** a user has quiet hours set from 19:00 to 08:00, **When** a message that would normally notify them is posted at 22:00 in their local time zone, **Then** no notification is delivered at that time.
2. **Given** messages were suppressed during quiet hours, **When** the quiet-hours window ends, **Then** the user can see the suppressed notifications as unread/missed activity.
3. **Given** a user has quiet hours configured, **When** a message matching one of their alert keywords is posted during quiet hours, **Then** the notification is delivered immediately despite quiet hours.
4. **Given** a user has no quiet hours configured, **When** messages arrive at any time, **Then** notifications follow the user's per-channel settings without time-based suppression.

---

### User Story 3 - Keyword Alerts That Always Come Through (Priority: P2)

A user is responsible for a production system and must never miss messages about it. They register alert keywords (e.g., "outage", "sev1", their project's name). Any message containing one of these keywords triggers an immediate notification regardless of channel settings, quiet hours, or digest mode.

**Why this priority**: This is the safety valve that makes aggressive muting acceptable — users will only turn down notification volume if they trust that critical topics still reach them. It is P2 rather than P1 because it only matters once users have muted something.

**Independent Test**: Can be tested by registering a keyword, muting a channel, and posting a message containing the keyword in that muted channel; the user must still receive an immediate notification.

**Acceptance Scenarios**:

1. **Given** a user has "outage" as an alert keyword and has muted channel #ops, **When** someone posts "we have an outage in region 2" in #ops, **Then** the user receives an immediate notification identifying the matching keyword.
2. **Given** a user has an alert keyword configured and digest mode enabled, **When** a message containing that keyword is posted, **Then** the notification is delivered immediately rather than held for the digest.
3. **Given** a user removes a keyword from their alert list, **When** a new message containing that keyword is posted, **Then** no keyword-triggered notification is sent for it.
4. **Given** a user has an alert keyword "deploy", **When** a message contains "deployment", **Then** the match behavior follows whole-word matching and the user is not notified.

---

### User Story 4 - Digest Mode for Non-Urgent Notifications (Priority: P3)

A user wants awareness without interruption. They enable digest mode, and non-urgent notifications (regular channel activity that would otherwise notify them) are held and delivered as a single periodic summary grouped by channel. Urgent notifications — direct messages, @-mentions, and keyword alerts — still arrive immediately.

**Why this priority**: Highest-effort, most-refined behavior; valuable for focus but the feature set is complete and coherent without it. It builds directly on the classification of urgent vs. non-urgent established by the earlier stories.

**Independent Test**: Can be tested by enabling digest mode, generating a mix of urgent (mention, keyword) and non-urgent (regular channel message) notifications, and verifying urgent ones arrive immediately while non-urgent ones appear only in the next digest summary.

**Acceptance Scenarios**:

1. **Given** a user has digest mode enabled with a 4-hour interval, **When** ten regular channel messages accumulate over that interval, **Then** the user receives one digest summarizing those notifications grouped by channel instead of ten individual notifications.
2. **Given** a user has digest mode enabled, **When** another member sends them a direct message or @-mentions them, **Then** that notification is delivered immediately and does not appear only in the digest.
3. **Given** no non-urgent notifications accumulated during a digest interval, **When** the interval elapses, **Then** no empty digest is sent.
4. **Given** a user disables digest mode, **When** notifications that were being held have not yet been delivered, **Then** pending items are delivered (or surfaced as unread activity) and subsequent notifications resume immediate delivery.

---

### Edge Cases

- What happens when a keyword-matching message is posted in a channel the user has muted entirely? (Keyword alerts win — see FR-007 — but the user should be able to understand *why* they were notified from a muted channel.)
- How does the system handle a quiet-hours window that spans midnight (e.g., 21:00–07:00)?
- What happens when the user travels across time zones — do quiet hours follow the device/local time zone or a fixed one?
- What happens when a message matches multiple alert keywords — does the user get one notification or several?
- How are notifications handled for a message that is edited to include an alert keyword after posting?
- What happens if the digest interval elapses while the user is in quiet hours — is the digest delivered, or held until quiet hours end?
- What happens to per-channel settings when a user leaves and later rejoins a channel?
- How does the system behave when a user has an extremely large keyword list or very high-volume channels (does matching or digest assembly degrade)?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Users MUST be able to set a notification level per channel, choosing at minimum: all messages, mentions only (includes direct @-mentions of the user), or muted.
- **FR-002**: System MUST apply a workspace-wide default notification level to any channel the user has not explicitly configured, and users MUST be able to change their personal default.
- **FR-003**: Users MUST be able to define a recurring daily quiet-hours window (start time and end time, evaluated in the user's local time zone), including windows that span midnight.
- **FR-004**: System MUST suppress delivery of notifications during the user's quiet hours, except for keyword alerts (see FR-007), and MUST preserve suppressed activity as unread/missed items visible after the window ends.
- **FR-005**: Users MUST be able to create, view, edit, and delete a personal list of alert keywords.
- **FR-006**: System MUST match alert keywords against message content case-insensitively on whole-word boundaries.
- **FR-007**: System MUST deliver keyword-alert notifications immediately, overriding per-channel settings (including muted channels), quiet hours, and digest mode, and MUST indicate which keyword triggered the notification.
- **FR-008**: Users MUST be able to enable or disable digest mode and select a digest delivery interval from a predefined set of options.
- **FR-009**: While digest mode is enabled, system MUST hold non-urgent notifications and deliver them as a single summary per interval, grouped by channel with message counts; urgent notifications (direct messages, @-mentions of the user, keyword alerts) MUST still be delivered immediately.
- **FR-010**: System MUST NOT deliver an empty digest when no non-urgent notifications accumulated during the interval.
- **FR-011**: System MUST apply notification preference changes to all messages received after the change takes effect, without requiring the user to sign out or restart.
- **FR-012**: System MUST persist all notification preferences per user so they apply consistently across the user's sessions and devices.
- **FR-013**: When digest mode is disabled with undelivered held notifications, system MUST surface those pending notifications to the user rather than discarding them.
- **FR-014**: When a single message triggers multiple notification reasons (e.g., a mention that also matches a keyword), system MUST deliver at most one notification for that message.

### Key Entities

- **Notification Preference Profile**: A user's overall notification configuration — personal default level, quiet-hours window, digest mode state and interval. One per user.
- **Channel Notification Setting**: A user's chosen notification level for a specific channel (all / mentions only / muted). Belongs to one user and one channel; absence means the default applies.
- **Alert Keyword**: A user-defined term whose appearance in a message always triggers an immediate notification. Belongs to one user; a user may have many.
- **Notification Event**: A pending or delivered notification derived from a message, carrying its trigger reason (channel activity, mention, direct message, keyword match), urgency classification, and delivery state (delivered immediately, suppressed by quiet hours, held for digest).
- **Digest**: A batched summary of a user's held non-urgent notification events for one interval, grouped by channel.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can configure a channel's notification level, quiet hours, or a keyword alert in under 1 minute each without documentation or assistance.
- **SC-002**: 100% of messages matching a user's alert keywords produce an immediate notification, regardless of channel mute, quiet hours, or digest state, in scenario testing.
- **SC-003**: Zero notifications are delivered during a user's quiet-hours window in scenario testing, excluding keyword alerts.
- **SC-004**: Users with digest mode enabled experience at least an 80% reduction in individual notification interruptions during a typical workday compared to the same activity without digest mode.
- **SC-005**: Keyword-alert and mention notifications are delivered within 5 seconds of the message being posted under normal load.
- **SC-006**: Within one month of release, support requests related to unwanted or missed notifications decrease by 30%.

## Assumptions

- Direct messages are always treated as urgent: they notify immediately (subject to quiet hours) and are never held for a digest. Only keyword alerts override quiet hours, per the description's "always come through" wording.
- "Mentions only" includes direct @-mentions of the user and group mentions that address the user (e.g., channel-wide callouts); the exact set of group-mention types honored can be tuned later without changing the feature's shape.
- Quiet hours are evaluated in the user's current local time zone (device-reported), and a single recurring daily window is sufficient for v1; per-day-of-week schedules are out of scope.
- Keyword matching is case-insensitive whole-word matching on message text; regular expressions, phrase proximity, and matching inside attachments are out of scope for v1.
- Digest intervals are chosen from a predefined set (e.g., hourly, every 4 hours, daily) rather than free-form scheduling; the default interval is daily.
- A digest that comes due during quiet hours is held and delivered when quiet hours end.
- Notification preferences are per user across the whole workspace; per-device overrides are out of scope for v1.
- The existing team chat system already provides channels, membership, direct messages, @-mentions, and a notification delivery mechanism; this feature governs *which* notifications are delivered and *when*, not the delivery channels (push, email, etc.) themselves.
