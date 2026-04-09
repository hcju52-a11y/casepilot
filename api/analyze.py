"""Vercel Serverless Function — CasePilot 사건검토 API (all-in-one)"""

import os
import json
import base64
from http.server import BaseHTTPRequestHandler

# ────────────────────────────────────────────
# [INLINED] prompts.py
# ────────────────────────────────────────────

SYSTEM_PROMPT = """당신은 대한민국 고용노동부 소속 근로감독관의 초동검토를 돕는 업무보조 AI입니다.

[역할]
- 접수된 진정서/고소장/민원을 분석하여 초동검토 초안을 작성합니다.
- 최종 판단을 단정하지 말고, "가능성", "검토 필요" 형식으로 작성합니다.

[출력 형식 — 반드시 아래 6개 섹션으로 작성]

## 📝 사건 개요
누가 누구에게 무엇을 주장하는지 3~5문장으로 요약

## ⚖️ 핵심 쟁점
위반 의심 항목을 번호 리스트로 (3개 이내)
각 쟁점별 짧은 설명 1~2문장

## 📖 검토 포인트
각 쟁점에 해당하는 법 조항명과 조문 핵심 내용
법 위반 가능성 및 필요한 사실관계
(벌칙 조항은 "**[참고 — 벌칙]**" 별도 소제목으로 분리)
부당해고 등 노동위원회 구제신청 대상 사안은 별도 안내 명시

## 🔍 추가 확인사항
조사 시 반드시 확인해야 할 항목 (서류/일정/진술/증빙)
"~~ 확인 필요" 형태로 구체적으로

## 🧭 처리방향 초안
조사 방향, 우선 확인사항, 주의할 표현
시정지시/과태료/기각/추가조사 등 방향 제시

## ✉️ 회신/내부검토 초안
민원인 답변 초안 또는 내부 검토 메모 (공공기관 격식체)
너무 길지 않게 (10줄 이내)

[금지사항]
- "위법이다", "범죄이다" 등 단정적 법적 결론 금지
- 법조문 허위 인용 금지 — 불확실하면 "확인 필요"로 명시
- 감정적 표현 금지
- 민원인/피진정인을 일방적으로 비난하는 표현 금지
- 입력 문서에 없는 사실을 추정하지 말 것
- 모호한 부분은 반드시 "추가 확인 필요"로 명시
- "부당해고이다/아니다" 단정 금지 — 해고예고·서면통지 요건 검토 후 노동위원회 구제신청 안내 여부를 제시할 것

[문체]
- 한국어, 실무 문체, 짧고 명확하게
- 공공기관에 적합한 격식체 사용

[참고 법조문]
{law_context}"""


def build_user_prompt(text: str, doc_type: str) -> str:
    return f"다음은 접수된 {doc_type}입니다. 초동분석을 수행해주세요.\n\n---\n{text}\n---"


def build_vision_prompt(doc_type: str) -> str:
    return f"이 이미지는 접수된 {doc_type}입니다. 문서 내용을 읽고 초동분석을 수행해주세요."


# ────────────────────────────────────────────
# [INLINED] law_reference.py
# ────────────────────────────────────────────

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

# ── 도메인 규칙 (JSON 파일 대신 인라인) ──

CASE_RULES = {
    "base": {
        "domain": "base",
        "display_name": "공통",
        "prompt_rules": [
            "법 위반 여부를 단정하지 말 것",
            "확인되지 않은 사실은 '추가 확인 필요'로 표시할 것",
            "감독관의 판단 보조용으로 작성할 것",
        ],
    },
    "construction": {
        "domain": "construction",
        "display_name": "건설",
        "prompt_rules": [
            "건설업 특수성을 반영할 것",
            "원수급인, 하수급인, 노무수급 관계를 구분하여 검토할 것",
            "건설일용근로자 여부를 확인할 것",
            "임금지급 주체와 실제 사용자를 구분하여 검토할 것",
            "근로자성, 사용종속성, 출역 방식, 작업지휘 관계를 점검할 것",
        ],
        "investigation_checklist": [
            "공사명 및 현장 위치",
            "원수급인/하수급인 명칭",
            "실제 지휘감독자",
            "출역기록 또는 작업일지 존재 여부",
            "임금 산정 방식 (일당/월급/도급)",
            "퇴직공제부금 가입 여부",
        ],
        "caution": "건설업 사건은 계약 형식보다 실제 지휘감독 및 노무 제공 실태를 중심으로 검토",
    },
}


def get_law_context() -> str:
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


def build_prompt_context(domain: str) -> str:
    base = CASE_RULES["base"]
    rules_text = "[공통 규칙]\n" + "\n".join(f"- {r}" for r in base["prompt_rules"])

    if domain not in ("general", "base"):
        domain_rules = CASE_RULES.get(domain, CASE_RULES["base"])
        rules_text += f"\n\n[{domain_rules['display_name']} 도메인 규칙]\n"
        rules_text += "\n".join(f"- {r}" for r in domain_rules["prompt_rules"])

        if "investigation_checklist" in domain_rules:
            rules_text += "\n\n[추가 확인사항]\n"
            rules_text += "\n".join(f"- {item}" for item in domain_rules["investigation_checklist"])

        if "caution" in domain_rules:
            rules_text += f"\n\n⚠️ {domain_rules['caution']}"

    return rules_text


# ────────────────────────────────────────────
# [INLINED] classifier.py
# ────────────────────────────────────────────

CONSTRUCTION_KEYWORDS = [
    # 핵심 키워드 (GPT 응답에서 자주 등장)
    "건설", "현장", "공사", "시공", "건축", "토목",
    # 계약·조직 관계
    "원수급", "하도급", "원청", "하청", "하수급", "직장수급인",
    # 근로 형태
    "일용직", "출역", "노무비", "기성",
    # 현장 관련
    "공사현장", "현장소장", "타워크레인", "철근", "콘크리트", "반장",
    # 진정서 양식 건설공사 난
    "건설공사", "공사명칭", "공사명", "현장소재지", "준공여부",
    "건설회사", "현장전화", "공사중", "준공", "개인업자", "직영",
    # GPT Vision 응답에서 등장할 수 있는 표현
    "주택공사", "아파트", "발주", "시공사", "건설근로자공제회",
]


# 진정서 양식의 "건설공사" 난 필드명 — 하나라도 있으면 건설 확정
CONSTRUCTION_FORM_FIELDS = [
    "건설공사", "공사명칭", "현장소재지", "건설회사", "직장수급인",
    "현장전화", "준공여부",
]


def keyword_classify(text: str) -> dict:
    # 1단계: 진정서 양식 건설공사 난 필드 감지 (강력 신호)
    form_hits = [kw for kw in CONSTRUCTION_FORM_FIELDS if kw in text]
    if form_hits:
        return {
            "domain": "construction",
            "confidence": 0.95,
            "keyword_hits": form_hits,
            "hit_count": len(form_hits),
            "reason": "진정서 건설공사 난 감지",
        }

    # 2단계: 일반 키워드 매칭
    hits = [kw for kw in CONSTRUCTION_KEYWORDS if kw in text]
    hit_count = len(hits)
    if hit_count >= 5:
        confidence = 0.95
    elif hit_count >= 2:
        confidence = 0.85
    elif hit_count >= 1:
        confidence = 0.65
    else:
        confidence = 0.10
    domain = "construction" if confidence >= 0.80 else "general"
    return {"domain": domain, "confidence": confidence, "keyword_hits": hits, "hit_count": hit_count}


def resolve_domain(user_selection: str, extracted_text: str) -> tuple:
    if user_selection != "auto":
        return user_selection, {"method": "manual", "domain": user_selection}
    classification = keyword_classify(extracted_text)
    if classification["confidence"] >= 0.80:
        return classification["domain"], {"method": "auto", **classification}
    return "general", {"method": "fallback", **classification}


# ────────────────────────────────────────────
# 사건 유형 자동 분류
# ────────────────────────────────────────────

DOC_TYPE_KEYWORDS = {
    "고소": ["고소", "고발", "고소장", "고발장", "고소(고발)"],
    "진정": ["진정", "진정서", "진정인"],
    "민원": ["민원", "민원서", "민원인", "질의", "건의"],
}


def detect_doc_type(text: str) -> tuple:
    """텍스트에서 사건 유형을 자동 판별.
    Returns: (doc_type: str, detection_info: dict)
    """
    scores = {}
    for dtype, keywords in DOC_TYPE_KEYWORDS.items():
        hits = [kw for kw in keywords if kw in text]
        scores[dtype] = len(hits)

    best = max(scores, key=scores.get)
    if scores[best] > 0:
        return best, {"method": "auto", "detected": best, "scores": scores}
    return "기타", {"method": "fallback", "detected": "기타", "scores": scores}


# ────────────────────────────────────────────
# 섹션 파싱
# ────────────────────────────────────────────

SECTION_TITLES = [
    "## \U0001f4dd 사건 개요",
    "## \u2696\ufe0f 핵심 쟁점",
    "## \U0001f4d6 검토 포인트",
    "## \U0001f50d 추가 확인사항",
    "## \U0001f9ed 처리방향 초안",
    "## \u2709\ufe0f 회신/내부검토 초안",
]
SECTION_KEYS = ["summary", "issues", "review_points", "questions", "direction", "reply_draft"]

OPENAI_MODEL = "gpt-4o"


def parse_response(text: str) -> dict:
    result = {}
    positions = []
    for title in SECTION_TITLES:
        pos = text.find(title)
        positions.append(pos)
    found = [(i, p) for i, p in enumerate(positions) if p != -1]
    if not found:
        return {"fallback": text}
    found.sort(key=lambda x: x[1])
    for idx, (section_idx, pos) in enumerate(found):
        title = SECTION_TITLES[section_idx]
        key = SECTION_KEYS[section_idx]
        start = pos + len(title)
        end = found[idx + 1][1] if idx + 1 < len(found) else len(text)
        content = text[start:end].strip()
        if key == "review_points":
            penalty_marker = "**[참고 — 벌칙]**"
            penalty_pos = content.find(penalty_marker)
            if penalty_pos != -1:
                result["review_penalty"] = content[penalty_pos + len(penalty_marker):].strip()
                content = content[:penalty_pos].strip()
        result[key] = content
    return result


# ────────────────────────────────────────────
# AI 호출
# ────────────────────────────────────────────

def get_system_prompt(domain_context: str = "") -> str:
    law_context = get_law_context()
    prompt = SYSTEM_PROMPT.format(law_context=law_context)
    if domain_context:
        prompt = f"{prompt}\n\n{domain_context}"
    return prompt


def analyze_text(text: str, doc_type: str, system_prompt: str, api_key: str) -> str:
    from openai import OpenAI
    user_prompt = build_user_prompt(text, doc_type)
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        max_tokens=4096,
        temperature=0.1,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content


def analyze_vision(image_bytes: bytes, mime_type: str, doc_type: str,
                   system_prompt: str, api_key: str) -> str:
    from openai import OpenAI
    user_prompt = build_vision_prompt(doc_type)
    img_b64 = base64.b64encode(image_bytes).decode("utf-8")
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        max_tokens=4096,
        temperature=0.1,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{img_b64}",
                            "detail": "high",
                        },
                    },
                    {"type": "text", "text": user_prompt},
                ],
            },
        ],
    )
    return response.choices[0].message.content


def get_mime_type(filename: str) -> str:
    name = filename.lower()
    if name.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if name.endswith(".png"):
        return "image/png"
    if name.endswith(".pdf"):
        return "application/pdf"
    return "application/octet-stream"


# ────────────────────────────────────────────
# Vercel Handler
# ────────────────────────────────────────────

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8"))

            doc_type_option = data.get("doc_type", "진정")
            domain_option = data.get("domain", "auto")
            text = data.get("text", "")
            file_base64 = data.get("file_base64", "")
            file_name = data.get("file_name", "")

            api_key = os.environ.get("OPENAI_API_KEY", "")
            if not api_key:
                self._send_json(500, {"error": "OPENAI_API_KEY 환경변수가 설정되지 않았습니다."})
                return

            # 사건 유형 자동 판별
            doc_type_info = None
            if doc_type_option == "auto" and text:
                doc_type, doc_type_info = detect_doc_type(text)
            elif doc_type_option == "auto":
                doc_type = "진정"  # 파일 업로드 시 기본값 (Vision 분석 후 재판별)
                doc_type_info = {"method": "default", "detected": "진정"}
            else:
                doc_type = doc_type_option

            # 도메인 결정
            text_for_classify = text
            domain, classification_info = resolve_domain(domain_option, text_for_classify)
            domain_context = build_prompt_context(domain)
            system_prompt = get_system_prompt(domain_context)

            # 분석 실행
            if file_base64:
                file_bytes = base64.b64decode(file_base64)
                mime_type = get_mime_type(file_name)

                if file_name.lower().endswith(".txt"):
                    decoded_text = file_bytes.decode("utf-8", errors="replace")
                    # txt 파일에서 사건 유형 + 도메인 자동 판별
                    if doc_type_option == "auto":
                        doc_type, doc_type_info = detect_doc_type(decoded_text)
                    if domain_option == "auto":
                        domain, classification_info = resolve_domain("auto", decoded_text)
                        domain_context = build_prompt_context(domain)
                        system_prompt = get_system_prompt(domain_context)
                    response_text = analyze_text(decoded_text, doc_type, system_prompt, api_key)
                elif file_name.lower().endswith(".pdf"):
                    try:
                        import fitz
                        doc = fitz.open(stream=file_bytes, filetype="pdf")
                        page = doc[0]
                        zoom = 200 / 72
                        mat = fitz.Matrix(zoom, zoom)
                        pix = page.get_pixmap(matrix=mat)
                        img_bytes = pix.tobytes("png")
                        doc.close()
                        response_text = analyze_vision(img_bytes, "image/png", doc_type, system_prompt, api_key)
                    except ImportError:
                        response_text = analyze_vision(file_bytes, mime_type, doc_type, system_prompt, api_key)
                else:
                    # 이미지 파일 → Vision 분석
                    response_text = analyze_vision(file_bytes, mime_type, doc_type, system_prompt, api_key)

                # Vision/파일 분석 결과에서 사건 유형 + 도메인 재판별
                if response_text:
                    if doc_type_option == "auto":
                        detected_type, det_info = detect_doc_type(response_text)
                        if det_info["method"] != "fallback":
                            doc_type = detected_type
                            doc_type_info = det_info
                    if domain_option == "auto":
                        domain, classification_info = resolve_domain("auto", response_text)
            elif text:
                response_text = analyze_text(text, doc_type, system_prompt, api_key)
            else:
                self._send_json(400, {"error": "텍스트 또는 파일을 입력해주세요."})
                return

            sections = parse_response(response_text)

            result = {
                "sections": sections,
                "domain": domain,
                "classification_info": classification_info,
                "doc_type": doc_type,
                "is_demo": False,
            }
            if doc_type_info:
                result["doc_type_info"] = doc_type_info

            self._send_json(200, result)

        except Exception as e:
            self._send_json(500, {"error": str(e)})

    def _send_json(self, status_code: int, data: dict):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
