# Claude Code 프롬프트 — Syndicate Lab 감독관 초동분석 코파일럿 v1.1.1

## 프로젝트 개요

팀명: Syndicate Lab
프로젝트명: 감독관 초동분석 코파일럿
목적: 고용노동부 바이브코딩 대회(2026.4.9) 출품용 Streamlit 시제품
한줄: 진정서·민원 접수문서를 AI로 요약·분석해 쟁점, 확인사항, 처리방향 초안을 제시하는 근로감독 업무보조 도구

## ⚠️ 최우선 원칙

1. **디자인보다 동작을 우선한다.** CSS 커스터마이징은 최소화할 것.
2. **Phase 분리 개발:** 첫 실행 목표는 "텍스트 입력 → 6개 섹션 출력"까지만(Phase 1). 이미지/PDF/Vision/데모모드(Phase 2)는 텍스트 분석이 `streamlit run app.py`로 완벽히 동작한 후에만 추가한다.
3. **session_state 키 단일화:** text_area는 `key="input_text"`로 통일한다. 별도 `key="main_input"` 사용 금지. 샘플 버튼 클릭 시 `st.session_state["input_text"] = SAMPLES[...]` 후 `st.rerun()` 호출.
4. **parse_response 파싱 전략:** 아이콘 문자 하나로 split하지 않는다. 전체 섹션 제목 문자열(예: `"## 📝 사건 개요"`, `"## ⚖️ 핵심 쟁점"`)을 anchor로 사용하여 파싱한다. 파싱 실패 시 전체 텍스트를 하나의 블록으로 표시하는 graceful fallback 필수.
5. **모델명 변수화:** 모델명을 하드코딩하지 않고 상단 상수로 분리한다. `CLAUDE_MODEL = "claude-sonnet-4-20250514"`, `OPENAI_MODEL = "gpt-4o"`.
6. 한국어로 모든 UI, 주석, 프롬프트, 출력을 작성한다.
7. **각 Phase가 끝날 때마다 전체 파일을 계속 생성하지 말고, 현재 생성된 파일 목록과 실행 결과를 먼저 요약한 뒤 다음 Phase로 진행할 것.**

## 작업 디렉터리

```
~/casepilot/
```

이 디렉터리를 생성하고 모든 파일을 여기에 만든다.

## 생성할 파일 목록 (11개)

```
casepilot/
├── app.py                 # Streamlit 메인 앱
├── prompts.py             # 시스템/사용자 프롬프트
├── law_reference.py       # 주요 법조문 참조 데이터 (core/penalty/referral 분리)
├── samples.py             # 데모용 비식별화 샘플 진정서 3건
├── demo_results.py        # 데모 모드 fallback용 사전 분석 결과 (Python dict)
├── pii_mask.py            # 간이 비식별화 (정규식)
├── vision_utils.py        # Vision API 연동 + PDF→이미지 변환
├── requirements.txt       # 의존성
├── .streamlit/
│   └── config.toml        # Streamlit 테마 설정
├── .gitignore
└── README.md              # 프로젝트 설명
```

## 핵심 제약 (반드시 준수)

1. **단일 페이지 Streamlit 앱** — 멀티페이지 금지
2. **API Key는 UI에 절대 표시하지 않음** — `st.secrets` 또는 환경변수(`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`)로만 로드. 키 없으면 안내 메시지 표시 후 중단
3. **temperature=0.1** — Claude/OpenAI 모두 환각 방지 극보수적 세팅
4. **PyPDF2 사용 금지** — PDF는 PyMuPDF(fitz)로 이미지 변환 → Vision API로 분석
5. **PDF 최대 3페이지** — 4페이지 이상이면 `st.warning("PDF는 처음 3페이지만 분석됩니다.")` 표시. 1차 버전은 **첫 페이지만 우선 분석**으로 구현 (단순화)
6. **이미지 MIME 자동 분기** — 업로드 파일 확장자 기준: .jpg/.jpeg → `image/jpeg`, .png → `image/png`
7. **벌칙 조항은 `st.expander`로 접기** — 기본 화면에 벌칙 노출하지 않음
8. **"부당해고이다/아니다" 단정 금지** — 프롬프트에서 해고예고·서면통지 검토 + 노동위 안내로 유도
9. **면책조항 필수** — 하단에 안전 문구 2개 표시
10. **데모 모드 fallback** — API 장애 시 `demo_results.py`의 사전 결과를 import하여 표시
11. **OpenAI는 텍스트 입력 fallback 전용** — 이미지/PDF Vision은 Claude만 담당. OpenAI는 텍스트 분석 백업용으로만 구현
12. **샘플 버튼과 입력창은 `st.session_state["input_text"]`를 사용** — 버튼 클릭 시 세션 상태를 갱신하고 `st.rerun()` 호출

## 구현 단계 (이 순서를 반드시 따를 것)

### Phase 1: 핵심 동작 (반드시 먼저 완성)
1. requirements.txt, .gitignore, .streamlit/config.toml
2. prompts.py
3. law_reference.py
4. samples.py
5. demo_results.py
6. pii_mask.py
7. **app.py (Phase 1 — 텍스트 모드만):** 사이드바(사건유형, 샘플버튼, 모델선택), text_area(`key="input_text"`), 분석 버튼, Claude/OpenAI 텍스트 API 호출, 6개 섹션 출력, 면책조항
8. **`streamlit run app.py`로 정상 동작 확인 후, 파일 목록과 결과를 요약 보고**

### Phase 2: 확장 기능 (Phase 1 완료 후에만 진행)
9. vision_utils.py — Vision API + PDF→이미지 (상수 `CLAUDE_MODEL`, `OPENAI_MODEL` 적용)
10. **app.py (Phase 2 — 파일 업로드 추가):** 입력 방식 radio에 "파일 업로드" 옵션 추가, file_uploader(pdf/txt/jpg/jpeg/png), Vision API 경로 추가, PDF 3페이지 제한 경고
11. 데모 모드 fallback 연결
12. README.md
13. **동작 확인 후, 파일 목록과 결과를 요약 보고**

### Phase 3: 마무리 (Phase 2 완료 후)
14. UI 다듬기 (아이콘, 구분선, expander)
15. 최종 테스트 (샘플 3건 전체 + 데모 모드)

---

## 의존성 (requirements.txt)

```
streamlit>=1.30.0
anthropic>=0.40.0
openai>=1.0.0
PyMuPDF>=1.24.0
python-dotenv>=1.0.0
```

## .gitignore

```
.env
.streamlit/secrets.toml
__pycache__/
*.pyc
```

## .streamlit/config.toml

```toml
[theme]
primaryColor = "#2563EB"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F8FAFC"
textColor = "#1E293B"
font = "sans serif"

[server]
headless = true
```

---

## 파일별 상세 명세

### 1. app.py — Streamlit 메인 앱

#### 페이지 설정
```python
st.set_page_config(
    page_title="감독관 초동분석 코파일럿",
    page_icon="🔬",
    layout="wide"
)
```

#### 헤더
- 타이틀: "🔬 감독관 초동분석 코파일럿"
- 서브: "by Syndicate Lab"
- 설명: "접수 문서를 요약하고 쟁점·확인사항·처리방향 초안을 제시하는 AI 업무보조 도구"

#### Session State 초기화
```python
if "input_text" not in st.session_state:
    st.session_state["input_text"] = ""
```

#### 사이드바 구성
- 📋 사건 유형: radio ["진정", "고소", "민원", "기타"]
- 📝 샘플 불러오기: 3개 버튼
  - "임금체불 사례" → 클릭 시 `st.session_state["input_text"] = SAMPLES["임금체불"]` 후 `st.rerun()`
  - "해고 관련 사례" → 클릭 시 `st.session_state["input_text"] = SAMPLES["해고 관련"]` 후 `st.rerun()`
  - "계약서 미작성 사례" → 클릭 시 `st.session_state["input_text"] = SAMPLES["계약서 미작성"]` 후 `st.rerun()`
- 🔧 AI 모델 선택: selectbox ["Claude (Anthropic)", "GPT-4o (OpenAI)"]
- API Key는 사이드바에 **절대 표시하지 않음**

#### Phase 1: 메인 영역 — 텍스트 입력
```python
user_input = st.text_area(
    "진정서 내용을 입력하세요",
    height=300,
    placeholder="여기에 진정서 내용을 붙여넣으세요...",
    key="input_text"
)
```
- `key="input_text"` 하나로 통일 — 별도 key 금지

#### Phase 2에서 추가: 파일 업로드 모드
- 입력 방식: radio ["텍스트 입력", "파일 업로드"] (Phase 2에서만 추가)
- `st.file_uploader` (type=["pdf", "txt", "jpg", "jpeg", "png"])
  - txt: 텍스트 직접 읽기
  - pdf: `vision_utils.pdf_to_images()` → 이미지
  - jpg/png: 바이트 그대로 Vision API 전송
  - 업로드 성공 시 미리보기 표시

#### 실행 버튼
```python
st.button("🔍 초동분석 시작", type="primary", use_container_width=True)
```

#### 분석 로직
1. API Key 확인 — 없으면 `st.error("API Key가 설정되지 않았습니다. .env 파일 또는 Streamlit secrets를 확인해주세요.")` 후 중단
2. 입력 확인 — 없으면 `st.warning("분석할 내용을 입력해주세요.")`
3. `st.spinner("AI가 초동분석 중입니다...")` 표시
4. 텍스트 입력:
   - Claude 선택 시 → `vision_utils.analyze_text_claude()`
   - OpenAI 선택 시 → `vision_utils.analyze_text_openai()`
5. 이미지/PDF 입력 (Phase 2) → `vision_utils`의 Vision API 함수 (Claude만)
6. API 호출 실패 시 → `demo_results.py`에서 import한 결과 표시 + `st.info("⚡ 데모 모드: 네트워크 또는 API 연결 문제로 사전 생성된 분석 결과를 표시합니다.")`

#### AI 응답 파싱
`parse_response(text: str) -> dict` 함수:
- **전체 섹션 제목 문자열**을 anchor로 사용하여 파싱:
  - `"## 📝 사건 개요"`
  - `"## ⚖️ 핵심 쟁점"`
  - `"## 📖 검토 포인트"`
  - `"## 🔍 추가 확인사항"`
  - `"## 🧭 처리방향 초안"`
  - `"## ✉️ 회신/내부검토 초안"`
- 아이콘 문자 하나로 split하지 않는다
- 벌칙 부분은 `"**[참고 — 벌칙]**"` 소제목 기준으로 추가 분리
- **파싱 실패 시 전체 텍스트를 하나의 블록으로 표시** (graceful fallback)

#### 결과 표시 — 2컬럼 레이아웃
```python
col1, col2 = st.columns(2)
```

좌측 (col1):
- 📝 사건 개요 — `st.subheader` + `st.markdown`
- ⚖️ 핵심 쟁점 — `st.subheader` + `st.markdown`
- 📖 검토 포인트 — `st.subheader` + `st.markdown`
  - 벌칙 조항: `st.expander("⚠️ 벌칙 조항 참고")` 안에 표시

우측 (col2):
- 🔍 추가 확인사항 — `st.subheader` + `st.markdown`
- 🧭 처리방향 초안 — `st.subheader` + `st.markdown`
- ✉️ 회신/내부검토 초안 — `st.subheader` + `st.text_area` (편집 가능)

#### 하단 면책조항
```python
st.divider()
st.warning("⚠️ 본 분석은 AI 보조 초안이며, 최종 판단은 담당자의 전문적 검토가 필요합니다.")
st.info("💡 민감 개인정보는 비식별화 후 입력을 권장합니다. 실제 운영 시에는 내부망 적용, 검토 로그 저장 등 행정 보완장치를 함께 설계할 수 있습니다.")
```

---

### 2. prompts.py — 프롬프트

#### SYSTEM_PROMPT (전문)

```
당신은 대한민국 고용노동부 소속 근로감독관의 초동검토를 돕는 업무보조 AI입니다.

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
{law_context}
```

#### build_user_prompt(text, doc_type) 함수
```python
def build_user_prompt(text: str, doc_type: str) -> str:
    return f"다음은 접수된 {doc_type}입니다. 초동분석을 수행해주세요.\n\n---\n{text}\n---"
```

#### build_vision_prompt(doc_type) 함수
```python
def build_vision_prompt(doc_type: str) -> str:
    return f"이 이미지는 접수된 {doc_type}입니다. 문서 내용을 읽고 초동분석을 수행해주세요."
```

---

### 3. law_reference.py — 법조문 참조 데이터

dict 구조: 키=쟁점명, 값={"core": [...], "penalty": [...], "referral": [...]}

포함할 쟁점 6개:
- **임금체불**: 근기법 36조(금품청산 — 퇴직 후 14일), 43조(임금지급 — 매월 1회 통화 직접) / 벌칙 109조(3년 이하 징역 또는 3천만원 이하 벌금)
- **해고 관련**: 근기법 23조(해고제한 — 정당한 이유), 26조(해고예고 — 30일 전 또는 30일분 통상임금), 27조(서면통지 — 해고사유 서면 명시) / referral 28조(노동위 구제신청 — 3개월 이내) + "※ 부당해고 여부 판정은 노동위원회 소관"
- **퇴직금**: 퇴직급여법 8조(설정 — 1년 이상), 9조(지급 — 14일)
- **근로조건 위반**: 근기법 17조(명시 — 서면 교부 의무), 50조(근로시간 — 1주 40시간, 1일 8시간), 56조(가산임금 — 연장·야간·휴일 50%)
- **최저임금**: 최저임금법 6조(효력 — 미만 계약 무효) + "2025년 최저시급: 10,030원 / 2026년 최저시급: 10,320원" / 벌칙 28조(3년/2천만원)
- **직장 내 괴롭힘**: 근기법 76조의2(금지), 76조의3(발생 시 조치)

`get_law_context() -> str` 함수: 전체 법조문을 프롬프트 삽입용 문자열로 반환

---

### 4. samples.py — 데모용 샘플 3건

dict `SAMPLES`: {"임금체불": "...", "해고 관련": "...", "계약서 미작성": "..."}

각 샘플은 진정서 형식의 **완전한 텍스트**로 작성 (진정인, 피진정인, 소재지, 진정취지, 날짜 포함)

#### 샘플 1: 임금체불형
```
[진정서]

진정인: 김○○ (만 28세)
피진정인: ○○물류 주식회사 (대표 이○○)
소재지: 충북 청주시 ○○구 ○○로 123

진정 취지:
본인은 2025년 6월 1일부터 2026년 2월 28일까지 위 사업장에서
물류 배송 업무를 담당하며 근무하였습니다.

그러나 사업주는 2025년 12월분부터 2026년 2월분까지
3개월간의 급여 합계 금 7,200,000원을 지급하지 않고 있습니다.

또한 근무 기간 중 주 6일, 일 10시간 이상 근무하였으나
연장근로수당이 한 번도 지급된 적이 없습니다.

퇴직 시 퇴직금도 지급받지 못하였습니다.

근로계약서는 입사 시 작성하였으나 사본을 받지 못하였습니다.

위와 같이 진정하오니 조사하여 주시기 바랍니다.

2026년 3월 15일
진정인 김○○
```

#### 샘플 2: 해고예고·서면통지 검토형
```
[진정서]

진정인: 박○○ (만 35세)
피진정인: ○○테크 주식회사 (대표 정○○)
소재지: 세종시 ○○로 456

진정 취지:
본인은 2024년 3월 1일 입사하여 개발팀에서 근무하였습니다.

2026년 3월 10일 팀장으로부터 "회사 사정이 어려우니
자발적으로 퇴사해 달라"는 통보를 받았습니다.

본인이 거부하자 3월 12일자로 "경영상 이유에 의한 해고"
통보서를 받았으나, 해고 예고는 없었고 해고 사유가
구체적으로 기재되어 있지 않았습니다.

또한 같은 부서 5명 중 본인만 해고되었으며,
신규 채용 공고가 같은 날 올라온 사실을 확인하였습니다.

해고예고수당 지급, 해고사유 서면통지 적정성 검토,
그리고 부당해고에 해당한다면 관련 구제절차 안내를 요청합니다.

2026년 3월 20일
진정인 박○○
```

#### 샘플 3: 계약서 미작성 + 최저임금 위반형
```
[진정서]

진정인: 이○○ (만 22세)
피진정인: ○○카페 (대표 최○○)
소재지: 대전시 ○○구 ○○길 78

진정 취지:
본인은 2025년 9월 1일부터 2026년 2월 28일까지
위 카페에서 바리스타로 근무하였습니다.

입사 시 근로계약서를 작성하지 않았으며,
구두로 시급 9,000원에 합의하였습니다.
(참고: 2025년 최저시급 10,030원, 2026년 최저시급 10,320원)

주 5일, 일 8시간 근무하였으나 주휴수당은
한 번도 지급받지 못하였습니다.

퇴직 후 마지막 달(2026년 2월) 급여도 아직 받지 못하였습니다.

위와 같이 진정하오니 조사하여 주시기 바랍니다.

2026년 3월 10일
진정인 이○○
```

---

### 5. demo_results.py — 데모 모드 Fallback

**JSON 파일이 아닌 Python dict로 구현한다.**

`DEMO_RESULT` dict: 샘플 1(임금체불)에 대한 6개 섹션 + 벌칙 분리 완전한 분석 결과

```python
DEMO_RESULT = {
    "summary": "김○○(진정인)은 ○○물류 주식회사에서 2025년 6월부터 2026년 2월까지 물류 배송 업무에 종사하였으며, 2025년 12월분부터 2026년 2월분까지 3개월간 급여 합계 7,200,000원을 지급받지 못하였다고 주장합니다. 아울러 주 6일, 일 10시간 이상 근무하였으나 연장근로수당이 지급되지 않았고, 퇴직금도 미지급 상태이며, 근로계약서 사본을 교부받지 못하였다고 진정하고 있습니다.",
    "issues": "1. **임금체불 가능성** — 3개월간(2025.12~2026.02) 급여 합계 7,200,000원이 미지급된 것으로 보이며, 근로기준법 제43조 위반 가능성 검토 필요\n2. **연장근로수당 미지급 가능성** — 주 6일 일 10시간 근무 주장에 따르면 법정 근로시간(주 40시간) 초과분에 대한 가산임금 미지급 가능성 검토 필요\n3. **퇴직금 미지급 가능성** — 약 9개월 근무로 1년 미만이나, 정확한 근로기간 확인을 통해 퇴직급여 보장법 적용 여부 검토 필요",
    "review_points": "- **근로기준법 제36조 (금품 청산)** — 퇴직 후 14일 이내 임금 등 지급 의무. 미지급 시 위반 가능성 검토 필요\n- **근로기준법 제43조 (임금 지급)** — 매월 1회 이상 통화로 직접 지급 원칙. 3개월 미지급은 동 조항 위반 가능성 검토 필요\n- **근로기준법 제56조 (연장·야간·휴일 근로)** — 연장근로에 대해 통상임금의 50% 이상 가산 지급 의무. 실근로시간 확인 필요\n- **근로기준법 제17조 (근로조건의 명시)** — 근로계약서 서면 교부 의무. 사본 미교부 여부 확인 필요",
    "review_penalty": "- **근로기준법 제109조** — 임금체불 시 3년 이하 징역 또는 3천만원 이하 벌금\n- **근로기준법 제114조** — 근로조건 명시 위반 시 500만원 이하 벌금",
    "questions": "- 근로계약서 원본 존재 여부 및 내용 확인 필요\n- 임금대장, 급여명세서 제출 요구 필요\n- 출퇴근기록부 또는 근태기록 확인 필요\n- 실제 근로일수 및 1일 근로시간 확인 필요\n- 퇴직일자 및 정확한 근로기간 산정 확인 필요 (퇴직금 지급 요건 1년 이상 여부)\n- 사업주 측 미지급 사유 청취 필요",
    "direction": "1. 피진정인(사업주)에 대한 출석요구서 발부\n2. 임금대장, 근로계약서, 출퇴근기록부 제출 요구\n3. 체불 사실 확인 시 시정지시 → 미이행 시 사법처리 검토\n4. 연장근로수당은 실근로시간 확인 후 산정\n5. 퇴직금은 근로기간 1년 이상 여부 우선 확인\n6. 근로계약서 사본 미교부 건은 별도 확인",
    "reply_draft": "진정인 김○○ 귀하\n\n귀하께서 2026년 3월 15일자로 제출하신 임금체불 등 관련 진정 사건이 접수되었음을 알려드립니다.\n\n본 건은 담당 근로감독관이 배정되어 사실관계 확인 및 조사를 진행할 예정이오니, 추가 자료(근로계약서 사본, 급여 이체내역 등)가 있으시면 조사 시 제출하여 주시기 바랍니다.\n\n조사 진행 상황은 별도로 안내드리겠습니다.\n\n○○지방고용노동청 ○○지청"
}
```

---

### 6. pii_mask.py — 간이 비식별화

상단 주석: "간이 비식별화 예시입니다. 주소/상호 등은 완전 마스킹되지 않을 수 있습니다."

`mask_pii(text: str) -> str` 함수:
- 주민번호 (000000-0000000) → ○○○○○○-○○○○○○○
- 전화번호 (010-0000-0000) → ○○○-○○○○-○○○○
- 이메일 → ○○○@○○○.○○○

---

### 7. vision_utils.py — Vision API + PDF→이미지

#### 상수 정의 (상단)
```python
CLAUDE_MODEL = "claude-sonnet-4-20250514"
OPENAI_MODEL = "gpt-4o"
```

#### pdf_to_images(pdf_bytes: bytes, max_pages: int = 3) → tuple[list[bytes], bool]
- PyMuPDF(fitz)로 PDF 페이지별 PNG 변환 (dpi=200)
- max_pages 초과 시 truncated=True 반환
- 반환: (이미지 바이트 리스트, truncated 여부)
- 에러 시 빈 리스트 + False

#### get_mime_type(filename: str) -> str
- .jpg/.jpeg → "image/jpeg"
- .png → "image/png"
- 기타 → "image/png"

#### analyze_with_vision_claude(image_bytes, mime_type, doc_type, system_prompt, api_key) → str
- Anthropic Messages API
- model=CLAUDE_MODEL, temperature=0.1, max_tokens=4096
- content에 image(base64) + text

#### analyze_text_claude(text, doc_type, system_prompt, api_key) → str
- Anthropic Messages API 텍스트 전용
- model=CLAUDE_MODEL, temperature=0.1, max_tokens=4096

#### analyze_text_openai(text, doc_type, system_prompt, api_key) → str
- OpenAI Chat Completions API 텍스트 전용
- model=OPENAI_MODEL, temperature=0.1, max_tokens=4096

(OpenAI Vision은 구현하지 않는다 — 이미지 분석은 Claude 전용)

---

### 8. README.md

프로젝트 설명:
- 프로젝트명: 감독관 초동분석 코파일럿
- 팀명: Syndicate Lab
- 한줄 소개
- 실행 방법: `pip install -r requirements.txt` → `.env`에 `ANTHROPIC_API_KEY=sk-...` 세팅 → `streamlit run app.py`
- 기능 목록 5개
- 기술 스택: Python, Streamlit, Claude API, PyMuPDF
- 면책조항: "AI 보조 초안이며 최종 판단은 담당자 검토 필요"

---

## 구현 완료 후 검증 (반드시 수행)

1. `pip install -r requirements.txt` 에러 없이 완료
2. `.env` 파일에 `ANTHROPIC_API_KEY=sk-...` 세팅
3. `streamlit run app.py` 실행 → 브라우저 자동 열림
4. 사이드바 샘플 "임금체불 사례" 버튼 클릭 → 입력창에 텍스트 채워짐 확인
5. "초동분석 시작" 클릭 → 6개 섹션 정상 출력 확인
6. API Key 미설정 시 에러 메시지 정상 표시 확인
7. API 호출 실패 시 데모 모드 fallback 정상 동작 확인

---

## 절대 금지 사항

- localStorage, sessionStorage 사용 금지
- 외부 DB 연결 금지
- 로그인/인증 구현 금지
- 자동 발송/자동 판단 기능 금지
- API Key를 코드에 하드코딩 금지
- PyPDF2 사용 금지 (PyMuPDF만 사용)
- 디자인에 과도한 시간 투자 금지 — 동작 우선
- `text_area`에 `key="input_text"` 외의 별도 key 사용 금지
