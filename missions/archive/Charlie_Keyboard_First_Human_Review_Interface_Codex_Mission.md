# Charlie — Keyboard-First Human Review Interface
## Codex implementation and independent validation mission

**Date:** 2026-10-29  
**Repository:** `mrgarmise/charlie`  
**Primary integration:** existing draft PR #15 (`feature/executive-model-learning`) and the existing asynchronous human-question gateway; inspect current state before selecting a branch.  
**Mission type:** focused, independently tested implementation increment. **Not** a replacement architecture or an authorization to deploy models or operate hardware.

## Objective

Turn Charlie's currently functional but cumbersome offline image-review workflow into a **reusable, keyboard-first, one-question-at-a-time review experience**, suitable for repeated human teaching. Prioritize a fast and accessible review loop with an expected **two to three keystrokes per ordinary image**. Reuse and improve the prior score-entry review UI patterns rather than creating a parallel, Robotron-only subsystem. Lay a clean integration path to Charlie's asynchronous human-question webpage, preserving existing functioning workflows until replacements are verified.

The operator reviewed **64 new frames** via a single long offline gallery with dropdowns, then exported `reviews.json` and ran `apply-reviews.sh`. That worked but would be inefficient at scale. The learning notebook subsequently reported **70 authentic, human-labeled images across 13 capture sessions**, with **33 `title_menu`, 37 `gameplay`, zero `terminal`, zero reviewed `unknown`**. The existing classifier agreed on **55/70** of these retained examples (a descriptive replay, **not** independent accuracy). Normal Executive initiation has recorded a real `robotron.screen_state` need and returned `NEEDS_LABELS`; no authentic candidate training, independent qualification, or model activation has been demonstrated. Do **not** weaken the missing-class or independent-holdout gates or reassign labels to satisfy them. A genuine Robotron GAME OVER display is `terminal`; a nonzero score alone does not make a title/attract screen `terminal`.

## Before changing code

1. Inspect the current repository, worktrees, draft PRs, published HEADs and CI. In particular inspect PR #15 and the asynchronous human-question gateway branch/PR, as well as the existing score-entry interface, previous operator feedback, the recent offline review gallery, and local documentation. Avoid overlapping or clobbering unmerged changes. Choose the **appropriate existing feature branch** for the UI and document cross-PR integration dependencies; create a new isolated worktree/branch **only if truly necessary** to avoid contaminating active work. Do not merge or close active PRs without separate authorization.
2. Identify the actual human-review data contract: item IDs, task schema, available answer choices, review attribution, retained history/supersession, image references, export/import format, session/provenance boundaries, and gateway security. Preserve historical labels and receipts; treat previous `reviews.json` as evidence, not a disposable staging file.
3. Inspect the real user workflow on Charlie's Pi where available. Avoid claiming Pi-browser acceptance if no display/browser is accessible. Existing review state lives at `/home/five/charlie-model-review`; offline gallery artifacts have been under `/home/five/charlie-dataset-qualification-20261029/`. **Never overwrite or reset these directories.**

## Required user experience

- **One primary review item visible at a time:** image large enough to inspect comfortably, concise context, task-specific question, clearly visible choices, progress (reviewed/total/remaining), and an indication of whether the item is already answered. No infinitely scrolling page of dozens of active questions.
- **Fast controls:** radio buttons or equivalent single-choice control; `1`–`4` select corresponding category where applicable; **Enter** commits the selected answer and advances; **Backspace** moves to previous item. Support click/tap controls as well. Provide a visible hint for shortcuts. Use sensible key mapping for tasks with different numbers of answer options (e.g., score correction); no hard-coded Robotron logic in common components.
- **Accessible keyboard behavior:** focusable controls, visible focus, appropriate labels, semantic buttons/radio groups, screen-reader announcements for current item/progress and save status. Do not hijack number keys/Enter/Backspace when typing into inputs, textareas, contenteditable fields, modal dialogs or other controls. Avoid browser Back navigation when using Backspace for review, without blocking ordinary typing. Buttons remain usable without shortcuts. Respect browser zoom and narrow/mobile layouts.
- **Fast, reliable progression:** selection and save/advance must be unambiguous; no double-submit from key repeat; show save failures instead of silently advancing; preserve prior answers and enable corrections. If a selection should save automatically, that behavior must be visibly communicated and tested—otherwise use `Enter` as explicit commit. Preserve reviewer identity, timestamps, provenance, observation ID, and immutable review/supersession semantics.
- **Resume and queue management:** restore progress after browser reload or returning later; filter to unanswered, uncertain/skipped, all, or corrections where supported; skip/defer ambiguous questions **without inventing an `unknown` ground-truth label**. Distinguish *reviewer unsure* from *genuine out-of-distribution*.
- **Task-independent:** support Robotron screen states now and a general schema for future score review, pet identity, bird identification, and other Charlie learning questions. Do not claim those future task adapters are operational unless actually implemented and tested. Reuse existing score-entry controls and human-question queue patterns where sound.
- **Offline continuity:** the existing offline HTML gallery + JSON download + `apply-reviews.sh` path must continue working until a direct submission path is independently validated. If implementing direct notebook-backed submission, use existing authenticated/bounded gateway contracts; handle replays, conflicts, malformed payloads, retries, unauthorized edits and audit retention. Do not expose a network listener publicly or grant unauthenticated write access merely for convenience. Prefer a local, offline-first workflow if gateway integration is not ready.

## Acceptance tests

Implement automated tests (and browser-level checks where environment allows) that verify:

1. Each keyboard shortcut selects/commits/navigates correctly, including key-repeat, absent selection, last item, previous item, changed selection and reload/resume.
2. Typing into editable controls is never intercepted; keyboard and pointer workflows agree; focus state and accessible labels are usable.
3. One-at-a-time rendering scales to at least hundreds of review items without requiring a giant scrolling page; progress and filtering are accurate.
4. Previous `reviews.json` and `apply-reviews.sh` data round-trip without losing records, attribution, provenance, IDs, timestamps or supersession; imports are safe on retries and report errors.
5. Review uncertainty remains separate from the `unknown`/OOD category. Correcting an earlier answer is auditable, not destructive.
6. Different answer schemas (screen-state radio choices and numeric score correction at minimum) can use the common queue/navigation layer, while preserving relevant existing score-review behavior.
7. No changes to model training qualification thresholds, dataset partitions, hardware movement gates, camera ownership, Hailo access or model activation are introduced incidentally.
8. Independent tests pass. Record any original failed/timeout CI run and its retry; do not suppress failures or describe unexecuted browser/native tests as passed.

## Execution and publication

Implement eligible improvements now; run focused tests, the applicable full/combined regression suites, and independent CI. Commit and publish **tested increments** to the selected existing feature PR where appropriate, or a clearly justified isolated UI PR with explicit integration plan. Do not overwrite concurrently developing PRs. Keep PRs draft until their actual acceptance criteria are met. Preserve all authentic images, prior human labels, original evidence, review receipts, unmerged work, hardware restrictions and model safety controls. Do not use the mission to relabel the existing 70 frames, freeze train/validation/test partitions, train or activate a model, start hardware motion, or flash firmware.

## Report back

Give the operator: branch/PR and commit(s), concrete UI entrypoint/path/URL if available, concise keyboard instructions, offline vs direct-submission status, exact test/CI results, any browser or Pi-native validation blockers, backward-compatibility results, and **at most one simple human acceptance walkthrough**. Explicitly state any remaining integration requirement with the asynchronous question gateway. Distinguish completed implementation from proposals. Do not block useful improvements merely because native GUI testing is unavailable.

**Intended end state:** Charlie manages the review queue, shows one clearly framed question at a time, accepts an answer in about two keystrokes, preserves a correction trail, and can reuse the interaction for new learning tasks. The human should be an occasional teacher—not a data-entry operator.