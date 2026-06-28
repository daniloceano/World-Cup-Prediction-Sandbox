# Daily Prompts (today's context + yesterday's results)

Two copy-paste prompts you send to ChatGPT every day. **Neither requires you to
type a date** — ChatGPT resolves "today" and "yesterday" on its own.

The ready-to-paste prompt text lives in standalone files (kept here as the
single source of truth so they never drift from this doc):

- **Prompt A — today's match context** → [`docs/prompt_a.txt`](prompt_a.txt).
  Returns the daily context JSON for *all* of today's World Cup matches. Save it
  to `data/context/YYYY-MM-DD.json` (or paste it in the app's **Daily Context**
  page) and generate predictions. Saving also auto-registers today's fixtures
  into the schedule.
- **Round prompt — the whole round at once** → [`docs/prompt_a_round.txt`](prompt_a_round.txt).
  Same JSON shape as Prompt A but covering *every* match of the current round
  (across several days). Paste it in the **Daily Context** page: it is split into
  per-date context files and predictions are generated for every date in one go.
- **Prompt B — yesterday's results** → [`docs/prompt_b.txt`](prompt_b.txt).
  Returns the final scores of *all* of yesterday's World Cup matches, in the
  app's results schema. Merge it into `data/results/actual_results.json` so the
  **History** page can score every model and the ensemble.

> **Reminder:** WCPS is a recreational simulation sandbox. Ask only for football
> context and results (form, injuries, tactical profile, final scores). Do **not**
> request betting odds, bookmaker lines, or wagering advice.

---

## Conventions both prompts follow

- **Date resolution & "match day" window:** ChatGPT uses the *actual current
  date* (it has it — do not ask for it). A **match day runs from 06:00 to 06:00
  the next day** in the **America/Sao_Paulo (UTC−3)** timezone, so late-night /
  after-midnight ("madrugada") kickoffs are grouped into the day they *belong*
  to, not the calendar date they spill into. "Today" = `[today 06:00, tomorrow
  06:00)`; "yesterday" = `[yesterday 06:00, today 06:00)`. The **match-day
  (slate) date** is the calendar date on which the window *starts*, and it is
  echoed back in the `date` field so the file is auditable.
- **`match_id` format (identical in both prompts):**
  `wc-YYYY-MM-DD-<HOME>-<AWAY>`, where `HOME`/`AWAY` are the **uppercase**
  3-letter FIFA codes and `YYYY-MM-DD` is the **match-day (slate) date** above —
  the window-start date, *not* necessarily the kickoff's calendar date (a 01:00
  kickoff uses the previous calendar day). The match's `date` field uses this
  same slate date. This is what makes Prompt B's result `match_id` line up with
  the `match_id` Prompt A produced that morning.
  Examples: `wc-2026-06-15-BEL-EGY`, `wc-2026-06-15-KSA-URU`,
  `wc-2026-06-14-CIV-ECU`.
  (The History evaluation is also tolerant of older/different id conventions,
  reversed home/away order, and a ±1-day shift — it joins results to predictions
  by team pair + date — but using this format keeps the join exact.)
- **Home/away orientation:** "home" = the team listed **first** in the official
  FIFA schedule for that match. Keep the same orientation in both prompts so
  results line up with predictions.
- **If unsure of the schedule/scores:** browse for the official FIFA World Cup
  2026 fixtures/results if you can; otherwise use best knowledge and flag the
  uncertainty in `notes`. Never invent a final score for a match that has not
  finished — omit it instead.

Field meanings and allowed ranges: see [`docs/data_schema.md`](data_schema.md)
(§3 for context, §5 for results).

---

## Applying the outputs

- **Prompt A:** paste the JSON into the app's **Daily Context** page → Validate →
  Save & generate predictions (or save it yourself to
  `data/context/YYYY-MM-DD.json`, using the slate date in the filename).
- **Prompt B:** paste the objects from the `"results"` array into the `"results"`
  array of [`data/results/actual_results.json`](../data/results/actual_results.json)
  (replacing or adding by `match_id`). The History page picks them up immediately.

---

## Notes / changelog for these prompts

- *2026-06-17* — Match day redefined as a **06:00→06:00 window** (America/Sao_Paulo)
  so after-midnight kickoffs are grouped into the correct slate; `match_id` and
  the `date` field now use the **match-day (slate) date** (window-start),
  not the kickoff's calendar date. Prompt bodies moved to `prompt_a.txt` /
  `prompt_b.txt`.
- *2026-06-17* — Prompts self-resolve "today"/"yesterday" (no manual date),
  cover **all** of the day's matches, emit the canonical `match_id` convention,
  and carry match metadata. Added the separate Prompt B for yesterday's results.
- *2026-06-17* — v1 (replaced): original single template that required pasting
  the date and fixtures by hand.
