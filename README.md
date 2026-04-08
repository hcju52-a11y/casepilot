# 사건검토 도우미

**팀명:** Syndicate Lab

진정·민원·고소 문서를 빠르게 검토하고 핵심 쟁점과 처리방향 초안을 정리하는 AI 보조도구입니다.
고용노동부 바이브코딩 대회(2026.4.9) 출품용 Streamlit 시제품입니다.

## 실행 방법

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. API 키 설정
echo "GEMINI_API_KEY=your-key-here" > .env
# (선택) echo "OPENAI_API_KEY=your-key-here" >> .env

# 3. 실행
streamlit run app.py
```

## 주요 기능

- 진정서/고소장/민원 텍스트 입력 후 AI 초동검토 초안 생성
- 6개 섹션 자동 구성: 사건 개요, 핵심 쟁점, 검토 포인트, 추가 확인사항, 처리방향 초안, 회신 초안
- 이미지(jpg/png) 및 PDF 파일 업로드 분석 (Gemini Vision)
- 샘플 진정서 3건 내장 (임금체불, 해고 관련, 계약서 미작성)
- API 장애 시 데모 모드 자동 전환

## 기술 스택

- Python, Streamlit
- Google Gemini API (google-genai)
- OpenAI API (텍스트 분석 백업)
- PyMuPDF (PDF 처리)

## 면책조항

본 도구의 분석 결과는 AI 보조 초안이며, 최종 판단은 담당자의 전문적 검토가 필요합니다.
