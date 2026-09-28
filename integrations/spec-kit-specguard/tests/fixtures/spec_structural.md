# Feature Specification: Team Invitations

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Invite a teammate

A team owner invites a teammate by email.

**Acceptance Scenarios**:

1. **Given** a team owner, **When** the owner enters an email address, **Then** an invitation is sent.

### User Story 2 - Accept an invitation (Priority: P2)

An invited person joins the team from the invitation email.

- The invited person clicks the link in the email.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Team owners MUST be able to invite teammates by email address.
- **FR-002**: Invitations MUST expire 14 days after they are sent.
- **FR-002**: Invitations MUST be revocable by the team owner.
- **FR-005**: The invitation email contains the team name and the inviter's name.

The team never shares invitation links publicly; see the `[NEEDS CLARIFICATION]` convention in the team handbook.

## Success Criteria *(mandatory)*

- **SC-001**: Invited people find joining the team straightforward.
- **SC-002**: Every accepted invitation adds exactly one member to the team.
