"""
Public web UI for the resume scorer.

A polished, deploy-ready Streamlit front end over the open-source hiring-agent
scoring engine. Upload a resume PDF and get an instant, explainable score with the
exact fixes to rank higher. Built for public hosting:

- Privacy: the PDF is processed in a temp file and deleted; nothing is persisted
  (DEVELOPMENT_MODE defaults to off, so no on-disk cache or PII CSV is written).
- Cost control: a per-session score cap, plus a friendly message when the
  (budget-limited) API key hits its ceiling.

Scoring engine: https://github.com/interviewstreet/hiring-agent (MIT).
"""

import os
import io
import csv
import json
import html
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

PROJECT_DIR = Path(__file__).resolve().parent
os.chdir(PROJECT_DIR)

from dotenv import load_dotenv

load_dotenv(PROJECT_DIR / ".env")

from storage import save_submission, is_configured

PRODUCT_NAME = "ResumeRadar"
MAX_SCORES_PER_SESSION = 2
REPO_URL = "https://github.com/interviewstreet/hiring-agent"
# Email shown in the privacy note for data-deletion requests.
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "abhijeetguptaphd@gmail.com")

# --- Category metadata: key -> (icon, label, max, "how to score higher") -------
CATEGORY_META = {
    "open_source": (
        "🌐",
        "Open Source",
        35,
        "Counts contributions to OTHER people's projects — not your own repos. "
        "25–35 needs major/popular-project contributions or GSoC; personal repos "
        "alone are capped at ~10 points.",
    ),
    "self_projects": (
        "🚀",
        "Self Projects",
        30,
        "Rewards complex, real-world projects with working links / live demos. "
        "Tutorial, CRUD, todo/weather apps, or projects with no link score low "
        "and trigger deductions.",
    ),
    "production": (
        "🏢",
        "Production Experience",
        25,
        "Internships, jobs and production-grade work. Founder / co-founder and "
        "early-startup-engineer roles earn extra credit.",
    ),
    "technical_skills": (
        "💻",
        "Technical Skills",
        10,
        "Breadth and depth of languages & tools — backed by evidence in your "
        "projects, work and competitions.",
    ),
}

esc = html.escape


# ------------------------------------------------------------------ helpers ----
def compute_overall(evaluation):
    total_score = 0.0
    max_score = 0
    for _, cat in evaluation.scores.model_dump().items():
        total_score += min(cat["score"], cat["max"])
        max_score += cat["max"]
    if evaluation.bonus_points:
        total_score += evaluation.bonus_points.total
    if evaluation.deductions:
        total_score -= evaluation.deductions.total
    total_score = min(total_score, max_score + 20)
    return total_score, max_score


def bar_color(pct: float) -> str:
    if pct >= 0.7:
        return "#22c55e"
    if pct >= 0.4:
        return "#f59e0b"
    return "#ef4444"


def overall_band(total: float):
    if total >= 75:
        return "Excellent", "#22c55e"
    if total >= 55:
        return "Strong", "#14b8a6"
    if total >= 40:
        return "Moderate", "#f59e0b"
    return "Needs work", "#ef4444"


def account_age(created_at: str) -> str:
    try:
        d = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        years = (datetime.now(timezone.utc) - d).days / 365.25
        return f"{years:.1f} yr" + ("s" if years >= 2 else "")
    except Exception:
        return "—"


def donut_svg(value: float, maxv: int, band_color: str) -> str:
    import math

    pct = max(min(value / maxv, 1.0), 0.0) if maxv else 0.0
    size, r, sw = 200, 78, 18
    cx = cy = size / 2
    circ = 2 * math.pi * r
    dash = pct * circ
    return f"""
    <svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">
      <circle cx="{cx}" cy="{cy}" r="{r}" stroke="#262d3d" stroke-width="{sw}" fill="none"/>
      <circle cx="{cx}" cy="{cy}" r="{r}" stroke="{band_color}" stroke-width="{sw}"
              fill="none" stroke-linecap="round" stroke-dasharray="{dash:.1f} {circ:.1f}"
              transform="rotate(-90 {cx} {cy})"/>
      <text x="{cx}" y="{cy-4}" text-anchor="middle" font-size="46" font-weight="800"
            fill="#E6E9EF">{value:.0f}</text>
      <text x="{cx}" y="{cy+26}" text-anchor="middle" font-size="15"
            fill="#9aa3b2">/ {maxv}</text>
    </svg>
    """


# ------------------------------------------------------------------ page -------
st.set_page_config(
    page_title=f"{PRODUCT_NAME} — Resume Scorer",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
/* hide Streamlit chrome for a clean product look */
#MainMenu, header[data-testid="stHeader"], footer,
[data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"], .stDeployButton { display:none !important; }
.block-container { padding-top: 1.6rem; max-width: 1080px; }

.ha-brand { font-size:.95rem; font-weight:800; letter-spacing:.04em; color:#9d8bff;
            text-transform:uppercase; }
.ha-hero h1 { font-size: 2.35rem; font-weight: 800; margin:.35rem 0 .35rem; line-height:1.12; }
.ha-sub { color:#aab2c0; font-size:1.02rem; max-width:680px; line-height:1.55; }
.ha-trust { color:#6b7384; font-size:.85rem; margin-top:.5rem; }
.ha-card { background:#161b26; border:1px solid #232a39; border-radius:16px;
           padding:18px 20px; margin-bottom:14px; }
.ha-pill { display:inline-block; padding:3px 10px; border-radius:999px;
           font-size:.72rem; font-weight:700; letter-spacing:.02em; }
.ha-sec { font-size:1.18rem; font-weight:750; margin:14px 0 6px; }
.ha-cat-head { display:flex; justify-content:space-between; align-items:baseline; }
.ha-cat-name { font-size:1.02rem; font-weight:700; }
.ha-cat-score { font-size:1.0rem; font-weight:800; }
.ha-track { background:#262d3d; border-radius:999px; height:11px; margin:9px 0 10px; overflow:hidden; }
.ha-fill { height:11px; border-radius:999px; }
.ha-ev { color:#c5ccd9; font-size:.9rem; line-height:1.5; }
.ha-tip { color:#8b93a4; font-size:.83rem; margin-top:8px; border-left:2px solid #3a4256; padding-left:10px; }
.ha-tip b { color:#b9a7ff; }
.ha-good { background:#0f1f17; border:1px solid #1d4732; border-radius:16px; padding:16px 18px; }
.ha-bad  { background:#211314; border:1px solid #4a2326; border-radius:16px; padding:16px 18px; }
.ha-good h4, .ha-bad h4 { margin:0 0 8px; font-size:1.02rem; }
.ha-good ul, .ha-bad ul { margin:.2rem 0 0 1rem; padding:0; }
.ha-good li, .ha-bad li { margin:5px 0; font-size:.9rem; color:#d4dae5; }
.ha-gh-stat { text-align:center; }
.ha-gh-stat .v { font-size:1.35rem; font-weight:800; }
.ha-gh-stat .l { font-size:.74rem; color:#9aa3b2; text-transform:uppercase; letter-spacing:.04em; }
.ha-proj { background:#11151e; border:1px solid #232a39; border-radius:12px; padding:12px 14px; margin-bottom:9px; }
.ha-proj .nm { font-weight:700; font-size:.97rem; }
.ha-proj .meta { color:#9aa3b2; font-size:.82rem; margin-top:4px; }
.ha-badge-os { background:#14321f; color:#5ee08a; }
.ha-badge-self { background:#2a2440; color:#b9a7ff; }
.ha-math { color:#aab2c0; font-size:.92rem; }
.ha-math b { color:#E6E9EF; }
.ha-footer { color:#6b7384; font-size:.83rem; text-align:center; margin:2.4rem 0 1rem;
             border-top:1px solid #232a39; padding-top:1.1rem; line-height:1.6; }
a { color:#9d8bff !important; }
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    f"""
<div class="ha-hero">
  <div class="ha-brand">⚡ {PRODUCT_NAME}</div>
  <h1>How strong is your resume, really?</h1>
  <div class="ha-sub">Upload your resume and get an instant, explainable score across open
  source, projects, production experience and skills — plus the exact fixes to rank higher.</div>
  <div class="ha-trust">Free · no signup · results in ~60s</div>
</div>
""",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown(f"### ⚡ {PRODUCT_NAME}")
    with st.expander("📐 How scoring works", expanded=True):
        st.markdown(
            "**100 base points + up to 20 bonus, minus deductions.**\n\n"
            "- 🌐 **Open Source — 35**: contributions to *others'* repos\n"
            "- 🚀 **Self Projects — 30**: complex projects w/ live links\n"
            "- 🏢 **Production — 25**: internships, jobs, founder roles\n"
            "- 💻 **Technical Skills — 10**: breadth & depth of stack\n\n"
            "**Bonus:** GSoC +5, founder +3–5, portfolio +2, LinkedIn +1."
        )
    st.caption(f"Engine: [hiring-agent]({REPO_URL}) (MIT)")


# ----------------------------------------------------------- result rendering --
def render_results(result: dict):
    evaluation = result["evaluation"]
    resume = result.get("resume") or {}
    github = result.get("github") or {}
    name = result.get("name") or "Candidate"

    total, max_score = compute_overall(evaluation)
    band_label, band_col = overall_band(total)
    cats = evaluation.scores

    st.subheader(f"Results for: {name}")

    gaps = []
    for key, (icon, label, cap, _) in CATEGORY_META.items():
        c = getattr(cats, key, None)
        if c:
            shown = min(c.score, cap)
            gaps.append((cap - shown, icon, label, shown, cap))
    biggest = max(gaps, key=lambda x: x[0]) if gaps else None
    best = min(gaps, key=lambda x: (x[4] - x[3]) / x[4] if x[4] else 1) if gaps else None

    bonus_total = evaluation.bonus_points.total if evaluation.bonus_points else 0
    ded_total = evaluation.deductions.total if evaluation.deductions else 0

    hcol1, hcol2 = st.columns([1, 1.7])
    with hcol1:
        st.markdown(donut_svg(total, max_score, band_col), unsafe_allow_html=True)
    with hcol2:
        st.markdown(
            f"""
<div class="ha-card" style="height:100%;">
  <span class="ha-pill" style="background:{band_col}22;color:{band_col};">{band_label.upper()}</span>
  <div class="ha-math" style="margin-top:12px;line-height:1.9;">
    Category points: <b>{total - bonus_total + ded_total:.0f}</b> / {max_score}<br>
    Bonus: <b style="color:#22c55e;">+{bonus_total:.0f}</b>
    &nbsp;·&nbsp; Deductions: <b style="color:#ef4444;">−{ded_total:.0f}</b><br>
    <span style="font-size:1.05rem;">Final: <b style="color:{band_col};">{total:.0f} / {max_score}</b></span>
  </div>
  {"<div class='ha-math' style='margin-top:10px;'>📉 Biggest opportunity: <b>" + esc(biggest[1] + ' ' + biggest[2]) + f"</b> — up to <b style='color:#f59e0b;'>+{biggest[0]:.0f}</b> more</div>" if biggest and biggest[0] > 0 else ""}
  {"<div class='ha-math' style='margin-top:4px;'>💪 Strongest area: <b>" + esc(best[1] + ' ' + best[2]) + f"</b> ({best[3]:.0f}/{best[4]})</div>" if best else ""}
</div>
""",
            unsafe_allow_html=True,
        )

    st.markdown('<div class="ha-sec">📈 Category breakdown — where the points come from</div>', unsafe_allow_html=True)
    for key, (icon, label, cap, tip) in CATEGORY_META.items():
        c = getattr(cats, key, None)
        if not c:
            continue
        shown = min(c.score, cap)
        pct = (shown / cap) if cap else 0
        col = bar_color(pct)
        st.markdown(
            f"""
<div class="ha-card">
  <div class="ha-cat-head">
    <span class="ha-cat-name">{icon} {label}</span>
    <span class="ha-cat-score" style="color:{col};">{shown:g} / {cap}</span>
  </div>
  <div class="ha-track"><div class="ha-fill" style="width:{pct*100:.0f}%;background:{col};"></div></div>
  <div class="ha-ev">{esc(c.evidence)}</div>
  <div class="ha-tip">💡 <b>How to score higher:</b> {esc(tip)}</div>
</div>
""",
            unsafe_allow_html=True,
        )

    st.markdown('<div class="ha-sec">⚖️ What\'s helping vs. hurting your score</div>', unsafe_allow_html=True)
    g, b = st.columns(2)
    with g:
        bonus = evaluation.bonus_points
        strengths = "".join(f"<li>{esc(s)}</li>" for s in (evaluation.key_strengths or []))
        bonus_line = (
            f"<div class='ha-ev' style='margin:2px 0 8px;'>⭐ <b>Bonus +{bonus.total:g}</b> — {esc(bonus.breakdown)}</div>"
            if bonus and bonus.total
            else ""
        )
        st.markdown(
            f"""<div class="ha-good"><h4 style="color:#5ee08a;">✅ Helping</h4>{bonus_line}<ul>{strengths}</ul></div>""",
            unsafe_allow_html=True,
        )
    with b:
        ded = evaluation.deductions
        improvements = "".join(f"<li>{esc(s)}</li>" for s in (evaluation.areas_for_improvement or []))
        ded_line = (
            f"<div class='ha-ev' style='margin:2px 0 8px;'>⚠️ <b style='color:#ff8a8a;'>Deductions −{ded.total:g}</b> — {esc(ded.reasons)}</div>"
            if ded and ded.total
            else ""
        )
        st.markdown(
            f"""<div class="ha-bad"><h4 style="color:#ff8a8a;">🔧 Hurting / to improve</h4>{ded_line}<ul>{improvements}</ul></div>""",
            unsafe_allow_html=True,
        )

    # --- GitHub signals ---
    profile = github.get("profile") or {}
    projects = github.get("projects") or []
    st.markdown('<div class="ha-sec">🐙 GitHub signals the agent used</div>', unsafe_allow_html=True)
    if not profile and not projects:
        gh_url = ""
        for p in (resume.get("basics") or {}).get("profiles") or []:
            if (p.get("network") or "").lower() == "github":
                gh_url = p.get("url", "")
        st.warning(
            "No GitHub data was fetched — "
            + (
                f"the profile link on the resume (`{gh_url}`) couldn't be reached. "
                if gh_url
                else "no GitHub profile was found on the resume. "
            )
            + "Open Source is 35% of the score, so a working GitHub link matters a lot."
        )
    else:
        if profile:
            pc1, pc2 = st.columns([1, 3])
            with pc1:
                if profile.get("avatar_url"):
                    st.image(profile["avatar_url"], width=110)
            with pc2:
                stats = [
                    ("Repos", profile.get("public_repos", "—")),
                    ("Followers", profile.get("followers", "—")),
                    ("Following", profile.get("following", "—")),
                    ("Account age", account_age(profile.get("created_at", ""))),
                ]
                cells = "".join(
                    f"<div class='ha-gh-stat'><div class='v'>{esc(str(v))}</div><div class='l'>{l}</div></div>"
                    for l, v in stats
                )
                st.markdown(
                    f"""<div class="ha-card">
                    <div style="font-weight:700;font-size:1.05rem;">@{esc(profile.get('username') or '')}</div>
                    <div class="ha-ev" style="margin:4px 0 12px;">{esc(profile.get('bio') or '')}</div>
                    <div style="display:flex;gap:26px;">{cells}</div></div>""",
                    unsafe_allow_html=True,
                )
        if projects:
            os_n = sum(1 for p in projects if p.get("project_type") == "open_source")
            st.markdown(
                f"<div class='ha-ev' style='margin:2px 0 8px;'>Top <b>{len(projects)}</b> "
                f"repos the agent selected · <b>{os_n}</b> open-source, "
                f"<b>{len(projects)-os_n}</b> self-projects:</div>",
                unsafe_allow_html=True,
            )
            for p in projects:
                d = p.get("github_details") or {}
                is_os = p.get("project_type") == "open_source"
                badge_cls = "ha-badge-os" if is_os else "ha-badge-self"
                badge_txt = "open source" if is_os else "self project"
                lang = d.get("language") or (p.get("technologies") or [None])[0] or "—"
                live = p.get("live_url")
                live_html = f" · <a href='{esc(live)}' target='_blank'>live demo ↗</a>" if live else ""
                st.markdown(
                    f"""<div class="ha-proj">
                    <div class="nm"><a href="{esc(p.get('github_url') or '#')}" target="_blank">{esc(p.get('name') or 'repo')} ↗</a>
                      <span class="ha-pill {badge_cls}" style="margin-left:8px;">{badge_txt}</span></div>
                    <div class="ha-ev" style="margin-top:3px;">{esc((p.get('description') or '')[:140])}</div>
                    <div class="meta">⭐ {d.get('stars', 0)} &nbsp;·&nbsp; 🛠 {esc(str(lang))} &nbsp;·&nbsp;
                      commits: you {p.get('author_commit_count', 0)} / {p.get('total_commit_count', 0)} total{live_html}</div></div>""",
                    unsafe_allow_html=True,
                )

    # --- parsed resume ---
    with st.expander("📋 What the agent extracted from your resume"):
        rc1, rc2 = st.columns(2)
        work = resume.get("work") or []
        edu = resume.get("education") or []
        skills = resume.get("skills") or []
        projs = resume.get("projects") or []
        with rc1:
            st.markdown(f"**💼 Work ({len(work)})**")
            for w in work[:8]:
                st.markdown(f"- {esc(str(w.get('position') or '—'))} @ {esc(str(w.get('name') or '—'))}")
            st.markdown(f"**🎓 Education ({len(edu)})**")
            for e in edu[:6]:
                st.markdown(f"- {esc(str(e.get('studyType') or ''))} {esc(str(e.get('area') or ''))} — {esc(str(e.get('institution') or '—'))}")
        with rc2:
            st.markdown(f"**🧩 Projects ({len(projs)})**")
            for p in projs[:8]:
                st.markdown(f"- {esc(str(p.get('name') or '—'))}")
            flat_skills = []
            for s in skills:
                if s.get("name"):
                    flat_skills.append(s["name"])
                flat_skills.extend(s.get("keywords") or [])
            st.markdown(f"**🛠 Skills ({len(flat_skills)})**")
            st.markdown(esc(", ".join(flat_skills[:40])) or "—")

    # --- export ---
    st.markdown('<div class="ha-sec">⬇️ Export</div>', unsafe_allow_html=True)
    safe_name = (name or "resume").replace(" ", "_")
    dl1, dl2 = st.columns(2)
    with dl1:
        st.download_button(
            "Download full evaluation (JSON)",
            data=json.dumps(evaluation.model_dump(), indent=2),
            file_name=f"{safe_name}_evaluation.json",
            mime="application/json",
        )
    with dl2:
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["candidate", "overall", "max", *CATEGORY_META.keys(), "bonus", "deductions"])
        w.writerow(
            [
                name,
                f"{total:.1f}",
                max_score,
                *[f"{min(getattr(cats, k).score, m):g}/{m}" for k, (_, _, m, _) in CATEGORY_META.items()],
                bonus_total,
                ded_total,
            ]
        )
        st.download_button(
            "Download scorecard (CSV)",
            data=buf.getvalue(),
            file_name=f"{safe_name}_scorecard.csv",
            mime="text/csv",
        )


# ------------------------------------------------------------------ flow -------
if "scores_done" not in st.session_state:
    st.session_state.scores_done = 0

uploaded = st.file_uploader("Resume PDF", type=["pdf"], accept_multiple_files=False)

with st.expander("🔒 Privacy"):
    st.markdown(
        f"""
We process your resume in memory to generate your score. We store **only your name and
email address** (read from your resume) so we know who's using {PRODUCT_NAME} — nothing
else, no resume content. We do **not** sell your data. Email **{CONTACT_EMAIL}** to have
it removed.

Engine: the open-source [hiring-agent]({REPO_URL}) project (MIT).
"""
    )

remaining = MAX_SCORES_PER_SESSION - st.session_state.scores_done
run = st.button(
    "⚡ Score my resume",
    type="primary",
    disabled=uploaded is None or remaining <= 0,
)
st.caption(
    f"Free scores remaining this session: {max(remaining, 0)} of {MAX_SCORES_PER_SESSION}  ·  "
    "by scoring, you agree we store your name & email (see Privacy)"
)

if run and uploaded is not None:
    if st.session_state.scores_done >= MAX_SCORES_PER_SESSION:
        st.warning("You've used all free scores for this session. Refresh the page to start a new one.")
    else:
        # Write to a temp file, score, then delete — nothing persists on disk.
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        result = None
        error_shown = False
        try:
            tmp.write(uploaded.getvalue())
            tmp.flush()
            tmp.close()
            from score import main as run_scoring

            with st.spinner("Parsing PDF, fetching GitHub signals, and evaluating… ~30–60s."):
                result = run_scoring(tmp.name)
        except Exception as e:
            error_shown = True
            msg = str(e).lower()
            if any(t in msg for t in ("402", "payment", "insufficient", "quota", "credit")):
                st.error("⚠️ We've hit today's scoring limit. Please check back soon — thanks for your patience!")
            else:
                st.error(f"Scoring failed: {e}")
        finally:
            try:
                os.unlink(tmp.name)
            except Exception:
                pass

        if not error_shown:
            if not result or result.get("evaluation") is None:
                st.error(
                    "Couldn't parse that PDF into a resume. Try a text-based "
                    "(non-scanned) PDF."
                )
            else:
                ev = result["evaluation"]
                rd = result.get("resume_data")
                gh = result.get("github_data") or {}
                basics = rd.basics if rd else None
                name = basics.name if (basics and basics.name) else "Candidate"
                st.session_state.result = {
                    "evaluation": ev,
                    "resume": rd.model_dump() if rd else {},
                    "github": gh,
                    "name": name,
                }
                st.session_state.scores_done += 1
                st.success("Evaluation complete.")

                # Store name + email from every scan (requires a storage backend via
                # SUPABASE_URL / SUPABASE_KEY). Collection is disclosed in the UI.
                if is_configured():
                    save_submission(
                        {
                            "name": name,
                            "email": getattr(basics, "email", None),
                        }
                    )

if st.session_state.get("result"):
    render_results(st.session_state.result)
elif uploaded is None:
    st.info("⬆️ Upload a resume PDF to get your score.")

st.markdown(
    f"""
<div class="ha-footer">
  Scoring engine powered by the open-source
  <a href="{REPO_URL}" target="_blank">hiring-agent</a> project (MIT) by HackerRank.<br>
  Your resume is processed in memory. We save <b>only your name & email</b> (from your resume). See Privacy.
</div>
""",
    unsafe_allow_html=True,
)
