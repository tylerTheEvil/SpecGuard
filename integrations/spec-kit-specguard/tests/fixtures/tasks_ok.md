# Tasks: Recipe Bookmarks

**Input**: Design documents from `/specs/002-recipe-bookmarks/`

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

- [x] T001 Create bookmark module structure in src/bookmarks/

## Phase 2: User Story 1 - Bookmark a recipe (Priority: P1) 🎯 MVP

- [x] T002 [P] [US1] Contract test for bookmark endpoint in tests/contract/test_bookmark.py (FR-001, FR-002)
- [x] T003 [US1] Implement bookmark service in src/bookmarks/service.py (FR-001, FR-002, FR-005)
- [ ] T004 [US1] Persist bookmarks per account in src/bookmarks/store.py (FR-006)

## Phase 3: User Story 2 - Browse bookmarks (Priority: P2)

- [ ] T005 [P] [US2] Bookmark list ordering by date in src/bookmarks/list.py (FR-003)
- [ ] T006 [US2] Render title, author and date per entry in src/bookmarks/view.py (FR-004)

```text
- [ ] T999 [US9] Example inside a fence (FR-099) must be ignored
```
