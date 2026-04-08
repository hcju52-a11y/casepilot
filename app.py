import os
import streamlit as st
from dotenv import load_dotenv

from prompts import SYSTEM_PROMPT, build_user_prompt
from law_reference import get_law_context, build_prompt_context
from classifier import resolve_domain
from samples import SAMPLES
from demo_results import DEMO_RESULT
from pii_mask import mask_pii
from vision_utils import (
    pdf_to_images,
    get_mime_type,
    fix_image_orientation,
    analyze_with_vision_gemini,
    analyze_text_gemini,
    analyze_text_openai,
    analyze_with_vision_ollama,
    analyze_text_ollama,
)

# --- 환경 변수 로드 ---
load_dotenv()

# --- LLM 백엔드 (gemini | openai | ollama) ---
LLM_BACKEND = os.getenv("LLM_BACKEND", "gemini")

# --- 모델 상수 ---
GEMINI_MODEL = "gemini-2.5-flash"
OPENAI_MODEL = "gpt-4o"

# --- 섹션 제목 (파싱 anchor) ---
SECTION_TITLES = [
    "## 📝 사건 개요",
    "## ⚖️ 핵심 쟁점",
    "## 📖 검토 포인트",
    "## 🔍 추가 확인사항",
    "## 🧭 처리방향 초안",
    "## ✉️ 회신/내부검토 초안",
]

SECTION_KEYS = ["summary", "issues", "review_points", "questions", "direction", "reply_draft"]


# --- 페이지 설정 ---
st.set_page_config(
    page_title="사건검토 도우미",
    page_icon="🔎",
    layout="wide",
)

# --- 헤더 ---
st.title("🔎 사건검토 도우미")
st.caption("by Syndicate Lab")
st.markdown("진정·민원·고소 문서를 빠르게 검토하고 핵심 쟁점과 처리방향 초안을 정리하는 AI 보조도구")

# --- Session State 초기화 ---
if "input_text" not in st.session_state:
    st.session_state["input_text"] = ""

# --- 사이드바 ---
with st.sidebar:
    st.header("📋 사건 유형")
    doc_type = st.radio(
        "유형 선택",
        ["진정", "고소", "민원", "기타"],
        label_visibility="collapsed",
    )

    st.header("📝 샘플 불러오기")
    if st.button("임금체불", use_container_width=True):
        st.session_state["input_text"] = SAMPLES["임금체불"]
        st.rerun()
    if st.button("해고 관련", use_container_width=True):
        st.session_state["input_text"] = SAMPLES["해고 관련"]
        st.rerun()
    if st.button("계약서 미작성", use_container_width=True):
        st.session_state["input_text"] = SAMPLES["계약서 미작성"]
        st.rerun()

    st.header("🔧 AI 모델 선택")
    _default_idx = 2 if LLM_BACKEND == "ollama" else 0
    model_choice = st.selectbox(
        "모델",
        ["Gemini (Google)", "GPT-4o (OpenAI)", "🏠 Gemma 로컬 (Ollama)"],
        index=_default_idx,
        label_visibility="collapsed",
    )
    selected_ollama_model = None
    if model_choice == "🏠 Gemma 로컬 (Ollama)":
        ollama_model_choice = st.selectbox(
            "Ollama 모델",
            ["gemma4:e4b (9.6GB, 권장)", "gemma4:26b (18GB, 고품질)", "gemma4:e2b (7.2GB, 경량)"],
            label_visibility="collapsed",
        )
        selected_ollama_model = ollama_model_choice.split(" ")[0]

    st.markdown("---")
    st.subheader("🏗️ 사건 도메인")
    domain_option = st.selectbox(
        "도메인 선택",
        options=["auto", "general", "construction"],
        format_func=lambda x: {
            "auto": "🔄 자동 판별",
            "general": "📋 일반",
            "construction": "🏗️ 건설"
        }[x],
        index=0,
    )


# --- 응답 파싱 ---
def parse_response(text: str) -> dict:
    """AI 응답을 6개 섹션으로 파싱. 실패 시 전체 텍스트를 fallback으로 표시."""
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

        if idx + 1 < len(found):
            end = found[idx + 1][1]
        else:
            end = len(text)

        content = text[start:end].strip()

        if key == "review_points":
            penalty_marker = "**[참고 — 벌칙]**"
            penalty_pos = content.find(penalty_marker)
            if penalty_pos != -1:
                result["review_penalty"] = content[penalty_pos + len(penalty_marker):].strip()
                content = content[:penalty_pos].strip()

        result[key] = content

    return result


def display_demo_result():
    """데모 모드 결과 표시"""
    st.info("⚡ 데모 모드: 사전 생성된 분석 결과입니다.")
    display_sections(DEMO_RESULT)


def display_sections(sections: dict):
    """6개 섹션을 2컬럼 레이아웃으로 표시"""
    if "fallback" in sections:
        st.markdown(sections["fallback"])
        return

    col1, col2 = st.columns(2)

    with col1:
        if "summary" in sections:
            st.subheader("📝 사건 개요")
            st.markdown(sections["summary"])

        if "issues" in sections:
            st.subheader("⚖️ 핵심 쟁점")
            st.markdown(sections["issues"])

        if "review_points" in sections:
            st.subheader("📖 검토 포인트")
            st.markdown(sections["review_points"])
            if "review_penalty" in sections:
                with st.expander("⚠️ 벌칙 조항 참고"):
                    st.markdown(sections["review_penalty"])

    with col2:
        if "questions" in sections:
            st.subheader("🔍 추가 확인사항")
            st.markdown(sections["questions"])

        if "direction" in sections:
            st.subheader("🧭 처리방향 초안")
            st.markdown(sections["direction"])

        if "reply_draft" in sections:
            st.subheader("✉️ 회신/내부검토 초안")
            st.text_area(
                "회신 초안 (편집 가능)",
                value=sections["reply_draft"],
                height=200,
                label_visibility="collapsed",
            )


def get_system_prompt(domain_context: str = "") -> str:
    """법조문 컨텍스트를 포함한 시스템 프롬프트 반환"""
    law_context = get_law_context()
    prompt = SYSTEM_PROMPT.format(law_context=law_context)
    if domain_context:
        prompt = f"{prompt}\n\n{domain_context}"
    return prompt


def is_ollama_mode() -> bool:
    """현재 Ollama 로컬 모드인지 판별"""
    return model_choice == "🏠 Gemma 로컬 (Ollama)"


def get_api_key() -> str:
    """선택된 모델에 맞는 API Key 반환 (Ollama는 불필요)"""
    if is_ollama_mode():
        return "__ollama_local__"
    if model_choice == "Gemini (Google)":
        return os.environ.get("GEMINI_API_KEY", "")
    else:
        return os.environ.get("OPENAI_API_KEY", "")


def run_text_analysis(text: str, domain_context: str = "") -> str:
    """텍스트 분석 API 호출 — 백엔드 분기"""
    system_prompt = get_system_prompt(domain_context)

    if is_ollama_mode():
        return analyze_text_ollama(text, doc_type, system_prompt, model=selected_ollama_model)

    api_key = get_api_key()
    if model_choice == "Gemini (Google)":
        return analyze_text_gemini(text, doc_type, system_prompt, api_key)
    else:
        return analyze_text_openai(text, doc_type, system_prompt, api_key)


def run_vision_analysis(image_bytes: bytes, mime_type: str, domain_context: str = "") -> str:
    """이미지 Vision 분석 API 호출 — 백엔드 분기"""
    system_prompt = get_system_prompt(domain_context)

    if is_ollama_mode():
        return analyze_with_vision_ollama(image_bytes, mime_type, doc_type, system_prompt, model=selected_ollama_model)

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("Gemini API Key가 필요합니다. 이미지 분석은 Gemini만 지원합니다.")
    return analyze_with_vision_gemini(image_bytes, mime_type, doc_type, system_prompt, api_key)


# --- 메인 영역: 입력 방식 선택 ---
input_mode = st.radio(
    "입력 방식",
    ["텍스트 입력", "파일 업로드"],
    horizontal=True,
)

uploaded_file = None
file_text = None
file_images = None

if input_mode == "텍스트 입력":
    user_input = st.text_area(
        "진정서 내용을 입력하세요",
        height=300,
        placeholder="여기에 진정서 내용을 붙여넣으세요...",
        key="input_text",
    )
else:
    uploaded_file = st.file_uploader(
        "파일을 업로드하세요",
        type=["pdf", "txt", "jpg", "jpeg", "png"],
    )

    if uploaded_file is not None:
        file_bytes = uploaded_file.read()
        file_name = uploaded_file.name.lower()

        if file_name.endswith(".txt"):
            file_text = file_bytes.decode("utf-8", errors="replace")
            st.text_area("업로드된 텍스트 미리보기", value=file_text[:2000], height=200, disabled=True)

        elif file_name.endswith(".pdf"):
            images, truncated = pdf_to_images(file_bytes, max_pages=3)
            if truncated:
                st.warning("PDF는 처음 3페이지만 분석됩니다.")
            if images:
                # 1차 버전: 첫 페이지만 우선 분석
                file_images = [(images[0], "image/png")]
                st.image(images[0], caption="PDF 첫 페이지 미리보기", use_container_width=True)
            else:
                st.error("PDF를 읽을 수 없습니다.")

        elif file_name.endswith((".jpg", ".jpeg", ".png")):
            mime = get_mime_type(file_name)
            file_bytes = fix_image_orientation(file_bytes)
            file_images = [(file_bytes, mime)]
            st.image(file_bytes, caption="업로드된 이미지 미리보기", use_container_width=True)

# --- 실행 버튼 ---
if st.button("🔎 검토 시작", type="primary", use_container_width=True):
    api_key = get_api_key()

    # Ollama 모드에서는 API 키 불필요 — 서버 연결만 확인
    if is_ollama_mode():
        from vision_utils import _check_ollama_running
        if not _check_ollama_running():
            st.error("⚠️ Ollama 서버에 연결할 수 없습니다. `ollama serve` 명령으로 먼저 실행해주세요.")
            st.stop()
    elif not api_key:
        if input_mode == "파일 업로드" and file_images:
            gemini_key = os.environ.get("GEMINI_API_KEY", "")
            if not gemini_key:
                st.error("API Key가 설정되지 않았습니다. .env 파일 또는 Streamlit secrets를 확인해주세요.")
                st.stop()
        else:
            st.error("API Key가 설정되지 않았습니다. .env 파일 또는 Streamlit secrets를 확인해주세요.")
            st.stop()

    # --- 도메인 결정 ---
    _text_for_classify = ""
    if input_mode == "텍스트 입력":
        _text_for_classify = st.session_state.get("input_text", "")
    elif file_text is not None:
        _text_for_classify = file_text

    domain, classification_info = resolve_domain(domain_option, _text_for_classify)
    domain_context = build_prompt_context(domain)

    if domain == "construction":
        method_label = "자동 판별" if classification_info["method"] == "auto" else "수동 선택"
        st.info(f"🏗️ 건설 도메인 적용 ({method_label}) — 원수급인 연대책임 등 건설 특수 검토 포인트가 포함됩니다.")

    spinner_msg = "🏠 로컬 AI가 검토 중입니다... (로컬 환경이라 약간 시간이 소요됩니다)" if is_ollama_mode() else "AI가 검토 중입니다..."

    if input_mode == "텍스트 입력":
        if not user_input or not user_input.strip():
            st.warning("분석할 내용을 입력해주세요.")
        else:
            with st.spinner(spinner_msg):
                try:
                    response_text = run_text_analysis(user_input, domain_context)
                    label = "🏠 로컬 AI" if is_ollama_mode() else "☁️ 클라우드 AI"
                    st.success(f"✅ {label} 분석 결과입니다.")
                    sections = parse_response(response_text)
                    display_sections(sections)
                except ConnectionError as e:
                    st.error(f"🔌 Ollama 연결 오류: {e}")
                except Exception as e:
                    st.warning(f"API 호출 중 오류가 발생했습니다: {e}")
                    display_demo_result()

    elif input_mode == "파일 업로드":
        if uploaded_file is None:
            st.warning("파일을 업로드해주세요.")
        elif file_text is not None:
            # txt 파일 → 텍스트 분석
            with st.spinner(spinner_msg):
                try:
                    response_text = run_text_analysis(file_text, domain_context)
                    label = "🏠 로컬 AI" if is_ollama_mode() else "☁️ 클라우드 AI"
                    st.success(f"✅ {label} 분석 결과입니다.")
                    sections = parse_response(response_text)
                    display_sections(sections)
                except ConnectionError as e:
                    st.error(f"🔌 Ollama 연결 오류: {e}")
                except Exception as e:
                    st.warning(f"API 호출 중 오류가 발생했습니다: {e}")
                    display_demo_result()
        elif file_images is not None:
            # 이미지/PDF → Vision 분석 (Gemini만)
            if model_choice == "GPT-4o (OpenAI)":
                st.info("이미지/PDF 분석은 Gemini 또는 Gemma 로컬만 지원합니다. Gemini로 자동 전환합니다.")
            vision_spinner = "🏠 로컬 AI가 이미지를 분석 중입니다... (로컬 환경이라 약간 시간이 소요됩니다)" if is_ollama_mode() else "AI가 이미지를 분석 중입니다..."
            with st.spinner(vision_spinner):
                try:
                    img_bytes, mime_type = file_images[0]
                    response_text = run_vision_analysis(img_bytes, mime_type, domain_context)
                    label = "🏠 로컬 AI" if is_ollama_mode() else "☁️ 클라우드 AI"
                    st.success(f"✅ {label} 분석 결과입니다.")
                    sections = parse_response(response_text)
                    display_sections(sections)
                except ConnectionError as e:
                    st.error(f"🔌 Ollama 연결 오류: {e}")
                except Exception as e:
                    st.warning(f"API 호출 중 오류가 발생했습니다: {e}")
                    display_demo_result()
        else:
            st.error("파일을 처리할 수 없습니다.")

# --- 하단 면책조항 ---
st.divider()
st.warning("⚠️ 본 분석은 AI 보조 초안이며, 최종 판단은 담당자의 전문적 검토가 필요합니다.")
st.info("💡 민감 개인정보는 비식별화 후 입력을 권장합니다. 실제 운영 시에는 내부망 적용, 검토 로그 저장 등 행정 보완장치를 함께 설계할 수 있습니다.")
