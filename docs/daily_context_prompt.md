# Daily Context Prompt

This file stores the prompt used to ask ChatGPT each morning for updated
contextual information about the day's matches, returned as JSON that WCPS can
ingest directly.

> **Reminder:** WCPS is a recreational simulation sandbox. Ask only for football
> context (form, injuries, tactical profile, etc.). Do **not** request betting
> odds, bookmaker lines, or wagering advice.

---

## How to use it

1. Edit the **Inputs** at the top of the prompt below (date + the day's fixtures).
2. Paste the whole prompt into ChatGPT.
3. Copy the JSON it returns.
4. In the app, open **Daily Context** → paste → **Validate** → **Save & generate
   predictions**. (Or save it yourself to `data/context/YYYY-MM-DD.json`.)

The exact field meanings and allowed ranges are in
[`docs/data_schema.md`](data_schema.md) §3.

---

## ✂️ Prompt template (edit the Inputs, then copy everything below)

````text
You are assisting a RECREATIONAL football match-simulation hobby project (no
betting, no gambling, no odds). I need pre-match CONTEXT for the fixtures below,
expressed as scores I will feed into a Monte Carlo simulator.

INPUTS
- date: 2026-06-17
- fixtures (home vs away, with a stable match_id):
  - match_id: demo-2026-06-17-ARG-KSA | home: ARG (Argentina) | away: KSA (Saudi Arabia)
  - match_id: demo-2026-06-17-FRA-AUS | home: FRA (France)    | away: AUS (Australia)

For EACH fixture, assess these and return STRICT JSON only (no prose).

A) v1_scores — seven criteria, each with a "home" and "away" value in [-1.0, 1.0]
   where +1.0 = strong advantage to that team, 0.0 = neutral:
   - fifa_ranking, short_form (last ~5), long_form (last ~15), injuries,
     weather_adaptation, off_field, tactical_similarity

B) v2_strategic — strategic context:
   - favorite: "home" | "away"
   - low_block_capacity: 0..1   (underdog's ability to hold a low block)
   - draw_value_weaker: 0..1     (how valuable a draw is for the weaker side)
   - need_to_win: {home: 0..1, away: 0..1}
   - first_goal_prob: {home: p, away: p, none: p}  (should sum to ~1)
   - collapse_risk_weaker: 0..1  (underdog disorganization after conceding)
   - is_group_debut: true | false
   - transition_threat_weaker: 0..1   (underdog counter-attack threat)
   - set_piece_threat_weaker: 0..1    (underdog set-piece threat)
   - notes: one short sentence of justification

OUTPUT FORMAT — return EXACTLY this JSON shape and nothing else:
{
  "date": "2026-06-17",
  "generated_by": "ChatGPT daily context prompt v1",
  "matches": [
    {
      "match_id": "demo-2026-06-17-ARG-KSA",
      "home_team": "ARG",
      "away_team": "KSA",
      "v1_scores": {
        "fifa_ranking":        {"home": 0.0, "away": 0.0},
        "short_form":          {"home": 0.0, "away": 0.0},
        "long_form":           {"home": 0.0, "away": 0.0},
        "injuries":            {"home": 0.0, "away": 0.0},
        "weather_adaptation":  {"home": 0.0, "away": 0.0},
        "off_field":           {"home": 0.0, "away": 0.0},
        "tactical_similarity": {"home": 0.0, "away": 0.0}
      },
      "v2_strategic": {
        "favorite": "home",
        "low_block_capacity": 0.0,
        "draw_value_weaker": 0.0,
        "need_to_win": {"home": 0.0, "away": 0.0},
        "first_goal_prob": {"home": 0.0, "away": 0.0, "none": 0.0},
        "collapse_risk_weaker": 0.0,
        "is_group_debut": false,
        "transition_threat_weaker": 0.0,
        "set_piece_threat_weaker": 0.0,
        "notes": ""
      }
    }
  ]
}

RULES
- Output JSON only, valid and parseable, no markdown fences, no commentary.
- Use your best football judgement; if unsure, use values near 0 and say so in notes.
- Keep all scores within the stated ranges.
````

---

## Notes / changelog for this prompt

- *2026-06-17* — Initial template (v1) covering the seven v1 criteria and the v2
  strategic block. Update this section when you change the prompt so past
  context files stay interpretable.
