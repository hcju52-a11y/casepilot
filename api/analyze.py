"""Vercel Serverless Function — CasePilot 사건검토 API"""

import os
import sys
import json
import base64

# --- Vercel에서 프로젝트 루트를 import 경로에 추가 ---
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from prompts import SYSTEM_PROMPT, build_user_prompt, build_vision_prompt
from law_reference import get_law_context, build_prompt_context
from classifier import resolve_domain

# --- 섹션 파싱 ---
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
    """AI 응답을 6개 섹션으로 파싱"""
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


def get_system_prompt(domain_context: str = "") -> str:
    """법조문 컨텍스트를 포함한 시스템 프롬프트"""
    law_context = get_law_context()
    prompt = SYSTEM_PROMPT.format(law_context=law_context)
    if domain_context:
        prompt = f"{prompt}\n\n{domain_context}"
    return prompt


def analyze_text(text: str, doc_type: str, system_prompt: str, api_key: str) -> str:
    """OpenAI Chat Completions — 텍스트 분석"""
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
    """OpenAI GPT-4o Vision — 이미지 분석"""
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


# --- Vercel Handler (ASGI 방식이 아닌 http.server 호환) ---
from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        """CORS preflight"""
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

            doc_type = data.get("doc_type", "진정")
            domain_option = data.get("domain", "auto")
            text = data.get("text", "")
            file_base64 = data.get("file_base64", "")
            file_name = data.get("file_name", "")

            api_key = os.environ.get("OPENAI_API_KEY", "")
            if not api_key:
                self._send_json(500, {"error": "OPENAI_API_KEY 환경변수가 설정되지 않았습니다."})
                return

            # --- 도메인 결정 ---
            text_for_classify = text
            domain, classification_info = resolve_domain(domain_option, text_for_classify)
            domain_context = build_prompt_context(domain)
            system_prompt = get_system_prompt(domain_context)

            # --- 분석 실행 ---
            if file_base64:
                # 파일 모드
                file_bytes = base64.b64decode(file_base64)
                mime_type = get_mime_type(file_name)

                if file_name.lower().endswith(".txt"):
                    # txt → 텍스트 분석
                    decoded_text = file_bytes.decode("utf-8", errors="replace")
                    response_text = analyze_text(decoded_text, doc_type, system_prompt, api_key)
                elif file_name.lower().endswith(".pdf"):
                    # PDF → 첫 페이지 이미지로 변환 후 Vision
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
                        # PyMuPDF 없으면 Vision으로 직접 시도
                        response_text = analyze_vision(file_bytes, mime_type, doc_type, system_prompt, api_key)
                else:
                    # 이미지 → Vision
                    response_text = analyze_vision(file_bytes, mime_type, doc_type, system_prompt, api_key)
            elif text:
                # 텍스트 모드
                response_text = analyze_text(text, doc_type, system_prompt, api_key)
            else:
                self._send_json(400, {"error": "텍스트 또는 파일을 입력해주세요."})
                return

            # --- 응답 파싱 ---
            sections = parse_response(response_text)

            self._send_json(200, {
                "sections": sections,
                "domain": domain,
                "classification_info": classification_info,
                "is_demo": False,
            })

        except Exception as e:
            self._send_json(500, {"error": str(e)})

    def _send_json(self, status_code: int, data: dict):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
