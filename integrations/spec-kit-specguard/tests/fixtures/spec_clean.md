# Feature Specification: Recipe Bookmarks

**Feature Branch**: `002-recipe-bookmarks`

**Created**: 2026-09-01

**Status**: Draft

**Input**: User description: "Let readers bookmark recipes and find them again later."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Bookmark a recipe (Priority: P1)

A signed-in reader marks a recipe as bookmarked from the recipe page.

**Why this priority**: Bookmarking is the core value of the feature.

**Independent Test**: Bookmark one recipe and confirm it appears in the bookmark list.

**Acceptance Scenarios**:

1. **Given** a signed-in reader on a recipe page, **When** the reader selects "Bookmark", **Then** the recipe appears at the top of the reader's bookmark list.
2. **Given** a bookmarked recipe, **When** the reader selects "Remove bookmark", **Then** the recipe disappears from the bookmark list.

---

### User Story 2 - Browse bookmarks (Priority: P2)

A signed-in reader opens the bookmark list and opens a saved recipe.

**Why this priority**: Saved recipes are only useful if readers can reach them again.

**Independent Test**: Open the bookmark list with three saved recipes and open each one.

**Acceptance Scenarios**:

1. **Given** a reader with three bookmarks, **When** the reader opens the bookmark list, **Then** the list shows the three recipes ordered by bookmark date, newest first.

---

### Edge Cases

- A bookmarked recipe is deleted by its author: the bookmark list shows the entry as "Recipe removed" with a remove action.
- A reader reaches the bookmark limit: the bookmark action shows the limit and offers the bookmark list.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Signed-in readers MUST be able to bookmark a recipe from the recipe page.
- **FR-002**: Readers MUST be able to remove a bookmark from the recipe page and from the bookmark list.
- **FR-003**: The bookmark list MUST order recipes by bookmark date, newest first.
- **FR-004**: The bookmark list MUST show the recipe title, author name and bookmark date for each entry.
- **FR-005**: Each reader MUST be limited to 500 bookmarks.
- **FR-006**: Bookmarks MUST persist across sessions and devices for the same reader account.

### Key Entities

- **Bookmark**: A link between a reader account and a recipe, with the bookmark date.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 90% of readers bookmark a recipe in under 5 seconds from opening the recipe page.
- **SC-002**: The bookmark list opens in under 2 seconds for readers with up to 500 bookmarks.
- **SC-003**: 95% of readers who bookmark a recipe open the bookmark list at least once within 30 days.

## Assumptions

- Readers already sign in through the existing account system.
- Recipe deletion is handled by the existing recipe service.
