# LectureForge 🎓

**AI-Powered Lecture Material Generator using Multi-Agent Pipeline System**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-0.2.6-blue.svg)](https://github.com/bullpeng72/Lecture_forge)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status](https://img.shields.io/badge/status-beta-green.svg)](https://github.com/bullpeng72/Lecture_forge)
[![Test Coverage](https://img.shields.io/badge/coverage-45--50%25-brightgreen.svg)](https://github.com/bullpeng72/Lecture_forge)

> 🚀 **v0.2.6 Beta Release** | Critical Image Bug Fixed - Original Resolution Guaranteed

PDF, 웹페이지, 인터넷 검색에서 정보를 수집하여 고품질 강의자료를 자동 생성하는 AI 시스템입니다.

**핵심 통계**: 10개 에이전트 | 9개 도구 | 3,288줄 CLI | 53+ 테스트 (45-50% 커버리지) | ~$0.035/60분 강의

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
- **45%+ 커버리지**: pytest 기반 자동화 테스트
- **타입 힌트 75%**: 40% → 75% 향상

### 설정 시스템 개선 🔧
- **Config 리팩토링**: 모든 하드코딩 제거, .env 기반 중앙 집중식 설정
- **15+ 환경변수**: 검색, 크롤링, 이미지, 타임아웃 등 모든 설정 조정 가능
- **환경별 설정**: 개발/스테이징/프로덕션 환경 분리 지원
- **런타임 Config 검증**: `--help` 정상 작동

### 통계 비교
| 메트릭 | v0.1.0 | v0.2.6 | 개선 |
|--------|--------|--------|------|
| 테스트 커버리지 | 15% | 45-50% | +200%+ |
| 타입 힌트 | 40% | 75% | +87% |
| 테스트된 에이전트 | 3/10 | 10/10 | +233% |
| RAG 성능 | Baseline | +60% | 캐싱 |
| API 안정성 | 수동 | 자동 3회 | 재시도 |
| 설정 방식 | 하드코딩 | .env 기반 | 유연성 |
| 이미지 해상도 | 200px 축소 | 원본 보존 | v0.2.6 수정 |

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

### 2️⃣ 환경 설정

#### 방법 1: 대화형 설정 (권장 ⭐)

```bash
# 대화형 설정 마법사 실행
lecture-forge init
```

이 명령어는 다음을 수행합니다:
- ✅ 플랫폼별 최적 위치에 `.env` 파일 자동 생성
  - **Windows**: `%LOCALAPPDATA%\lecture-forge\.env`
  - **Mac/Linux**: `~/.lecture-forge/.env`
- ✅ 필수 API 키 입력 안내 (OpenAI, Serper)
- ✅ 선택적 이미지 검색 API 설정 (Pexels, Unsplash)
- ✅ 파일 권한 자동 설정 (Unix/Mac: 600)

#### 방법 2: 수동 설정

```bash
# .env 파일 생성 (프로젝트 개발 시)
cp .env.example .env
```

`.env` 파일을 열어 다음 항목을 설정하세요:

**필수 API 키**:
```bash
# OpenAI API (필수)
OPENAI_API_KEY=sk-proj-...

# 검색 API (필수)
SERPER_API_KEY=...                # 무료: 2,500회/월
```

**선택 사항**:
```bash
# 이미지 검색 API (선택)
PEXELS_API_KEY=...                # 무료 무제한
UNSPLASH_ACCESS_KEY=...           # 무료: 50회/시간

# 검색 및 크롤링 설정 (기본값으로 충분)
SEARCH_NUM_RESULTS=10             # 검색 결과 수 (최대 100)
DEEP_CRAWLER_MAX_PAGES=10         # 크롤링 페이지 수
IMAGE_SEARCH_PER_PAGE=10          # 이미지 검색 결과 수

# 품질 설정
QUALITY_THRESHOLD=80              # 품질 임계값 (70-90)
MAX_ITERATIONS=3                  # 최대 개선 반복 횟수
```

💡 **더 많은 설정 옵션은 `.env.example` 파일 참조**

#### .env 파일 위치

LectureForge는 다음 순서로 `.env` 파일을 탐색합니다:

1. **환경 변수**: `LECTURE_FORGE_ENV_FILE`로 지정한 경로
2. **현재 디렉토리**: `./.env`
3. **사용자 디렉토리** (권장):
   - Windows: `%LOCALAPPDATA%\lecture-forge\.env`
   - Mac/Linux: `~/.lecture-forge/.env`

**API 키 획득**:
- **OpenAI**: [platform.openai.com](https://platform.openai.com/) (사용량 기반 과금)
- **Serper**: [serper.dev](https://serper.dev/) (무료 2,500회/월)
- **Pexels**: [pexels.com/api](https://www.pexels.com/api/) (무료)
- **Unsplash**: [unsplash.com/developers](https://unsplash.com/developers) (무료 50회/시간)

### 3️⃣ 첫 강의 생성

```bash
lecture-forge create
```

대화형으로 강의 정보를 입력하면 자동으로 강의자료가 생성됩니다! 🎉

---

## 💻 사용법

### 명령어 개요

| 명령어 | 설명 | 주요 옵션 |
|--------|------|----------|
| **init** | 초기 설정 | `--path` |
| **create** | 강의 생성 | `--image-search`, `--quality-level` |
| **chat** | Q&A 모드 | `--knowledge-base` |
| **edit-images** | 이미지 편집 | `--output` |
| **improve** | 강의 향상 | `--to-slides` |
| **cleanup** | 지식베이스 관리 | `--all` |

### 빠른 실행 예제

```bash
# 🚀 초기 설정 (처음 한 번만)
lecture-forge init

# 🎓 강의 생성 (대화형 - 가장 간단)
lecture-forge create

# 🎓 고품질 강의 (이미지 검색 포함)
lecture-forge create --image-search --quality-level strict

# 💬 Q&A 모드 (자동으로 최신 지식베이스 선택)
lecture-forge chat

# 🎨 슬라이드 변환
lecture-forge improve outputs/lecture.html --to-slides

# 🖼️ 이미지 편집
lecture-forge edit-images outputs/lecture.html

# 🧹 지식베이스 정리 (대화형 선택)
lecture-forge cleanup
```

### 명령어 상세 가이드

#### 🚀 `init` - 초기 설정

**기본 사용:**
```bash
lecture-forge init
```
대화형 마법사가 API 키 입력을 안내하고 자동으로 `.env` 파일을 생성합니다.

**옵션:**

| 옵션 | 설명 | 사용 예 |
|------|------|---------|
| `--path PATH` | 커스텀 디렉토리 지정 | `--path /custom/path` |

**기본 저장 위치:**
- **Windows**: `C:\Users\<username>\AppData\Local\lecture-forge\.env`
- **Mac/Linux**: `~/.lecture-forge/.env`

**예제:**
```bash
# 기본 위치에 설정 (권장)
lecture-forge init

# 커스텀 디렉토리 사용
lecture-forge init --path /my/config/dir

# 현재 디렉토리에 생성
lecture-forge init --path .
```

**하는 일:**
1. 필수 API 키 입력 (OpenAI, Serper)
2. 선택적 이미지 API 설정 (Pexels, Unsplash)
3. `.env` 파일 자동 생성
4. 기본 설정 값 자동 설정
5. 파일 권한 보안 설정 (Unix/Mac)

---

#### 📚 `create` - 강의 생성

**기본 사용:**
```bash
lecture-forge create
```
대화형으로 정보를 입력하면 자동으로 강의를 생성합니다.

**옵션:**

| 옵션 | 설명 | 사용 예 |
|------|------|---------|
| `--config FILE` | YAML 설정 파일 사용 | `--config lecture.yaml` |
| `--image-search` | 웹 이미지 검색 활성화 (Pexels/Unsplash) | `--image-search` |
| `--quality-level LEVEL` | 품질 기준 설정 | `--quality-level strict` |
| `--output FILE` | 출력 파일명 지정 | `--output my_lecture.html` |
| `--include-pdf-images` | PDF 이미지 포함 (비권장, Location-based가 더 좋음) | `--include-pdf-images` |

**품질 레벨:**
- `lenient` (70점): 빠른 초안
- `balanced` (80점): 기본값 ✅
- `strict` (90점): 고품질

**예제:**
```bash
# 기본 생성
lecture-forge create

# 고품질 + 이미지 검색
lecture-forge create --image-search --quality-level strict

# YAML 설정 사용
lecture-forge create --config my_config.yaml
```

---

#### 💬 `chat` - Q&A 모드

**기본 사용:**
```bash
lecture-forge chat
```
자동으로 최신 지식베이스를 선택합니다.

**옵션:**

| 옵션 | 설명 | 사용 예 |
|------|------|---------|
| `--knowledge-base PATH` | 특정 지식베이스 지정 | `-kb ./data/vector_db/AI_xxx` |

**대화형 명령어:**
- `/help`: 도움말 표시
- `/exit` 또는 `/quit`: 종료
- `/clear`: 채팅 기록 지우기
- `/sources`: 마지막 답변의 출처 표시

**예제:**
```bash
# 자동 선택
lecture-forge chat

# 특정 지식베이스 사용
lecture-forge chat -kb ./data/vector_db/lecture_20260209_123456
```

---

#### 🖼️ `edit-images` - 이미지 편집

**기본 사용:**
```bash
lecture-forge edit-images outputs/lecture.html
```

**옵션:**

| 옵션 | 설명 | 사용 예 |
|------|------|---------|
| `--output FILE` | 출력 파일 경로 | `-o outputs/edited.html` |

**대화형 명령어:**

| 명령어 | 설명 | 예시 |
|--------|------|------|
| `d <번호>` | 이미지 삭제 | `d 3` |
| `u <번호>` | 삭제 취소 | `u 3` |
| `r <번호>` | 이미지 교체 (Vector DB 검색) | `r 5` |
| `s` | 변경사항 저장 | `s` |
| `q` | 종료 (저장 안 함) | `q` |
| `h` | 도움말 | `h` |

**예제:**
```bash
# 기본 (원본_edited.html로 저장)
lecture-forge edit-images outputs/my_lecture.html

# 출력 파일 지정
lecture-forge edit-images outputs/my_lecture.html -o outputs/final.html
```

---

#### 🎨 `improve` - 강의 향상

**기본 사용:**
```bash
lecture-forge improve outputs/lecture.html --to-slides
```

**옵션:**

| 옵션 | 설명 | 사용 예 |
|------|------|---------|
| `--to-slides` | Reveal.js 슬라이드 변환 | `--to-slides` |
| `--enhance-pdf-images` | PDF 이미지 설명 추가 (레거시) | `--enhance-pdf-images` |
| `--source-pdf FILE` | 원본 PDF 경로 (레거시용) | `--source-pdf doc.pdf` |

⚠️ **주의**: `--enhance-pdf-images`는 레거시 기능입니다. v0.2.0부터는 Location-based 매칭이 자동으로 적용됩니다.

**예제:**
```bash
# 슬라이드 변환 (권장)
lecture-forge improve outputs/lecture.html --to-slides

# PDF 이미지 보강 (레거시)
lecture-forge improve outputs/lecture.html --enhance-pdf-images --source-pdf original.pdf
```

---

#### 🧹 `cleanup` - 지식베이스 관리

**기본 사용:**
```bash
lecture-forge cleanup
```
대화형으로 삭제할 지식베이스를 선택합니다.

**옵션:**

| 옵션 | 설명 | 사용 예 |
|------|------|---------|
| `--all` | 모든 지식베이스 삭제 (⚠️ 주의!) | `--all` |

**예제:**
```bash
# 대화형 선택 (안전)
lecture-forge cleanup

# 전체 삭제 (복구 불가능!)
lecture-forge cleanup --all
```

### 📤 출력 결과

강의 생성 완료 후 다음 파일들이 생성됩니다:

```
outputs/
├── [주제]_[날짜시간].html           # 📄 HTML 강의자료
└── [주제]_[날짜시간]_slides.html   # 🎬 슬라이드 (--to-slides 사용 시)

data/
└── vector_db/
    └── [주제]_[날짜시간]/           # 🗄️ 지식베이스 (Q&A용)
        ├── chroma.sqlite3
        └── ...
```

**포함 내용:**
- ✅ **HTML 강의자료**: 이미지, Mermaid 다이어그램, 코드 하이라이팅, 검색 인덱스
- ✅ **지식베이스**: ChromaDB 벡터 DB (대화형 Q&A 지원)
- ✅ **통계 정보**: 품질 점수, 토큰 사용량, 예상 비용
- ✅ **슬라이드**: Reveal.js 프레젠테이션 (선택 사항)

### 🔧 고급 설정 (.env 파일)

더 많은 제어가 필요한 경우 `.env` 파일에서 다음 설정을 조정할 수 있습니다:

```bash
# 검색 및 크롤링
SEARCH_NUM_RESULTS=20              # 기본: 10, 최대: 100
DEEP_CRAWLER_MAX_PAGES=30          # 기본: 10
DEEP_CRAWLER_MAX_DEPTH=3           # 기본: 2

# 이미지
IMAGE_SEARCH_PER_PAGE=15           # 기본: 10
MAX_IMAGES_PER_SEARCH=20           # 기본: 10

# 품질
QUALITY_THRESHOLD=90               # 기본: 80 (70-90)
MAX_ITERATIONS=5                   # 기본: 3

# 성능
CHUNK_SIZE=800                     # 기본: 1000 (작을수록 정밀)
WEB_SCRAPER_TIMEOUT=60             # 기본: 30초
```

💡 **전체 설정 목록**: `.env.example` 파일 참조 (15+ 환경변수)

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
┃ 번호  ┃ 설명                               ┃ 섹션              ┃ 페이지   ┃ 상태      ┃
┡━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━┩
│  1   │ Neural network architecture       │ 1. Introduction  │  5     │ 유지      │
│  2   │ Backpropagation diagram           │ 2. Core Concepts │  12    │ 🗑️ 삭제   │
│  3   │ Training process flowchart        │ 2. Core Concepts │  15    │ 🔄 교체   │
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
│  CLI Interface (입력 수집, 진행 상황, Q&A 인터랙션)                │
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────┴────────────────┐
        │    Pipeline Orchestrator        │
        └────────────────┬────────────────┘
                         │
    ┌────────────────────┴──────────────────┐
    │                                       │
┌───▼────────────┐                   ┌──────▼──────────┐
│  Phase 1-2     │                   │  Knowledge Base │
│  Collection    │──────────────────▶│  (Vector DB)    │
│  & Analysis    │                   │  + RAG Caching  │
└───┬────────────┘                   └──────┬──────────┘
    │                                       │
┌───▼────────────┐                          │
│  Phase 3-4     │◀─────────────────────────┘
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

<details>
<summary><b>Q: 어떤 Python 버전이 필요한가요?</b></summary>

A: Python 3.11 이상이 필요합니다.
```bash
python --version  # Python 3.11+ 확인
```
</details>

<details>
<summary><b>Q: API 키가 꼭 필요한가요?</b></summary>

A:
- **필수**: OpenAI API, Serper API
- **선택**: Pexels API, Unsplash API (이미지 검색용)

이미지 API 없이도 PDF/웹 이미지만으로 작동합니다.
</details>

<details>
<summary><b>Q: 비용이 얼마나 드나요?</b></summary>

A: **실제 측정 비용** (v0.2.4+ 기준):
- 60분 강의: 약 **$0.035**
- 180분 강의: 약 **$0.105**

(GPT-4o-mini 사용. 보수적 이론 추정: $0.22/180분)

생성 완료 후 정확한 비용이 표시됩니다.
</details>

<details>
<summary><b>Q: .env 파일 설정을 바꾸려면?</b></summary>

A: `.env` 파일을 열어 원하는 값을 수정하세요:
```bash
# 검색 결과 증가
SEARCH_NUM_RESULTS=20

# 크롤링 범위 확대
DEEP_CRAWLER_MAX_PAGES=30

# 타임아웃 증가
WEB_SCRAPER_TIMEOUT=60
```

변경 후 재시작하면 바로 적용됩니다.
</details>

### 사용법

<details>
<summary><b>Q: 오프라인에서 사용 가능한가요?</b></summary>

A:
- **생성 시**: API 필요 (OpenAI, Serper 등)
- **생성 후**: HTML 파일과 지식창고는 오프라인 사용 가능
- **Chat 모드**: 지식창고는 오프라인 작동하지만 LLM API는 필요
</details>

<details>
<summary><b>Q: 품질 레벨의 차이는?</b></summary>

A:
| 레벨 | 임계값 | 용도 | 시간 |
|------|--------|------|------|
| `lenient` | 70점 | 빠른 초안 | 짧음 |
| `balanced` | 80점 | **기본값** ✅ | 보통 |
| `strict` | 90점 | 고품질 프로덕션 | 김 |

임계값 미달 시 최대 3회 자동 개선합니다.
</details>

<details>
<summary><b>Q: Chat 모드 종료 방법은?</b></summary>

A: 다음 중 하나 사용:
- `/exit` 또는 `/quit`
- `exit` 또는 `quit`
- `Ctrl+C`
</details>

<details>
<summary><b>Q: 이미지가 제대로 매칭되지 않으면?</b></summary>

A: v0.2.0의 Location-based 매칭이 자동으로 작동합니다:
1. PDF 이미지: 85% 자동 매칭 (페이지 기반)
2. 웹 이미지: 키워드 기반 보완
3. 수동 편집: `lecture-forge edit-images`로 교체 가능
</details>

### 기술적 질문

<details>
<summary><b>Q: 테스트는 어떻게 실행하나요?</b></summary>

```bash
# 전체 테스트
pytest tests/ -v

# 커버리지 확인
pytest tests/ --cov=lecture_forge --cov-report=html

# 특정 테스트
pytest tests/unit/agents/test_content_writer.py -v

# 특정 에이전트만
pytest tests/unit/agents/ -v
```
</details>

<details>
<summary><b>Q: API 호출이 실패하면 어떻게 되나요?</b></summary>

A: v0.2.0부터 **자동 재시도** 기능이 있습니다:
- 최대 3회 재시도
- 지수 백오프: 2초 → 4초 → 10초
- 일시적 오류 자동 복구
- OpenAI, Serper, Pexels, Unsplash 모두 지원
</details>

<details>
<summary><b>Q: RAG 쿼리 캐싱은 어떻게 작동하나요?</b></summary>

A:
- 쿼리와 결과 개수를 MD5 해시로 변환하여 메모리 캐시
- 동일 질문은 **60% 빠른 응답**
- 캐시 히트/미스 통계 자동 추적
- 세션 동안 유지 (프로세스 종료 시 초기화)
</details>

<details>
<summary><b>Q: 설정을 환경별로 다르게 하려면?</b></summary>

A: `.env` 파일을 환경별로 분리하세요:
```bash
# 개발 환경
.env.development

# 프로덕션 환경
.env.production

# 사용
cp .env.production .env
lecture-forge create
```
</details>

---

## 📝 변경 이력

### v0.2.6 (2026-02-12) - 🐛 Critical Image Bug Fix

**Critical Bug Fix**:
- 🐛 **이미지 thumbnail 버그 완전 해결**: 품질 분석 중 원본 이미지가 200px로 축소되던 치명적 버그 수정
  - **문제**: `_analyze_image_content_fast()`에서 `pil_image.thumbnail()` 호출 시 원본 이미지 수정
  - **증상**: 모든 PDF 추출 이미지가 정확히 200px 너비로 저장됨 (예: 200x44, 200x89, 200x125)
  - **해결**: 분석 전 이미지 복사본 생성 (`pil_image.copy()`)으로 원본 보존
  - **결과**: 800x600 이미지는 이제 **800x600 그대로 저장** ✅

**영향**:
- ✅ PDF 이미지 **원본 크기 완전 보존**
- ✅ IMAGE_MIN_WIDTH=500, IMAGE_MIN_HEIGHT=300 필터 정상 작동
- ✅ 고해상도 이미지 품질 완전 보장
- ✅ v0.2.5의 이미지 품질 개선 기능이 이제 정상 작동

**기술 상세**:
```python
# 수정 전 (버그 - image_extractor.py:333):
pil_image.thumbnail((200, 200), Image.Resampling.LANCZOS)  # ❌ 원본 수정!

# 수정 후 (정상):
analysis_img = pil_image.copy()  # ✅ 복사본 생성
analysis_img.thumbnail((200, 200), Image.Resampling.LANCZOS)  # ✅ 복사본만 수정
```

### v0.2.5 (2026-02-12) - Image Quality & Resolution Improvements (Partial) 🖼️

**주의**: v0.2.5의 이미지 개선 기능은 thumbnail 버그(v0.2.6에서 수정)로 인해 부분적으로만 작동했습니다.

**이미지 품질 혁신**
- 🎨 **고품질 WebP 저장**: quality=95, method=6 적용 (이미지 압축 시 품질 손실 방지)
- 📐 **Full HD 해상도**: IMAGE_MAX_WIDTH 1200px → 1920px (고해상도 지원)
- 🔍 **최소 크기 강화**: IMAGE_MIN_WIDTH 200px → 500px, IMAGE_MIN_HEIGHT 200px → 300px
- ⬆️ **API 품질 업그레이드**:
  - Unsplash "regular" (1080px) → "full" (2400px)
  - Pexels "large" (940px) → "original" (전체 크기)

**이미지 표시 개선**
- 🎯 **HTML 템플릿 최적화**: `w-full` → `max-w-full` + `min-width: 600px` (작은 이미지 강제 확대 방지)
- ✨ **CSS 렌더링 향상**: `image-rendering: crisp-edges` (고품질 렌더링)
- 📱 **반응형 크기 조정**: 모바일/데스크톱 적응형 이미지 크기

**이미지 편집 개선**
- 🔧 **VectorStore 초기화 수정**: `persist_directory` → `collection_name` 파라미터 사용
- 📂 **파일시스템 폴백 검색**: Vector DB 실패 시 페이지 기반 스코어링으로 대안 검색
- 🎯 **스마트 디렉토리 탐지**: `./data/images` 우선 탐색 (개발 모드 지원)

**Config 개선**
- ⚙️ **기본값 업데이트**: `.env.example` 및 `config.py` 최적화

### v0.2.2 (2026-02-11) - Documentation & Consistency Updates 📝

**문서화**
- 📝 버전 정보 통일 (setup.py, pyproject.toml, __version__.py, CLI, 문서)
- 📖 CLAUDE.md, README.md, INPUT_LIMITS_ANALYSIS.md 업데이트
- ✨ 코드와 문서 일치성 개선

### v0.2.1 (2026-02-10) - Bug Fixes & Improvements 🐛

**버그 수정**
- 🐛 Visual score 항상 0으로 표시되는 문제 수정 (이미지 카운팅 로직 추가)
- 🐛 품질 평가 무한 반복 문제 해결 (섹션별 임계값 완화 + 조기 종료)
- 🐛 슬라이드 orphaned heading 문제 개선 (look-ahead 로직 적용)

**개선사항**
- ✨ CLI 도움말 텍스트 가독성 향상 (줄바꿈 개선)
- ✨ Reveal.js 키보드 단축키 설명 추가 (--to-slides 도움말)
- ✨ 슬라이드 구성 알고리즘 개선 (max_items_per_slide 3→4)
- ✨ 품질 평가 효율성 향상 (3점 미만 개선 시 조기 종료)

**문서**
- 📚 INPUT_LIMITS_ANALYSIS.md에 멀티소스 전략 상세 분석 추가 (Section 8)
- 📖 README.md 및 CLAUDE.md v0.2.1 정보 업데이트

### v0.2.0 (2026-02-09) - Enhanced Quality Release 🚀

**성능 향상**
- ⚡ RAG 쿼리 캐싱 (60% 성능 향상)
- 🔄 자동 API 재시도 로직 (지수 백오프)

**품질 개선**
- 🧪 77+ 단위 테스트 작성 (35%+ 커버리지)
- 🔧 타입 힌트 75% 커버리지 (40% → 75%)
- 🐛 Config 검증 런타임 이동
- 🐛 Bare except 안티패턴 수정

**설정 관리**
- 🔧 **Config 리팩토링**: 모든 하드코딩 제거, .env 기반 설정 시스템 도입
- ⚙️ **15+ 환경변수**: 검색, 크롤링, 이미지, 타임아웃 등 모든 설정 조정 가능
- 🎛️ **유연한 배포**: 개발/프로덕션 환경별 설정 분리 지원

**문서**
- 📚 CLAUDE.md, README.md, INPUT_LIMITS_ANALYSIS.md 업데이트
- 📖 Config 기반 설정 가이드 추가

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

- **이슈 트래커**: [GitHub Issues](https://github.com/bullpeng72/Lecture_forge/issues)
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
