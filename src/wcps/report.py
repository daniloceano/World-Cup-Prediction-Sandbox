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

import io
from typing import Any

import matplotlib
from fpdf import FPDF

from . import data_io, evaluation
from .config import load_config

matplotlib.use("Agg")  # headless, no display needed
import matplotlib.pyplot as plt  # noqa: E402

# Outcome donut colours (match the app: home blue, draw grey, away red).
_OUTCOME_COLORS = ["#2563eb", "#9ca3af", "#dc2626"]

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


def _donut_png(pred: dict[str, Any], home: str, away: str) -> bytes:
    """Render an outcome donut (Home/Draw/Away %) as PNG bytes."""
    vals = [pred["prob_home"], pred["prob_draw"], pred["prob_away"]]
    labels = [f"{home} win", "Draw", f"{away} win"]
    fig, ax = plt.subplots(figsize=(2.0, 2.0), dpi=150)
    wedges, _ = ax.pie(
        vals, colors=_OUTCOME_COLORS, startangle=90, counterclock=False,
        wedgeprops={"width": 0.42, "edgecolor": "white", "linewidth": 1.5},
    )
    # percentage labels just outside each wedge
    for w, v, lab in zip(wedges, vals, labels):
        if v < 0.04:
            continue
        ang = (w.theta2 + w.theta1) / 2.0
        import math
        x = math.cos(math.radians(ang))
        y = math.sin(math.radians(ang))
        ax.annotate(
            f"{lab}\n{v*100:.0f}%", xy=(x * 0.8, y * 0.8),
            xytext=(x * 1.15, y * 1.15), ha="center", va="center", fontsize=7,
            color="#222",
        )
    ax.set(aspect="equal")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", transparent=True)
    plt.close(fig)
    return buf.getvalue()


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

    # blocks are tall (table + donut + per-model scorelines); ~2 per page
    if pdf.get_y() > 180:
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

    sources = _ordered_sources(mp)
    ens = mp.get("ensemble") or (sources[0][1] if sources else None)

    # --- probability table (left) + outcome donut (right), same band ---
    y0 = pdf.get_y()
    if ens:
        try:
            pdf.image(io.BytesIO(_donut_png(ens, home, away)), x=152, y=y0, w=46)
            pdf.set_xy(pdf.l_margin, y0)
        except Exception:  # never let a chart failure break the report
            pdf.set_xy(pdf.l_margin, y0)

    pdf.set_font("helvetica", "B", 8)
    widths = [40, 16, 16, 16, 22, 18]
    headers = ["Model", "Home", "Draw", "Away", "Preferred", "Score"]
    pdf.set_fill_color(245, 245, 245)
    for w, htext in zip(widths, headers):
        pdf.cell(w, 6, htext, border=1, align="C", fill=True)
    pdf.ln()
    for sid, p in sources:
        pdf.set_x(pdf.l_margin)
        pdf.set_font("helvetica", "B" if sid == "ensemble" else "", 8)
        row = [
            _SOURCE_LABELS.get(sid, sid),
            f"{p['prob_home']*100:.0f}%",
            f"{p['prob_draw']*100:.0f}%",
            f"{p['prob_away']*100:.0f}%",
            _OUTCOME_WORD.get(p["recommended_outcome"], p["recommended_outcome"]),
            p["recommended_score"],
        ]
        for w, val in zip(widths, row):
            pdf.cell(w, 6, _safe(val), border=1, align="C")
        pdf.ln()

    # drop below whichever is taller: the table or the donut
    pdf.set_y(max(pdf.get_y(), y0 + 48))

    # --- top 5 scorelines per model ---
    pdf.set_font("helvetica", "B", 8)
    pdf.cell(0, 5, "Top 5 scorelines per model", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 8)
    for sid, p in sources:
        tops = p.get("top_scorelines", [])[:5]
        if not tops:
            continue
        scores = ", ".join(f"{t['score']} ({t['prob']*100:.0f}%)" for t in tops)
        label = _SOURCE_LABELS.get(sid, sid)
        pdf.set_font("helvetica", "B", 8)
        pdf.cell(30, 5, _safe(label))
        pdf.set_font("helvetica", "", 8)
        pdf.multi_cell(0, 5, _safe(scores), new_x="LMARGIN", new_y="NEXT")

    agg = mp.get("models", {}).get("aggressive", {}).get("metrics", {})
    if agg:
        pdf.set_font("helvetica", "", 8)
        txt = (f"Aggressive blowout: P(win by 2+)={agg.get('p_favourite_win_by_2plus',0)*100:.0f}%  "
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
