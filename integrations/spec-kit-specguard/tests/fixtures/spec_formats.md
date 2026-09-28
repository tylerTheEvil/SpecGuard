# Feature Specification: Format Drift

## User Scenarios & Testing

### User Story 1 — Parse every variant (Priority: P1) 🎯 MVP

**Acceptance Scenarios**:

1. **Given** a spec with drifted formatting, **When** it is parsed, **Then** every requirement is found once.

#### Notes inside the story

- **Given** a nested heading, **When** parsing continues, **Then** the story still owns this scenario.

### Edge Cases

- Requirement IDs mentioned in prose are references, not definitions.

## Requirements

### Functional Requirements

- **FR-001**: The parser MUST accept the template form.
- **FR-002 — Titles inside bold.** The parser MUST keep the bold title as part of the text.
- FR-003: The parser MUST accept unbolded IDs followed by a colon.
**FR-004**: The parser MUST accept a bold ID paragraph with a colon.
- **FR-005**: The parser MUST join wrapped lines
  into one requirement text
  and include indented sub-bullets:
  - (a) the first sub-item
  - (b) the second sub-item
- **FR-006**: The parser MUST end a requirement at a sibling bullet.
- Plain sibling bullet that is not a requirement.

**FR-007** applies to prose that merely references an ID, so this line defines nothing.

FR-008 in plain prose is a reference too.

| ID | Mentioned in a table |
|----|----------------------|
| FR-009 | table rows are references |

```markdown
- **FR-010**: fenced examples are ignored [NEEDS CLARIFICATION: ignored in fences]
```

1. **FR-011**: Numbered list items MUST be accepted.

## Success Criteria

- **SC-001**: 100% of the variants above parse in under 1 second.
- **NFR-001**: The parser MUST run on Python 3.9 or newer.
