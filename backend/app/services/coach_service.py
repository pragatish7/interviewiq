"""
AI Coach conversation service.

A deterministic, fully-local conversation engine that makes the coach feel
like a human mentor:

- intent rules detect what the user needs (vent / anxiety / answer help /
  practice / harder question / clarify / explain simply / weak topic...)
- the full conversation history is re-read every turn, so context, follow-ups
  and callbacks ("that question", "the thing you said") work naturally
- practice mode: the coach asks a dataset question, the user answers, the
  EXISTING live-eval engine (TF-IDF semantics, concept coverage, structure,
  filler words, pace) + the trained ML model score the answer, and the coach
  gives honest human feedback instead of the raw rubric output
- mock-interview mode: a multi-question interview run inside the chat
- analysis context: completed video-interview and live-interview results are
  turned into short coach briefing lines and used to guide advice

No external AI API is used — everything runs locally alongside the existing
analysis infrastructure.
"""
import re
import logging
import random
from typing import Dict, Any, List, Optional, Tuple

from app.services import live_dataset_service as ds
from app.services import live_eval_service as ev
from app.ml import live_bridge

logger = logging.getLogger(__name__)

MAX_TURNS = 30  # messages of history kept in the model context

# ---------------------------------------------------------------------------
# Style directives extracted from a user message ("answer in bullet points",
# "keep it short", "explain in simpler words"...)
# ---------------------------------------------------------------------------

STYLE_RULES: List[Tuple[str, str]] = [
    (r"\b(bullet\s*points?|as\s+a\s+list|make\s+a\s+list|list\s*form)\b", "bullets"),
    (r"\b(keep\s*it\s*short|be\s+brief|shorter|one\s*line|tldr|tl;dr)\b", "short"),
    (r"\b(in\s*(more|a\s*lot\s*of)?\s*detail|go\s+deeper|elaborate|expand)\b", "detail"),
    (r"\b(simpl(er|ify)|simpler\s*words|explain\s*like|eli5|dumb\s*it\s*down)\b", "simple"),
    (r"\b(strict(er)?|harsh(er)?|brutal(ly)?\s*honest|no\s*sugarcoating|don'?t\s*go\s*easy)\b", "strict"),
    (r"\b(be\s*nice|go\s*easy|gentle|encourage\s*me)\b", "warm"),
]

MOOD_RULES: List[Tuple[str, str]] = [
    (r"\b(nervous|anxious|scared|afraid|freaking\s*out|panic|panicking)\b", "nervous"),
    (r"\b(failed|flunked|messed\s*up|blew\s*it|bombed|rejected|screwed\s*up)\b", "dejected"),
    (r"\b(stuck|confused|lost|no\s*idea|don'?t\s*know\s*(what|how)|overwhelmed)\b", "stuck"),
    (r"\b(excited|got\s*(the|an)\s*interview|landed|shortlisted|selected|call(ed)?\s*back)\b", "excited"),
]

FILLER_HINT = re.compile(r"\b(um+|uh+|like|basically|actually|you\s*know|i\s*mean|so\s*,)\b", re.I)

HISTORY_CALLBACK = re.compile(
    r"\b(that|this|it|the)\s+(question|answer|topic|one|point|issue|thing)\b", re.I
)


def _rand(rng: random.Random, seq: List[str]) -> str:
    return rng.choice(seq)


# ---------------------------------------------------------------------------
# Knowledge: how the coach explains interview topics
# ---------------------------------------------------------------------------

TOPIC_GUIDES: Dict[str, Dict[str, Any]] = {
    "tell me about yourself": {
        "keys": [r"tell\s*me\s*about\s*yourself", r"introduce\s*yourself", r"walk\s*me\s*through\s*your\s*(resume|profile)"],
        "advice": (
            "Here's the version that actually works — a 60–90 second story with four beats:\n"
            "1) **Present** — one line on what you do right now: \"I'm a final-year CS student focused on backend development.\"\n"
            "2) **Proof** — your strongest 1–2 things: a project, internship, or skill with a number attached (\"built a REST API that handles X\").\n"
            "3) **Why this role** — connect your skills to THIS job: \"that's exactly the stack your posting mentions.\"\n"
            "4) **Handoff** — end by passing it back: \"...which is why I'm excited about this role.\"\n"
            "The trap most people fall into: reciting their resume cover-to-cover or starting with \"I was born in...\". Nobody hired anyone for their birthplace."
        ),
        "followup": "Want to draft your version now? Just tell me your current role or field of study and one project you're proud of — rough words are fine, we'll shape it together.",
    },
    "weakness": {
        "keys": [r"weakness(es)?", r"greatest\s*weakness"],
        "advice": (
            "The weakness question isn't a confession booth — it's a self-awareness test. Structure that scores:\n"
            "1) A **real** weakness (not \"I'm a perfectionist\" — interviewers hear that 50 times a week).\n"
            "2) **Concrete**, not character-level: \"I used to avoid delegating\" beats \"I'm impatient\".\n"
            "3) **What you did about it** — the fix, in action terms.\n"
            "4) **Evidence it's working** — a small, believable result.\n"
            "One safe template: \"I used to [real thing] → so I started [specific fix] → now [small proof it's improving].\" Honest, short, done."
        ),
        "followup": "If you want, tell me a weakness you've actually noticed in yourself (speaking too fast, overthinking, public speaking...) and I'll help you package it properly.",
    },
    "strengths": {
        "keys": [r"strength(s)?", r"why\s*should\s*we\s*hire\s*you", r"what\s*makes\s*you\s*(a\s*)?(good\s*fit|unique|different)"],
        "advice": (
            "Strengths only land when they're **claimed + proven**. Formula: \"I'm strong at X — for example, [specific situation where you did X, with a result].\" "
            "Pick strengths the job posting actually asks for, and never say \"I'm a hard worker\" without a story behind it. Anyone can claim it; stories make it true."
        ),
        "followup": "Tell me the role you're targeting and I'll help you pick the two strengths worth leading with.",
    },
    "going blank": {
        "keys": [r"forget(ting)?\s*(what|it|my|everything)", r"go(es)?\s*blank", r"(my\s*)?mind\s*(goes|went)\s*(blank|empty)",
                 r"lose\s*(my\s*)?(train|track)", r"halfway\s*through", r"forget(ting)?\s*(my\s*)?(point|answer|words|line)"],
        "advice": (
            "Going blank halfway through is a memory problem, not a knowledge problem — and it has a precise fix.\n"
            "It happens because you're rehearsing a SCRIPT (word-for-word sentences), and scripts collapse the moment "
            "you lose one word. Coaches train POINTS, not scripts:\n"
            "• Boil each answer down to 3 bullet beats — situation, what you did, result. Say them in whatever words come out that day.\n"
            "• Keep a signpost phrase ready for the wobble: \"Let me put that in order…\" — it buys 3 seconds and sounds composed, not lost.\n"
            "• Rehearse the same answer 3 times with different wording each time. If you can only say it one way, you've memorized a script.\n"
            "• Slow down when it happens. Blanks feed on speed; a pause starves them."
        ),
        "followup": "Want to train it right now? Say \"ask me a question\" and we'll practice until points flow instead of scripts.",
    },
    "nervous": {
        "keys": [r"nervous", r"anxious", r"scared", r"panic", r"freak(ing)?\s*out", r"stage\s*fright"],
        "advice": (
            "Nerves before an interview are normal — even the interviewer had them once. What actually helps:\n"
            "• **Rehearse the first 60 seconds cold.** Most jitters live in the opening; once it's smooth, the rest follows.\n"
            "• **Breathe 4-in, 6-out** a few times right before you join. Slower exhale slows the heart.\n"
            "• **Reframe it:** you're not on trial — you're two people checking if the work fits. They WANTS you to be good.\n"
            "• Prepare two or three stories you know by heart — certainty calms nerves."
        ),
        "followup": "Want to burn the nerves off with practice? Say \"ask me something\" and we'll do a low-stakes round right now.",
    },
    "filler": {
        "keys": [r"filler", r"\bum+\s*(words)?", r"\buh+\b", r"saying\s*like\s*too\s*much", r"stop\s*saying"],
        "advice": (
            "Filler words are almost never a vocabulary problem — they're a **silence problem**. Your brain fills pauses with \"um\" because silence feels dangerous. It isn't.\n"
            "The fix that works:\n"
            "1) **Pause + breathe instead of filling.** A silent pause sounds thoughtful; \"um\" sounds unsure.\n"
            "2) **Slow down ~10%.** Fillers spike when your mouth outruns your brain.\n"
            "3) **Record yourself once** answering one question — you'll spot your personal filler instantly (it's usually one or two words, not twenty).\n"
            "Best part: this improves in about a week of deliberate practice."
        ),
        "followup": "Let's test it live — say \"ask me a question\" and answer slowly, consciously swapping fillers for pauses. I'll count them for you.",
    },
    "pace": {
        "keys": [r"(speak|talking|talk)\w*\s*(too\s*)?fast", r"too\s*fast", r"slow\s*down", r"(speak|talk)\w*\s*(too\s*)?slow", r"too\s*slow"],
        "advice": (
            "Speaking too fast usually happens when you're reciting instead of explaining — your brain plays the tape at double speed.\n"
            "What fixes it:\n"
            "• **Break answers into points** and put a real breath between them. The pause IS the pacing.\n"
            "• **Anchor sentences:** land the first and last word of each sentence deliberately.\n"
            "• Aim for roughly 120–160 words per minute — conversational, not lecture speed.\n"
            "• Practice explaining one concept out loud to a wall daily; walls don't rush you."
        ),
        "followup": "Want to practice one right now? Say \"ask me a technical question\" and I'll watch your pacing with you.",
    },
    "project": {
        "keys": [r"(my|the|our)\s*(project|projects)", r"explain\s*my\s*project", r"final\s*(year\s*)?project", r"resume\s*project"],
        "advice": (
            "Projects impress when they follow **PSR**: Problem → Solution → Result.\n"
            "• Problem: one sentence on what sucked before it existed.\n"
            "• Solution: what YOU built and why that approach — mention the hard part, that's where skill shows.\n"
            "• Result: a number, a user, a demo, a lesson. \"It works\" is not a result; \"it cut load time 40%\" is.\n"
            "Then prepare for the two follow-ups that always come: **\"what would you improve?\"** (have a real answer — it shows growth) and **\"why X and not Y?\"** (your tech-choice defense)."
        ),
        "followup": "Tell me about your project in plain words — messy is fine — and I'll help you tighten it into that shape.",
    },
    "star": {
        "keys": [r"\bstar\b", r"situation\s*task\s*action", r"behavioral", r"behavioural"],
        "advice": (
            "Behavioral questions score with STAR: **Situation** (one sentence of context) → **Task** (what you were responsible for) → **Action** (what YOU did — 60% of the answer) → **Result** (what changed, ideally with a number).\n"
            "The common failure: spending 80% on the situation and racing through the result. Interviewers hire the Action and the Result.\n"
            "Prepare 4–5 stories from college/projects/internships that flex — one conflict, one failure, one leadership, one deadline, one technical win. Those five cover almost every behavioral question they'll throw."
        ),
        "followup": "Want to try one? Say \"give me a behavioral question\" and I'll score your STAR structure.",
    },
    "salary": {
        "keys": [r"salary", r"ctc", r"pay\s*expect", r"compensation", r"package"],
        "advice": (
            "Salary talk, cleanly handled: research the market band first (levels-style sites, peers, the role's level), then give a **range** whose bottom you'd genuinely accept, and tie it to the role: \"Based on the market for this role and my experience, I'm looking at X–Y.\"\n"
            "If they push before you're ready: \"I'd like to learn more about the role first — could you share the budgeted range?\" That's confident, not evasive. Never apologize for the number and never give one you'd resent."
        ),
        "followup": None,
    },
    "company research": {
        "keys": [r"research\s*(the\s*)?company", r"know\s*about\s*the\s*company", r"why\s*(do\s*you\s*want\s*to\s*work|this\s*company|us)\b", r"our\s*company"],
        "advice": (
            "For \"why this company\", the winning shape is: **their** thing + **your** thing = fit. "
            "Two minutes of research: what they build, who they serve, one recent launch or value that resonates. Then connect it to you: \"you ship X, I've spent the last year on exactly X — here's proof.\" "
            "Generic praise (\"you're an industry leader\") reads as copy-paste; specificity reads as interest."
        ),
        "followup": None,
    },
    "resume": {
        "keys": [r"resume", r"\bcv\b"],
        "advice": (
            "Resume rules that matter: one page (unless 10+ years), results not duties (\"built X → reduced Y by Z%\"), tailored keywords per posting because the first filter is a machine, "
            "and every line must survive the question \"what did YOU do here?\" Cut courses-by-name, photo, and 'references available'. Your project bullets are interview ammo — write them so Future-You can talk about them."
        ),
        "followup": None,
    },
    "online interview": {
        "keys": [r"online\s*interview", r"video\s*(call|interview)", r"zoom|google\s*meet|teams"],
        "advice": (
            "Virtual interviews: camera at eye level, light in FRONT of you (window behind = witness-protection silhouette), look at the lens when making key points, "
            "and kill notifications. Have your resume + the JD open in tabs. Test audio with a friend the night before — tech trouble in minute one is a mood you don't want. "
            "And keep water nearby; dry-mouth is real."
        ),
        "followup": None,
    },
    "group discussion": {
        "keys": [r"group\s*discussion", r"\bgd\b"],
        "advice": (
            "Group discussions reward quality + timing over volume: enter early with one structured point, build on others (\"adding to that...\") rather than attacking, "
            "and if the topic's alien, listen 60 seconds and summarize what you heard — that counts as leadership. Never shout, never monologue past 45 seconds."
        ),
        "followup": None,
    },
    "hr vs technical": {
        "keys": [r"hr\s*(round|interview|questions)", r"technical\s*(round|interview)"],
        "advice": (
            "Different rounds, different games: technical rounds test **reasoning out loud** — narrate your thinking even when unsure, interviewers grade the path, not just the answer. "
            "HR rounds test **consistency and self-knowledge** — know your resume cold, keep answers honest but framed, and never badmouth anyone. The safest HR strategy: specific stories, zero complaints."
        ),
        "followup": None,
    },
}


def _match_topic(text: str) -> Optional[str]:
    t = text.lower()
    for name, spec in TOPIC_GUIDES.items():
        for pat in spec["keys"]:
            if re.search(pat, t):
                return name
    return None


# ---------------------------------------------------------------------------
# Question picking (dataset) — used for practice & mock interviews
# ---------------------------------------------------------------------------

def _pick_question(categories: Optional[List[str]] = None, difficulty: Optional[str] = None,
                   exclude: Optional[List[str]] = None, rng: Optional[random.Random] = None) -> Optional[Dict[str, Any]]:
    pool = ds.load_dataset()
    if not pool:
        return None
    rng = rng or random.Random()
    exclude = set(exclude or [])
    candidates = [q for q in pool
                  if q["question_id"] not in exclude
                  and (not categories or any(c.lower() == q["category"].lower() for c in categories))
                  and (not difficulty or q["difficulty"].lower() == difficulty.lower())]
    if not candidates:
        candidates = [q for q in pool if q["question_id"] not in exclude] or pool
    return rng.choice(candidates)


def _detect_category_pref(text: str) -> Optional[List[str]]:
    """Category mentions in free text: 'java question', 'ask me sql', 'something on networks'."""
    t = text.lower()
    cats = ds.get_categories()
    hits = []
    aliases = {
        "oop": "object-oriented programming", "object oriented": "object-oriented programming",
        "dsa": "data structures & algorithms", "data structures": "data structures & algorithms",
        "networking": "computer networks", "networks": "computer networks",
        "os": "operating systems", "operating system": "operating systems",
        "dbms": "dbms", "database": "dbms", "sql": "sql", "java": "java",
        "python": "python", "c++": "c++", "cpp": "c++", "hr": "hr / behavioral",
        "behavioral": "hr / behavioral", "behavioural": "hr / behavioral",
    }
    for token, cat in aliases.items():
        if re.search(rf"\b{re.escape(token)}\b", t):
            for c in cats:
                if c.lower() == cat:
                    hits.append(c)
    return hits or None


def _difficulty_pref(text: str) -> Optional[str]:
    t = text.lower()
    if re.search(r"\b(hard(er)?|tough|difficult|challenging|advanced)\b", t):
        return "Hard"
    if re.search(r"\b(easy|simple|basic|warm\s*up|starter)\b", t):
        return "Easy"
    if re.search(r"\bmedium|moderate\b", t):
        return "Medium"
    return None


# ---------------------------------------------------------------------------
# Practice & mock-interview evaluation: reuse the EXISTING ML/NLP pipeline
# ---------------------------------------------------------------------------

def evaluate_practice_answer(question: Dict[str, Any], answer: str, duration_s: float = 0.0) -> Dict[str, Any]:
    """Score one practice answer with the existing live-eval engine + ML model."""
    try:
        return ev.evaluate_answer(question=question, candidate_answer=answer, duration_s=duration_s)
    except Exception as e:  # never let a scoring hiccup kill the chat
        logger.warning(f"coach practice evaluation failed: {e}")
        words = len(answer.split())
        est = max(0.0, min(100.0, 40 + words * 1.2))
        return {
            "question_id": question.get("question_id", ""), "question": question.get("question", ""),
            "category": question.get("category", ""), "difficulty": question.get("difficulty", ""),
            "candidate_answer": answer, "expected_answer": question.get("expected_answer", ""),
            "answer_score": est, "answer_score_10": est / 10, "grade_label": "Average",
            "semantic_similarity": 0.0, "concept_coverage": 0.0, "completeness": 0.0,
            "duration_s": duration_s, "words": words, "keywords_hit": [], "keywords_missed": [],
            "structure": 50.0, "speech": {"count": 0, "rate_per_minute": 0.0, "score": 50,
                                          "words_per_minute": 0, "pace_score": 50},
            "clarity": 50.0, "hedges": 0, "feedback": "", "key_points_missing": [],
            "ml_prediction": {"available": False, "predicted_score": None},
        }


def _practice_feedback(ev_res: Dict[str, Any], tone: str, rng: random.Random, mock: bool = False) -> str:
    """Turn the numeric rubric output into the way a human coach talks."""
    score = ev_res.get("answer_score", 0.0)
    label = ev_res.get("grade_label", "Average")
    words = ev_res.get("words", 0)
    fillers = (ev_res.get("speech") or {}).get("count", 0)
    wpm = (ev_res.get("speech") or {}).get("words_per_minute", 0)
    missed = ev_res.get("keywords_missed") or []
    sim = ev_res.get("semantic_similarity", 0.0)
    ml = ev_res.get("ml_prediction") or {}

    parts: List[str] = []
    # Opening — honest, direct, no "your response demonstrates..."
    if score >= 80:
        parts.append(_rand(rng, [
            "That's a genuinely strong answer.",
            "Solid. If you said that in a real room, I'd have no follow-up concerns.",
            "Nice — that's interview-grade.",
        ]))
    elif score >= 65:
        parts.append(_rand(rng, [
            "That's a good answer with one clear gap — let's tighten it.",
            "You're most of the way there; it just needs sharpening.",
            "Decent. Not quite 'hire' level yet, but close.",
        ]))
    elif score >= 45:
        parts.append(_rand(rng, [
            "You touched the right area, but the answer stayed too shallow.",
            "Honest take: you circled the topic without landing on it.",
            "Partial credit. The idea's there; the delivery isn't doing it justice.",
        ]))
    elif words <= 3:
        parts.append(_rand(rng, [
            "That one stayed (almost) empty — totally fine here, that's what practice is for. Let's build the real answer together.",
            "Not much to score yet, so let's construct it from scratch. No judgement — that's the point of practice.",
        ]))
    else:
        parts.append(_rand(rng, [
            "Straight up: that answer missed the core of the question.",
            "I'll be honest — that would read as off-topic in a real interview.",
            "That one drifted away from what was actually asked.",
        ]))

    # Specifics — mirrors the human-coach style from the brief
    if score < 80 and words > 3 and missed:
        parts.append(f"You left out concepts the interviewer will expect: {', '.join(missed[:3])}.")
    if words in range(1, 15) and score < 80:
        parts.append("It was also thin — aim for roughly 40–60 spoken words so the answer has room to breathe.")
    if fillers >= 4:
        parts.append(f"I counted about {fillers} filler words. Swap them for a silent pause — same effect, better sound.")
    # WPM is only meaningful for spoken answers; typed chat has no duration.
    spoken = 40 <= (wpm or 0) <= 400
    if spoken and wpm > 190:
        parts.append(f"You clocked ~{wpm} WPM — that's racing. Break it into points and breathe between them.")
    elif spoken and wpm < 100 and words > 25:
        parts.append(f"~{wpm} WPM is a bit slow; keep the same content but push the energy slightly.")
    if sim < 0.15 and words > 15 and score < 65:
        parts.append("Also — re-read the question before answering. Part of your answer was answering a different question.")

    # ML cross-check, framed honestly as a second opinion
    if ml.get("available") and ml.get("predicted_score") is not None:
        ms = ml["predicted_score"]
        if abs(ms - score) >= 12:
            parts.append(f"For what it's worth, the trained ML model estimates {ms:.0f}/100 — same ballpark, so take both with equal seriousness.")

    # Show the model answer for weak answers, structure fix for mid answers
    if score < 65:
        ref = (ev_res.get("expected_answer") or "").strip()
        if ref:
            parts.append("Here's the shape of a strong answer for this one:\n> " + ref[:420])
    elif score < 80:
        kp = ev_res.get("key_points_missing") or []
        if kp:
            parts.append("To push it higher, cover: " + "; ".join(k[:90] for k in kp[:2]) + ".")

    if mock:
        parts.append(_rand(rng, [
            "Next question coming up.",
            "Alright — next one.",
            "Moving on.",
        ]))
    else:
        parts.append(_rand(rng, [
            "Want another go at it, or shall we move to the next question?",
            "Your call — retry this one, or say \"next\" for a new question.",
            "Try it again with that in mind, or say \"next\" to keep moving.",
        ]))
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Analysis context — turn completed analyses into coach briefing lines
# ---------------------------------------------------------------------------

def _video_brief(interview: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    label = interview.get("title") or f"video analysis #{interview.get('id')}"
    scores = interview.get("detailed_scores") or {}
    overall = interview.get("overall_score")
    if overall is not None:
        lines.append(f"- Video analysis \"{label}\": overall {overall:.0f}/100.")
    if interview.get("words_per_minute"):
        wpm = interview["words_per_minute"]
        if wpm > 180:
            lines.append(f"- Speaking pace runs fast at ~{wpm:.0f} WPM (ideal 120–160).")
        elif wpm < 110:
            lines.append(f"- Speaking pace runs slow at ~{wpm:.0f} WPM.")
    if interview.get("filler_rate") is not None and interview["filler_rate"] >= 5:
        lines.append(f"- Filler words at ~{interview['filler_rate']:.1f}/minute.")
    cs = interview.get("communication_score")
    if cs is not None and cs < 60:
        lines.append(f"- Communication scored {cs:.0f}/100 — structure and clarity need work.")
    if interview.get("answer_quality_score") is not None:
        lines.append(f"- Answer quality scored {interview['answer_quality_score']:.0f}/100.")
    if scores.get("star_score") is not None and scores["star_score"] < 60:
        lines.append(f"- STAR structure scored {scores['star_score']:.0f}/100 — behavioral stories need the Situation-Task-Action-Result shape.")
    imp = interview.get("improvement_plan")
    if isinstance(imp, list) and imp:
        first = imp[0] if isinstance(imp[0], str) else (imp[0] or {}).get("action") or (imp[0] or {}).get("area") or ""
        if first:
            lines.append(f"- Top improvement item from that analysis: {str(first)[:140]}")
    return lines


def _live_brief(rep: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    if rep.get("overall_score") is not None:
        lines.append(f"- Live interview session: overall {rep['overall_score']:.0f}/100.")
    if rep.get("words_per_minute"):
        wpm = rep["words_per_minute"]
        if wpm > 180:
            lines.append(f"- Pace was fast across answers (~{wpm:.0f} WPM).")
        elif 0 < wpm < 110:
            lines.append(f"- Pace was slow across answers (~{wpm:.0f} WPM).")
    if rep.get("fillers_total"):
        lines.append(f"- {rep['fillers_total']} filler words across the session.")
    for s in (rep.get("areas_for_improvement") or [])[:2]:
        lines.append(f"- Area flagged: {str(s)[:130]}")
    weak = sorted(rep.get("results") or [], key=lambda r: r.get("answer_score", 0))[:2]
    for w in weak:
        if w.get("answer_score", 100) < 65:
            lines.append(f"- Weak answer on \"{str(w.get('question'))[:70]}...\" ({w.get('answer_score', 0):.0f}/100) — worth re-drilling.")
    return lines


def build_snapshot_context(snapshot: Optional[Dict], kind: Optional[str]) -> List[str]:
    if not snapshot:
        return []
    try:
        if kind == "video":
            return _video_brief(snapshot)
        if kind == "live":
            return _live_brief(snapshot)
    except Exception as e:
        logger.warning(f"snapshot context build failed: {e}")
    return []


# ---------------------------------------------------------------------------
# Intent detection
# ---------------------------------------------------------------------------

def _last_assistant_text(history: List[Dict[str, str]]) -> str:
    for m in reversed(history):
        if m.get("role") == "coach":
            return m.get("content", "")
    return ""


def _is_questionish(text: str) -> bool:
    return text.strip().endswith("?") or bool(re.match(
        r"^\s*(what|how|why|when|where|who|which|can|could|should|do|does|did|is|are|tell\s*me|explain|give\s*me|ask\s*me)\b",
        text.strip(), re.I))


def _looks_like_answer(text: str, intents: Dict[str, bool]) -> bool:
    """While a question is on the table, is this message actually an ATTEMPT
    to answer it — not a clarification, a meta-request, or a new topic?
    Deliberately generous: real spoken answers are messy. But questions,
    clarifications, role-prep talk and interviewer commands must fall through
    to the normal conversation flow instead of being scored as an answer."""
    if intents["clarify"] or intents["simpler"] or intents["new_chat"]:
        return False
    if intents["role_prep"]:
        return False
    if intents["harder"]:
        return False
    if intents["ask_me"]:
        return False
    t = text.strip().lower()
    # Advice-seeking during light practice falls back to coaching mode (a
    # strict mock interviewer would still treat it as an answer).
    if intents["improve"] and len(t.split()) <= 12:
        return False
    # Meta commands about the interviewer/setup itself
    if re.search(r"\b(pretend|act\s*like|be\s*my|interview\s*me|mock|interviewer\s*mode|stop|pause|hold\s*on|give\s*me\s*a\s*(hint|tip)|i\s*give\s*up|skip\s*this)\b", t):
        return False
    # Questions are not answers
    if intents["questionish"] or text.strip().endswith("?"):
        return False
    return True


class _Intents:
    new_chat = re.compile(r"\b(new\s*(chat|conversation|topic|session)|start\s*over|reset|clear\s*(the\s*)?(chat|conversation))\b", re.I)
    clarify = re.compile(r"\b(don'?t|do\s*not|didn'?t|did\s*not|can'?t|cannot|can\s*not)?\s*(don'?t\s*understand|do\s*not\s*understand|didn'?t\s*get|did\s*not\s*get|what\s*do\s*you\s*mean|confus(ed|ing)|can\s*you\s*(explain|say)\s*(that\s*)?(again|in\s*simple)|in\s*other\s*words|come\s*again|i\s*don'?t\s*get\s*(it|that|you))\b", re.I)
    simpler = re.compile(r"\b(simpler|too\s*complicated|too\s*complex|plain\s*(english|words)|eli5|break\s*it\s*down|in\s*easy)\b", re.I)
    harder = re.compile(r"\b(too\s*easy|too\s*basic|harder|more\s*difficult|tougher|challenge\s*me|hard\s*(one|question))\b", re.I)
    ask_me = re.compile(r"\b(ask\s*me|give\s*me\s*(an?|another|one)\s*(interview\s*)?(question|q)\b|next\s*question|quiz\s*me|interview\s*me|mock\s*(interview)?|practice|you\s*(are|become)\s*my\s*interviewer|pretend\s*(that\s*)?(you'?re|you\s*are)\s*(my|the|an)?\s*interviewer|be\s*(my|the)\s*interviewer|act\s*(like|as)\s*(an?|my|the)?\s*(interviewer|panel))\b", re.I)
    evaluate = re.compile(r"\b(evaluate|score|rate|grade|feedback\s*(on)?|review)\b", re.I)
    improve = re.compile(r"\b(improve|better|weak|suck|struggle|bad\s*at|mess(ed)?\s*up|wrong\s*with|help\s*me\s*(with|fix)|polish)\b", re.I)
    vent = re.compile(r"\b(messed\s*up|failed|flunked|bombed|blew\s*it|rejected|screwed\s*(up|it)|demoralized|dejected|worthless|hate\s*(this|myself)|giving\s*up)\b", re.I)
    anxiety = re.compile(r"\b(nervous|anxious|scared|afraid|panic|freaking\s*out|stressed|pressure|tomorrow('s)?\s*interview)\b", re.I)
    role_prep = re.compile(r"\b(applying\s*for|prepar(e|ing)\s*for|target(ing)?\s*(role|job)|software\s*(developer|engineer)|sde|frontend|backend|full\s*stack|data\s*(scientist|analyst|engineer)|intern(ship)?\s*(role|position)?|fresher)\b", re.I)
    questionish_q = re.compile(r"^\s*(what|how|why|when|where|who|which|can|could|should|do|does|did|is|are)\b.*\?$", re.I)


def _detect_intents(text: str, history: List[Dict[str, str]], ap: Optional[Dict]) -> Dict[str, bool]:
    t = text.lower()
    hist_text = " ".join(m.get("content", "") for m in history[-6:]).lower()
    return {
        "new_chat": bool(_Intents.new_chat.search(t)),
        "clarify": bool(_Intents.clarify.search(t)),
        "simpler": bool(_Intents.simpler.search(t)),
        "harder": bool(_Intents.harder.search(t)),
        "ask_me": bool(_Intents.ask_me.search(t)),
        "evaluate": bool(_Intents.evaluate.search(t)),
        "improve": bool(_Intents.improve.search(t)),
        "vent": bool(_Intents.vent.search(t)),
        "anxiety": bool(_Intents.anxiety.search(t)),
        "role_prep": bool(_Intents.role_prep.search(t)),
        "history_callback": bool(HISTORY_CALLBACK.search(t)) and bool(_last_assistant_text(history)),
        "in_practice": ap is not None,
        "questionish": bool(_is_questionish(text)),
        "mentions_coach_question": "question" in t and re.search(r"\b(your|that|last|same|this|the)\b", t) is not None,
        "about_coach_analysis": bool(re.search(r"\b(my\s+)?(report|analysis|results?|scores?|metrics?)\b", t)) and bool(
            re.search(r"\b(my|the|that|last)\b", t)) and "report" in hist_text or "analysis" in t,
    }


# ---------------------------------------------------------------------------
# Reply composition — the "brain"
# ---------------------------------------------------------------------------

def generate_reply(
    message: str,
    history: List[Dict[str, str]],
    session: Dict[str, Any],
) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
    """Produce the coach's next message.

    Returns (reply_text, updated_session_fields, meta).
    session carries: mode, tone, target_role, active_practice, snapshot fields,
    asked question ids.
    """
    text = (message or "").strip()
    if not text:
        return ("I'm here — say whatever's on your mind.", {}, {"intent": "empty"})

    rng = random.Random(f"{session.get('id', 0)}:{len(history)}:{abs(hash(text)) % 99999}")
    tone = session.get("tone") or "friendly"
    ap = session.get("active_practice")
    intents = _detect_intents(text, history, ap)
    style = {name for pat, name in STYLE_RULES if re.search(pat, text, re.I)}
    moods = {name for pat, name in MOOD_RULES if re.search(pat, text, re.I)}

    extra_fields: Dict[str, Any] = {}

    # --- 0. Practice-mode branch: the user is answering the coach's question
    if ap and not intents["new_chat"] and _looks_like_answer(text, intents):
        return _handle_practice_answer(text, history, session, ap, intents, tone, rng, style)

    # --- 1. Meta: new chat / reset
    if intents["new_chat"]:
        return (
            "Fresh page. What's on your mind — prep, practice, or just thinking out loud about interviews?",
            {"active_practice": None, "mode": "coaching", "title": None},
            {"intent": "reset"},
        )

    # --- 2. Clarification / simpler wording — always re-explain the last point
    if intents["clarify"] or intents["simpler"]:
        return _handle_clarify(history, intents, rng)

    # --- 3. Harder question escalation
    if intents["harder"] and (ap or intents["ask_me"] or "question" in text.lower()):
        # Mid-mock: escalate inside the running interview; otherwise free practice.
        if ap and ap.get("kind") == "mock":
            q = _pick_question(categories=ap.get("categories"), difficulty="Hard",
                               exclude=session.get("asked_ids") or [], rng=rng)
            if q:
                return _serve_question(q, session, mode_label="mock", kind="mock",
                                       index=ap.get("index", 1), total=ap.get("total", 0),
                                       categories=ap.get("categories"), rng=rng)
        q = _pick_question(categories=_detect_category_pref(text) or None,
                           difficulty="Hard", exclude=session.get("asked_ids") or [], rng=rng)
        if q:
            return _serve_question(q, session, mode_label=None, kind="practice", rng=rng)

    # --- 4. Explicit ask-me / practice / mock interview
    if intents["ask_me"]:
        return _handle_ask_me(text, history, session, intents, rng)

    # --- 5. Emotional support first — never bury feelings under advice
    if intents["vent"] or "dejected" in moods:
        return _supportive(text, VENT_REPLIES, VENT_ADVICE, session, rng)

    if intents["anxiety"] or "nervous" in moods:
        guide = TOPIC_GUIDES["nervous"]
        reply = _rand(rng, ANXIETY_REPLIES) + "\n\n" + guide["advice"]
        if guide["followup"]:
            reply += "\n\n" + guide["followup"]
        return (reply, {"title": session.get("title") or _title_from(text)}, {"intent": "anxiety"})

    # --- 6. Role preparation
    if intents["role_prep"]:
        return _handle_role_prep(text, session, rng)

    # --- 7. Known topic guides (tell me about yourself, weakness, pace, fillers...)
    topic = _match_topic(text)
    if topic and not intents["evaluate"]:
        guide = TOPIC_GUIDES[topic]
        reply = guide["advice"]
        if guide.get("followup"):
            reply += "\n\n" + guide["followup"]
        return (reply, {"title": session.get("title") or _title_from(text)}, {"intent": f"topic:{topic}"})

    # --- 8. "Evaluate/improve this answer" — a pasted answer block
    if (intents["evaluate"] or intents["improve"]) and len(text.split()) > 45:
        return _handle_free_answer_review(text, session, rng)

    # --- 9. History callback: "that question", "the thing you said"
    if intents["history_callback"]:
        return _handle_history_callback(text, history, session, rng)

    # --- 10. Snapshot-related questions ("what did my report say about pace?")
    snap_lines = build_snapshot_context(session.get("snapshot"), session.get("snapshot_source_kind"))
    if snap_lines and re.search(r"\b(report|analysis|results?|scores?|pace|filler|wpm|metrics|feedback)\b", text, re.I):
        reply = ("I've got your latest analysis in front of me — here's what stands out:\n"
                 + "\n".join(snap_lines[:5])
                 + "\n\nPick the one that bugs you most, or say \"let's practice that\" and we'll work on it together.")
        return (reply, {"title": session.get("title") or _title_from(text)}, {"intent": "snapshot_discussion"})

    # --- 11. Generic interview question → answer like a knowledgeable mentor
    if intents["questionish"]:
        return _handle_general_question(text, history, session, rng)

    # --- 12. Statements: acknowledge + steer somewhere useful
    return _handle_statement(text, session, intents, moods, rng)


def _title_from(text: str) -> str:
    words = re.sub(r"\s+", " ", text.strip())[:60]
    return (words[:57] + "...") if len(words) > 60 else (words or "New chat")


# --------------------------- practice mode -------------------------------

def _handle_practice_answer(text, history, session, ap, intents, tone, rng, style):
    q = ap.get("q")
    mode_label = ap.get("kind")  # practice | mock
    q_idx = ap.get("index", 1)
    total = ap.get("total", 0)

    ev_res = evaluate_practice_answer(q, text, duration_s=ap.get("asked_at_elapsed", 0.0) or 0.0)
    feedback = _practice_feedback(ev_res, tone, rng, mock=(mode_label == "mock"))

    # Track session-long answers
    asked_ids = list(session.get("asked_ids") or [])
    scores = list(session.get("practice_scores") or [])
    scores.append({"question": q.get("question"), "score": ev_res["answer_score"]})
    extra = {
        "active_practice": None,  # answered — wait for user to ask next
        "practice_scores": scores,
        "last_evaluation": ev_res,
    }

    if mode_label == "mock" and q_idx < total:
        nxt = _pick_question(categories=ap.get("categories"), difficulty=None, exclude=asked_ids, rng=rng)
        if nxt:
            asked_ids.append(nxt["question_id"])
            extra["asked_ids"] = asked_ids
            extra["active_practice"] = {
                "kind": "mock", "index": q_idx + 1, "total": total,
                "categories": ap.get("categories"), "q": nxt,
            }
            tail = (f"\n\n**Question {q_idx + 1} of {total}:** {nxt['question']}\n\n"
                    "Take your time — answer as if I'm the real panel.")
            return (feedback + tail, extra, {"intent": "practice_answer", "evaluation": ev_res, "next": True})

    if mode_label == "mock" and q_idx >= total:
        scored = [s["score"] for s in scores if s.get("score") is not None]
        avg = sum(scored) / len(scored) if scored else 0.0
        tail = (f"That's a wrap on the mock interview. Your {len(scored)} answers averaged **{avg:.0f}/100**. "
                + ("Strong session — you'd walk out of that room feeling good."
                   if avg >= 75 else
                   "Decent bones; the gaps we hit are exactly what to drill before the real thing. "
                   "Say \"review my mock\" if you want a question-by-question debrief."))
        extra["mode"] = "coaching"
        return (feedback + "\n\n" + tail, extra, {"intent": "mock_complete", "evaluation": ev_res})

    return (feedback, extra, {"intent": "practice_answer", "evaluation": ev_res})


def _serve_question(q, session, mode_label, rng, kind="practice", index=1, total=0, categories=None):
    asked_ids = list(session.get("asked_ids") or [])
    if q["question_id"] not in asked_ids:
        asked_ids.append(q["question_id"])
    ap = {"kind": kind, "index": index, "total": total, "categories": categories, "q": q}
    lead = ""
    if kind == "mock" and index == 1:
        lead = _rand(rng, [
            "Alright — interview mode. I'm your interviewer from here on; answers should be spoken-length, "
            "roughly 40–60 words, like you're talking to a real panel.\n\n",
            "Okay, let's do this properly. From now on I'm the interviewer — no hints until the end.\n\n",
        ])
    elif kind == "mock":
        lead = ""
    else:
        lead = _rand(rng, [
            "Here we go:\n\n",
            "Love it. Question:\n\n",
            "Let's practice. Here's your question:\n\n",
        ])
    text = f"{lead}**{q['question']}**\n\n_{q['category']} · {q['difficulty']}_"
    if kind == "practice":
        text += "\n\nAnswer in your own words — messy is fine, that's what this is for. Say \"next\" when you want a different one."
    extra = {"active_practice": ap, "asked_ids": asked_ids, "mode": session.get("mode") or "coaching"}
    if kind == "mock":
        extra["mode"] = "strict_interviewer"
    return (text, extra, {"intent": "serve_question", "question_id": q["question_id"]})


def _handle_ask_me(text, history, session, intents, rng):
    t = text.lower()
    cats = _detect_category_pref(t)
    difficulty = _difficulty_pref(t)
    asked_ids = session.get("asked_ids") or []
    ap = session.get("active_practice")

    # Mock interview request — N questions in sequence
    if re.search(r"\b(mock|interview\s*me|strict|panel|full\s*interview|like\s*(a|an)\s*(real|strict)\s*interviewer|my\s*interviewer|the\s*interviewer)\b", t):
        m = re.search(r"\b(\d{1,2})\s*(questions?|qs)\b", t)
        total = int(m.group(1)) if m else 5
        total = max(2, min(10, total))
        q = _pick_question(categories=cats, difficulty=difficulty, exclude=asked_ids, rng=rng)
        if q:
            return _serve_question(q, session, mode_label="mock", kind="mock", index=1, total=total,
                                   categories=cats, rng=rng)

    # "That question was too easy. Give me something harder." — handled by harder intent earlier;
    # here: normal next question. If practice is active and user says "next"/"skip", serve a new one.
    if ap and re.search(r"^\s*(next|skip|another|different\s*(one|question)?)\s*[.!]?\s*$", t):
        q = _pick_question(categories=ap.get("categories") or cats, difficulty=difficulty or _difficulty_pref(t),
                           exclude=asked_ids, rng=rng)
        if q:
            return _serve_question(q, session, mode_label=None, kind=ap.get("kind", "practice"),
                                   index=ap.get("index", 1), total=ap.get("total", 0),
                                   categories=ap.get("categories"), rng=rng)

    q = _pick_question(categories=cats, difficulty=difficulty, exclude=asked_ids, rng=rng)
    if q:
        return _serve_question(q, session, mode_label=None, kind="practice", rng=rng)
    return ("My question dataset isn't loading right now — but describe the topic and I'll ask you about it off the cuff.", {}, {"intent": "serve_question_failed"})


def _handle_clarify(history, intents, rng):
    last = _last_assistant_text(history)
    # Compress the previous coach message into a simpler, shorter version.
    if last:
        # Take the most actionable lines, strip markdown, shorten.
        lines = [l.strip() for l in last.split("\n") if l.strip()]
        core = [l for l in lines if not l.startswith(">")][:4]
        simplified = " ".join(re.sub(r"\*\*|__|`", "", l) for l in core)[:600]
        reply = (_rand(rng, [
            "No problem — let me put it more simply:\n\n",
            "Sure, simpler version:\n\n",
            "Fair — let me say it another way:\n\n",
        ]) + simplified)
        if intents["clarify"] and intents["simpler"]:
            reply += "\n\nIf it's still fuzzy, tell me which part and I'll zoom in on just that."
    else:
        reply = "Nothing to clarify yet — ask me anything about interviews and we'll go from there."
    return (reply, {}, {"intent": "clarify"})


def _handle_role_prep(text, session, rng):
    t = text.lower()
    role = None
    m = re.search(r"\b(?:applying\s*for|prepar(?:e|ing)\s*for|target(?:ing)?|interview\s*for)\s+(?:a\s+|an\s+|the\s+|my\s+)?(?P<role>[a-z0-9+# ./-]{3,60}?)(?:\s+(?:role|job|position|interview)\b|[,.]|$)", t)
    if m and m.group("role"):
        role = m.group("role").strip(" .")
    if not role:
        m2 = re.search(r"\b(software\s*(?:developer|engineer)|sde|frontend|backend|full\s*stack|data\s*(?:scientist|analyst|engineer))\b", t)
        if m2:
            role = m2.group(0)
    role = role or "the role you mentioned"

    is_tech = bool(re.search(r"software|developer|engineer|sde|backend|frontend|full.?stack|data|java|python", t))
    plan = [
        f"Prepping for {role} — solid, let's build the plan:",
        "",
        "**1. Your story (60–90s)** — a tight \"tell me about yourself\" is the highest-leverage thing you can own. Present → proof → why this role.",
        "**2. Two projects, PSR-shaped** — Problem, Solution, Result for each, with a number in the result. These get asked everywhere.",
        "**3. Core fundamentals for the stack**" + (" — language internals, data structures, DB and OS basics for developer roles." if is_tech else " — the domain knowledge this role actually uses day-to-day."),
        "**4. Behavioral bank** — 4–5 STAR stories: conflict, failure, deadline, leadership, technical win.",
        "**5. Their questions to you** — have 2–3 real ones; \"no questions\" reads as low interest.",
        "",
        "Then it's reps: practice answers out loud, timed, and drill the weak spots.",
    ]
    reply = "\n".join(plan)
    reply += "\n\nWant to pressure-test any of these right now? Say \"mock interview\" for a full round, or tell me your weakest area and we'll start there."
    return (reply, {"target_role": (role or session.get("target_role")), "title": session.get("title") or f"Prep: {role}"}, {"intent": "role_prep", "role": role})


def _handle_free_answer_review(text, session, rng):
    # The user pasted an answer for review. Find the answer portion heuristically:
    # use the text minus the command sentence.
    body = text
    for pat in (r"^.*?(improve|evaluate|review|feedback|rate|score)\s*(this|it)?\s*[:,]?\s*",
                r"^(can|could)\s*you\s*\w+\s*"):
        body = re.sub(pat, "", body, count=1, flags=re.I)
    fake_q = {
        "question_id": "freeform", "question": "Tell me about this experience or topic (free-form answer review)",
        "category": "Free-form", "difficulty": "—", "expected_answer": "",
    }
    ev_res = evaluate_practice_answer(fake_q, body)
    # Free-form answers have no reference; lean on structure/clarity and the ML model.
    ml = ev_res.get("ml_prediction") or {}
    parts = []
    score = ev_res.get("answer_score", 0)
    structure = ev_res.get("structure", 0)
    words = ev_res.get("words", 0)
    if ml.get("available") and ml.get("predicted_score") is not None:
        parts.append(f"Honest read: this lands around **{ml['predicted_score']:.0f}/100** as an interview answer.")
    else:
        parts.append(f"Honest read: this is roughly a **{score:.0f}/100** answer in an interview setting.")
    if words < 35:
        parts.append("It's thin — a spoken version should run 40–60 words minimum. Interviewers can't score what you don't say.")
    if structure < 55:
        parts.append("Structure is the weak point: the idea arrives late and the sentences sprawl. Lead with the point, then support it, then land the result.")
    if ev_res.get("hedges", 0) >= 2:
        parts.append("You're hedging a lot (\"I think\", \"maybe\"). State what you know; hedge only what's genuinely uncertain.")
    fillers = (ev_res.get("speech") or {}).get("count", 0)
    if fillers >= 3:
        parts.append(f"~{fillers} filler words in there too — pause instead, it reads as confidence.")
    parts.append("Want me to rewrite one paragraph as a demo? Quote the line you like least and I'll show you the polished version side by side.")
    return ("\n\n".join(parts), {"title": session.get("title") or "Answer review"}, {"intent": "free_answer_review"})


def _handle_history_callback(text, history, session, rng):
    last = _last_assistant_text(history)
    t = text.lower()
    if re.search(r"\btoo\s*(easy|basic)\b|\bharder\b", t):
        q = _pick_question(difficulty="Hard", exclude=session.get("asked_ids"), rng=rng)
        if q:
            return _serve_question(q, session, mode_label=None, kind="practice", rng=rng)
    if re.search(r"\b(again|repeat|one\s*more\s*time|what\s*was\s*(it|that))\b", t) and last:
        return ("Here it is again:\n\n" + last, {}, {"intent": "repeat"})
    if re.search(r"\bwhy\b", t) and last:
        return (
            _rand(rng, ["Good question — here's the reasoning behind it:\n\n", "Let me back that up:\n\n"])
            + "The core idea: interviewers hire evidence, not adjectives. Every recommendation I give traces back to that — "
              "structure makes your evidence findable, pace and fillers decide whether they actually hear it, and honest practice is what turns both into muscle memory."
              + ("\n\nAnd on your earlier point — " + last[:220] if last else ""),
            {}, {"intent": "explain_reasoning"},
        )
    # Generic: build on the last message
    if last:
        return (
            _rand(rng, ["Right, continuing from where we were —\n\n", "Okay, building on that:\n\n"])
            + last[:500]
            + "\n\nBut tell me the specific angle you want and I'll go deeper — example, practice round, or a harder version.",
            {}, {"intent": "history_callback"},
        )
    return ("I think we just crossed wires — give me the full thought and I'll pick it up properly.", {}, {"intent": "history_callback_empty"})


def _handle_general_question(text, history, session, rng):
    """Any interview-ish question the guides don't cover: answer like a mentor."""
    topic = _match_topic(text)
    if topic:
        g = TOPIC_GUIDES[topic]
        reply = g["advice"] + (("\n\n" + g["followup"]) if g.get("followup") else "")
        return (reply, {"title": session.get("title") or _title_from(text)}, {"intent": f"topic:{topic}"})

    # Conceptual technical question (e.g. "what is normalization?") — answer
    # with the dataset's reference explanation when we have one.
    if re.search(r"\b(explain|what\s+is|what\s+are|how\s+does|difference\s+between)\b", text, re.I):
        best = _best_dataset_match(text)
        if best:
            q = best
            ref = (q.get("expected_answer") or "").strip()
            core = (
                _rand(rng, [f"Here's how I'd explain it, the interview-safe way:\n\n", "Good question. The version that lands in interviews:\n\n"])
                + f"**{q['question']}**\n\n{ref[:520]}"
            )
            reply = core + (
                "\n\nThat's the core — want me to go one level deeper, or turn it into a practice question?"
                if len(core) < 700 else "\n\nWant the deeper cut or a practice round on this?"
            )
            return (reply, {"title": session.get("title") or _title_from(text)}, {"intent": "concept", "question_id": q["question_id"]})

    # Everything else: mentor answer skeleton tuned to the question shape.
    reply = (
        _rand(rng, ["Good question — here's how I'd approach it:\n\n", "Let me give you the practical answer:\n\n"])
        + f"On **{_short_topic(text)}** specifically, the interview lens is: what does the interviewer actually want to learn from this? Almost always one of three things — can you structure a thought, do you know your stuff, and do they want to work with you.\n\n"
        + "So the strong answer shape: one-line direct answer → the why (2–3 sentences) → a concrete example from your own work → a short close. Keep the whole thing under 90 seconds.\n\n"
        + "If you want, draft your version right here — even a rough one — and I'll tighten it with you."
    )
    return (reply, {"title": session.get("title") or _title_from(text)}, {"intent": "general_question"})


def _best_dataset_match(text: str) -> Optional[Dict[str, Any]]:
    """Find the dataset question most similar to the user's concept question."""
    pool = ds.load_dataset()
    if not pool:
        return None
    from difflib import SequenceMatcher
    t = text.lower().strip("? ")
    best, best_r = None, 0.0
    probe = re.sub(r"^(explain|what is|what are|how does|difference between)\s+", "", t)
    for q in pool[:150]:
        qq = q["question"].lower().strip("? ")
        r = SequenceMatcher(None, probe, qq).ratio()
        if r > best_r:
            best, best_r = q, r
    return best if best_r >= 0.42 else None


def _short_topic(text: str) -> str:
    t = re.sub(r"\?", "", text).strip()
    return (t[:70] + "…") if len(t) > 70 else t


def _handle_statement(text, session, intents, moods, rng):
    """Chit-chat, statements, scattered thoughts — keep it human and useful."""
    t = text.lower()
    if re.search(r"\b(thanks|thank\s*you|ty|got\s*it|makes\s*sense|cool|nice|great|awesome|perfect|okay|ok|will\s*do)\b", t) and len(t.split()) <= 6:
        return (
            _rand(rng, [
                "Anytime. What's next — more practice, or something else on your mind?",
                "Glad it clicked. Want to put it into practice right now?",
                "That's what I'm here for. Where to next?",
            ]),
            {}, {"intent": "ack"},
        )
    if re.search(r"\b(hi|hello|hey|yo|good\s*(morning|afternoon|evening))\b", t) and len(t.split()) <= 5:
        return (
            _rand(rng, [
                "Hey! Good to see you. What are we working on today?",
                "Hello! Interview stuff on your mind, or something else?",
                "Hey there — ready when you are. Practice round, prep plan, or just talk it out?",
            ]),
            {}, {"intent": "greeting"},
        )
    if re.search(r"\b(who\s*are\s*you|what\s*can\s*you\s*do|what\s*are\s*you)\b", t):
        return (
            "I'm your interview coach — think of me as the mentor friend who's sat on both sides of the table. "
            "Talk to me like you'd talk to them: vent about a bad interview, ask how to answer anything, paste an answer for honest critique, "
            "or say \"mock interview\" and I'll run you through a real one, question by question. "
            "I also read your interview-analysis results when you've got them, so my advice gets specific to you.",
            {}, {"intent": "about"},
        )
    # "excited" mood
    if "excited" in moods:
        return (
            _rand(rng, [
                "That's great news — congrats! Now let's convert that into an offer.",
                "Love that. Channel the energy: what's the role, and how much runway do we have?",
            ]) + "\n\nTell me the company/role and I'll help you prep exactly what they're likely to ask.",
            {}, {"intent": "excited"},
        )
    if "stuck" in moods:
        return (
            _rand(rng, [
                "Okay, let's un-stick it. What's the last thing that made sense, and where did it stop making sense?",
                "That foggy feeling is normal before interviews. Give me the messiest version of the problem and we'll untangle it from there.",
            ]),
            {}, {"intent": "stuck"},
        )
    # Generic acknowledgment that moves things forward
    return (
        _rand(rng, [
            "Got it. Here's what I'd do with that:\n\n",
            "Understood — let's make that useful:\n\n",
            "Fair enough. Practical next step:\n\n",
        ])
        + "Pick ONE of these and we'll go deep: (1) practice a question on it right now, (2) draft your answer together, "
          "(3) I explain the underlying concept simply. Tell me the number — or just keep talking and I'll steer.",
        {}, {"intent": "statement"},
    )


# --------------------------- support snippets ----------------------------

def _supportive(text, replies, advice, session, rng):
    """Emotional support first, then one concrete way forward."""
    reply = _rand(rng, replies) + "\n\n" + advice
    return (reply, {"title": session.get("title") or _title_from(text)}, {"intent": "support"})


VENT_REPLIES = [
    "Ouch. I'm sorry — that sinking feeling after an interview you cared about is rough.",
    "That stings. But for the record: messing up an interview is data, not a verdict on you.",
    "Rough one, huh. Okay — let's figure out what actually went wrong, because that's the part you control.",
]
VENT_ADVICE = (
    "Here's the thing: a failed interview is the most honest feedback you'll ever get, and most people throw it away by wallowing. Not you.\n\n"
    "Walk me through it — which question got you, and what happened the moment you froze or fumbled? "
    "We'll rebuild that exact answer so the next version of you has it ready."
)

ANXIETY_REPLIES = [
    "Take a breath — you came to the right place, and nerves are just your brain treating an opportunity like a threat.",
    "Okay, deep breath. Nervous is normal; unprepared is the actual problem, and that one we can fix.",
]

# ---------------------------------------------------------------------------
# History summarizer for very long chats (keeps context, caps tokens)
# ---------------------------------------------------------------------------

def context_messages(history: List[Dict[str, str]], snapshot_lines: List[str], session: Dict[str, Any]) -> List[Dict[str, str]]:
    """The message window the engine effectively 'remembers' (kept for the
    route layer / future LLM swap; the rule engine reads history directly)."""
    msgs = list(history[-MAX_TURNS:])
    if snapshot_lines:
        brief = {"role": "system", "content": "Candidate's latest analysis:\n" + "\n".join(snapshot_lines)}
        msgs = [brief] + msgs
    if session.get("target_role"):
        msgs = [{"role": "system", "content": f"Target role: {session['target_role']}"}] + msgs
    return msgs
