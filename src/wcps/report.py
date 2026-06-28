"""PDF report generation for a day's detailed predictions.

Pure (no Streamlit) so it can be reused from the app, a CLI or tests. Builds an
A4 PDF with, for every match of a date: metadata + actual result, a per-model
and ensemble probability table, recommended outcome/score, the ensemble's top
scorelines, the aggressive model's blowout metrics, and each team's recent form.

Uses fpdf2 core fonts (Latin-1); text is sanitised so accented team names
(Côte d'Ivoire, Curaçao, Türkiye) render and any stray Unicode is dropped.
Emojis/flags are intentionally omitted (not representable in core fonts).
"""

from __future__ import annotations

from typing import Any

from fpdf import FPDF

from . import data_io, evaluation
from .config import load_config

# Source display order + labels for the report.
_SOURCE_ORDER = ["standard", "conservative", "aggressive", "chatgpt_legacy"]
_SOURCE_LABELS = {
    "standard": "Standard",
    "conservative": "Conservative",
    "aggressive": "Aggressive",
    "chatgpt_legacy": "ChatGPT (legacy)",
    "ensemble": "Ensemble",
}
_OUTCOME_WORD = {"home": "Home", "draw": "Draw", "away": "Away"}

_PUNCT = {
    "–": "-", "—": "-", "‘": "'", "’": "'",
    "“": '"', "”": '"', "…": "...", "−": "-",
}


def _safe(text: Any) -> str:
    """Make text safe for fpdf2 core (Latin-1) fonts."""
    s = str(text)
    for k, v in _PUNCT.items():
        s = s.replace(k, v)
    return s.encode("latin-1", "replace").decode("latin-1")


def _team_label(code: str, teams: dict[str, Any]) -> str:
    name = teams.get(code, {}).get("name", code)
    return f"{name} ({code})"


def _ordered_sources(mp: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Return [(source_id, prediction)] in a stable order, ensemble last."""
    models = mp.get("models", {})
    out = [(sid, models[sid]) for sid in _SOURCE_ORDER if sid in models]
    # any other model ids not in the known order
    out += [(sid, p) for sid, p in models.items() if sid not in _SOURCE_ORDER]
    if mp.get("ensemble"):
        out.append(("ensemble", mp["ensemble"]))
    return out


class _Report(FPDF):
    def header(self) -> None:
        pass

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("helvetica", "I", 7)
        self.set_text_color(130)
        self.cell(
            0, 6,
            _safe("WCPS - recreational probabilistic simulation sandbox. "
                  "Not betting / financial advice."),
            align="C",
        )
        self.set_text_color(0)


def _match_block(
    pdf: _Report, match: dict[str, Any], mp: dict[str, Any], teams: dict[str, Any],
    date: str,
) -> None:
    home, away = match["home_team"], match["away_team"]
    h_lab = _team_label(home, teams)
    a_lab = _team_label(away, teams)

    # keep a block together-ish: page break if little room left
    if pdf.get_y() > 235:
        pdf.add_page()

    # --- title line ---
    pdf.set_font("helvetica", "B", 12)
    pdf.set_fill_color(238, 242, 255)
    pdf.cell(0, 8, _safe(f"{h_lab}  vs  {a_lab}"), new_x="LMARGIN", new_y="NEXT",
             fill=True)

    meta = []
    if match.get("kickoff"):
        meta.append(f"Kickoff {match['kickoff']}")
    if match.get("venue"):
        meta.append(match["venue"])
    grp = f"Group {match.get('group')}" if match.get("group") else match.get("phase", "")
    if grp:
        meta.append(grp)
    actual = evaluation.result_for_match(match)
    if actual:
        meta.append(f"FINAL {actual['home_goals']}-{actual['away_goals']}")
    pdf.set_font("helvetica", "", 8)
    pdf.set_text_color(90)
    pdf.cell(0, 5, _safe("  -  ".join(meta)), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0)

    # --- probability table ---
    sources = _ordered_sources(mp)
    pdf.set_font("helvetica", "B", 8)
    widths = [42, 18, 18, 18, 22, 20]
    headers = ["Model", "Home", "Draw", "Away", "Preferred", "Score"]
    pdf.set_fill_color(245, 245, 245)
    for w, htext in zip(widths, headers):
        pdf.cell(w, 6, htext, border=1, align="C", fill=True)
    pdf.ln()
    pdf.set_font("helvetica", "", 8)
    for sid, p in sources:
        label = _SOURCE_LABELS.get(sid, sid)
        bold = "B" if sid == "ensemble" else ""
        pdf.set_font("helvetica", bold, 8)
        row = [
            label,
            f"{p['prob_home']*100:.0f}%",
            f"{p['prob_draw']*100:.0f}%",
            f"{p['prob_away']*100:.0f}%",
            _OUTCOME_WORD.get(p["recommended_outcome"], p["recommended_outcome"]),
            p["recommended_score"],
        ]
        for w, val in zip(widths, row):
            pdf.cell(w, 6, _safe(val), border=1, align="C")
        pdf.ln()

    # --- ensemble extras ---
    ens = mp.get("ensemble", {})
    pdf.set_font("helvetica", "", 8)
    tops = ens.get("top_scorelines", [])[:5]
    if tops:
        txt = "Ensemble top scorelines: " + ", ".join(
            f"{t['score']} ({t['prob']*100:.0f}%)" for t in tops
        )
        pdf.multi_cell(0, 5, _safe(txt), new_x="LMARGIN", new_y="NEXT")

    agg = mp.get("models", {}).get("aggressive", {}).get("metrics", {})
    if agg:
        txt = (f"Aggressive: P(win by 2+)={agg.get('p_favourite_win_by_2plus',0)*100:.0f}%  "
               f"P(win by 3+)={agg.get('p_favourite_win_by_3plus',0)*100:.0f}%")
        pdf.multi_cell(0, 5, _safe(txt), new_x="LMARGIN", new_y="NEXT")

    # --- recent form ---
    for code, lab in ((home, h_lab), (away, a_lab)):
        form = evaluation.recent_results_for_team(code, before_date=date, limit=5)
        if form:
            parts = [f"{r['outcome']} {r['gf']}-{r['ga']} "
                     f"{'v' if r['venue']=='H' else '@'}{r['opponent']}" for r in form]
            pdf.multi_cell(0, 5, _safe(f"Form {lab}: " + "  |  ".join(parts)),
                           new_x="LMARGIN", new_y="NEXT")

    pdf.ln(3)


def build_day_pdf(date: str, config: dict[str, Any] | None = None) -> bytes:
    """Build a PDF (bytes) with detailed predictions for every match on ``date``."""
    config = config or load_config()
    matches = data_io.matches_for_date(date)
    payload = data_io.load_predictions(date) or {"predictions": {}}
    preds = payload.get("predictions", {})
    teams = data_io.load_teams()

    pdf = _Report(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()

    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, _safe(f"WCPS - Predictions for {date}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 9)
    pdf.set_text_color(90)
    n_pred = sum(1 for m in matches if m["match_id"] in preds)
    pdf.cell(0, 6, _safe(f"{len(matches)} match(es) - {n_pred} with model predictions"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0)
    pdf.ln(2)

    if not matches:
        pdf.set_font("helvetica", "", 11)
        pdf.cell(0, 8, _safe("No matches scheduled for this date."),
                 new_x="LMARGIN", new_y="NEXT")
    for match in matches:
        mp = preds.get(match["match_id"])
        if not mp:
            continue
        _match_block(pdf, match, mp, teams, date)

    return bytes(pdf.output())
