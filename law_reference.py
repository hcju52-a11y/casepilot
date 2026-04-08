# 주요 법조문 참조 데이터 (core/penalty/referral 분리)

LAW_REFERENCE = {
    "임금체불": {
        "core": [
            "근로기준법 제36조 (금품 청산) — 사용자는 근로자가 사망 또는 퇴직한 경우 14일 이내에 임금, 보상금 등 일체의 금품을 지급하여야 한다.",
            "근로기준법 제43조 (임금 지급) — 임금은 통화로 직접 근로자에게 그 전액을 매월 1회 이상 일정한 기일을 정하여 지급하여야 한다.",
        ],
        "penalty": [
            "근로기준법 제109조 — 제36조, 제43조 위반 시 3년 이하의 징역 또는 3천만원 이하의 벌금",
        ],
        "referral": [],
    },
    "해고 관련": {
        "core": [
            "근로기준법 제23조 (해고 등의 제한) — 사용자는 근로자에게 정당한 이유 없이 해고, 휴직, 정직, 전직, 감봉, 그 밖의 징벌을 하지 못한다.",
            "근로기준법 제26조 (해고의 예고) — 사용자는 근로자를 해고하려면 적어도 30일 전에 예고하여야 하며, 30일 전에 예고하지 아니하였을 때에는 30일분 이상의 통상임금을 지급하여야 한다.",
            "근로기준법 제27조 (해고사유 등의 서면통지) — 사용자는 근로자를 해고하려면 해고사유와 해고시기를 서면으로 통지하여야 한다.",
        ],
        "penalty": [],
        "referral": [
            "근로기준법 제28조 (부당해고 등의 구제신청) — 부당해고를 당한 근로자는 노동위원회에 구제를 신청할 수 있다. (해고일로부터 3개월 이내)",
            "※ 부당해고 여부 판정은 노동위원회 소관",
        ],
    },
    "퇴직금": {
        "core": [
            "근로자퇴직급여 보장법 제8조 (퇴직급여제도의 설정) — 사용자는 퇴직하는 근로자에게 급여를 지급하기 위하여 퇴직급여제도를 설정하여야 한다. (계속근로기간 1년 이상)",
            "근로자퇴직급여 보장법 제9조 (퇴직금의 지급) — 퇴직금은 근로자가 퇴직한 날부터 14일 이내에 지급하여야 한다.",
        ],
        "penalty": [],
        "referral": [],
    },
    "근로조건 위반": {
        "core": [
            "근로기준법 제17조 (근로조건의 명시) — 사용자는 근로계약 체결 시 임금, 소정근로시간, 휴일, 연차유급휴가 등을 서면으로 명시하고 교부하여야 한다.",
            "근로기준법 제50조 (근로시간) — 1주간의 근로시간은 휴게시간을 제외하고 40시간을 초과할 수 없으며, 1일의 근로시간은 휴게시간을 제외하고 8시간을 초과할 수 없다.",
            "근로기준법 제56조 (연장·야간 및 휴일 근로) — 사용자는 연장근로, 야간근로(오후 10시~오전 6시), 휴일근로에 대하여 통상임금의 50% 이상을 가산하여 지급하여야 한다.",
        ],
        "penalty": [],
        "referral": [],
    },
    "최저임금": {
        "core": [
            "최저임금법 제6조 (최저임금의 효력) — 사용자는 최저임금액 이상의 임금을 지급하여야 하며, 최저임금에 미치지 못하는 임금을 정한 근로계약은 그 부분에 한하여 무효로 한다.",
            "2025년 최저시급: 10,030원 / 2026년 최저시급: 10,320원",
        ],
        "penalty": [
            "최저임금법 제28조 — 최저임금액 미만 지급 시 3년 이하의 징역 또는 2천만원 이하의 벌금",
        ],
        "referral": [],
    },
    "직장 내 괴롭힘": {
        "core": [
            "근로기준법 제76조의2 (직장 내 괴롭힘의 금지) — 사용자 또는 근로자는 직장에서의 지위 또는 관계 등의 우위를 이용하여 업무상 적정범위를 넘어 다른 근로자에게 신체적·정신적 고통을 주거나 근무환경을 악화시키는 행위를 하여서는 아니 된다.",
            "근로기준법 제76조의3 (직장 내 괴롭힘 발생 시 조치) — 사용자는 직장 내 괴롭힘 발생 사실을 인지한 경우 지체 없이 사실 확인을 위한 조사를 실시하여야 한다.",
        ],
        "penalty": [],
        "referral": [],
    },
}


def get_domain_rules(domain: str) -> dict:
    """도메인 규칙 JSON 로드. 파일 없으면 base 반환."""
    import json
    import os
    rules_dir = os.path.join(os.path.dirname(__file__), "case_rules")
    path = os.path.join(rules_dir, f"{domain}.json")
    if not os.path.exists(path):
        path = os.path.join(rules_dir, "base.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_prompt_context(domain: str) -> str:
    """도메인 규칙을 프롬프트 삽입용 텍스트로 조립."""
    base = get_domain_rules("base")
    rules_text = "[공통 규칙]\n" + "\n".join(f"- {r}" for r in base["prompt_rules"])

    if domain not in ("general", "base"):
        domain_rules = get_domain_rules(domain)
        rules_text += f"\n\n[{domain_rules['display_name']} 도메인 규칙]\n"
        rules_text += "\n".join(f"- {r}" for r in domain_rules["prompt_rules"])

        if "investigation_checklist" in domain_rules:
            rules_text += "\n\n[추가 확인사항]\n"
            rules_text += "\n".join(f"- {item}" for item in domain_rules["investigation_checklist"])

        if "caution" in domain_rules:
            rules_text += f"\n\n⚠️ {domain_rules['caution']}"

    return rules_text


def get_law_context() -> str:
    """전체 법조문을 프롬프트 삽입용 문자열로 반환"""
    lines = []
    for topic, refs in LAW_REFERENCE.items():
        lines.append(f"### {topic}")
        for item in refs["core"]:
            lines.append(f"- {item}")
        if refs["penalty"]:
            lines.append("  [벌칙]")
            for item in refs["penalty"]:
                lines.append(f"  - {item}")
        if refs["referral"]:
            lines.append("  [참고]")
            for item in refs["referral"]:
                lines.append(f"  - {item}")
        lines.append("")
    return "\n".join(lines)
