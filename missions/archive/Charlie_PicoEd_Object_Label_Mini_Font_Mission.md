# Charlie pico:ed — Isolated Object-Label Miniature Font Mission

## Objective

Change **only how object-recognition labels are drawn** on Charlie's **17×7 pico:ed LED matrix**, using an efficient, readable, **variable-width 3×5 pixel font** instead of the existing vendor `matrix.wordStock` glyphs. **Short labels must display statically, not scroll.** Long labels should retain nonblocking scrolling using the existing label timing and safety priorities. This is a **display-only change**, not a recognition, protocol, motion, or architecture mission.

## Target and scope

- Repository: `mrgarmise/charlie`. Inspect the *current active integrated firmware* and its deployment path first; the prior reference implementation was `rp2040/display.py`, method `Display._draw_object_label()`, introduced on PR #11 (`feature/object-label-picoed-display`). Do not assume that older PR branch is the current integration target.
- Allowed production edit: **`rp2040/display.py` only**. Put the miniature font table and private rendering helpers in that file so firmware synchronization/deployment does not need to change. Add or adjust **only display-related unit tests**, ideally in `tests/test_object_display.py` or an existing equivalent. Do not change any other production file. If this exact scope is not sufficient, stop and report the blocker rather than broadening the change.
- Do **not** modify `rp2040/object_label.py`, the vendor `Pico_ed` library or `wordStock`, host object recognition, UART command/response formats, recognition models, label normalization or throttling, label TTL or step cadence, message rendering, other modes/animations, brightness policy, camera subscriptions, servos, motors, interlocks, watchdogs, or hardware configuration.

## Required behavior

1. Define 3×5 bitmap glyphs for **A–Z, 0–9, and space**, using MicroPython-compatible plain Python data. Characters are uppercase through the existing pipeline. Glyphs are at most **3 columns wide and 5 rows high**, with genuinely narrow glyphs (such as `I` and space) consuming fewer columns. Draw via the existing `Display._pixel()` method only; preserve its clipping and brightness rules. Align glyphs to rows **1–5** (one empty row above and below).
2. Measure the **actual pixel width** of each label from its variable-width glyphs, including **one blank column between adjacent characters** (no trailing blank column). Do not use `len(label) * 6` or the vendor stock font for object labels. Example design targets: `CAT` = 11 columns; `CHAIR` can fit in 17 columns when `I` is 1 column wide. Test exact widths against the chosen glyph definitions.
3. If measured width is **≤17 columns**, render the **entire label, stationary and horizontally centered**, immediately on its first eligible display update. Do not scroll, blink, page, or repeatedly reposition it. Existing TTL, repeated-label refresh behavior, and display precedence still apply.
4. If measured width is **>17 columns**, use the existing **nonblocking, time-driven, one-pixel-step** scrolling mechanism, adjusted for actual variable-width pixel length instead of 6 pixels per character. Preserve the existing step timing, start/reset behavior on a *changed* label, same-label refresh semantics, and TTL. Avoid new sleeps, threads, blocking vendor `show()` calls, frame queues, or UART work in the renderer. The label must be able to cycle/reset without dropping final glyph columns. Do not alter current timing defaults in an attempt to force full words to finish within a TTL.
5. Preserve the existing object-label override/expiration/clear semantics and the exact display priority rules (including error/`NO_BRAIN`, ordinary text, feedback, capability messages, sleep, and progress). Non-object text **must continue using its existing font and page behavior**.
6. Keep all object labels display-only: there must be **no path** from font/rendering code to motion authorization, servo or motor control, camera acquisition, inference, or other Charlie behavior.

## Validation / acceptance gates

- Add focused, hardware-free tests covering: every glyph within 3×5 bounds; `A–Z`, `0–9`, spaces; deterministic variable-width measurement; centered static labels including `CAT` and `CHAIR`; exact 17-column boundary; >17-column clipping/scrolling and reset at the true end of the glyphs; changed-label restart versus unchanged-label refresh; expiration/clear; and unchanged brightness/clipping via `_pixel()`.
- Regression-test that ordinary `show_text()` and status/animation rendering are **unmodified**, and that emergency/error/`NO_BRAIN` and higher-priority messages still suppress object labels as before. Preserve existing tests ensuring long labels do **not** block `PING`, `STOP`, or normal firmware servicing; test that rendering never issues a motion command.
- Run focused tests and then the repository's relevant existing device-free regression suite. Record the **commands and exact results**. Do not assert that hardware or complete native behavior was validated if it was not. Do not change test expectations merely to hide regressions.
- Show **before/after character-fit examples** and identify the precise files and lines changed. The expected diff must be confined to `rp2040/display.py` and display-specific tests.

## Execution and delivery restrictions

- First inspect the working tree, current branch, active PRs, and the live source implementation; **do not overwrite or merge other PRs**. Use a small dedicated branch/commit (and draft PR only if useful), preserving all ongoing work.
- No firmware flash, physical motion, device access, or hardware changes. Host-only code/tests are authorized. Provide the exact firmware deployment/physical viewing step for the operator to perform later, but **do not perform it**.
- Treat any required change beyond the allowed production file as an explicit **out-of-scope blocker**. Do not reinterpret this request as a display-system refactor, integration mission, or cleanup opportunity.
- Completion report: short summary; exact commit/PR link if published; changed-file list; test receipts; any limitations; and **a clear statement that no other function was intentionally changed**. Never claim zero regressions without supporting tests.