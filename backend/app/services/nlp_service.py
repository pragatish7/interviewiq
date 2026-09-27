"""
NLP analysis service for content quality, question detection, STAR framework analysis.
"""
import re
import math
import logging
from typing import Dict, Any, List, Tuple, Optional
from collections import Counter

logger = logging.getLogger(__name__)

# Interview question patterns
QUESTION_PATTERNS = {
    "hr_general": [
        r"tell me about yourself",
        r"what are your (strengths|weaknesses)",
        r"where do you see yourself",
        r"why do you want",
        r"what motivates you",
        r"describe your (ideal|dream)",
        r"what are your goals",
        r"why should we hire you",
        r"tell me about a time",
        r"how would you describe yourself",
        r"what do you know about",
        r"do you have any questions",
        r"what are you looking for",
        r"what is your greatest",
    ],
    "behavioral": [
        r"tell me about a (time|situation|moment) (when|where)",
        r"(describe|explain) a (time|situation|occasion)",
        r"give me an example of",
        r"how did you (handle|deal|manage|overcome)",
        r"what (did you do|would you do) when",
        r"(tell|describe) about (a|your) (challenge|difficult|problem|conflict)",
        r"have you ever had to",
        r"(describe|tell) a situation where you",
        r"how do you (handle|deal with|manage)",
        r"what is your approach to",
        r"share an experience",
    ],
    "technical": [
        r"explain (the|a|how|what)",
        r"what is (a|an|the)",
        r"how does .* work",
        r"what (are|is) the (difference|advantage|disadvantage)",
        r"describe the (process|architecture|design)",
        r"implement|code|write",
        r"algorithm|data structure",
        r"what (database|language|framework|tool)",
        r"how would you (optimize|improve|design|build)",
        r"complexity|Big O|runtime",
        r"machine learning|neural network|deep learning",
    ],
    "situational": [
        r"what would you do if",
        r"how would you handle",
        r"imagine .* (situation|scenario)",
        r"suppose .* (happens|occurs)",
        r"if you were .* what would",
        r"how would you respond",
        r"what (approach|strategy) would you take",
    ],
}

# STAR indicators
STAR_INDICATORS = {
    "situation": [
        r"when i (was|worked|had|joined|started)",
        r"at my (previous|last|current) (job|company|role|position)",
        r"in my (previous|last|current) (job|company|role|position|team)",
        r"during (my|the|a) (time|project|period|experience)",
        r"there was (a|an|this|one) (time|situation|project|instance)",
        r"we (had|were|faced|experienced|encountered)",
        r"i was working on",
        r"the team was",
        r"our (project|client|company|system)",
        r"in (a|this|that|one|my) (situation|case|project|instance|experience)",
        r"one (time|day|instance|experience)",
        r"back when",
        r"at (the|that) (time|point|moment)",
        r"this (happened|occurred)",
    ],
    "task": [
        r"my (role|job|responsibility|task|goal|objective) was",
        r"i (needed|had to|was responsible|was tasked|was assigned)",
        r"i was (asked|expected|required|supposed) to",
        r"the (goal|objective|task|challenge|problem) was",
        r"we needed to",
        r"i (needed|had) to (find|solve|fix|implement|create|build|deliver|improve|reduce|increase)",
        r"my responsibility was to",
        r"i (was assigned|was given the task|was responsible for)",
        r"the challenge was",
        r"we were tasked with",
        r"i (had to|needed to) (ensure|make sure|achieve|complete|deliver)",
    ],
    "action": [
        r"i (decided|chose|implemented|developed|created|designed|built|wrote|analyzed|led|managed|organized|initiated|proposed|coordinated|facilitated|conducted|executed|performed|introduced|established|launched|spearheaded|drove|oversaw|supervised|mentored|trained|coached|guided|negotiated|resolved|addressed|approached|tackled|handled|dealt with|managed|improved|optimized|streamlined|automated|redesigned|refactored|migrated|deployed|configured|tested|debugged|troubleshot|documented|presented|communicated|collaborated|partnered|liaised|reported|escalated|prioritized|planned|scheduled|allocated|budgeted|forecasted|evaluated|assessed|reviewed|audited|monitored|tracked|measured|quantified|benchmark|compared|investigated|researched|explored|assessed|surveyed|gathered|collected|aggregated|synthesized|interpreted|concluded|recommended|advised|counseled|influenced|persuaded|convinced|advocated|championed|spearheaded|pioneered|innovated|transformed|revolutionized|disrupted|discovered|invented|designed|architected|engineered|programmed|coded|developed|built|created|assembled|constructed|produced|generated|fabricated|manufactured|constructed|formed|shaped|molded|sculpted|crafted|refined|polished|perfected|enhanced|amplified|magnified|boosted|elevated|advanced|progressed|evolved|matured|developed|grew|expanded|scaled|proliferated|multiplied|duplicated|replicated|reproduced|expanded|extended|broadened|widened|deepened|strengthened|fortified|reinforced|solidified|stabilized|secured|protected|guarded|defended|shielded|shielded|defended|protected|guarded|protected|safeguarded|ensured|guaranteed|warranted|certified|verified|validated|confirmed|authenticated|corroborated|substantiated|documented|recorded|logged|noted|registered|enrolled|listed|cataloged|indexed|filed|archived|stored|saved|preserved|maintained|sustained|continued|persisted|endured|lasted|survived|outlasted|overcame|conquered|defeated|vanquished|triumphed|prevailed|succeeded|excelled|outperformed|surpassed|exceeded|outshone|outdid|outstripped|outranked|outclassed|outmatched|outwitted|outsmarted|outmaneuvered|outperformed|excelled|surpassed|exceeded|surmounted|overcame|conquered|vanquished|triumphed|prevailed|succeeded|excelled|prospered|flourished|thrived|bloomed|blossomed|flourished|prospered|succeeded|triumphed|prevailed|won|conquered|dominated|mastered|ruled|governed|led|directed|guided|steered|navigated|piloted|captained|commanded|headed|managed|oversaw|supervised|administered|regulated|controlled|regulated|governed|managed|directed|guided|steered|navigated|piloted|captained|commanded|headed|administered|regulated|controlled|governed|managed|directed|guided|steered|navigated|piloted|captained|commanded|headed|administered|regulated|controlled|governed|managed|directed|guided|steered|navigated|piloted|captained|commanded|headed|administered|regulated|controlled",
        r"(then|next|after that|subsequently|as a result)",
        r"(first|secondly|finally|additionally|moreover)",
        r"the (approach|strategy|method|solution) i (used|took|implemented|applied|adopted)",
        r"to (solve|address|tackle|resolve|fix|improve|handle)",
        r"(one approach|what i did|here's what i|my approach was|the way i)",
        r"i (applied|used|leveraged|utilized|employed|adopted|implemented|executed|deployed|launched|rolled out|introduced|instituted|established|created|developed|designed|built|constructed|engineered|programmed|coded|developed|built|created|assembled|constructed|produced|generated|fabricated|manufactured|constructed|formed|shaped|molded|sculpted|crafted|refined|polished|perfected|enhanced|amplified|magnified|boosted|elevated|advanced|progressed|evolved|matured|developed|grew|expanded|scaled|proliferated|multiplied|duplicated|replicated|reproduced|expanded|extended|broadened|widened|deepened|strengthened|fortified|reinforced|solidified|stabilized|secured|protected|guarded|defended|shielded|ensured|guaranteed|warranted|certified|verified|validated|confirmed|authenticated|corroborated|substantiated|documented|recorded|logged|noted|registered|enrolled|listed|cataloged|indexed|filed|archived|stored|saved|preserved|maintained|sustained|continued|persisted|endured|lasted|survived|outlasted|overcame|conquered|defeated|vanquished|triumphed|prevailed|succeeded|excelled|outperformed|surpassed|exceeded|outshone|outdid|outstripped|outranked|outclassed|outmatched|outwitted|outsmarted|outmaneuvered|outperformed|excelled|surpassed|exceeded|surmounted|overcame|conquered|vanquished|triumphed|prevailed|succeeded|excelled|prospered|flourished|thrived|bloomed|blossomed|prospered|succeeded|triumphed|prevailed|won|conquered|dominated|mastered|ruled|governed|led|directed|guided|steered|navigated|piloted|captained|commanded|headed|managed|oversaw|supervised|administered|regulated|controlled)",
        r"(also|in addition|furthermore|additionally|moreover|besides)",
        r"(using|leveraging|utilizing|employing|applying|implementing|adopting|executing|deploying|introducing|establishing|creating|developing|designing|building|constructing|engineering|programming|coding|producing|generating|manufacturing|constructing|forming|shaping|molding|sculpting|crafting|refining|polishing|perfecting|enhancing|amplifying|magnifying|boosting|elevating|advancing|progressing|evolving|maturing|developing|growing|expanding|scaling|proliferating|multiplying|duplicating|replicating|reproducing|expanding|extending|broadening|widening|deepening|strengthening|fortifying|reinforcing|solidifying|stabilizing|securing|protecting|guarding|defending|shielding|ensuring|guaranteeing|warranting|certifying|verifying|validating|confirming|authenticating|corroborating|substantiating|documenting|recording|logging|noting|registering|enrolling|listing|cataloging|indexing|filing|archiving|storing|saving|preserving|maintaining|sustaining|continuing|persisting|enduring|lasting|surviving|outlasting|overcoming|conquering|defeating|vanquishing|triumphing|prevailing|succeeding|excelling|outperforming|surpassing|exceeding|outshining|outdoing|outstripping|outranking|outclassing|outmatching|outwitting|outsmarting|outmaneuvering|outperforming|excelling|surpassing|exceeding|surmounting|overcoming|conquering|vanquishing|triumphing|prevailing|succeeding|excelling|prospering|flourishing|thriving|blooming|blossoming|prospering|succeeding|triumphing|prevailing|winning|conquering|dominating|mastering|ruling|governing|leading|directing|guiding|steering|navigating|piloting|captaining|commanding|heading|managing|overseeing|supervising|administering|regulating|controlling|governing|managing|directing|guiding|steering|navigating|piloting|captaining|commanding|heading|administering|regulating|controlling|governed|managed|directed|guided|steered|navigated|piloted|captained|commanded|headed|administered|regulated|controlled)",
    ],
    "result": [
        r"(as a result|consequently|therefore|this led to|this resulted in)",
        r"(the outcome|the result|the impact|the effect)",
        r"(we (achieved|accomplished|reduced|increased|improved|saved|delivered|completed|met|exceeded|surpassed|outperformed|won|gained|achieved|attained|realized|fulfilled|completed|concluded|finished|terminated|ended|concluded|resolved|settled|decided|determined|established|confirmed|verified|validated|verified|confirmed|authenticated|corroborated|substantiated|documented|recorded|logged|noted|registered|enrolled|listed|cataloged|indexed|filed|archived|stored|saved|preserved|maintained|sustained|continued|persisted|endured|lasted|survived|outlasted|overcame|conquered|defeated|vanquished|triumphed|prevailed|succeeded|excelled|outperformed|surpassed|exceeded|outshone|outdid|outstripped|outranked|outclassed|outmatched|outwitted|outsmarted|outmaneuvered|outperformed|excelled|surpassed|exceeded|surmounted|overcame|conquered|vanquished|triumphed|prevailed|succeeded|excelled|prospered|flourished|thrived|bloomed|blossomed|prospered|succeeded|triumphed|prevailed|won|conquered|dominated|mastered))",
        r"(\d+%|\d+x|\$\d+|saved|reduced by|increased by|improved by|grew by)",
        r"(achieved|accomplished|delivered|completed|finished|concluded|resolved|settled|decided|determined|established|confirmed|verified|validated|confirmed|authenticated|corroborated|substantiated|documented|recorded|logged|noted|registered)",
        r"(improved|increased|reduced|decreased|saved|gained|grew|expanded|scaled|boosted|elevated|advanced|progressed|evolved|matured|developed)",
        r"(successfully|effectively|efficiently|productively|successfully|triumphantly|victoriously|conclusively)",
        r"(our team|i was able to|i (managed|succeeded|was able) to)",
        r"(the feedback (was|from)|customers (said|reported|noted|mentioned)|users (loved|appreciated|enjoyed|preferred)|management (approved|supported|endorsed|praised))",
        r"(ROI|KPI|metric|metric|benchmark|target|goal|objective|milestone)",
        r"(leaderboard|ranking|award|recognition|promotion|raise|bonus|commendation)",
    ],
}


def detect_questions(text: str) -> List[Dict[str, Any]]:
    """Detect interview questions from transcript text."""
    questions = []
    sentences = re.split(r'(?<=[.?])\s+', text)

    q_idx = 0
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence or len(sentence) < 10:
            continue

        is_question = (
            sentence.endswith("?") or
            sentence.lower().startswith(("what", "how", "why", "can you", "could you",
                                         "do you", "have you", "tell me", "describe",
                                         "explain", "give me", "would you", "if you"))
        )

        if is_question:
            category = classify_question(sentence)
            questions.append({
                "index": q_idx,
                "text": sentence,
                "category": category,
                "position": text.find(sentence),
            })
            q_idx += 1

    return questions


def classify_question(question: str) -> str:
    """Classify question into category."""
    q_lower = question.lower()
    for category, patterns in QUESTION_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, q_lower):
                return category
    return "general"


def analyze_star(text: str) -> Dict[str, Any]:
    """Analyze text for STAR framework components."""
    text_lower = text.lower()
    results = {}

    for component, indicators in STAR_INDICATORS.items():
        matches = 0
        for indicator in indicators:
            try:
                if re.search(indicator, text_lower):
                    matches += 1
            except re.error:
                pass
        results[component] = {
            "present": matches >= 1,
            "confidence": min(matches / 2, 1.0),
            "match_count": matches,
        }

    components_present = sum(1 for v in results.values() if v["present"])
    star_score = round((components_present / 4) * 100, 1)

    return {
        "situation": results["situation"]["present"],
        "task": results["task"]["present"],
        "action": results["action"]["present"],
        "result": results["result"]["present"],
        "score": star_score,
        "components_present": components_present,
    }


def analyze_content(text: str, is_behavioral: bool = False) -> Dict[str, Any]:
    """Comprehensive content analysis."""
    words = re.split(r'\s+', text)
    words_lower = [w.lower().strip(".,!?;:\"'()") for w in words if w.strip()]
    sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]

    word_count = len(words_lower)
    sentence_count = len(sentences)

    # Vocabulary diversity
    unique_words = set(words_lower)
    vocab_diversity = len(unique_words) / len(words_lower) if words_lower else 0

    # Repetition
    word_freq = Counter(words_lower)
    repeated = sum(c - 1 for c in word_freq.values() if c > 2)
    repetition_rate = repeated / len(words_lower) if words_lower else 0

    # Sentiment (basic)
    positive_words = {"good", "great", "excellent", "successful", "achieved", "improved",
                      "increased", "reduced", "delivered", "accomplished", "effective",
                      "efficient", "strong", "positive", "benefit", "advantage", "best",
                      "innovative", "creative", "solution", "success", "win", "achieve"}
    negative_words = {"problem", "issue", "challenge", "difficult", "failed", "error",
                      "mistake", "weakness", "concern", "risk", "unfortunately", "unable",
                      "struggle", "frustrated", "stuck", "complicated"}

    pos_count = sum(1 for w in words_lower if w in positive_words)
    neg_count = sum(1 for w in words_lower if w in negative_words)
    total_sentiment = pos_count + neg_count
    sentiment = (pos_count - neg_count) / total_sentiment if total_sentiment > 0 else 0

    # Average sentence length
    avg_sentence_len = word_count / sentence_count if sentence_count > 0 else 0

    # Clarity: based on average sentence length and vocabulary diversity
    clarity_score = 50.0
    if 10 <= avg_sentence_len <= 25:
        clarity_score += 25
    elif avg_sentence_len < 10:
        clarity_score += 10
    else:
        clarity_score += 5

    if vocab_diversity >= 0.7:
        clarity_score += 20
    elif vocab_diversity >= 0.5:
        clarity_score += 10
    else:
        clarity_score += 0

    clarity_score = min(100, clarity_score)

    # Fluency
    fluency_score = 50.0
    if word_count > 20:
        fluency_score += 20
    if vocab_diversity > 0.6:
        fluency_score += 15
    if repetition_rate < 0.1:
        fluency_score += 15
    fluency_score = min(100, fluency_score)

    # Conciseness
    if sentence_count > 0:
        avg_words = word_count / sentence_count
        if 10 <= avg_words <= 20:
            conciseness = 90
        elif 8 <= avg_words <= 25:
            conciseness = 75
        else:
            conciseness = 55
    else:
        conciseness = 50

    # Professionalism
    prof_indicators = [
        "experience", "skill", "project", "team", "result", "solution",
        "approach", "strategy", "achieved", "delivered", "managed", "led",
        "developed", "implemented", "designed", "analyzed", "improved",
    ]
    prof_count = sum(1 for w in words_lower if w in prof_indicators)
    professionalism = min(100, 50 + prof_count * 5)

    # Keywords
    keywords = [w for w, c in word_freq.most_common(20)
                if w not in _STOP_WORDS and len(w) > 2]

    return {
        "word_count": word_count,
        "sentence_count": sentence_count,
        "vocabulary_diversity": round(vocab_diversity, 4),
        "repetition_rate": round(repetition_rate, 4),
        "sentiment": round(sentiment, 4),
        "sentiment_label": "positive" if sentiment > 0.1 else ("negative" if sentiment < -0.1 else "neutral"),
        "clarity_score": round(clarity_score, 1),
        "fluency_score": round(fluency_score, 1),
        "conciseness_score": round(conciseness, 1),
        "professionalism_score": round(professionalism, 1),
        "avg_sentence_length": round(avg_sentence_len, 1),
        "keywords": keywords,
        "positive_signals": pos_count,
        "negative_signals": neg_count,
    }


_STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
    "be", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "shall", "can", "need", "dare",
    "i", "you", "he", "she", "it", "we", "they", "me", "him", "her",
    "us", "them", "my", "your", "his", "its", "our", "their", "this",
    "that", "these", "those", "am", "so", "if", "then", "than", "too",
    "very", "just", "about", "also", "how", "what", "when", "where",
    "why", "who", "which", "while", "into", "through", "during", "before",
    "after", "above", "below", "between", "same", "such", "own", "other",
}


def extract_keywords(text: str, top_n: int = 15) -> List[Tuple[str, float]]:
    """Extract keywords with TF scores."""
    words = re.split(r'\s+', text)
    words_lower = [w.lower().strip(".,!?;:\"'()") for w in words
                   if w.strip() and len(w.strip()) > 2]

    filtered = [w for w in words_lower if w not in _STOP_WORDS]
    word_freq = Counter(filtered)
    total = len(filtered) if filtered else 1

    keywords = [(word, round(count / total, 4)) for word, count in word_freq.most_common(top_n)]
    return keywords


def segment_qa_pairs(text: str, questions: List[Dict]) -> List[Dict[str, Any]]:
    """Segment text into question-answer pairs."""
    qa_pairs = []

    if not questions:
        return [{
            "question": None,
            "answer": text,
            "start": 0,
            "end": len(text),
            "category": "full_transcript",
        }]

    for i, q in enumerate(questions):
        start = q.get("position", 0) + len(q.get("text", ""))
        end = questions[i + 1].get("position", len(text)) if i + 1 < len(questions) else len(text)
        answer_text = text[start:end].strip()

        qa_pairs.append({
            "question": q.get("text", ""),
            "question_category": q.get("category", "general"),
            "answer": answer_text,
            "start": q.get("position", 0),
            "end": end,
        })

    return qa_pairs
