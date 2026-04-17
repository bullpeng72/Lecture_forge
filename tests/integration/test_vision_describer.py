"""
Vision Describer Integration Tests

테스트 항목:
  T1. Config.get_vision_model() — Ollama 모드에서 올바른 모델 반환
  T2. Vision LLM 직접 호출 — 실제 이미지 설명 생성 (3장)
  T3. Fallback 동작 — 존재하지 않는 이미지로 강제 실패 후 텍스트 추론 복구
  T4. 텍스트 추론 비교 — 동일 이미지에 대한 vision vs 텍스트 설명 나란히 출력

실행:
  cd /Users/fomalhaut/Projects/Lecture_forge
  python tests/integration/test_vision_describer.py
"""

import os
import sys
import time
from pathlib import Path

# ── 프로젝트 src를 sys.path에 추가 ──────────────────────────────
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

# .env 로드 (~/Documents/LectureForge/.env)
from dotenv import load_dotenv

env_path = Path.home() / "Documents" / "LectureForge" / ".env"
load_dotenv(env_path)

# ── 컬러 출력 헬퍼 ───────────────────────────────────────────────
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

IMAGES_DIR = Path.home() / "Documents" / "LectureForge" / "outputs" / "AI_Engineering_20260416_183658_images"
SAMPLE_COUNT = 3  # vision 테스트할 이미지 수


def ok(msg):
    print(f"  {GREEN}✅ {msg}{RESET}")


def fail(msg):
    print(f"  {RED}❌ {msg}{RESET}")


def warn(msg):
    print(f"  {YELLOW}⚠️  {msg}{RESET}")


def header(msg):
    print(f"\n{BOLD}{CYAN}{'='*60}{RESET}")
    print(f"{BOLD}{CYAN} {msg}{RESET}")
    print(f"{BOLD}{CYAN}{'='*60}{RESET}")


def section(msg):
    print(f"\n{BOLD}── {msg} ──{RESET}")


# ────────────────────────────────────────────────────────────────
# T1: Config 라우팅
# ────────────────────────────────────────────────────────────────
def test_config_routing():
    header("T1: Config.get_vision_model() 라우팅")

    from lecture_forge.config import Config

    provider = Config.LLM_PROVIDER
    vision_model = Config.get_vision_model()
    ollama_model = Config.OLLAMA_MODEL
    ollama_vision = Config.OLLAMA_VISION_MODEL

    print(f"  LLM_PROVIDER       = {provider}")
    print(f"  OLLAMA_MODEL       = {ollama_model}")
    print(f"  OLLAMA_VISION_MODEL= '{ollama_vision}' (비어있으면 OLLAMA_MODEL 사용)")
    print(f"  get_vision_model() = {vision_model}")

    if provider == "ollama":
        expected = ollama_vision or ollama_model
        if vision_model == expected:
            ok(f"올바른 vision 모델 반환: {vision_model}")
            return True
        else:
            fail(f"예상: {expected}, 실제: {vision_model}")
            return False
    else:
        expected = Config.VISION_MODEL or Config.DEFAULT_MODEL
        if vision_model == expected:
            ok(f"OpenAI vision 모델 반환: {vision_model}")
            return True
        else:
            fail(f"예상: {expected}, 실제: {vision_model}")
            return False


# ────────────────────────────────────────────────────────────────
# T2: Vision LLM 직접 호출
# ────────────────────────────────────────────────────────────────
def test_vision_direct():
    header("T2: Vision LLM 직접 호출 (실제 이미지 설명)")

    if not IMAGES_DIR.exists():
        warn(f"이미지 디렉토리 없음: {IMAGES_DIR}")
        warn("create 명령어로 강의를 먼저 생성하세요.")
        return None  # skip

    images = sorted(IMAGES_DIR.glob("*.webp"))[:SAMPLE_COUNT]
    if not images:
        warn("webp 이미지 없음 — skip")
        return None

    from lecture_forge.tools.pdf_image_describer import PDFImageDescriber

    describer = PDFImageDescriber()

    print(f"  Vision 모델: {describer._get_vision_llm()}")
    print(f"  테스트 이미지 {len(images)}장\n")

    results = []
    all_ok = True
    for img_path in images:
        section(f"이미지: {img_path.name}")
        t0 = time.time()
        try:
            desc = describer._describe_image_with_vision(img_path, page_text="")
            elapsed = time.time() - t0
            print(f"  설명: {desc}")
            print(f"  소요: {elapsed:.1f}s")
            if desc and len(desc) > 10:
                ok("설명 생성 성공")
                results.append({"file": img_path.name, "vision": desc, "ok": True})
            else:
                warn("설명이 너무 짧거나 비어있음")
                results.append({"file": img_path.name, "vision": desc, "ok": False})
                all_ok = False
        except Exception as e:
            elapsed = time.time() - t0
            fail(f"Vision 호출 실패: {e.__class__.__name__}: {e}")
            results.append({"file": img_path.name, "vision": None, "ok": False, "error": str(e)})
            all_ok = False

    return results if all_ok else None


# ────────────────────────────────────────────────────────────────
# T3: Fallback 동작 검증
# ────────────────────────────────────────────────────────────────
def test_fallback():
    header("T3: Vision 실패 → 텍스트 추론 Fallback")

    from lecture_forge.tools.pdf_image_describer import PDFImageDescriber

    describer = PDFImageDescriber()

    # 존재하지 않는 이미지 경로로 강제 실패
    fake_path = IMAGES_DIR / "nonexistent_fake_image.webp"
    page_text = "This page discusses neural network architectures and transformer models."

    print("  존재하지 않는 이미지 경로로 _describe_page_images_vision 호출")
    print(f"  fake path: {fake_path.name}")
    print(f"  page_text: '{page_text[:60]}...'")

    descriptions = describer._describe_page_images_vision(
        page_num=1,
        image_files=[fake_path],
        page_text=page_text,
    )

    print(f"  _vision_available 상태: {describer._vision_available}")
    print(f"  Fallback 설명: {descriptions}")

    if not describer._vision_available:
        ok("_vision_available=False 로 올바르게 전환")
    else:
        fail("_vision_available이 여전히 True — fallback 미작동")
        return False

    if descriptions and any(d for d in descriptions):
        ok(f"Fallback 설명 생성 성공: '{descriptions[0][:80]}'")
        return True
    else:
        fail("Fallback 설명 생성 실패")
        return False


# ────────────────────────────────────────────────────────────────
# T4: Vision vs 텍스트 추론 비교
# ────────────────────────────────────────────────────────────────
def test_vision_vs_text(vision_results):
    header("T4: Vision vs 텍스트 추론 비교")

    if not vision_results:
        warn("T2 결과 없음 — 비교 불가")
        return

    if not IMAGES_DIR.exists():
        warn("이미지 디렉토리 없음 — skip")
        return

    from lecture_forge.tools.pdf_image_describer import PDFImageDescriber

    describer = PDFImageDescriber()
    # 텍스트 추론용 더미 페이지 텍스트
    dummy_page_text = (
        "This chapter covers AI engineering concepts including model training, "
        "evaluation, and deployment. Key topics: neural networks, transformers, "
        "RAG systems, and LLM fine-tuning."
    )

    for item in vision_results:
        section(item["file"])
        print(f"  [Vision]  {item.get('vision', '(실패)')}")

        page_num = int(item["file"].split("_")[0].replace("page", ""))
        text_descs = describer._generate_descriptions_for_page(
            page_num=page_num,
            page_text=dummy_page_text,
            num_images=1,
        )
        print(f"  [텍스트]  {text_descs[0] if text_descs else '(실패)'}")

    ok("비교 출력 완료")


# ────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────
def main():
    print(f"\n{BOLD}LectureForge Vision Describer — Integration Test{RESET}")
    print(f"env: {env_path}")
    print(f"images: {IMAGES_DIR}")

    results_summary = []

    # T1
    t1 = test_config_routing()
    results_summary.append(("T1 Config 라우팅", t1))

    # T2
    vision_results = test_vision_direct()
    t2_ok = vision_results is not None
    results_summary.append(("T2 Vision 직접 호출", t2_ok))

    # T3
    t3 = test_fallback()
    results_summary.append(("T3 Fallback 동작", t3))

    # T4
    test_vision_vs_text(vision_results)
    results_summary.append(("T4 Vision vs 텍스트 비교", True))  # 출력 테스트

    # 최종 요약
    header("테스트 결과 요약")
    all_pass = True
    for name, passed in results_summary:
        if passed is None:
            warn(f"SKIP  {name}")
        elif passed:
            ok(f"PASS  {name}")
        else:
            fail(f"FAIL  {name}")
            all_pass = False

    print()
    if all_pass:
        print(f"{BOLD}{GREEN}🎉 모든 테스트 통과{RESET}\n")
    else:
        print(f"{BOLD}{RED}일부 테스트 실패 — 위 결과 확인{RESET}\n")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
