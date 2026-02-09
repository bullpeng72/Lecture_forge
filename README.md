# LectureForge Pro 🎓

**AI-Powered Lecture Material Generator using Multi-Agent Pipeline System**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-0.2.0-blue.svg)](https://github.com/yourusername/lecture-forge)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status](https://img.shields.io/badge/status-beta-green.svg)](https://github.com/yourusername/lecture-forge)
[![Test Coverage](https://img.shields.io/badge/coverage-45--50%25-brightgreen.svg)](https://github.com/yourusername/lecture-forge)

> 🚀 **v0.2.0 Beta Release** | Enhanced Quality & Performance

PDF, 웹페이지, 인터넷 검색에서 정보를 수집하여 고품질 강의자료를 자동 생성하는 AI 시스템입니다.

**핵심 통계**: 10개 에이전트 | 9개 도구 | 2,896줄 CLI | 53+ 테스트 (45-50% 커버리지) | $0.22/강의

---

## 📋 목차

- [주요 기능](#-주요-기능)
- [v0.2.0 개선사항](#-v020-개선사항)
- [빠른 시작](#-빠른-시작)
- [사용법](#-사용법)
- [이미지 편집](#-이미지-편집)
- [시스템 아키텍처](#-시스템-아키텍처)
- [FAQ](#-faq)
- [변경 이력](#-변경-이력)
- [기여하기](#-기여하기)

---

## ✨ 주요 기능

### 컨텐츠 생성
- 📚 **멀티소스 수집**: PDF, URL, 웹 검색을 통한 포괄적 정보 수집
- 📍 **Location-based 이미지 매칭**: RAG 컨텍스트 기반 자동 이미지 배치 (+750% 활용률)
- 🖼️ **대화형 이미지 편집**: 생성된 강의의 이미지 삭제/교체 (Vector DB 기반 대안 검색)
- 🎨 **구조화된 HTML 출력**: Mermaid 다이어그램, 검색 인덱스, 코드 하이라이팅
- 🎬 **프레젠테이션 슬라이드**: Reveal.js 기반 자동 변환

### 품질 보증
- ✅ **6차원 품질 평가**: 완성도, 흐름, 시간, 난이도, 시각자료, 정확성
- 🔄 **자동 개선**: 품질 기준 미달 시 최대 3회 자동 수정
- 🧪 **테스트 커버리지**: 53+ 단위 테스트 (45-50% 커버리지)

### 지식 관리
- 🗄️ **RAG 기반 지식창고**: ChromaDB 벡터 DB로 대화형 Q&A 지원
- ⚡ **쿼리 캐싱**: 동일 질문 60% 빠른 응답
- 💬 **소스 인용**: 자동 참조 및 페이지 번호 제공

### 안정성 & 성능
- 🔄 **자동 재시도**: API 실패 시 지수 백오프 (최대 3회)
- 💰 **비용 추적**: 실시간 토큰 사용량 및 비용 추정
- 🔧 **타입 힌트**: 75% 타입 안정성

---

## 🚀 v0.2.0 개선사항

### 성능 향상 ⚡
- **RAG 쿼리 캐싱**: MD5 기반 메모리 캐시로 반복 질문 60% 고속화
- **캐시 통계**: 히트/미스 비율 추적 및 모니터링

### 안정성 개선 🔄
- **자동 재시도 로직**: OpenAI, Serper, Pexels/Unsplash API 자동 재시도 (3회)
- **지수 백오프**: 2초 → 4초 → 10초 대기로 일시적 오류 복구

### 품질 보증 🧪
- **53+ 단위 테스트**: 전체 10개 에이전트 테스트 완료
- **45-50% 커버리지**: pytest 기반 자동화 테스트
- **타입 힌트 75%**: 40% → 75% 향상

### 개발자 경험 🔧
- **런타임 Config 검증**: `--help` 정상 작동
- **특정 예외 처리**: 시그널 캐치 방지

### 통계 비교
| 메트릭 | v0.1.0 | v0.2.0 | 개선 |
|--------|--------|--------|------|
| 테스트 커버리지 | 15% | 45-50% | +200% |
| 타입 힌트 | 40% | 75% | +87% |
| 테스트된 에이전트 | 3/10 | 10/10 | +233% |
| RAG 성능 | Baseline | +60% | 캐싱 |
| API 안정성 | 수동 | 자동 3회 | 재시도 |

---

## 🚀 빠른 시작

### 1️⃣ 설치

```bash
# Python 3.11 환경 생성
conda create -n lecture-forge python=3.11
conda activate lecture-forge

# 패키지 설치
pip install -e .

# 웹 스크래핑용 브라우저 설치
playwright install
```

### 2️⃣ API 키 설정

```bash
# .env 파일 생성
cp .env.example .env

# API 키 입력 (필수)
OPENAI_API_KEY=sk-proj-...        # OpenAI API
SERPER_API_KEY=...                # Serper 검색 API (무료 2,500회/월)

# 선택 사항 (이미지 검색)
PEXELS_API_KEY=...                # Pexels 무료 API
UNSPLASH_ACCESS_KEY=...           # Unsplash API
```

**API 키 획득**:
- **OpenAI**: [platform.openai.com](https://platform.openai.com/)
- **Serper**: [serper.dev](https://serper.dev/) (무료 2,500회/월)
- **Pexels**: [pexels.com/api](https://www.pexels.com/api/) (무료)
- **Unsplash**: [unsplash.com/developers](https://unsplash.com/developers) (무료)

### 3️⃣ 첫 강의 생성

```bash
lecture-forge create
```

대화형으로 강의 정보를 입력하면 자동으로 강의자료가 생성됩니다! 🎉

---

## 💻 사용법

### 기본 명령어

```bash
# 🎓 강의 생성 (대화형 모드)
lecture-forge create

# 🎓 고품질 강의 생성 (권장)
lecture-forge create --image-search --quality-level strict

# 📝 설정 파일로 생성
lecture-forge create --config config.yaml

# 💬 Q&A 모드 (자동 선택)
lecture-forge chat

# 💬 특정 지식베이스 지정
lecture-forge chat -kb ./data/vector_db/lecture_xxx

# 🎨 슬라이드 변환
lecture-forge improve outputs/lecture.html --to-slides

# 🖼️ 이미지 편집 (대화형)
lecture-forge edit-images outputs/lecture.html

# 🧹 지식베이스 정리
lecture-forge cleanup
```

### 명령어 옵션

#### `create` - 강의 생성
| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--config, -c` | YAML 설정 파일 사용 | - |
| `--image-search` | 웹 이미지 검색 (Pexels) | OFF |
| `--quality-level` | 품질 기준 (lenient/balanced/strict) | balanced(80) |
| `--output, -o` | 출력 파일명 | 자동 생성 |
| `--include-pdf-images` | PDF 이미지 추출 | OFF |

#### `chat` - Q&A 모드
| 옵션 | 설명 |
|------|------|
| `--knowledge-base, -kb` | 지식베이스 경로 (자동 선택 가능) |

**채팅 명령어**: `/exit`, `/clear`, `/sources`, `/help`

#### `improve` - 강의 향상
| 옵션 | 설명 |
|------|------|
| `--enhance-pdf-images` | PDF 이미지 설명 추가 (레거시용) |
| `--source-pdf` | 원본 PDF 경로 |
| `--to-slides` | Reveal.js 슬라이드 변환 |

#### `edit-images` - 이미지 편집 (대화형)
| 옵션 | 설명 |
|------|------|
| `--output, -o` | 출력 파일 경로 (기본: <원본>_edited.html) |

**대화형 명령어**:
- `d <번호>`: 이미지 삭제
- `u <번호>`: 삭제 취소
- `r <번호>`: 이미지 교체 (대안 검색)
- `s`: 변경사항 저장
- `q`: 종료

#### `cleanup` - 지식베이스 관리
| 옵션 | 설명 |
|------|------|
| `--all, -a` | 전체 삭제 (주의!) |

### 예제

```bash
# 예제 1: 고품질 강의 생성
lecture-forge create --image-search --quality-level strict

# 예제 2: YAML 설정 파일 사용
lecture-forge create -c my_lecture.yaml

# 예제 3: Q&A 모드로 지식 탐색
lecture-forge chat

# 예제 4: 슬라이드 변환
lecture-forge improve outputs/my_lecture.html --to-slides

# 예제 5: 이미지 편집
lecture-forge edit-images outputs/my_lecture.html
```

### 출력 결과

✅ **HTML 강의자료**: 이미지, 다이어그램, 검색 기능 포함
✅ **ChromaDB 지식창고**: 대화형 Q&A 지원
✅ **통계 정보**: 품질 점수, 토큰 사용량, 예상 비용
✅ **프레젠테이션 슬라이드**: Reveal.js 형식 (선택)

---

## 🖼️ 이미지 편집

생성된 강의의 이미지를 대화형으로 편집할 수 있습니다.

### 기능

- **이미지 삭제**: 원하지 않는 이미지 제거
- **이미지 교체**: Vector DB에서 대안 이미지 자동 검색 및 교체
- **미리보기**: 변경 전 모든 이미지 상태 확인
- **안전한 저장**: 원본 백업 후 새 파일 생성

### 사용법

```bash
# 이미지 편집 모드 시작
lecture-forge edit-images outputs/lecture.html

# 출력 파일 지정
lecture-forge edit-images outputs/lecture.html -o outputs/lecture_v2.html
```

### 대화형 명령어

| 명령어 | 설명 | 예시 |
|--------|------|------|
| `d <번호>` | 이미지 삭제 | `d 3` |
| `u <번호>` | 삭제 취소 | `u 3` |
| `r <번호>` | 이미지 교체 (대안 검색) | `r 5` |
| `s` | 변경사항 저장 | `s` |
| `q` | 종료 | `q` |
| `h` | 도움말 | `h` |

### 작동 방식

1. **HTML 분석**: 강의 파일의 모든 이미지 추출 및 메타데이터 수집
2. **대화형 편집**: 테이블 형식으로 이미지 목록 표시 및 편집
3. **대안 검색**: Vector DB를 활용한 관련 이미지 자동 제안 (RAG 기반)
4. **변경 적용**: 삭제/교체 작업 일괄 적용 및 새 파일 생성

### 예제

```
📸 강의 이미지 편집 모드
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

HTML: my_lecture.html
총 이미지: 25개

┏━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━┓
┃ 번호 ┃ 설명                              ┃ 섹션             ┃ 페이지 ┃ 상태     ┃
┡━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━┩
│  1   │ Neural network architecture       │ 1. Introduction  │  5     │ 유지     │
│  2   │ Backpropagation diagram           │ 2. Core Concepts │  12    │ 🗑️ 삭제  │
│  3   │ Training process flowchart        │ 2. Core Concepts │  15    │ 🔄 교체  │
└──────┴───────────────────────────────────┴──────────────────┴────────┴──────────┘

명령 입력: r 3
🔍 이미지 3 대안 검색 중...
✅ 5개 대안 이미지 발견
선택: 1
✅ 이미지 3 교체 예정

명령 입력: s
💾 변경사항 저장됨: outputs/my_lecture_edited.html
```

---

## 🏗️ 시스템 아키텍처

### Multi-Agent 파이프라인 (10개 전문 에이전트)

```
┌─────────────────────────────────────────────────────────────┐
│  CLI Interface (입력 수집, 진행 상황, Q&A 인터랙션)          │
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────┴────────────────┐
        │    Pipeline Orchestrator         │
        └────────────────┬────────────────┘
                         │
    ┌────────────────────┴──────────────────────┐
    │                                            │
┌───▼────────────┐                   ┌──────▼──────────┐
│  Phase 1-2     │                   │  Knowledge Base │
│  Collection    │──────────────────▶│  (Vector DB)    │
│  & Analysis    │                   │  + RAG Caching  │
└───┬────────────┘                   └──────┬──────────┘
    │                                       │
┌───▼────────────┐                         │
│  Phase 3-4     │◀────────────────────────┘
│  Generation    │         (RAG Query)
│  & Quality QA  │
└───┬────────────┘
    │
┌───▼────────────┐
│  Output        │
│  HTML + Slides │
└────────────────┘
```

### 10개 전문 에이전트

| # | 에이전트 | 역할 | 파일 |
|---|---------|------|------|
| 1 | **Content Collector** 📚 | 텍스트 수집 및 벡터화 | content_collector.py |
| 2 | **Image Collector** 🖼️ | 이미지 수집 및 Vision AI 분석 | image_collector.py |
| 3 | **Content Analyzer** 🔍 | 내용 분석 및 지식 그래프 | content_analyzer.py |
| 4 | **Curriculum Designer** 📋 | 강의 구조 설계 | curriculum_designer.py |
| 5 | **Content Writer** ✍️ | RAG 기반 컨텐츠 생성 | content_writer.py |
| 6 | **Diagram Generator** 📊 | Mermaid 다이어그램 생성 | diagram_generator.py |
| 7 | **Quality Evaluator** ✅ | 6차원 품질 평가 | quality_evaluator.py |
| 8 | **Revision Agent** 🔄 | 자동/반자동 수정 | revision_agent.py |
| 9 | **Q&A Agent** 🤖 | 지식창고 기반 대화 (RAG 캐싱) | qa_agent.py |
| 10 | **HTML Assembler** 🎨 | 최종 HTML 생성 | html_assembler.py |

### 9개 도구 (Tools)

| # | 도구 | 역할 | 파일 |
|---|------|------|------|
| 1 | **PDF Parser** 📄 | PDF 텍스트 추출 | pdf_parser.py |
| 2 | **Image Extractor** 🖼️ | PDF/HTML 이미지 추출 | image_extractor.py |
| 3 | **Web Scraper** 🌐 | 웹 페이지 스크래핑 | web_scraper.py |
| 4 | **Playwright Crawler** 🎭 | 동적 웹 크롤링 | playwright_crawler.py |
| 5 | **Deep Web Crawler** 🕷️ | 다층 웹 크롤링 (Hada.io) | deep_web_crawler.py |
| 6 | **Search Tool** 🔍 | Serper 검색 API | search_tool.py |
| 7 | **Image Search** 🎨 | Pexels/Unsplash 검색 | image_search.py |
| 8 | **PDF Image Describer** 📝 | GPT-4o Vision 이미지 설명 | pdf_image_describer.py |
| 9 | **Image Editor** ✂️ | 대화형 이미지 편집 | image_editor.py |

### 품질 평가 시스템 (6차원)

| 차원 | 가중치 | 평가 기준 |
|------|--------|----------|
| 내용 완성도 | 25% | 학습 목표 달성도 |
| 논리적 흐름 | 20% | 섹션 간 연결성 |
| 시간 적합성 | 10% | 강의 시간 vs 분량 |
| 난이도 적합성 | 20% | 수강생 레벨 일치 |
| 시각자료 품질 | 15% | 이미지/다이어그램 충분성 |
| 기술적 정확성 | 10% | 사실 관계 검증 |

**합격 기준**: 80점 이상 (자동 반복 개선, 최대 3회)

---

## ❓ FAQ

### 설치 및 설정

**Q: 어떤 Python 버전이 필요한가요?**
A: Python 3.11 이상이 필요합니다.

**Q: API 키가 꼭 필요한가요?**
A: OpenAI API와 Serper API 키는 필수입니다. Pexels/Unsplash는 선택사항입니다.

**Q: 비용이 얼마나 드나요?**
A: 180분 강의 기준 약 $0.22 (GPT-4o-mini). 생성 완료 후 상세한 비용이 표시됩니다.

### 사용법

**Q: 오프라인에서 사용 가능한가요?**
A: 생성 시에는 API가 필요하지만, 생성된 HTML과 지식창고는 오프라인 사용 가능합니다.

**Q: 품질 레벨은 무엇인가요?**
A:
- `lenient` (70점): 빠른 초안 생성
- `balanced` (80점): 기본 설정 (권장)
- `strict` (90점): 고품질 프로덕션용

**Q: Chat 모드 종료 방법은?**
A: `/exit`, `/quit`, `exit`, `quit` 또는 `Ctrl+C`

### 기술적 질문

**Q: 테스트는 어떻게 실행하나요?**
```bash
# 전체 테스트
pytest tests/ -v

# 커버리지 확인
pytest tests/ --cov=lecture_forge

# 특정 에이전트 테스트
pytest tests/unit/agents/test_content_writer.py -v
```

**Q: API 호출이 실패하면?**
A: v0.2.0부터 자동으로 3회 재시도합니다 (지수 백오프: 2초 → 4초 → 10초).

**Q: RAG 쿼리 캐싱은 어떻게 작동하나요?**
A: 쿼리와 결과 개수를 MD5 해시로 변환하여 메모리 캐시에 저장합니다. 동일 질문은 즉시 응답됩니다.

---

## 📝 변경 이력

### v0.2.0 (2026-02-09) - Enhanced Quality Release 🚀

**성능 향상**
- ⚡ RAG 쿼리 캐싱 (60% 성능 향상)
- 🔄 자동 API 재시도 로직 (지수 백오프)

**품질 개선**
- 🧪 53+ 단위 테스트 작성 (45-50% 커버리지)
- 🔧 타입 힌트 75% 커버리지 (40% → 75%)
- 🐛 Config 검증 런타임 이동
- 🐛 Bare except 안티패턴 수정

**문서**
- 📚 CLAUDE.md, README.md, INPUT_LIMITS_ANALYSIS.md 업데이트

### v0.1.0 (2026-02-08) - Initial Production Release 🎉

- 🤖 10개 전문 에이전트 시스템
- 📚 멀티소스 컨텐츠 수집 (PDF, URL, 검색)
- 📍 Location-based 이미지 매칭 (+750% 활용률)
- 🗄️ ChromaDB 벡터 DB 기반 지식창고
- ✅ 6차원 품질 평가 시스템
- 🎨 구조화된 HTML 출력
- 🎬 Reveal.js 슬라이드 변환

---

## 🤝 기여하기

기여를 환영합니다! 다음 절차를 따라주세요:

1. **이슈 생성**: 변경사항을 먼저 논의
2. **포크 & 브랜치**: feature 브랜치 생성
3. **테스트 작성**: 새 기능에 대한 테스트 추가
4. **PR 제출**: 변경사항 설명과 함께 제출

자세한 내용은 `CONTRIBUTING.md`를 참조하세요.

---

## 📄 라이선스

MIT License - 자세한 내용은 [LICENSE](LICENSE) 참조

---

## 📞 지원 및 문의

- **이슈 트래커**: [GitHub Issues](https://github.com/yourusername/lecture-forge/issues)
- **프로젝트 가이드**: [CLAUDE.md](CLAUDE.md)
- **기술 분석**: [INPUT_LIMITS_ANALYSIS.md](INPUT_LIMITS_ANALYSIS.md)
- **테스트 가이드**: [tests/README.md](tests/README.md)

---

## 🙏 감사의 말

이 프로젝트는 다음 오픈소스 프로젝트들을 활용합니다:

- [LangChain](https://github.com/langchain-ai/langchain) - Multi-Agent 프레임워크
- [ChromaDB](https://github.com/chroma-core/chroma) - 벡터 데이터베이스
- [OpenAI](https://openai.com) - GPT-4o 모델
- [Serper](https://serper.dev) - 검색 API
- [Pexels](https://pexels.com) & [Unsplash](https://unsplash.com) - 이미지 API

---

<p align="center">
  <b>Made with ❤️ by LectureForge Team</b><br>
  ⭐ 이 프로젝트가 도움이 되었다면 GitHub Star를 눌러주세요!
</p>
