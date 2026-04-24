"""
LectureForge × Agent-Evaluator 통합 — PerformanceMonitor 팩토리

Gate 설계 근거
──────────────
Gate A  ContentWriterAgent가 section.learning_outcomes 키워드를 본문에 반영하는가?
        CurriculumDesignerAgent의 섹션이 요청 topic / duration을 충족하는가?
Gate B  RevisionAgent 반복 루프가 MAX_ITERATIONS(3회) 이내로 수렴하는가?
        ContentWriterAgent가 동일 섹션을 반복 생성하는 루프에 빠지지 않는가?
Gate C  LLM retry 로직이 API 실패 후 정상 복구하는가?
        RAG 쿼리 실패 시 fallback 응답이 품질 하한(GracefulDegradation)을 유지하는가?
Gate D  섹션 생성 P95 ≤ 45s / 커리큘럼 설계 P95 ≤ 30s / 분석 P95 ≤ 20s / QA P95 ≤ 10s
        강의 1편 총 토큰 ≤ 120,000 (≈$0.035, 실측 기준)
Gate E  PDF 입력 내 프롬프트 인젝션 탐지 (외부 문서가 악의적 지시를 포함할 가능성)
        생성된 강의 콘텐츠에서 민감 정보 노출(OutputLeakage) 탐지
Gate F  ContentAnalyzer → CurriculumDesigner → ContentWriter 데이터 전파 정합성
        분석에서 추출된 key_topics가 커리큘럼 섹션에 실제로 반영됐는가?
Gate G  커리큘럼 설계 추론 과정 설명 가능성(Explainability)
        단계별 지연 기여도 분석 — 어느 에이전트가 전체 시간의 몇 %를 차지하는가?
"""
from pathlib import Path
from typing import Optional

from agent_evaluator import PerformanceMonitor


# ── Gate D 예산 상수 ─────────────────────────────────────────────────────────
BUDGET_TOKENS_PER_SECTION: int = 8_000   # 섹션 하나당 허용 최대 토큰
BUDGET_TOTAL_LECTURE: int = 120_000      # 강의 1편 전체 토큰 예산

# ── Gate D SLA (밀리초) ──────────────────────────────────────────────────────
SLA_CONTENT_WRITER_P95_MS: int = 45_000  # ContentWriterAgent 섹션 1개 P95
SLA_CURRICULUM_P95_MS: int = 30_000      # CurriculumDesignerAgent.design() P95
SLA_ANALYSIS_P95_MS: int = 20_000        # ContentAnalyzerAgent.analyze() P95
SLA_QA_P95_MS: int = 10_000             # QAAgent.answer() P95


def build_lecture_monitor(
    output_dir: str = "eval_results/",
    *,
    enable_llm_judge: bool = False,
    judge_model: Optional[str] = None,
) -> PerformanceMonitor:
    """
    LectureForge 파이프라인용 PerformanceMonitor를 생성한다.

    Gate A–G Config은 adapters.py 의 각 어댑터에서 record_task() 호출 시
    extra 필드로 전달된다. 여기서는 모니터 수준 옵션만 설정한다.

    Args:
        output_dir:       평가 결과 JSON/HTML 저장 경로 (없으면 자동 생성)
        enable_llm_judge: True이면 20% 샘플에 LLM 채점 적용
                          (커리큘럼 품질 및 섹션 완성도 자동 채점)
        judge_model:      None → API 키 기반 자동 결정 (Anthropic 우선)

    Returns:
        설정된 PerformanceMonitor 인스턴스
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    return PerformanceMonitor(
        output_dir=output_dir,
        # Gate E: PDF 입력 내 프롬프트 인젝션 + 출력 민감 정보 탐지
        enable_security_metrics=True,
        # 할루시네이션 탐지는 RAG 컨텍스트 전달 시 어댑터 레벨에서 활성화
        # 모니터 전체 활성화는 비용 영향이 크므로 기본 off
        enable_hallucination_detection=False,
        # LLM Judge — 강의 섹션 콘텐츠 품질 채점 (선택 opt-in)
        enable_llm_judge=enable_llm_judge,
        judge_model=judge_model,
        judge_sample_rate=0.2,       # 20% 샘플 채점으로 비용 절감
        # 자동 저장 — 5건마다 중간 저장 (파이프라인 중단 시에도 결과 보존)
        auto_save=True,
        auto_save_interval=5,
    )
