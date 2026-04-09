# Vision API 연동 + PDF→이미지 변환 + Ollama 로컬 Fallback

import os
import json
import base64
from typing import Optional, List
import requests as _requests

GEMINI_MODEL = "gemini-2.5-flash"
OPENAI_MODEL = "gpt-4o"

# --- Ollama 설정 ---
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:e4b")

# Ollama JSON 스키마 (마크다운 파싱 실패 시 fallback용)
_CASE_SCHEMA = {
    "type": "object",
    "properties": {
        "case_summary": {"type": "string"},
        "key_issues": {"type": "array", "items": {"type": "string"}},
        "check_points": {"type": "array", "items": {"type": "string"}},
        "handling_direction": {"type": "string"},
        "reply_draft": {"type": "string"},
    },
    "required": ["case_summary", "key_issues", "check_points", "handling_direction", "reply_draft"],
}


def _check_ollama_running() -> bool:
    """Ollama 서버 실행 여부 확인"""
    try:
        resp = _requests.get(
            OLLAMA_URL.replace("/api/generate", ""),
            timeout=3,
        )
        return resp.status_code == 200
    except Exception:
        return False


def _json_to_markdown(data: dict) -> str:
    """Ollama JSON 응답 → 기존 parse_response 호환 마크다운 변환"""
    lines = []
    if data.get("case_summary"):
        lines.append("## 📝 사건 개요")
        lines.append(data["case_summary"])
    if data.get("key_issues"):
        lines.append("\n## ⚖️ 핵심 쟁점")
        for i, issue in enumerate(data["key_issues"], 1):
            lines.append(f"{i}. {issue}")
    if data.get("check_points"):
        lines.append("\n## 🔍 추가 확인사항")
        for cp in data["check_points"]:
            lines.append(f"- {cp}")
    if data.get("handling_direction"):
        lines.append("\n## 🧭 처리방향 초안")
        lines.append(data["handling_direction"])
    if data.get("reply_draft"):
        lines.append("\n## ✉️ 회신/내부검토 초안")
        lines.append(data["reply_draft"])
    return "\n".join(lines)


def analyze_with_vision_ollama(image_bytes: bytes, mime_type: str,
                                doc_type: str, system_prompt: str,
                                model: str = None) -> str:
    """Ollama Vision API — 이미지 분석 (gemma4 멀티모달)
    마크다운 텍스트 반환 (Gemini와 동일 인터페이스)
    """
    if not _check_ollama_running():
        raise ConnectionError(
            "Ollama 서버가 실행되지 않았습니다. "
            "'ollama serve' 명령으로 먼저 실행해주세요."
        )

    use_model = model or OLLAMA_MODEL
    from prompts import build_vision_prompt
    img_b64 = base64.b64encode(image_bytes).decode("utf-8")
    user_prompt = build_vision_prompt(doc_type)

    payload = {
        "model": use_model,
        "system": system_prompt,
        "prompt": user_prompt,
        "images": [img_b64],
        "stream": False,
        "options": {"temperature": 0.1},
        "keep_alive": "10m",
    }

    resp = _requests.post(OLLAMA_URL, json=payload, timeout=180)
    resp.raise_for_status()
    response_text = resp.json().get("response", "").strip()

    # 마크다운 섹션이 정상 포함되면 그대로 반환
    if "## 📝 사건 개요" in response_text or "## ⚖️" in response_text:
        return response_text

    # 마크다운이 없으면 JSON 스키마 모드로 재시도
    return _retry_with_json_schema(system_prompt, user_prompt, images=[img_b64])


def analyze_text_ollama(text: str, doc_type: str, system_prompt: str,
                        model: str = None) -> str:
    """Ollama 텍스트 전용 분석
    마크다운 텍스트 반환 (Gemini와 동일 인터페이스)
    """
    if not _check_ollama_running():
        raise ConnectionError(
            "Ollama 서버가 실행되지 않았습니다. "
            "'ollama serve' 명령으로 먼저 실행해주세요."
        )

    use_model = model or OLLAMA_MODEL
    from prompts import build_user_prompt
    user_prompt = build_user_prompt(text, doc_type)

    payload = {
        "model": use_model,
        "system": system_prompt,
        "prompt": user_prompt,
        "stream": False,
        "options": {"temperature": 0.1},
        "keep_alive": "10m",
    }

    resp = _requests.post(OLLAMA_URL, json=payload, timeout=120)
    resp.raise_for_status()
    response_text = resp.json().get("response", "").strip()

    if "## 📝 사건 개요" in response_text or "## ⚖️" in response_text:
        return response_text

    return _retry_with_json_schema(system_prompt, user_prompt)


def _retry_with_json_schema(system_prompt: str, user_prompt: str,
                             images: Optional[List[str]] = None) -> str:
    """마크다운 출력 실패 시 JSON 스키마 강제 모드로 재시도 → 마크다운 변환"""
    payload = {
        "model": OLLAMA_MODEL,
        "system": system_prompt,
        "prompt": user_prompt + "\n\n반드시 JSON으로만 응답하세요.",
        "format": _CASE_SCHEMA,
        "stream": False,
        "options": {"temperature": 0.1},
        "keep_alive": "10m",
    }
    if images:
        payload["images"] = images

    resp = _requests.post(OLLAMA_URL, json=payload, timeout=180)
    resp.raise_for_status()
    raw = resp.json().get("response", "").strip()

    try:
        data = json.loads(raw)
        return _json_to_markdown(data)
    except (json.JSONDecodeError, KeyError):
        # 최후 수단: 원문 그대로 반환 (parse_response fallback 처리)
        return raw if raw else "⚠️ Ollama 응답을 파싱할 수 없습니다."


def pdf_to_images(pdf_bytes: bytes, max_pages: int = 3) -> tuple:
    """PyMuPDF(fitz)로 PDF 페이지별 PNG 변환 (dpi=200)
    반환: (이미지 바이트 리스트, truncated 여부)
    """
    try:
        import fitz

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_pages = len(doc)
        truncated = total_pages > max_pages
        pages_to_process = min(total_pages, max_pages)

        images = []
        for i in range(pages_to_process):
            page = doc[i]
            # dpi=200 → zoom = 200/72
            zoom = 200 / 72
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            images.append(pix.tobytes("png"))

        doc.close()
        return images, truncated
    except Exception:
        return [], False


def fix_image_orientation(image_bytes: bytes) -> bytes:
    """EXIF 방향 메타데이터에 따라 이미지 회전 보정 (스마트폰 촬영 이미지 대응)"""
    from PIL import Image, ImageOps
    import io

    img = Image.open(io.BytesIO(image_bytes))
    img = ImageOps.exif_transpose(img)

    buf = io.BytesIO()
    fmt = img.format or "PNG"
    img.save(buf, format=fmt)
    return buf.getvalue()


def get_mime_type(filename: str) -> str:
    """파일 확장자 기준 MIME 타입 반환"""
    name = filename.lower()
    if name.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if name.endswith(".png"):
        return "image/png"
    return "image/png"


def analyze_with_vision_gemini(image_bytes: bytes, mime_type: str, doc_type: str,
                                system_prompt: str, api_key: str) -> str:
    """Gemini Vision API — 이미지 분석"""
    from google import genai
    from google.genai import types

    from prompts import build_vision_prompt

    user_prompt = build_vision_prompt(doc_type)

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            user_prompt,
        ],
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.1,
            max_output_tokens=8192,
        ),
    )
    return response.text


def analyze_text_gemini(text: str, doc_type: str, system_prompt: str, api_key: str) -> str:
    """Gemini API 텍스트 전용"""
    from google import genai
    from google.genai import types

    from prompts import build_user_prompt

    user_prompt = build_user_prompt(text, doc_type)

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.1,
            max_output_tokens=8192,
        ),
    )
    return response.text


def analyze_text_openai(text: str, doc_type: str, system_prompt: str, api_key: str) -> str:
    """OpenAI Chat Completions API 텍스트 전용"""
    from openai import OpenAI

    from prompts import build_user_prompt

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


def analyze_with_vision_openai(image_bytes: bytes, mime_type: str, doc_type: str,
                                system_prompt: str, api_key: str) -> str:
    """OpenAI GPT-4o Vision API — 이미지 분석"""
    from openai import OpenAI

    from prompts import build_vision_prompt

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
