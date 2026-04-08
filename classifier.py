"""사건 도메인 자동분류기 (키워드 기반, LLM 호출 없음)"""

CONSTRUCTION_KEYWORDS = [
    "원수급", "하도급", "일용직", "공사현장", "노무비",
    "타워크레인", "현장소장", "출역", "기성",
    "건설근로자공제회", "하수급", "원청", "하청",
    "공사", "시공", "철근", "콘크리트", "반장"
]


def keyword_classify(text: str) -> dict:
    """키워드 기반 건설 도메인 판별. LLM 호출 없이 즉시 반환."""
    hits = [kw for kw in CONSTRUCTION_KEYWORDS if kw in text]
    hit_count = len(hits)

    if hit_count >= 5:
        confidence = 0.95
    elif hit_count >= 3:
        confidence = 0.85
    elif hit_count >= 1:
        confidence = 0.50
    else:
        confidence = 0.10

    domain = "construction" if confidence >= 0.80 else "general"

    return {
        "domain": domain,
        "confidence": confidence,
        "keyword_hits": hits,
        "hit_count": hit_count
    }


def resolve_domain(user_selection: str, extracted_text: str) -> tuple:
    """
    최종 도메인 결정. 앱에서는 이 함수만 호출.
    Returns: (domain: str, classification_info: dict)
    """
    if user_selection != "auto":
        return user_selection, {"method": "manual", "domain": user_selection}

    classification = keyword_classify(extracted_text)

    if classification["confidence"] >= 0.80:
        return classification["domain"], {"method": "auto", **classification}

    return "general", {"method": "fallback", **classification}
