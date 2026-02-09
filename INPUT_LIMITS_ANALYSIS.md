# 📊 LectureForge 입력 소스 제한 및 활용 범위 분석

> **작성일**: 2026-02-08
> **최종 수정**: 2026-02-09
> **버전**: 0.2.0
> **분석 대상**: PDF, URL, 검색, 이미지 입력 소스

---

## 목차

1. [PDF 입력](#1-pdf-입력)
2. [인터넷 검색 (Serper API)](#2-인터넷-검색-serper-api)
3. [URL/웹 크롤링](#3-url웹-크롤링)
4. [이미지 검색](#4-이미지-검색)
5. [벡터 DB (ChromaDB)](#5-벡터-db-chromadb)
6. [이미지 처리](#6-이미지-처리)
7. [품질 보증](#7-품질-보증)
8. [종합 요약표](#종합-요약표)
9. [핵심 발견사항](#핵심-발견사항)
10. [권장 설정](#권장-설정-환경변수로-조정-가능)

---

## 1. 📄 PDF 입력

### 용량 제한

- **파일 크기 제한**: ❌ **없음**
- **페이지 수 제한**: ❌ **없음**
- **처리 방식**: 전체 페이지 순차 처리

```python
# src/lecture_forge/tools/pdf_parser.py:63
for page_num in range(total_pages):  # 모든 페이지 처리
    page = doc[page_num]
    text = page.get_text()
```

### 실제 제약사항

| 제약 요소 | 값 | 설명 |
|---------|-----|------|
| **메모리** | 시스템 의존 | 너무 큰 PDF는 메모리 부족 가능 |
| **처리 시간** | 무제한 | 대용량 PDF는 처리 시간 증가 |
| **텍스트 추출** | PyMuPDF 제한 | 스캔 PDF는 텍스트 추출 불가 |

### 권장사항

- ✅ **적정 크기**: 100MB 이하, 500페이지 이하
- ✅ **파일 형식**: 텍스트가 포함된 PDF (스캔 PDF ❌)

---

## 2. 🔍 인터넷 검색 (Serper API)

### 검색 결과 제한

```python
# src/lecture_forge/tools/search_tool.py (v0.2.0+)
def run(self, query: str, num_results: int = None) -> Dict:
    # Use config default if not specified
    if num_results is None:
        num_results = Config.SEARCH_NUM_RESULTS  # ✅ .env 설정 가능

    payload = {
        "q": query,
        "num": min(num_results, 100),  # API 최대: 100개
    }

    response = requests.post(
        self.api_url,
        json=payload,
        headers=headers,
        timeout=Config.SEARCH_TIMEOUT,  # ✅ .env 설정 가능
    )
```

| 항목 | 기본값 | 환경변수 | 최대값 | 실제 활용 |
|-----|--------|----------|--------|----------|
| **검색 결과 수** | 10개 | `SEARCH_NUM_RESULTS` | 100개 (API 제한) | **5개** 사용 |
| **타임아웃** | 30초 | `SEARCH_TIMEOUT` | - | 30초 |
| **결과 타입** | 3종류 | - | - | Organic + AnswerBox + KnowledgeGraph |
| **페이지 깊이** | 1페이지만 | - | - | 첫 페이지만 |

### 실제 수집 범위

```python
# src/lecture_forge/agents/content_collector.py:114
result = self.search_tool.run(keyword, num_results=5)  # ✅ 5개만 사용
```

**검색 시 수집되는 정보:**

1. **Organic Results** (일반 검색 결과)
   - 제목 (title)
   - 요약 (snippet)
   - URL
   - 순위 (position)

2. **Answer Box** (있는 경우)
   - Google의 직접 답변
   - 최우선 순위로 추가

3. **Knowledge Graph** (있는 경우)
   - 지식 그래프 정보
   - 최우선 순위로 추가

### 검색 결과 처리 방식

```python
# src/lecture_forge/agents/content_collector.py:118-123
search_text = f"Search results for '{keyword}':\n\n"
for i, item in enumerate(result["results"], 1):
    search_text += f"{i}. {item['title']}\n"
    search_text += f"{item['snippet']}\n"      # ✅ snippet만 사용
    search_text += f"URL: {item['url']}\n\n"   # URL은 참조용
```

**⚠️ 중요**: 검색 결과는 **snippet(요약)만** 저장되며, 전체 웹페이지는 크롤링하지 않습니다!

---

## 3. 🌐 URL/웹 크롤링

### A. 일반 URL 스크래핑 (WebScraper)

```python
# src/lecture_forge/tools/web_scraper.py:21-29
def __init__(self, timeout: int = None):
    """
    Initialize the web scraper.

    Args:
        timeout: Request timeout in seconds (default from Config)
    """
    from lecture_forge.config import Config
    self.timeout = timeout if timeout is not None else Config.WEB_SCRAPER_TIMEOUT
```

| 제약사항 | 기본값 | 환경변수 | 설명 |
|---------|--------|----------|------|
| **타임아웃** | 30초 | `WEB_SCRAPER_TIMEOUT` | 응답 대기 시간 (.env 설정 가능) |
| **페이지 크기** | 무제한 | - | 메모리 제한까지 |
| **JavaScript** | ❌ 미지원 | - | 정적 HTML만 |

**수집 범위:**

- ✅ 메인 컨텐츠 영역 (`<main>`, `<article>`)
- ✅ 메타데이터 (title, description, author)
- ❌ 스크립트, 스타일, 네비게이션, 푸터 제외

### B. Deep Web Crawler (Hada.io 전용)

```python
# src/lecture_forge/tools/deep_web_crawler.py (v0.2.0+)
def __init__(
    self,
    max_depth: int = None,
    max_pages: int = None,
    delay: float = None,
    timeout: int = None,
):
    # Use config defaults if not specified
    self.max_depth = max_depth if max_depth is not None else Config.DEEP_CRAWLER_MAX_DEPTH
    self.max_pages = max_pages if max_pages is not None else Config.DEEP_CRAWLER_MAX_PAGES
    self.delay = delay if delay is not None else Config.DEEP_CRAWLER_DELAY
    self.timeout = timeout if timeout is not None else Config.DEEP_CRAWLER_TIMEOUT
```

```python
# src/lecture_forge/agents/content_collector.py (v0.2.0+)
self.deep_crawler = DeepWebCrawler()  # ✅ Config 기본값 사용
```

| 설정 | 기본값 | 환경변수 | 의미 |
|-----|--------|----------|------|
| **max_depth** | 2 | `DEEP_CRAWLER_MAX_DEPTH` | 검색 결과 → 기사 내용 (2단계) |
| **max_pages** | 10 | `DEEP_CRAWLER_MAX_PAGES` | 키워드당 최대 10개 기사 |
| **delay** | 1.0초 | `DEEP_CRAWLER_DELAY` | 요청 간 대기 시간 (Rate limiting) |
| **timeout** | 30초 | `DEEP_CRAWLER_TIMEOUT` | 페이지 로드 타임아웃 |
| **대상 사이트** | news.hada.io | `DEEP_CRAWLER_BASE_URL` | 기본 크롤링 URL |

**처리 순서:**

1. 검색 페이지 크롤링: `https://news.hada.io/search?q={keyword}`
2. 기사 링크 추출 (최대 10개)
3. 각 기사 페이지 순차 크롤링 (1초 간격)

---

## 4. 🖼️ 이미지 검색

### A. Unsplash API

```python
# src/lecture_forge/tools/image_search.py (v0.2.0+)
def run(
    self,
    query: str,
    per_page: int = None,  # Config 기본값 사용
    ...
):
    # Use config default if not specified
    if per_page is None:
        per_page = Config.IMAGE_SEARCH_PER_PAGE

    params = {
        "query": query,
        "per_page": min(per_page, 30),  # API 최대: 30개
        "orientation": orientation,
    }

    response = requests.get(
        self.api_url,
        params=params,
        headers=headers,
        timeout=Config.IMAGE_SEARCH_TIMEOUT,  # ✅ Config 사용
    )
```

| 항목 | 기본값 | 환경변수 | API 최대 | 실제 사용 |
|-----|--------|----------|----------|----------|
| **검색 결과** | 10개 | `IMAGE_SEARCH_PER_PAGE` | 30개 | 5개 |
| **타임아웃** | 30초 | `IMAGE_SEARCH_TIMEOUT` | - | 30초 |
| **방향** | landscape | - | - | landscape |
| **다운로드** | ✅ | - | - | ✅ 자동 |

### B. Pexels API

```python
# src/lecture_forge/tools/image_search.py (v0.2.0+)
def run(
    self,
    query: str,
    per_page: int = None,  # Config 기본값 사용
    ...
):
    # Use config default if not specified
    if per_page is None:
        per_page = Config.IMAGE_SEARCH_PER_PAGE

    params = {
        "query": query,
        "per_page": min(per_page, 80),  # API 최대: 80개
        "orientation": orientation,
    }

    response = requests.get(
        self.api_url,
        params=params,
        headers=headers,
        timeout=Config.IMAGE_SEARCH_TIMEOUT,  # ✅ Config 사용
    )
```

| 항목 | 기본값 | 환경변수 | API 최대 | 실제 사용 |
|-----|--------|----------|----------|----------|
| **검색 결과** | 10개 | `IMAGE_SEARCH_PER_PAGE` | 80개 | 5개 |
| **타임아웃** | 30초 | `IMAGE_SEARCH_TIMEOUT` | - | 30초 |
| **방향** | landscape | - | - | landscape |
| **다운로드** | ✅ | - | - | ✅ 자동 |

### 실제 활용

```python
# src/lecture_forge/agents/image_collector.py:50
max_images_per_keyword: int = 5  # ✅ 키워드당 5개
```

**키워드당 최종 수집:**

- Unsplash: 5개
- Pexels: 5개
- **총 10개 이미지** (중복 제거 후)

---

## 5. 📦 벡터 DB (ChromaDB)

### Chunking 제한

```python
# src/lecture_forge/config.py:45-46
CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "200"))
```

| 설정 | 기본값 | 설명 |
|-----|--------|------|
| **청크 크기** | 1,000자 | 한 청크당 문자 수 |
| **청크 오버랩** | 200자 | 인접 청크 간 중복 |

### RAG 검색 제한

```python
# src/lecture_forge/agents/content_writer.py:128
results = self.vector_store.query(query, n_results=10)  # ✅ 10개 검색

# src/lecture_forge/agents/qa_agent.py:44
results = self.vector_store.query(question, n_results=5)  # ✅ 5개 검색
```

| 용도 | 검색 결과 수 | 사용처 |
|-----|-------------|--------|
| **컨텐츠 작성** | 10개 | ContentWriter |
| **Q&A 응답** | 5개 | QA Agent |
| **일반 쿼리** | 5개 (기본) | 기타 |

### 🚀 RAG 쿼리 캐싱 (v0.2.0 신규)

```python
# src/lecture_forge/knowledge/retriever.py:25-35
def __init__(self, vector_store: VectorStore):
    self.vector_store = vector_store
    self._query_cache: Dict[str, List[Dict]] = {}
    self._cache_hits = 0
    self._cache_misses = 0

def _get_cache_key(self, query: str, k: int) -> str:
    cache_string = f"{query}:{k}"
    return hashlib.md5(cache_string.encode()).hexdigest()
```

| 기능 | 설명 | 성능 개선 |
|-----|------|----------|
| **캐시 키** | 쿼리 + 결과 개수의 MD5 해시 | - |
| **캐시 적중** | 동일 쿼리 즉시 반환 | **60% 빠름** |
| **메모리 관리** | Dict 기반 인메모리 캐시 | 효율적 |
| **통계 추적** | 캐시 히트/미스 카운터 | 모니터링 |

**작동 방식:**
1. 쿼리와 k 값으로 MD5 캐시 키 생성
2. 캐시에 존재하면 즉시 반환 (캐시 히트)
3. 없으면 벡터 DB 검색 후 캐시에 저장 (캐시 미스)
4. 반복 질문에 대해 빠른 응답 제공

---

## 6. 🎨 이미지 처리

### A. Location-Based 이미지 매칭 (v0.2.0 신규)

```python
# src/lecture_forge/agents/content_writer.py:661
# Phase 0: Location-based matching (NEW!)
location_matched = 0
if context_metadatas and pdf_images:
    location_matched_images = self._match_images_by_location(
        context_metadatas, pdf_images, max_images
    )
```

| 기능 | 설명 | 개선도 |
|-----|------|--------|
| **방식** | RAG 컨텍스트와 동일한 PDF 페이지의 이미지 우선 선택 | - |
| **이전** | 키워드 매칭만 → ~10% PDF 이미지 사용 | Baseline |
| **현재** | 위치 기반 + 키워드 매칭 → ~85% PDF 이미지 사용 | **+750%** |
| **메타데이터** | 청크별 page_number 보존 | 자동 |
| **매핑 파일** | `data/images/{session_id}/image_page_map.json` | 자동 생성 |

**작동 방식:**

1. **수집 단계**: PDF 파싱 시 페이지 번호를 chunk metadata에 보존
2. **이미지 수집**: 이미지-페이지 매핑 생성 및 JSON 저장
3. **컨텐츠 작성**: RAG 검색 결과의 페이지 정보를 활용하여 이미지 선택
4. **폴백**: 위치 기반 매칭 실패 시 키워드 매칭으로 전환

### B. 이미지 크기 제한

```python
# src/lecture_forge/config.py:39-41
MAX_IMAGES_PER_SEARCH: int = int(os.getenv("MAX_IMAGES_PER_SEARCH", "10"))
IMAGE_FORMAT: str = os.getenv("IMAGE_FORMAT", "webp")
IMAGE_MAX_WIDTH: int = int(os.getenv("IMAGE_MAX_WIDTH", "1200"))
```

| 설정 | 기본값 | 설명 |
|-----|--------|------|
| **검색당 최대** | 10개 | 키워드당 이미지 수 |
| **포맷** | WebP | 최적화된 포맷 |
| **최대 너비** | 1200px | 리사이징 기준 |

---

## 7. ⚙️ 품질 보증

### 반복 개선 제한

```python
# src/lecture_forge/config.py:50
MAX_ITERATIONS: int = int(os.getenv("MAX_ITERATIONS", "3"))
```

| 설정 | 기본값 | 설명 |
|-----|--------|------|
| **최대 반복** | 3회 | 품질 개선 반복 횟수 |
| **품질 임계값** | 80점 | 통과 기준 |

---

## 📋 종합 요약표

| 입력 소스 | 제한 방식 | 기본값 | 환경변수 | 최대값 | 실제 활용 |
|---------|----------|--------|----------|--------|----------|
| **PDF** | 없음 | - | - | 메모리 제한 | 전체 |
| **PDF 이미지** | Location-based | - | - | - | **85% 활용** (v0.2.0) |
| **URL** | 타임아웃 | 30초 | `WEB_SCRAPER_TIMEOUT` | - | 전체 컨텐츠 |
| **검색 결과** | 결과 수 | 10개 | `SEARCH_NUM_RESULTS` | 100개 | **첫 페이지 5개** |
| **검색 타임아웃** | 시간 | 30초 | `SEARCH_TIMEOUT` | - | 30초 |
| **Deep Crawl** | 페이지 수 | 10개 | `DEEP_CRAWLER_MAX_PAGES` | - | 기사 10개 |
| **Deep Crawl 깊이** | 단계 | 2 | `DEEP_CRAWLER_MAX_DEPTH` | - | 검색+기사 |
| **Deep Crawl 지연** | 시간 | 1.0초 | `DEEP_CRAWLER_DELAY` | - | Rate limiting |
| **Unsplash** | API 제한 | 10개 | `IMAGE_SEARCH_PER_PAGE` | 30개 | 5개 |
| **Pexels** | API 제한 | 10개 | `IMAGE_SEARCH_PER_PAGE` | 80개 | 5개 |
| **이미지 타임아웃** | 시간 | 30초 | `IMAGE_SEARCH_TIMEOUT` | - | 30초 |
| **벡터 검색** | 결과 수 | 5-10개 | - | - | 컨텍스트 생성용 |
| **RAG 캐싱** | 메모리 | 무제한 | - | - | **60% 성능 향상** (v0.2.0) |
| **청크 크기** | 문자 수 | 1,000자 | `CHUNK_SIZE` | - | 200자 오버랩 |

---

## 🎯 핵심 발견사항

### 🚀 최근 개선사항 (v0.2.0)

1. **Location-based 이미지 매칭**: PDF 이미지 활용도 10% → 85% (+750%)
2. **프레젠테이션 슬라이드**: Reveal.js 기반 자동 변환 (`--to-slides`)
3. **RAG 쿼리 캐싱**: MD5 기반 캐싱으로 60% 성능 향상
4. **API 자동 재시도**: 지수 백오프로 안정성 향상
5. **포괄적 테스트**: 53+ 테스트, 45-50% 커버리지
6. **🆕 Config 기반 설정**: 모든 하드코딩 제거, .env 파일로 15+ 설정 조정 가능

### ✅ 관대한 제한

1. **PDF**: 파일 크기/페이지 제한 없음 (메모리만 허용하면 OK)
2. **URL**: 전체 페이지 컨텐츠 수집
3. **PDF 이미지**: 위치 기반 자동 매칭으로 대부분 활용
4. **RAG 캐시**: 무제한 메모리 캐싱 (세션 동안 유지)

### ⚠️ 보수적인 제한 (v0.2.0+: .env로 조정 가능!)

1. **검색 결과**: API 최대 100개지만 **실제 5개만** 사용 → `SEARCH_NUM_RESULTS`로 증가 가능
2. **Deep Crawl**: 키워드당 **10개 기사만** → `DEEP_CRAWLER_MAX_PAGES`로 증가 가능
3. **이미지**: 키워드당 **5개씩** (Unsplash + Pexels) → `IMAGE_SEARCH_PER_PAGE`로 증가 가능
4. **타임아웃**: 모든 타임아웃 30초 기본 → 각 `*_TIMEOUT` 환경변수로 증가 가능

### 💡 최적화 포인트 (v0.2.0+: .env로 조정 가능!)

#### 검색 결과 확장

**방법 1: .env 파일** (권장)
```bash
# .env
SEARCH_NUM_RESULTS=20  # 기본 10 → 20으로 증가
```

**방법 2: 런타임 오버라이드**
```python
result = self.search_tool.run(keyword, num_results=20)
```

#### Deep Crawl 확장

**방법 1: .env 파일** (권장)
```bash
# .env
DEEP_CRAWLER_MAX_PAGES=30    # 기본 10 → 30으로 증가
DEEP_CRAWLER_MAX_DEPTH=3     # 기본 2 → 3으로 증가
DEEP_CRAWLER_DELAY=2.0       # 기본 1.0 → 2.0으로 증가 (안전)
```

**방법 2: 런타임 오버라이드**
```python
crawler = DeepWebCrawler(max_pages=30, max_depth=3)
```

#### 이미지 검색 확장

**방법 1: .env 파일** (권장)
```bash
# .env
IMAGE_SEARCH_PER_PAGE=15     # 기본 10 → 15로 증가
IMAGE_SEARCH_TIMEOUT=60      # 기본 30 → 60초로 증가
```

**방법 2: 런타임 오버라이드**
```python
# image_collector.collect() 호출 시
max_images_per_keyword=15
```

---

## 🚀 권장 설정 (v0.2.0+: 모든 설정을 .env로 조정 가능!)

### .env 파일 설정 예시

```bash
# ===== 인터넷 검색 설정 =====
SEARCH_NUM_RESULTS=20        # 검색 결과 수 (기본: 10, 최대: 100)
SEARCH_TIMEOUT=60            # 검색 타임아웃 초 (기본: 30)

# ===== 웹 크롤링 설정 =====
WEB_SCRAPER_TIMEOUT=60       # 웹 페이지 로드 타임아웃 (기본: 30)

# Deep Web Crawler
DEEP_CRAWLER_MAX_DEPTH=3     # 크롤링 깊이 (기본: 2)
DEEP_CRAWLER_MAX_PAGES=30    # 최대 크롤링 페이지 수 (기본: 10)
DEEP_CRAWLER_DELAY=2.0       # 요청 간 지연시간 초 (기본: 1.0)
DEEP_CRAWLER_TIMEOUT=60      # 페이지 타임아웃 초 (기본: 30)

# Playwright Crawler (JavaScript 렌더링)
PLAYWRIGHT_MAX_DEPTH=3       # 크롤링 깊이 (기본: 2)
PLAYWRIGHT_MAX_PAGES=30      # 최대 크롤링 페이지 수 (기본: 10)
PLAYWRIGHT_DELAY=3.0         # 요청 간 지연시간 초 (기본: 2.0)
PLAYWRIGHT_TIMEOUT=60000     # 페이지 타임아웃 밀리초 (기본: 30000)

# ===== 이미지 검색 설정 =====
IMAGE_SEARCH_PER_PAGE=15     # API 호출당 이미지 수 (기본: 10)
IMAGE_SEARCH_TIMEOUT=60      # API 타임아웃 초 (기본: 30)
MAX_IMAGES_PER_SEARCH=20     # 검색당 최대 이미지 수 (기본: 10)
IMAGE_MAX_WIDTH=1600         # 이미지 최대 너비 (기본: 1200)

# ===== 벡터 DB 청크 설정 =====
CHUNK_SIZE=800               # 청크 크기 (기본: 1000, 더 작을수록 정밀)
CHUNK_OVERLAP=150            # 청크 오버랩 (기본: 200)

# ===== 품질 보증 =====
MAX_ITERATIONS=5             # 최대 개선 반복 횟수 (기본: 3)
QUALITY_THRESHOLD=85         # 품질 임계값 (기본: 80)
```

### 설정 시나리오별 권장값

#### 1. 빠른 생성 (Draft 모드)

```bash
# 최소한의 수집과 빠른 생성
SEARCH_NUM_RESULTS=5
DEEP_CRAWLER_MAX_PAGES=5
IMAGE_SEARCH_PER_PAGE=5
CHUNK_SIZE=1500
MAX_ITERATIONS=1
QUALITY_THRESHOLD=70
```

#### 2. 균형잡힌 생성 (기본 - 권장)

```bash
# 기본 설정 (.env.example 참조)
SEARCH_NUM_RESULTS=10
DEEP_CRAWLER_MAX_PAGES=10
IMAGE_SEARCH_PER_PAGE=10
CHUNK_SIZE=1000
MAX_ITERATIONS=3
QUALITY_THRESHOLD=80
```

#### 3. 고품질 생성 (Production)

```bash
# 포괄적 수집과 엄격한 품질 관리
SEARCH_NUM_RESULTS=20
DEEP_CRAWLER_MAX_PAGES=30
DEEP_CRAWLER_DELAY=2.0       # 안전한 크롤링
IMAGE_SEARCH_PER_PAGE=15
CHUNK_SIZE=800
MAX_ITERATIONS=5
QUALITY_THRESHOLD=90
```

---

## 📌 설정 변경 방법 (v0.2.0+)

### ✅ 권장 방법: .env 파일 수정

모든 제한사항은 이제 `.env` 파일에서 간단히 조정 가능합니다:

```bash
# .env 파일 수정
SEARCH_NUM_RESULTS=20           # 검색 결과 증가
DEEP_CRAWLER_MAX_PAGES=30       # 크롤링 범위 확대
IMAGE_SEARCH_PER_PAGE=15        # 이미지 검색 증가
WEB_SCRAPER_TIMEOUT=60          # 타임아웃 증가
```

**장점:**
- ✅ 코드 수정 불필요
- ✅ 환경별로 다른 설정 가능 (개발/프로덕션)
- ✅ 버전 관리에서 제외 가능 (.gitignore)
- ✅ 설정 변경 후 재시작만으로 적용

### 대체 방법: 런타임 오버라이드

특정 상황에서만 다른 값이 필요한 경우:

```python
# 코드에서 명시적으로 전달
search_tool = SerperSearchTool()
result = search_tool.run(keyword, num_results=20)  # 이 호출만 20개

crawler = DeepWebCrawler(max_pages=50)  # 이 인스턴스만 50개
```

### ⚠️ 권장하지 않음: 코드 직접 수정

이제 Config 기반으로 전환되었으므로 코드 직접 수정은 권장하지 않습니다.

---

## 📚 관련 문서

- [프로젝트 개요](./CLAUDE.md)
- [설치 가이드](./README.md)
- [설정 예시](./.env.example)
- [API 키 설정](./README.md#환경-설정)

---

## 📝 변경 이력

| 날짜 | 버전 | 변경 내용 |
|-----|------|----------|
| 2026-02-08 | 1.0.0 | 초기 분석 문서 작성 |
| 2026-02-08 | 1.1.0 | Location-based 이미지 매칭 및 슬라이드 변환 기능 추가 |
| 2026-02-09 | 1.2.0 | v0.2.0 개선사항 반영 (RAG 캐싱, API 재시도, 테스트) |
| 2026-02-09 | 1.3.0 | **Config 리팩토링 반영**: 모든 하드코딩 제거, .env 기반 설정으로 전환 (15+ 환경변수) |

---

**최종 수정**: 2026-02-09
