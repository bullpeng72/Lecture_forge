# 📦 LectureForge PyPI 배포 가이드

> **버전**: 0.2.0 ✅ **배포 완료**
> **최종 수정**: 2026-02-09
> **대상**: PyPI (Python Package Index)
> **배포 URL**: https://pypi.org/project/lecture-forge/0.2.0/

---

## 📋 목차

1. [배포 전 체크리스트](#1-배포-전-체크리스트)
2. [필수 파일 준비](#2-필수-파일-준비)
3. [PyPI 계정 설정](#3-pypi-계정-설정)
4. [패키지 빌드](#4-패키지-빌드)
5. [테스트 PyPI 배포](#5-테스트-pypi-배포)
6. [실제 PyPI 배포](#6-실제-pypi-배포)
7. [설치 테스트](#7-설치-테스트)
8. [업데이트 배포](#8-업데이트-배포)
9. [문제 해결](#9-문제-해결)

---

## 1. 배포 전 체크리스트

### ✅ 필수 확인 사항

```bash
# 1. 버전 확인
grep -r "0.2.0" pyproject.toml setup.py src/lecture_forge/__version__.py

# 2. 테스트 실행
pytest tests/ -v

# 3. 코드 품질 확인
black src/ tests/
flake8 src/ tests/

# 4. 의존성 확인
pip list | grep -E "langchain|openai|chromadb"

# 5. 패키지 구조 확인
tree src/lecture_forge -L 2
```

### 📝 배포 체크리스트

- [x] ✅ setup.py의 entry_point 확인 완료 (`cli:cli`)
- [x] ✅ LICENSE 파일 생성 완료 (MIT License)
- [x] ✅ MANIFEST.in 파일 생성 완료
- [x] ✅ author 정보 업데이트 완료 (Sungwoo Kim)
- [x] ✅ GitHub URL 업데이트 완료 (https://github.com/bullpeng72/Lecture_forge)
- [x] ✅ 패키지 빌드 완료 (wheel + sdist)
- [x] ✅ twine check 통과
- [x] ✅ PyPI 업로드 완료 (2026-02-09)

---

## 2. 필수 파일 준비

### A. LICENSE 파일 생성

```bash
# MIT License 생성 (권장)
cat > LICENSE << 'EOF'
MIT License

Copyright (c) 2026 [Your Name]

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
EOF
```

### B. MANIFEST.in 생성 (선택, 권장)

```bash
cat > MANIFEST.in << 'EOF'
include README.md
include LICENSE
include requirements.txt
include .env.example
recursive-include src/lecture_forge/templates *
recursive-exclude * __pycache__
recursive-exclude * *.py[co]
EOF
```

### C. setup.py 확인

**✅ entry_point가 올바르게 설정되어 있는지 확인**

```python
# setup.py에서 확인
entry_points={
    "console_scripts": [
        "lecture-forge=lecture_forge.cli:cli",  # ✅ cli 함수 사용 (올바름)
    ],
},
```

**참고:** pyproject.toml을 사용하는 경우:
```toml
[project.scripts]
lecture-forge = "lecture_forge.cli:cli"
```

### D. .pypirc 파일 설정 ⭐ 권장

**~/.pypirc 파일을 설정하면 매번 토큰을 입력할 필요가 없습니다!**

```bash
# ~/.pypirc 생성
cat > ~/.pypirc << 'EOF'
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-여기에실제PyPI토큰입력

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-여기에실제TestPyPI토큰입력
EOF

chmod 600 ~/.pypirc
```

**중요:** ~/.pypirc가 설정되면 다음과 같이 간단하게 업로드 가능:
```bash
twine upload dist/*  # 토큰 자동 인증
```

**⚠️ 명령줄 옵션 우선순위:**
```
1. 명령줄 옵션 (-u, -p)      ← 최우선
2. 환경 변수 (TWINE_USERNAME, TWINE_PASSWORD)
3. ~/.pypirc 파일             ← 마지막
```

명령줄에서 `-u`나 `-p`를 지정하면 ~/.pypirc가 **무시**됩니다!

---

## 3. PyPI 계정 설정

### A. PyPI 계정 생성

1. **PyPI 계정**: https://pypi.org/account/register/
2. **TestPyPI 계정**: https://test.pypi.org/account/register/

### B. API 토큰 생성

#### PyPI 토큰
1. https://pypi.org/manage/account/token/ 접속
2. "Add API token" 클릭
3. Token name: `lecture-forge-upload`
4. Scope: "Entire account" (첫 배포) 또는 "Project: lecture-forge"
5. 생성된 토큰 복사: `pypi-AgEIcHlwaS5vcmc...`

#### TestPyPI 토큰
1. https://test.pypi.org/manage/account/token/ 접속
2. 동일한 절차로 토큰 생성

### C. 토큰 저장

```bash
# 환경 변수로 저장 (권장)
export PYPI_TOKEN="pypi-AgEIcHlwaS5vcmc..."
export TEST_PYPI_TOKEN="pypi-AgEIcHlwaS5vcmc..."

# ~/.pypirc에 저장
# (위 .pypirc 섹션 참조)
```

---

## 4. 패키지 빌드

### A. 빌드 도구 설치

```bash
# 최신 빌드 도구 설치
pip install --upgrade build twine setuptools wheel
```

### B. 패키지 정리

```bash
# 이전 빌드 결과 삭제
rm -rf build/ dist/ *.egg-info src/*.egg-info

# 캐시 삭제
find . -type d -name __pycache__ -exec rm -rf {} +
find . -type f -name "*.pyc" -delete
```

### C. 패키지 빌드

```bash
# 소스 및 wheel 배포판 빌드
python -m build

# 빌드 결과 확인
ls -lh dist/
# lecture-forge-0.2.0.tar.gz
# lecture_forge-0.2.0-py3-none-any.whl
```

### D. 빌드 파일 검증

```bash
# wheel 파일 내용 확인
unzip -l dist/lecture_forge-0.2.0-py3-none-any.whl

# 패키지 메타데이터 확인
tar -tzf dist/lecture-forge-0.2.0.tar.gz | grep -E "PKG-INFO|setup.py"

# Twine으로 검증
twine check dist/*
```

**예상 출력:**
```
Checking dist/lecture-forge-0.2.0.tar.gz: PASSED
Checking dist/lecture_forge-0.2.0-py3-none-any.whl: PASSED
```

---

## 5. 테스트 PyPI 배포

### A. TestPyPI 업로드

```bash
# TestPyPI에 업로드 (테스트용)
twine upload --repository testpypi dist/*

# 또는 토큰 직접 사용
twine upload --repository testpypi dist/* \
  --username __token__ \
  --password $TEST_PYPI_TOKEN
```

**예상 출력:**
```
Uploading distributions to https://test.pypi.org/legacy/
Uploading lecture-forge-0.2.0.tar.gz
Uploading lecture_forge-0.2.0-py3-none-any.whl
View at:
https://test.pypi.org/project/lecture-forge/0.2.0/
```

### B. TestPyPI 페이지 확인

```bash
# 브라우저에서 확인
open https://test.pypi.org/project/lecture-forge/
```

**확인 사항:**
- ✅ README가 제대로 렌더링되는가?
- ✅ 버전 정보가 올바른가?
- ✅ 의존성이 제대로 표시되는가?
- ✅ Classifiers가 올바른가?

### C. TestPyPI에서 설치 테스트

```bash
# 새 가상환경 생성
python -m venv test_venv
source test_venv/bin/activate  # Windows: test_venv\Scripts\activate

# TestPyPI에서 설치
pip install --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  lecture-forge

# 설치 확인
lecture-forge --version
lecture-forge --help

# 테스트 완료 후 정리
deactivate
rm -rf test_venv
```

---

## 6. 실제 PyPI 배포

### A. 최종 확인

```bash
# 체크리스트
echo "배포 전 최종 확인:"
echo "  [ ] 테스트 통과"
echo "  [ ] README 확인"
echo "  [ ] 버전 번호 확인"
echo "  [ ] LICENSE 파일 존재"
echo "  [ ] TestPyPI 설치 테스트 완료"
echo "  [ ] entry_point 수정 완료"
```

### B. PyPI 업로드

**방법 1: ~/.pypirc 사용 (권장 - 가장 간단)**
```bash
# ~/.pypirc에 토큰이 저장되어 있으면
twine upload dist/lecture_forge-0.2.0*

# 또는 (zsh에서 glob 패턴 문제 시)
twine upload dist/lecture_forge-0.2.0-py3-none-any.whl dist/lecture_forge-0.2.0.tar.gz
```

**방법 2: 환경 변수 사용**
```bash
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi-실제토큰

twine upload dist/lecture_forge-0.2.0*
```

**방법 3: 명령줄 옵션 (매번 입력)**
```bash
twine upload \
  -u __token__ \
  -p pypi-실제토큰 \
  dist/lecture_forge-0.2.0-py3-none-any.whl \
  dist/lecture_forge-0.2.0.tar.gz
```

**⚠️ macOS/zsh 사용자 주의:**
```bash
# ❌ 실패: zsh에서 glob 패턴 오류
twine upload dist/*
# zsh: no matches found: dist/*

# ✅ 해결 방법 1: 파일명 명시
twine upload dist/lecture_forge-0.2.0-py3-none-any.whl dist/lecture_forge-0.2.0.tar.gz

# ✅ 해결 방법 2: noglob 사용
noglob twine upload dist/*

# ✅ 해결 방법 3: bash로 실행
bash -c 'twine upload dist/*'
```

**실제 성공 출력 (2026-02-09):**
```
Uploading distributions to https://upload.pypi.org/legacy/
Uploading lecture_forge-0.2.0-py3-none-any.whl
100% ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 188.2/188.2 kB • 00:01 • 306.3 kB/s
Uploading lecture_forge-0.2.0.tar.gz
100% ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 197.9/197.9 kB • 00:00 • 174.9 MB/s

View at:
https://pypi.org/project/lecture-forge/0.2.0/
```

### C. PyPI 페이지 확인

```bash
# 브라우저에서 확인
open https://pypi.org/project/lecture-forge/
```

### D. 배포 완료! 🎉

**설치 명령어 공유:**
```bash
pip install lecture-forge
```

**패키지 정보:**
- 📦 Package: https://pypi.org/project/lecture-forge/
- 📊 Statistics: https://pypistats.org/packages/lecture-forge
- 🔍 검색: https://pypi.org/search/?q=lecture-forge

**다음 단계:**
1. README.md에 배포 배지 추가
2. GitHub Release 생성
3. 문서 사이트 업데이트
4. SNS/커뮤니티 공유

---

## 7. 설치 테스트

### A. 실제 설치 테스트

```bash
# 새 가상환경 생성
python -m venv prod_test_venv
source prod_test_venv/bin/activate

# PyPI에서 설치
pip install lecture-forge

# 버전 확인
lecture-forge --version
# 출력: python -m lecture_forge.cli, version 0.2.0

# 기능 테스트
lecture-forge --help
lecture-forge create --help
lecture-forge chat --help

# 정리
deactivate
rm -rf prod_test_venv
```

### B. 다양한 환경에서 테스트

```bash
# Python 3.11
python3.11 -m venv test_py311
source test_py311/bin/activate
pip install lecture-forge
lecture-forge --version
deactivate

# Python 3.12 (지원 확인)
python3.12 -m venv test_py312
source test_py312/bin/activate
pip install lecture-forge
lecture-forge --version
deactivate
```

---

## 8. 업데이트 배포

### A. 버전 업데이트

```bash
# 1. 버전 번호 변경
# pyproject.toml
version = "0.2.1"

# setup.py
version="0.2.1"

# src/lecture_forge/__version__.py
__version__ = "0.2.1"

# 2. CHANGELOG 업데이트 (권장)
cat >> CHANGELOG.md << 'EOF'
## [0.2.1] - 2026-02-10

### Fixed
- Bug fixes and improvements

### Added
- New features
EOF
```

### B. 새 버전 빌드 및 배포

```bash
# 1. 정리
rm -rf build/ dist/ *.egg-info

# 2. 빌드
python -m build

# 3. 검증
twine check dist/*

# 4. TestPyPI 업로드 (선택)
twine upload --repository testpypi dist/*

# 5. PyPI 업로드
twine upload dist/*
```

### C. Git 태그 생성

```bash
# Git 태그 생성
git tag -a v0.2.1 -m "Release version 0.2.1"
git push origin v0.2.1

# GitHub Release 생성 (선택)
gh release create v0.2.1 \
  --title "v0.2.1" \
  --notes "Release notes here"
```

---

## 9. 문제 해결

### A. 일반적인 오류

#### 1. "403 Forbidden" - Invalid or non-existent authentication

**증상:**
```
ERROR    HTTPError: 403 Forbidden from https://upload.pypi.org/legacy/
         Invalid or non-existent authentication information.
```

**원인:**
- API 토큰이 올바르지 않음
- 토큰이 만료됨
- 토큰에 업로드 권한이 없음
- `pypi-YOUR_TOKEN`을 실제 토큰으로 교체하지 않음

**해결 방법:**

1. **새 API 토큰 발급**
   - PyPI: https://pypi.org/manage/account/token/
   - Token name: `lecture-forge-upload`
   - Scope: **"Entire account (all projects)"** 선택 (첫 업로드 필수!)
   - 토큰 복사: `pypi-AgEI...` (한 번만 표시됨)

2. **토큰 확인 및 재시도**
   ```bash
   # 토큰을 환경 변수로 설정
   export TWINE_PASSWORD=pypi-새로발급받은실제토큰

   # 또는 ~/.pypirc 업데이트
   nano ~/.pypirc  # password 항목 수정

   # 재시도
   twine upload -u __token__ -p $TWINE_PASSWORD dist/*
   ```

3. **2FA 활성화된 경우**
   - 비밀번호로는 업로드 불가
   - 반드시 API 토큰 사용

#### 2. "zsh: no matches found: dist/*"

**증상:**
```bash
❯ twine upload dist/*
zsh: no matches found: dist/*
```

**원인:**
- zsh에서 glob 패턴이 매칭되지 않으면 오류 발생
- bash와 다른 동작

**해결 방법:**
```bash
# 방법 1: 파일명 명시 (권장)
twine upload dist/lecture_forge-0.2.0-py3-none-any.whl dist/lecture_forge-0.2.0.tar.gz

# 방법 2: noglob 사용
noglob twine upload dist/*

# 방법 3: bash로 실행
bash -c 'twine upload dist/*'

# 방법 4: 따옴표 사용
twine upload 'dist/*'
```

#### 3. ~/.pypirc가 무시되는 문제

**증상:**
- ~/.pypirc에 토큰이 있는데도 인증 실패
- 매번 토큰을 입력해야 함

**원인:**
- 명령줄에서 `-u`, `-p` 옵션을 지정하면 ~/.pypirc가 **무시**됨

**twine 인증 우선순위:**
```
1. 명령줄 옵션 (-u, -p)      ← 최우선 (이걸 쓰면 아래는 무시)
2. 환경 변수 (TWINE_USERNAME, TWINE_PASSWORD)
3. ~/.pypirc 파일             ← 마지막
```

**해결 방법:**
```bash
# ❌ 잘못된 사용 (.pypirc 무시됨)
twine upload -u __token__ -p pypi-WRONG dist/*

# ✅ 올바른 사용 (.pypirc 자동 사용)
twine upload dist/*
```

#### 4. "Cannot find file" - 파일을 찾을 수 없음

**증상:**
```
ERROR    InvalidDistribution: Cannot find file (or expand pattern):
         'dist/lecture_forge-0.2.0-py3-none-any.whl'
```

**원인:**
- 현재 디렉토리가 프로젝트 루트가 아님
- 빌드하지 않았거나 dist/ 폴더가 없음

**해결 방법:**
```bash
# 현재 위치 확인
pwd
ls -la | grep dist

# 프로젝트 루트로 이동
cd /path/to/lecture-forge

# 빌드 재실행
python -m build

# 파일 확인
ls -l dist/
```

#### 5. "File already exists"

**증상:**
```
ERROR    HTTPError: 400 Bad Request
         File already exists.
```

**원인:**
- 같은 버전을 다시 업로드하려고 함
- PyPI는 같은 버전 번호를 다시 업로드할 수 없음

**해결 방법:**
```bash
# 버전 번호 올리기
# pyproject.toml, setup.py, __version__.py 수정
version = "0.2.1"  # 0.2.0 → 0.2.1

# 재빌드
rm -rf dist/
python -m build

# 재업로드
twine upload dist/*
```

#### 6. "Invalid distribution"

**증상:**
```
ERROR    Invalid distribution
```

**원인:**
- 패키지 구조 오류
- 필수 파일 누락
- setup.py 또는 pyproject.toml 오류

**해결 방법:**
```bash
# 패키지 검증
twine check dist/*

# 빌드 재실행
rm -rf dist/ build/ *.egg-info
python -m build

# 패키지 내용 확인
tar -tzf dist/lecture_forge-0.2.0.tar.gz
unzip -l dist/lecture_forge-0.2.0-py3-none-any.whl
```

#### 7. "README rendering error"

**증상:**
- PyPI에서 README가 제대로 표시되지 않음

**원인:**
- Markdown 문법 오류
- 지원하지 않는 Markdown 기능 사용

**해결 방법:**
```bash
# README 검증
pip install readme-renderer
python -m readme_renderer README.md

# 또는
twine check dist/*
```

### B. 디버깅 명령어

```bash
# 빌드 파일 상세 확인
tar -xzf dist/lecture-forge-0.2.0.tar.gz
ls -la lecture-forge-0.2.0/

# wheel 파일 확인
unzip dist/lecture_forge-0.2.0-py3-none-any.whl -d wheel_contents
tree wheel_contents

# 설치된 패키지 확인
pip show lecture-forge
pip list | grep lecture-forge
```

---

## 📊 배포 체크리스트

### 배포 전

- [ ] 모든 테스트 통과
- [ ] README.md 업데이트
- [ ] CHANGELOG.md 작성
- [ ] 버전 번호 일치 (3곳)
- [ ] LICENSE 파일 존재
- [ ] setup.py entry_point 수정
- [ ] .env.example 존재
- [ ] 의존성 최신 버전

### 배포 중

- [ ] 빌드 성공
- [ ] twine check 통과
- [ ] TestPyPI 업로드 성공
- [ ] TestPyPI 설치 테스트
- [ ] PyPI 업로드 성공

### 배포 후

- [ ] PyPI 페이지 확인
- [ ] 설치 테스트 (Python 3.11+)
- [ ] CLI 명령어 테스트
- [ ] Git 태그 생성
- [ ] GitHub Release 생성
- [ ] 문서 업데이트

---

## 🔗 유용한 링크

- **PyPI**: https://pypi.org/project/lecture-forge/
- **TestPyPI**: https://test.pypi.org/project/lecture-forge/
- **PyPI 도움말**: https://packaging.python.org/
- **Twine 문서**: https://twine.readthedocs.io/
- **setuptools 가이드**: https://setuptools.pypa.io/

---

## 💡 팁과 모범 사례

### 1. 버전 관리
- **Semantic Versioning** 사용: MAJOR.MINOR.PATCH
- 예: 0.2.0 → 0.2.1 (버그 수정), 0.3.0 (기능 추가), 1.0.0 (메이저 릴리스)

### 2. 배포 자동화
```bash
# Makefile 생성
cat > Makefile << 'EOF'
.PHONY: clean build test upload

clean:
	rm -rf build/ dist/ *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +

build: clean
	python -m build
	twine check dist/*

test-upload: build
	twine upload --repository testpypi dist/*

upload: build
	twine upload dist/*
EOF

# 사용
make build      # 빌드
make test-upload  # TestPyPI 업로드
make upload     # PyPI 업로드
```

### 3. CI/CD 파이프라인
```yaml
# .github/workflows/publish.yml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install build twine
      - name: Build package
        run: python -m build
      - name: Publish to PyPI
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
        run: twine upload dist/*
```

---

## 10. 배포 후 할 일

### A. README 배지 추가

```markdown
# LectureForge

[![PyPI version](https://badge.fury.io/py/lecture-forge.svg)](https://pypi.org/project/lecture-forge/)
[![Python Version](https://img.shields.io/pypi/pyversions/lecture-forge.svg)](https://pypi.org/project/lecture-forge/)
[![License](https://img.shields.io/pypi/l/lecture-forge.svg)](https://github.com/bullpeng72/Lecture_forge/blob/main/LICENSE)
[![Downloads](https://pepy.tech/badge/lecture-forge)](https://pepy.tech/project/lecture-forge)
```

### B. GitHub Release 생성

```bash
# Git 태그 생성
git tag -a v0.2.0 -m "Release v0.2.0 - First PyPI release"
git push origin v0.2.0

# GitHub Release 생성
gh release create v0.2.0 \
  --title "v0.2.0 - First PyPI Release" \
  --notes "🎉 First official release on PyPI!

## Installation
\`\`\`bash
pip install lecture-forge
\`\`\`

## What's New
- Multi-agent lecture generation system
- RAG-based content creation
- HTML + Reveal.js output
- Interactive Q&A mode

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for details."
```

### C. 문서 업데이트

```bash
# README.md에 설치 방법 추가/업데이트
cat >> README.md << 'EOF'

## Installation

### From PyPI (Recommended)
```bash
pip install lecture-forge
```

### From Source
```bash
git clone https://github.com/bullpeng72/Lecture_forge.git
cd Lecture_forge
pip install -e .
```
EOF
```

### D. 모니터링 설정

**PyPI 통계 확인:**
- https://pypistats.org/packages/lecture-forge
- https://pepy.tech/project/lecture-forge

**다운로드 추적:**
```bash
# 일간 다운로드 수
curl -s https://pypistats.org/api/packages/lecture-forge/recent | jq

# 월간 다운로드 수
curl -s https://pypistats.org/api/packages/lecture-forge/overall
```

### E. 커뮤니티 공유

- [ ] Twitter/X 게시
- [ ] Reddit (r/Python, r/MachineLearning)
- [ ] Hacker News
- [ ] Product Hunt
- [ ] 한국 개발 커뮤니티 (OKKY, 생활코딩 등)

---

## 📈 배포 현황

### v0.2.0 (2026-02-09) ✅

- **상태**: 배포 완료
- **PyPI**: https://pypi.org/project/lecture-forge/0.2.0/
- **파일 크기**:
  - wheel: 188.2 KB
  - tarball: 197.9 KB
- **체크섬**:
  - wheel: `d58bf816bb5feac07814d499c06bd49be245e3f367890a2742b6002f13a3e3d7`
  - tarball: `e1d5b65355b6f90da149f411b29c4cd66e66b858b3778bccc157b624a1dfee6e`

### 다음 릴리스 계획

- v0.2.1: 버그 수정 및 문서 개선
- v0.3.0: 새로운 기능 추가
- v1.0.0: 안정 버전 릴리스

---

## 🎓 교훈 및 팁

### 실제 배포 경험 (2026-02-09)

**문제 1: zsh glob 패턴**
- **현상**: `twine upload dist/*` → `zsh: no matches found`
- **해결**: 파일명 명시 또는 `noglob` 사용
- **교훈**: macOS/zsh 사용자는 bash와 다른 동작 주의

**문제 2: 403 Forbidden**
- **현상**: TestPyPI/PyPI 업로드 시 403 오류
- **원인**: 토큰 권한 또는 잘못된 토큰
- **해결**: "Entire account" scope 토큰 재발급
- **교훈**: 첫 업로드는 반드시 "Entire account" 권한 필요

**문제 3: ~/.pypirc 무시**
- **현상**: ~/.pypirc에 토큰이 있어도 인증 실패
- **원인**: 명령줄 `-u`, `-p` 옵션 사용
- **해결**: 옵션 제거하고 `twine upload dist/*`만 실행
- **교훈**: 명령줄 옵션이 최우선 순위, .pypirc는 마지막

### 권장 워크플로우

```bash
# 1. 버전 업데이트
# pyproject.toml, setup.py, __version__.py

# 2. 테스트 및 코드 품질
pytest tests/ -v
black src/ tests/
flake8 src/ tests/

# 3. 빌드
rm -rf dist/ build/ *.egg-info
python -m build

# 4. 검증
twine check dist/*

# 5. 업로드 (가장 간단한 방법)
twine upload dist/lecture_forge-*

# 6. 확인
pip install --upgrade lecture-forge
lecture-forge --version

# 7. Git 태그 및 Release
git tag -a v0.x.x -m "Release v0.x.x"
git push origin v0.x.x
gh release create v0.x.x
```

---

## 📚 추가 자료

### 공식 문서
- [Python Packaging User Guide](https://packaging.python.org/)
- [PyPI Help](https://pypi.org/help/)
- [Twine Documentation](https://twine.readthedocs.io/)
- [setuptools Documentation](https://setuptools.pypa.io/)

### 유용한 도구
- [PyPI Package Health](https://snyk.io/advisor/python/)
- [Libraries.io](https://libraries.io/pypi/lecture-forge)
- [PyPI Stats](https://pypistats.org/)
- [Best PyPI](https://bestofpypi.com/)

### 보안
- [PyPI 2FA 설정](https://pypi.org/help/#twofa)
- [API Token 관리](https://pypi.org/help/#apitoken)
- [Package Security](https://pypi.org/security/)

---

**작성일**: 2026-02-09
**최종 업데이트**: 2026-02-09 (v0.2.0 배포 완료)
**버전**: 2.0.0
**저자**: Sungwoo Kim (@bullpeng72)
**상태**: ✅ 실전 검증 완료
