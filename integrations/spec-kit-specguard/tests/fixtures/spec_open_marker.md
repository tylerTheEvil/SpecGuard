# Feature Specification: Account Export

**Feature Branch**: `003-account-export`

**Status**: Draft

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Export account data (Priority: P1)

An account owner downloads a copy of their data.

**Acceptance Scenarios**:

1. **Given** a signed-in account owner, **When** the owner requests an export, **Then** a download link is sent by email within 24 hours.

### Edge Cases

- The owner requests a second export while one is pending: the pending request is reused.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Account owners MUST be able to request an export of their account data.
- **FR-002**: The export MUST be delivered as [NEEDS CLARIFICATION: file format not specified - JSON, CSV, or both?]
- **FR-003**: Export links MUST expire 7 days after they are sent.

## Success Criteria *(mandatory)*

- **SC-001**: 99% of export requests are delivered within 24 hours.
