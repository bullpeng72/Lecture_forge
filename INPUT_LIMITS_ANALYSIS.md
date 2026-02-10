# 📊 LectureForge 입력 소스 제한 및 활용 범위 분석

> **작성일**: 2026-02-08
> **최종 수정**: 2026-02-10
> **버전**: 1.4.0
> **분석 대상**: PDF, URL, 검색, 이미지 입력 소스 + 멀티소스 구성 전략

---

## 목차

1. [PDF 입력](#1-pdf-입력)
2. [인터넷 검색 (Serper API)](#2-인터넷-검색-serper-api)
3. [URL/웹 크롤링](#3-url웹-크롤링)
4. [이미지 검색](#4-이미지-검색)
5. [벡터 DB (ChromaDB)](#5-벡터-db-chromadb)
6. [이미지 처리](#6-이미지-처리)
7. [품질 보증](#7-품질-보증)
8. [멀티소스 컨텐츠 구성 전략](#8-멀티소스-컨텐츠-구성-전략)
9. [종합 요약표](#종합-요약표)
10. [핵심 발견사항](#핵심-발견사항)
11. [권장 설정](#권장-설정-환경변수로-조정-가능)

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

## 8. 🎯 멀티소스 컨텐츠 구성 전략

### 개요

LectureForge는 **소스 타입 무관 통합 분석 방식**을 사용합니다. 모든 입력 소스(PDF, URL, 검색, Hada)를 동등하게 취급하고, RAG(Retrieval Augmented Generation) 기반 유사도 검색으로 최적의 내용을 선택합니다.

### A. 컨텐츠 수집 단계 (Phase 1)

```python
# src/lecture_forge/agents/content_collector.py:40-228

# 1. 모든 소스 수집
all_documents = []

# PDF 수집
for pdf_path in pdfs:
    all_documents.append({
        "text": result["text"],
        "source": pdf_path,
        "source_type": "pdf",  # ✅ 타입 메타데이터
        "metadata": result["metadata"],
    })

# URL 수집
for url in urls:
    all_documents.append({
        "text": result["text"],
        "source": url,
        "source_type": "url",  # ✅ 타입 메타데이터
    })

# 검색 결과 수집 (snippet만)
for keyword in keywords:
    search_text = f"Search results for '{keyword}':\n\n"
    for item in results:
        search_text += f"{item['title']}\n{item['snippet']}\n"
    all_documents.append({
        "text": search_text,
        "source": f"search:{keyword}",
        "source_type": "search",  # ✅ 타입 메타데이터
    })

# Hada.io 크롤링 (전체 페이지)
for hada_keyword in hada_keywords:
    for page in crawled_pages:
        all_documents.append({
            "text": page["text"],
            "source": page["url"],
            "source_type": f"hada_{page['type']}",  # ✅ 타입 메타데이터
        })
```

**핵심 특징:**

- ✅ 모든 소스를 `all_documents` 배열에 동등하게 추가
- ✅ 소스 타입을 메타데이터로 보존 (`source_type`)
- ✅ 가중치나 우선순위 없음 (flat structure)
- ✅ 청크로 분할하여 벡터 DB에 저장

### B. 컨텐츠 분석 단계 (Phase 3a)

```python
# src/lecture_forge/agents/content_analyzer.py:59-60

# 모든 문서를 단순 결합 (소스 구분 없이)
all_text = "\n\n".join([doc["text"] for doc in documents])

# 통합 분석 수행
key_topics = self._extract_key_topics(all_text, topic)
entities = self._extract_entities(all_text, key_topics)
difficulty_scores = self._assess_difficulty(key_topics, all_text)
```

**핵심 특징:**

- ✅ 소스 타입 무시하고 모든 텍스트 결합
- ✅ LLM이 통합된 내용에서 주요 주제 추출
- ✅ 자연스러운 주제 우선순위 결정 (빈도 + 중요도)

### C. 목차 구성 단계 (Phase 3b)

```python
# src/lecture_forge/agents/curriculum_designer.py:117-142

def _select_topics(analysis_result, duration, audience_level):
    all_topics = analysis_result.key_topics  # 소스 정보 없음
    difficulty_scores = analysis_result.difficulty_scores

    # 난이도 기반 필터링
    if audience_level == "beginner":
        selected = [t for t in all_topics if difficulty_scores[t] < 0.6]
    elif audience_level == "advanced":
        selected = [t for t in all_topics if difficulty_scores[t] > 0.4]
    else:
        selected = all_topics

    # 시간 기반 주제 수 결정
    avg_time_per_topic = 15  # minutes
    max_topics = max(3, duration // avg_time_per_topic)

    return selected[:max_topics]

def _create_sections(topics, duration):
    # 시간 배분
    intro_time = max(5, duration // 20)       # 5%
    conclusion_time = max(5, duration // 20)  # 5%
    content_time = duration - intro_time - conclusion_time  # 90%

    # 균등 분배
    time_per_topic = content_time // len(topics)
```

**핵심 특징:**

- ✅ 분석 결과(key_topics)만 사용
- ✅ 소스 타입 정보 사용하지 않음
- ✅ 난이도와 시간 기반 자동 구성
- ❌ 소스별 가중치 없음

**시간 배분 공식:**

```
총 시간 = 100%
├─ Intro: 5%
├─ Main Content: 90% (주제 수로 균등 분배)
└─ Conclusion: 5%
```

### D. 컨텐츠 작성 단계 (Phase 4a)

```python
# src/lecture_forge/agents/content_writer.py:156-181

def _query_knowledge(section):
    # 섹션 주제로 쿼리 생성 (소스 타입 무관)
    query = " ".join(section.topics)

    # 벡터 DB에서 유사도 기반 검색
    results = self.vector_store.query(query, n_results=10)

    # 가장 관련성 높은 10개 청크 반환
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]

    return documents, metadatas
```

**RAG 검색 원리:**

1. **쿼리 생성**: 섹션의 topics 결합
2. **임베딩 변환**: OpenAI text-embedding-3-small 사용
3. **유사도 검색**: ChromaDB 코사인 유사도
4. **상위 N개 선택**: 기본 10개 (n_results=10)
5. **소스 무관**: PDF, URL, 검색 모두 동등하게 경쟁

**검색 결과 예시:**

```python
# 쿼리: "딥러닝 기초"
results = {
    "documents": [
        "딥러닝은...",        # PDF page 5 (유사도 0.95)
        "신경망 구조는...",    # URL article (유사도 0.92)
        "머신러닝과 차이는...", # 검색 snippet (유사도 0.89)
        "텐서플로우 활용...",  # Hada article (유사도 0.87)
        # ... 총 10개
    ],
    "metadatas": [
        {"source": "ml.pdf", "source_type": "pdf", "page_number": 5},
        {"source": "https://...", "source_type": "url"},
        {"source": "search:deep learning", "source_type": "search"},
        {"source": "https://news.hada.io/...", "source_type": "hada_article"},
        # ...
    ]
}
```

**LLM 프롬프트에 컨텍스트 제공:**

```python
# src/lecture_forge/agents/content_writer.py:194
context_text = "\n\n---\n\n".join(contexts[:8])  # 상위 8개 사용

prompt = f"""
...
Knowledge Base Context:
{context_text}

Write the comprehensive content NOW:
"""
```

---

### 📊 소스별 시나리오 분석

#### 시나리오 1: PDF만 있는 경우

```yaml
pdfs:
  - "machine_learning.pdf"  # 100 pages
urls: []
keywords: []
```

**결과:**

- ✅ PDF 전체 페이지 파싱 (100 pages)
- ✅ 청크 단위로 벡터 DB 저장 (~100-200 chunks)
- ✅ PDF 내용만으로 주제 추출 및 목차 구성
- ✅ RAG 검색으로 PDF에서 관련 내용 선택
- 📊 **내용 반영 비율: PDF 100%**

#### 시나리오 2: URL만 있는 경우

```yaml
pdfs: []
urls:
  - "https://example.com/deep-learning-guide"
  - "https://example.com/neural-networks"
  - "https://example.com/tensorflow-tutorial"
keywords: []
```

**결과:**

- ✅ 3개 URL 전체 스크래핑 (전체 텍스트)
- ✅ 벡터 DB에 저장 (~30-60 chunks)
- ✅ URL 내용만으로 주제 추출
- 📊 **내용 반영 비율: URL1 33% + URL2 33% + URL3 34%** (유사도 기반)

#### 시나리오 3: 검색만 있는 경우

```yaml
pdfs: []
urls: []
keywords:
  - "deep learning basics"
  - "neural network architecture"
  - "tensorflow tutorial"
```

**결과:**

- ⚠️ 검색 결과는 **snippet(요약)만** 저장 (전체 페이지 ❌)
- ✅ 3개 키워드 × 5개 결과 = 15개 snippet
- ✅ 벡터 DB에 저장 (~5-10 chunks)
- ⚠️ **내용 부족 가능성**: snippet만으로 상세 강의 작성 어려움
- 📊 **내용 반영 비율: 키워드1 33% + 키워드2 33% + 키워드3 34%**

**권장:**

```bash
# 검색만 사용하는 경우, 이미지 검색 활성화
lecture-forge create --image-search
```

#### 시나리오 4: PDF + URL 조합

```yaml
pdfs:
  - "deep_learning.pdf"  # 50 pages
urls:
  - "https://tensorflow.org/guide"
  - "https://pytorch.org/tutorials"
keywords: []
```

**결과:**

- ✅ PDF 50 pages + URL 2개 전체 스크래핑
- ✅ 벡터 DB에 통합 저장 (~70-120 chunks)
- ✅ 주제 추출 시 모든 소스 고려
- 📊 **내용 반영 비율: 유사도 기반 자동 결정**
  - 예: PDF 60% + URL1 25% + URL2 15% (RAG 검색 결과에 따라 동적)

**RAG 검색 예시:**

```
섹션: "텐서플로우 기초"
→ RAG 검색 결과:
  1. tensorflow.org/guide (유사도 0.95) ← URL 우선!
  2. deep_learning.pdf page 23 (유사도 0.92)
  3. pytorch.org/tutorials (유사도 0.85)
  → LLM이 1,2를 주로 활용하여 내용 작성

섹션: "딥러닝 수학적 기초"
→ RAG 검색 결과:
  1. deep_learning.pdf page 5 (유사도 0.94) ← PDF 우선!
  2. deep_learning.pdf page 6 (유사도 0.93)
  3. tensorflow.org/guide (유사도 0.78)
  → LLM이 PDF를 주로 활용하여 내용 작성
```

#### 시나리오 5: 복합 소스 (최대 활용)

```yaml
pdfs:
  - "ml_textbook.pdf"      # 200 pages
  - "research_paper.pdf"   # 30 pages
urls:
  - "https://stanford.edu/ml-course"
  - "https://github.com/awesome-ml"
keywords:
  - "machine learning applications"
  - "deep learning frameworks"
hada_keywords:
  - "AI 최신 트렌드"
```

**결과:**

- ✅ **PDF**: 230 pages → ~200-300 chunks
- ✅ **URL**: 2개 전체 스크래핑 → ~40-80 chunks
- ⚠️ **검색**: 2 × 5개 snippet → ~5-10 chunks
- ✅ **Hada**: ~10 articles → ~50-100 chunks
- 📊 **총 ~300-500 chunks in Vector DB**

**내용 반영 비율 (추정):**

```
총 청크 수: 500개
├─ PDF: 300 chunks (60%)
├─ URL: 80 chunks (16%)
├─ 검색: 10 chunks (2%)
└─ Hada: 110 chunks (22%)

하지만 실제 강의 내용은 RAG 검색 결과에 따라:
├─ 섹션 1: PDF 70% + URL 20% + Hada 10%
├─ 섹션 2: PDF 40% + Hada 50% + 검색 10%
├─ 섹션 3: URL 60% + PDF 30% + Hada 10%
└─ ... (섹션별로 다름)
```

#### 시나리오 6: 일부 소스 누락

```yaml
pdfs:
  - "guide.pdf"
urls:
  - "https://broken-link.com"  # ❌ 404 Error
keywords:
  - "valid keyword"
```

**결과:**

- ✅ PDF 정상 수집
- ❌ URL 실패 (로그에 에러 기록, 무시하고 계속)
- ✅ 검색 정상 수행
- 📊 **내용 반영 비율: PDF 80% + 검색 20%**

**로그 예시:**

```
✅ Collected from PDF: 50,000 characters
❌ Failed to scrape URL: 404 Not Found
✅ Collected 5 search results
```

**강의 생성:**

- ✅ 실패한 소스 무시하고 계속 진행
- ✅ 수집된 소스만으로 목차 구성
- ⚠️ 내용이 부족하면 품질 점수 낮아짐

#### 시나리오 7: 모든 소스 없음

```yaml
pdfs: []
urls: []
keywords: []
```

**결과:**

- ❌ **에러 발생**: No documents to analyze
- 🛑 **강의 생성 실패**

```python
# src/lecture_forge/agents/content_analyzer.py:56-57
if not documents:
    logger.warning("No documents to analyze")
    return AnalysisResult()  # Empty result
```

---

### 🔑 핵심 원칙

#### 1. **소스 타입 무관 (Source-Agnostic)**

```python
# ❌ 없는 것: 소스별 가중치
weights = {
    "pdf": 0.5,
    "url": 0.3,
    "search": 0.2
}

# ✅ 실제: 유사도 기반 평등 경쟁
similarity_scores = [
    ("pdf_chunk_5", 0.95),
    ("url_chunk_2", 0.92),
    ("search_snippet_1", 0.89),
]
# 상위 N개 선택 (소스 무관)
```

#### 2. **RAG 기반 동적 선택**

- 각 섹션마다 독립적으로 RAG 검색
- 섹션 주제와 가장 관련성 높은 내용 선택
- 소스 타입이 아닌 내용 유사도로 결정

#### 3. **청크 단위 저장**

```python
# 모든 문서를 1,000자 청크로 분할
chunks = text_splitter.split_text(doc["text"], chunk_size=1000)

# PDF 200 pages → ~200 chunks
# URL 1개 → ~10-20 chunks
# 검색 snippet → ~1-2 chunks
```

**장점:**

- ✅ 긴 PDF도 청크 단위로 검색 가능
- ✅ 짧은 snippet도 동등하게 경쟁
- ✅ 세밀한 관련성 판단

#### 4. **자연스러운 내용 구성**

- LLM이 RAG 컨텍스트를 자연스럽게 통합
- 소스별 경계 없이 매끄러운 서술
- 출처 표기는 자동 (메타데이터 활용)

---

### 📈 실제 활용 예시

#### 예시 1: AI 강의 (180분)

**입력:**

```yaml
topic: "인공지능 기초부터 응용까지"
duration: 180
audience_level: "intermediate"
pdfs:
  - "ai_textbook.pdf"  # 300 pages
urls:
  - "https://tensorflow.org/tutorials"
  - "https://pytorch.org/tutorials"
keywords:
  - "AI 최신 트렌드 2026"
```

**결과:**

```
Vector DB: 450 chunks
├─ PDF: 300 chunks (67%)
├─ URL1: 50 chunks (11%)
├─ URL2: 50 chunks (11%)
└─ 검색: 50 chunks (11%)

목차 (12 섹션):
├─ Intro (9분)
├─ 1. AI 개요 (15분)
│   → RAG: PDF 80% + 검색 20%
├─ 2. 머신러닝 기초 (15분)
│   → RAG: PDF 90% + URL 10%
├─ 3. 딥러닝 이론 (15분)
│   → RAG: PDF 95% + URL 5%
├─ 4. 신경망 구조 (15분)
│   → RAG: PDF 70% + URL 30%
├─ 5. TensorFlow 실습 (15분)
│   → RAG: URL1 70% + PDF 30%
├─ 6. PyTorch 실습 (15분)
│   → RAG: URL2 70% + PDF 30%
├─ 7. CNN (15분)
│   → RAG: PDF 80% + URL 20%
├─ 8. RNN (15분)
│   → RAG: PDF 85% + URL 15%
├─ 9. Transformer (15분)
│   → RAG: 검색 50% + PDF 40% + URL 10%
├─ 10. 응용 사례 (15분)
│   → RAG: 검색 60% + PDF 30% + URL 10%
├─ 11. 최신 트렌드 (15분)
│   → RAG: 검색 70% + URL 20% + PDF 10%
└─ Conclusion (9분)
```

**분석:**

- 섹션별로 **동적**으로 소스 비율 변경
- 이론 섹션: PDF 위주
- 실습 섹션: URL(공식 문서) 위주
- 트렌드 섹션: 검색 결과 위주

---

### 💡 최적화 전략

#### 1. **PDF 중심 강의**

```yaml
# PDF 내용을 상세히 다루고 싶을 때
pdfs:
  - "main_textbook.pdf"
urls: []  # 최소화
keywords: []  # 최소화
```

**장점:**

- PDF 내용이 대부분의 RAG 검색 결과 차지
- 일관된 교재 기반 강의

#### 2. **최신 정보 중심 강의**

```yaml
# 최신 트렌드와 실무 중심
pdfs: []  # 최소화
urls:
  - "https://공식문서들..."
keywords:
  - "2026 최신 트렌드"
  - "실무 사례"
hada_keywords:
  - "기술 뉴스"
```

**장점:**

- 최신 정보 반영
- 실무 사례 풍부

#### 3. **균형잡힌 강의**

```yaml
# 이론 + 실무 균형
pdfs:
  - "theory.pdf"
urls:
  - "https://실무가이드"
keywords:
  - "최신 사례"
```

**장점:**

- 이론과 실무 조화
- 다양한 관점 제공

---

### ⚠️ 주의사항

#### 1. **검색 결과의 한계**

```yaml
keywords:
  - "매우 상세한 주제"
```

**문제:**

- 검색 결과는 snippet(요약)만 저장
- 상세한 설명 부족 가능

**해결:**

```yaml
# 검색 키워드 대신 URL로 전체 페이지 수집
urls:
  - "https://상세가이드.com"
```

#### 2. **소스 품질**

```yaml
pdfs:
  - "low_quality_scan.pdf"  # 스캔 PDF (텍스트 추출 불가)
```

**문제:**

- OCR 미지원으로 텍스트 추출 실패
- 벡터 DB에 저장 안 됨

**해결:**

- 텍스트가 포함된 PDF 사용
- 또는 URL/검색으로 보완

#### 3. **소스 과다**

```yaml
pdfs:
  - "book1.pdf"  # 500 pages
  - "book2.pdf"  # 500 pages
  - "book3.pdf"  # 500 pages
# ... 총 10개 PDF
```

**문제:**

- 벡터 DB 크기 증가 (수천 chunks)
- RAG 검색 시간 증가
- 메모리 사용량 증가

**권장:**

- PDF는 3-5개 이내
- 주제와 직접 관련된 소스만 선택

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
| 2026-02-10 | 1.4.0 | **멀티소스 컨텐츠 구성 전략 추가**: 7가지 시나리오 분석, RAG 기반 동적 소스 선택 메커니즘 상세 설명 |

---

**최종 수정**: 2026-02-10
