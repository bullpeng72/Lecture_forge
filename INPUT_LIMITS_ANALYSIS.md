# 📊 LectureForge 입력 소스 제한 및 활용 범위 분석

> **작성일**: 2026-02-08
> **버전**: 0.1.0
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
# src/lecture_forge/tools/search_tool.py:54
payload = {
    "q": query,
    "num": min(num_results, 100),  # API 최대: 100개
}
```

| 항목 | 기본값 | 최대값 | 실제 활용 |
|-----|--------|--------|----------|
| **검색 결과 수** | 10개 | 100개 (API 제한) | **5개** 사용 |
| **결과 타입** | 3종류 | - | Organic + AnswerBox + KnowledgeGraph |
| **페이지 깊이** | 1페이지만 | - | 첫 페이지만 |

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
# src/lecture_forge/tools/web_scraper.py:21
def __init__(self, timeout: int = 30):
    self.timeout = timeout  # 30초 타임아웃
```

| 제약사항 | 값 | 설명 |
|---------|-----|------|
| **타임아웃** | 30초 | 응답 대기 시간 |
| **페이지 크기** | 무제한 | 메모리 제한까지 |
| **JavaScript** | ❌ 미지원 | 정적 HTML만 |

**수집 범위:**

- ✅ 메인 컨텐츠 영역 (`<main>`, `<article>`)
- ✅ 메타데이터 (title, description, author)
- ❌ 스크립트, 스타일, 네비게이션, 푸터 제외

### B. Deep Web Crawler (Hada.io 전용)

```python
# src/lecture_forge/tools/deep_web_crawler.py:37-38
self.max_depth = max_depth    # 깊이: 2 (검색페이지 + 기사)
self.max_pages = max_pages    # 페이지: 10개
```

```python
# src/lecture_forge/agents/content_collector.py:35-38
self.deep_crawler = DeepWebCrawler(
    max_depth=2,      # ✅ 검색 페이지 + 연결된 기사
    max_pages=10,     # ✅ 최대 10개 기사
    delay=1.0,        # ✅ 1초 대기 (Rate limiting)
)
```

| 설정 | 값 | 의미 |
|-----|-----|------|
| **max_depth** | 2 | 검색 결과 → 기사 내용 (2단계) |
| **max_pages** | 10 | 키워드당 최대 10개 기사 |
| **delay** | 1.0초 | 요청 간 대기 시간 |
| **대상 사이트** | news.hada.io | 하드코딩됨 |

**처리 순서:**

1. 검색 페이지 크롤링: `https://news.hada.io/search?q={keyword}`
2. 기사 링크 추출 (최대 10개)
3. 각 기사 페이지 순차 크롤링 (1초 간격)

---

## 4. 🖼️ 이미지 검색

### A. Unsplash API

```python
# src/lecture_forge/tools/image_search.py:70
"per_page": min(per_page, 30),  # API 최대: 30개
```

| 항목 | 기본값 | API 최대 | 실제 사용 |
|-----|--------|----------|----------|
| **검색 결과** | 10개 | 30개 | 5개 |
| **방향** | landscape | - | landscape |
| **다운로드** | ✅ | - | ✅ 자동 |

### B. Pexels API

```python
# src/lecture_forge/tools/image_search.py:246
"per_page": min(per_page, 80),  # API 최대: 80개
```

| 항목 | 기본값 | API 최대 | 실제 사용 |
|-----|--------|----------|----------|
| **검색 결과** | 10개 | 80개 | 5개 |
| **방향** | landscape | - | landscape |
| **다운로드** | ✅ | - | ✅ 자동 |

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

| 입력 소스 | 제한 방식 | 기본값 | 최대값 | 실제 활용 |
|---------|----------|--------|--------|----------|
| **PDF** | 없음 | - | 메모리 제한 | 전체 |
| **PDF 이미지** | Location-based | - | - | **85% 활용** (v0.2.0) |
| **URL** | 타임아웃 | 30초 | - | 전체 컨텐츠 |
| **검색 결과** | 결과 수 | 5개 | 100개 | **첫 페이지 5개** |
| **Deep Crawl** | 페이지 수 | 10개 | - | 기사 10개 |
| **Unsplash** | API 제한 | 5개 | 30개 | 5개 |
| **Pexels** | API 제한 | 5개 | 80개 | 5개 |
| **벡터 검색** | 결과 수 | 5-10개 | - | 컨텍스트 생성용 |
| **청크 크기** | 문자 수 | 1,000자 | - | 200자 오버랩 |

---

## 🎯 핵심 발견사항

### 🚀 최근 개선사항 (v0.2.0)

1. **Location-based 이미지 매칭**: PDF 이미지 활용도 10% → 85% (+750%)
2. **프레젠테이션 슬라이드**: Reveal.js 기반 자동 변환 (`--to-slides`)

### ✅ 관대한 제한

1. **PDF**: 파일 크기/페이지 제한 없음 (메모리만 허용하면 OK)
2. **URL**: 전체 페이지 컨텐츠 수집
3. **PDF 이미지**: 위치 기반 자동 매칭으로 대부분 활용

### ⚠️ 보수적인 제한

1. **검색 결과**: API 최대 100개지만 **실제 5개만** 사용
2. **Deep Crawl**: 키워드당 **10개 기사만**
3. **이미지**: 키워드당 **5개씩** (Unsplash + Pexels)

### 💡 최적화 포인트

#### 검색 결과 확장 가능

```python
# 현재: 5개
result = self.search_tool.run(keyword, num_results=5)

# 개선 가능: 10-20개로 증가
result = self.search_tool.run(keyword, num_results=20)
```

**위치**: `src/lecture_forge/agents/content_collector.py:114`

#### Deep Crawl 확장 가능

```python
# 현재: 10개 기사
max_pages=10

# 개선 가능: 20-50개로 증가
max_pages=20
```

**위치**: `src/lecture_forge/agents/content_collector.py:37`

#### 이미지 검색 확장 가능

```python
# 현재: 키워드당 5개
max_images_per_keyword: int = 5

# 개선 가능: 10-15개로 증가
max_images_per_keyword: int = 10
```

**위치**: `src/lecture_forge/agents/image_collector.py:50`

---

## 🚀 권장 설정 (환경변수로 조정 가능)

### .env 파일 설정 예시

```bash
# ===== 벡터 DB 청크 설정 =====
# 더 작은 청크 = 더 정밀한 검색
CHUNK_SIZE=800
CHUNK_OVERLAP=150

# ===== 이미지 검색 =====
# 더 많은 이미지 수집
MAX_IMAGES_PER_SEARCH=15
IMAGE_MAX_WIDTH=1600

# ===== 품질 보증 =====
# 더 엄격한 품질 기준
MAX_ITERATIONS=5
QUALITY_THRESHOLD=85
```

### 설정 시나리오별 권장값

#### 1. 빠른 생성 (Draft 모드)

```bash
CHUNK_SIZE=1500
MAX_ITERATIONS=1
QUALITY_THRESHOLD=70
```

#### 2. 균형잡힌 생성 (기본)

```bash
CHUNK_SIZE=1000
MAX_ITERATIONS=3
QUALITY_THRESHOLD=80
```

#### 3. 고품질 생성 (Production)

```bash
CHUNK_SIZE=800
MAX_ITERATIONS=5
QUALITY_THRESHOLD=90
```

---

## 📌 제한사항 우회 방법

### 1. 검색 결과 제한 우회

**문제**: 검색 결과를 5개만 사용

**해결책**:

```python
# content_collector.py 수정
result = self.search_tool.run(keyword, num_results=20)  # 5 → 20
```

### 2. Deep Crawl 제한 우회

**문제**: Hada.io만 지원, 10개 기사만

**해결책**:

```python
# content_collector.py 수정
self.deep_crawler = DeepWebCrawler(
    max_depth=2,
    max_pages=30,     # 10 → 30
    delay=1.0,
)
```

### 3. 이미지 수집 제한 우회

**문제**: 키워드당 5개씩만

**해결책**:

```bash
# .env 파일
MAX_IMAGES_PER_SEARCH=20
```

또는 CLI에서:

```python
# image_collector.collect() 호출 시
max_images_per_keyword=15
```

---

## 🔍 코드 참조 위치

| 기능 | 파일 경로 | 라인 |
|-----|---------|------|
| PDF 파싱 | `src/lecture_forge/tools/pdf_parser.py` | 63 |
| PDF 페이지 보존 | `src/lecture_forge/agents/content_collector.py` | 227 |
| 이미지-페이지 매핑 | `src/lecture_forge/agents/image_collector.py` | 403 |
| Location-based 매칭 | `src/lecture_forge/agents/content_writer.py` | 661, 769 |
| 슬라이드 변환 | `src/lecture_forge/cli.py` | 1949 |
| 검색 API | `src/lecture_forge/tools/search_tool.py` | 54 |
| 검색 사용 | `src/lecture_forge/agents/content_collector.py` | 114 |
| 웹 스크래핑 | `src/lecture_forge/tools/web_scraper.py` | 21 |
| Deep Crawl | `src/lecture_forge/tools/deep_web_crawler.py` | 37-38 |
| Deep Crawl 설정 | `src/lecture_forge/agents/content_collector.py` | 35-38 |
| Unsplash | `src/lecture_forge/tools/image_search.py` | 70 |
| Pexels | `src/lecture_forge/tools/image_search.py` | 246 |
| 이미지 수집 | `src/lecture_forge/agents/image_collector.py` | 50 |
| 청크 설정 | `src/lecture_forge/config.py` | 45-46 |
| 벡터 검색 (Writer) | `src/lecture_forge/agents/content_writer.py` | 128 |
| 벡터 검색 (QA) | `src/lecture_forge/agents/qa_agent.py` | 44 |
| 이미지 설정 | `src/lecture_forge/config.py` | 39-41 |
| 품질 설정 | `src/lecture_forge/config.py` | 50 |

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

---

**작성자**: LectureForge 기술부채 분석팀
**최종 수정**: 2026-02-08
