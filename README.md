# LectureForge Pro 🎓

**AI-Powered Lecture Material Generator using Multi-Agent Pipeline System**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status](https://img.shields.io/badge/status-production%20ready-brightgreen.svg)](https://github.com/yourusername/lecture-forge)
[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)](https://github.com/yourusername/lecture-forge)

> 🚀 **Production Ready** (2026-02-08) | 지금 바로 사용 가능!

## 🎯 개요

LectureForge Pro는 PDF, 웹페이지, 인터넷 검색 등 다양한 소스로부터 정보를 자동으로 수집하여 고품질 강의자료를 생성하는 Multi-Agent 파이프라인 시스템입니다.

**통계:** 10개 에이전트 | 8개 도구 | 1,926 라인 CLI | ~200KB 코드 | $0.22/강의

### 핵심 기능

- 📚 **멀티소스 컨텐츠 수집**: PDF, URL, 키워드 검색, 깊은 웹 크롤링
- 🖼️ **고품질 이미지**: Pexels/Unsplash 검색 이미지 (PDF 이미지는 기본 비활성화)
- 📍 **Location-based 이미지 매칭**: RAG 컨텍스트 페이지 기반 자동 배치 (PDF 이미지 사용률 +750%)
- 🗄️ **지식창고 + RAG**: ChromaDB 벡터 DB 기반 Q&A 시스템
- ✅ **자동 품질 보증**: 6차원 평가 및 반복적 개선 (최대 3회)
- 🎨 **구조화된 HTML 출력**: Mermaid 다이어그램, 검색 가능한 인덱스
- 🎬 **프레젠테이션 슬라이드**: Reveal.js 기반 자동 슬라이드 변환
- 💰 **비용 추적**: 실시간 토큰 사용량 및 API 비용 추정
- 🧹 **지식베이스 관리**: 선택적 정리 및 디스크 공간 관리

## 🚀 빠른 시작

### 1. 설치

```bash
# Conda 환경 생성 (권장)
conda create -n lecture-forge python=3.11
conda activate lecture-forge

# 패키지 설치
pip install -e .

# Playwright 브라우저 설치 (웹 스크래핑용)
playwright install
```

### 2. API 키 설정

```bash
# .env.example 복사
cp .env.example .env

# .env 파일을 열어 API 키 입력
# 필수: OPENAI_API_KEY, SERPER_API_KEY
# 선택: UNSPLASH_ACCESS_KEY, PEXELS_API_KEY
```

**API 키 획득 방법**:
- **OpenAI**: https://platform.openai.com/
- **Serper** (무료 2,500회/월): https://serper.dev/
- **Unsplash** (무료): https://unsplash.com/developers
- **Pexels** (무료): https://www.pexels.com/api/

### 3. 첫 강의 생성

```bash
lecture-forge create
```

대화형으로 강의 정보를 입력하면 자동으로 강의자료가 생성됩니다!

## 💻 사용법

### 기본 명령어

```bash
# ===== 강의 생성 =====
# 대화형 모드 (가장 간단!)
lecture-forge create

# 설정 파일로 생성
lecture-forge create --config config.yaml

# 이미지 검색 + 품질 레벨 설정 (권장)
lecture-forge create --image-search --quality-level strict

# PDF 이미지 포함 + 자동 설명 (비권장 - 관련성 낮음)
lecture-forge create --include-pdf-images --auto-describe-images

# ===== Q&A 모드 =====
# 자동 선택 (권장)
lecture-forge chat

# 특정 지식베이스 지정
lecture-forge chat -kb ./data/vector_db/lecture_xxx

# ===== 강의 향상 =====
# PDF 이미지 설명 추가 (레거시 강의용)
lecture-forge improve ./outputs/my_lecture.html \
    --enhance-pdf-images \
    --source-pdf ./original.pdf

# 슬라이드 변환
lecture-forge improve ./outputs/my_lecture.html --to-slides

# 전체 향상 (이미지 설명 + 슬라이드)
lecture-forge improve ./outputs/my_lecture.html \
    --enhance-pdf-images \
    --source-pdf ./original.pdf \
    --to-slides

# ===== 지식베이스 관리 =====
# 대화형 선택 삭제
lecture-forge cleanup

# 전체 삭제 (주의!)
lecture-forge cleanup --all
```

### 명령어 상세

#### `create` - 강의 생성
- `--config, -c`: 설정 YAML 파일
- `--interactive, -i`: 대화형 Q&A 모드
- `--image-search`: 웹 이미지 검색 활성화 (Pexels, 권장)
- `--quality-level`: lenient(70) / balanced(80) / strict(90)
- `--output, -o`: 출력 파일명
- `--include-pdf-images`: PDF 이미지 추출 (기본: 비활성화, 비권장)
- `--auto-describe-images/--no-auto-describe-images`: PDF 이미지 자동 설명 (기본: 활성화, --include-pdf-images 사용 시)

#### `chat` - Q&A 모드
- `--knowledge-base, -kb`: 지식베이스 경로 (없으면 자동 선택)
- 명령어: `/exit`, `/clear`, `/sources`, `/help`

#### `improve` - 강의 향상
- `--enhance-pdf-images`: PDF 이미지 설명 추가 (레거시 강의용)
- `--source-pdf`: 원본 PDF 파일 경로 (--enhance-pdf-images 필요)
- `--to-slides`: Reveal.js 프레젠테이션 슬라이드 변환

#### `cleanup` - 지식베이스 정리
- `--all, -a`: 전체 삭제 (주의!)

### 입력 예시

```
? 강의 주제: Deep Learning Fundamentals
? 강의 시간 (분): 180
? 수강생 레벨: 중급
? PDF 파일: paper1.pdf, paper2.pdf
? URL: https://example.com/tutorial
? 검색 키워드: "deep learning basics", "neural networks"
```

### 출력

- **HTML 파일**: 완성된 강의자료 (이미지, 다이어그램, 검색 기능 포함)
- **지식창고**: ChromaDB Vector DB (Q&A용, 대화형 탐색 가능)
- **통계 정보**:
  - 섹션 수, 단어 수, 이미지 수
  - 품질 점수 (6차원 평가)
  - 토큰 사용량 (입력/출력)
  - 예상 비용 (모델별 상세)

## 🏗️ 시스템 아키텍처

### Multi-Agent 구조 (10개 전문 에이전트)

1. **Content Collector** 📚 - 텍스트 수집 및 벡터화
2. **Image Collector** 🖼️ - 이미지 수집 및 Vision AI 분석
3. **Content Analyzer** 🔍 - 내용 분석 및 지식 그래프
4. **Curriculum Designer** 📋 - 강의 구조 설계
5. **Content Writer** ✍️ - RAG 기반 컨텐츠 생성
6. **Diagram Generator** 📊 - Mermaid 다이어그램 생성
7. **Quality Evaluator** ✅ - 품질 평가 (6개 차원)
8. **Revision Agent** 🔄 - 자동/반자동 수정
9. **Q&A Agent** 🤖 - 지식창고 기반 대화
10. **HTML Assembler** 🎨 - 최종 HTML 생성

### 워크플로우

```
입력 → 수집 → 분석 → 설계 → 생성 → 평가 → (수정) → 출력
                                    ↑       ↓
                                    └───반복───┘
```

## 📊 품질 평가 시스템

생성된 강의자료는 다음 6개 차원에서 평가됩니다:

1. **내용 완성도** (25%) - 학습 목표 달성도
2. **논리적 흐름** (20%) - 섹션 간 연결성
3. **시간 적합성** (10%) - 시간 vs 분량
4. **난이도 적합성** (20%) - 수강생 레벨 일치
5. **시각자료 품질** (15%) - 이미지/다이어그램 충분성
6. **기술적 정확성** (10%) - 사실 관계 검증

**합격 기준**: 80점 이상 (자동 반복 개선, 최대 3회)

## 💬 지식창고 Q&A 시스템

생성된 강의자료의 지식창고를 활용하여 언제든 질문할 수 있습니다:

```bash
lecture-forge chat --kb ./data/vector_db/lecture_xxx

You: What is backpropagation?