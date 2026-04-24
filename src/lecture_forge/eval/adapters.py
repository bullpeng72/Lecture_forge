"""
LectureForge 에이전트 어댑터 모음

설계 원칙 (Level 1 — 최소 침습)
──────────────────────────────────────────────────────────────────────────────
기존 에이전트 코드를 일절 수정하지 않는다.
위임(Delegation) 패턴: 어댑터가 원본 에이전트의 메서드를 호출하고,
결과를 TaskResult로 변환해 monitor에 기록한 뒤 원래 반환값을 그대로 돌려준다.
__getattr__ 위임으로 계측하지 않는 메서드/속성은 원본으로 투명하게 전달된다.

@agent_eval 데코레이터를 직접 쓰지 않는 이유
──────────────────────────────────────────────────────────────────────────────
@agent_eval 데코레이터는 래핑 대상 함수가 str(또는 (str, EvalMetadata))을 반환해야 한다.
LectureForge 에이전트 메서드는 Pydantic 모델(SectionContent, Curriculum, AnalysisResult 등)을
반환하므로 데코레이터를 직접 적용할 수 없다.

대신 아래 패턴을 사용한다:
  1. 원본 메서드 호출 → Pydantic 모델 획득
  2. 모델에서 의미 있는 str 요약 추출
  3. create_taskresult() + monitor.record_task() 로 수동 기록

이 패턴은 Chapter 24 "첫 번째 이식 — Level 1" 접근법과 동일하다.

Gate 측정 항목 (각 어댑터 docstring 참조)
──────────────────────────────────────────────────────────────────────────────
adapter             |  Gate A  |  Gate C  |  Gate D  |  Gate E  |  Gate G
--------------------|----------|----------|----------|----------|----------
ContentWriterAdapter|  ✅ (A)  |  ✅ (C)  |  ✅ (D)  |  ✅ (E)  |  ✅ (G)
CurriculumAdapter   |  ✅ (A)  |          |  ✅ (D)  |          |  ✅ (G)
ContentAnalyzerAdap.|  ✅ (A)  |          |  ✅ (D)  |          |
QualityEvalAdapter  |          |  ✅ (C)  |          |          |
"""
import time
from typing import List, Optional

from agent_evaluator import (
    PerformanceMonitor,
    create_taskresult,
)


class ContentWriterAdapter:
    """
    ContentWriterAgent를 감싸 각 섹션 생성을 계측한다.

    측정 항목
    ─────────
    Gate A  InstructionConfig 의 required_keywords 검증에 해당:
            section.learning_outcomes 키워드가 생성 본문(markdown_content)에 반영됐는가?
            → response = markdown_content, ground_truth = learning_outcomes 문자열
              AccuracyEvaluator Token F1 이 키워드 일치율을 자동 측정한다.

    Gate C  FaultToleranceConfig 해당:
            has_error=True TaskResult를 기록해 TCR(태스크 완료율) 계산에 포함된다.

    Gate D  SLAConfig 해당:
            execution_time을 LatencyTracker에 전달 — 섹션별 P95를 ≤45s로 관리한다.
            extra["phase"] = "content_writing" 으로 LatencyAttributionConfig 기여도 분석 지원.

    Gate E  enable_security_metrics=True 설정으로 PerformanceMonitor가
            response(생성 콘텐츠)에서 민감 정보 노출을 자동 탐지한다.

    Gate G  extra["word_count", "section_id", "phase"] 로
            LatencyAttributionConfig 단계별 지연 기여도 분석을 지원한다.

    사용 예
    ───────
    writer = ContentWriterAgent(vector_store=vs)
    writer = ContentWriterAdapter(writer, monitor, curriculum.learning_objectives)
    # 이후 writer.write_section() 호출 시 자동 계측
    content = writer.write_section(section, curriculum, available_images)
    """

    def __init__(
        self,
        agent,
        monitor: PerformanceMonitor,
        learning_objectives: List[str],
    ) -> None:
        self._agent = agent
        self._monitor = monitor
        self._learning_objectives = learning_objectives

    def write_section(self, section, curriculum, available_images=None):
        """원본 write_section()을 호출하고 결과를 monitor에 기록한다."""
        task_id = f"section_{getattr(section, 'id', 'unknown')}"
        start = time.perf_counter()
        has_error = False
        error_msg: Optional[str] = None
        result = None

        try:
            result = self._agent.write_section(section, curriculum, available_images)
        except Exception as exc:
            has_error = True
            error_msg = str(exc)
            raise
        finally:
            elapsed = time.perf_counter() - start

            # 생성된 마크다운 본문 — Gate A(키워드 일치) + Gate E(보안 스캔) 대상
            content_text = getattr(result, "markdown_content", "") if result else ""

            # ground_truth: 섹션 학습목표 → AccuracyEvaluator가 키워드 일치율 자동 측정
            section_objectives = getattr(section, "learning_outcomes", []) or []
            ground_truth = " ".join(section_objectives)

            extra = {
                "phase": "content_writing",           # Gate G 단계별 지연 분석
                "section_id": getattr(section, "id", ""),
                "section_title": getattr(section, "title", ""),
                "word_count": getattr(result, "word_count", 0) if result else 0,
                "difficulty": getattr(section, "difficulty_level", ""),
            }

            task = create_taskresult(
                task_id=task_id,
                question=(
                    f"섹션 '{getattr(section, 'title', '')}' 콘텐츠를 작성하라. "
                    f"학습목표: {ground_truth[:200]}"
                ),
                response=content_text,
                ground_truth=ground_truth,
                execution_time=elapsed,
                task_type="document_creation",
                has_error=has_error,
                error_message=error_msg,
                extra=extra,
            )
            self._monitor.record_task(task)

        return result

    def __getattr__(self, name: str):
        """계측하지 않는 메서드/속성은 원본 에이전트로 투명하게 위임한다."""
        return getattr(self._agent, name)


class CurriculumDesignerAdapter:
    """
    CurriculumDesignerAgent.design()을 계측한다.

    측정 항목
    ─────────
    Gate A  PlanConfig / SubtaskConfig 해당:
            요청 topic 키워드가 learning_objectives에 반영됐는가?
            섹션 수 × 평균 시간이 요청 duration과 정렬됐는가?
            → response에 섹션 제목 목록과 총 예상 시간을 포함해 기록한다.

    Gate D  SLAConfig 해당:
            커리큘럼 설계 P95 ≤ 30s.
            extra["duration_requested", "duration_actual"]로 오차 추적.

    Gate G  ExplainabilityConfig 해당:
            response에 학습목표와 섹션 구성 근거를 담아 설명 가능성 지표를 측정한다.
    """

    def __init__(self, agent, monitor: PerformanceMonitor) -> None:
        self._agent = agent
        self._monitor = monitor

    def design(self, analysis_result, topic: str, duration: int, audience_level: str):
        task_id = f"curriculum_{topic[:40].replace(' ', '_')}"
        start = time.perf_counter()
        has_error = False
        error_msg: Optional[str] = None
        result = None

        try:
            result = self._agent.design(analysis_result, topic, duration, audience_level)
        except Exception as exc:
            has_error = True
            error_msg = str(exc)
            raise
        finally:
            elapsed = time.perf_counter() - start

            if result is not None:
                sections = getattr(result, "sections", [])
                objectives = getattr(result, "learning_objectives", [])
                total_time = getattr(result, "total_estimated_time", 0)
                section_titles = [getattr(s, "title", "") for s in sections]

                # response: 커리큘럼 요약 — Gate A 키워드 일치 + Gate G 설명 가능성 측정
                response_text = (
                    f"커리큘럼 설계 완료. "
                    f"섹션 {len(sections)}개, 총 {total_time}분. "
                    f"학습목표: {'; '.join(objectives[:3])}. "
                    f"섹션 구성: {', '.join(section_titles)}"
                )
                # ground_truth: 요청 조건 — topic 포함 여부와 시간 충족 여부로 정확도 측정
                ground_truth = f"{topic} {duration}분 {audience_level}"
            else:
                response_text = ""
                ground_truth = f"{topic} {duration}분 {audience_level}"
                total_time = 0
                sections = []

            extra = {
                "phase": "curriculum_design",
                "topic": topic,
                "audience_level": audience_level,
                "duration_requested": duration,
                "duration_actual": total_time,
                "sections_count": len(sections),
            }

            task = create_taskresult(
                task_id=task_id,
                question=(
                    f"주제 '{topic}', {duration}분, {audience_level} 수준의 "
                    f"강의 커리큘럼을 설계하라."
                ),
                response=response_text,
                ground_truth=ground_truth,
                execution_time=elapsed,
                task_type="planning",
                has_error=has_error,
                error_message=error_msg,
                extra=extra,
            )
            self._monitor.record_task(task)

        return result

    def __getattr__(self, name: str):
        return getattr(self._agent, name)


class ContentAnalyzerAdapter:
    """
    ContentAnalyzerAgent.analyze()를 계측한다.

    측정 항목
    ─────────
    Gate A  GoalAlignmentConfig 해당:
            분석 결과의 key_topics가 요청 topic 키워드를 포함하는가?
            → response에 key_topics를 나열, ground_truth = topic 으로 기록.

    Gate D  SLAConfig 해당:
            분석 P95 ≤ 20s.

    Gate F  PropagationConfig 해당 (간접):
            extra["key_topics"]를 기록해 이후 커리큘럼 섹션의 키워드와 비교 추적 가능.
    """

    def __init__(self, agent, monitor: PerformanceMonitor) -> None:
        self._agent = agent
        self._monitor = monitor

    def analyze(self, collection_result, image_result, topic: str):
        task_id = f"analysis_{topic[:40].replace(' ', '_')}"
        start = time.perf_counter()
        has_error = False
        error_msg: Optional[str] = None
        result = None

        try:
            result = self._agent.analyze(collection_result, image_result, topic)
        except Exception as exc:
            has_error = True
            error_msg = str(exc)
            raise
        finally:
            elapsed = time.perf_counter() - start

            if result is not None:
                key_topics = getattr(result, "key_topics", [])
                entities = getattr(result, "entities", [])
                # key_topics를 문자열로 변환 (list[str] 또는 list[object] 모두 처리)
                topic_strs = [str(t) for t in key_topics[:10]]
                response_text = (
                    f"분석 완료. 핵심 주제 {len(key_topics)}개: "
                    f"{', '.join(topic_strs)}. "
                    f"엔티티 {len(entities)}개 추출."
                )
            else:
                key_topics = []
                entities = []
                response_text = ""

            extra = {
                "phase": "content_analysis",
                "topic": topic,
                "key_topics": [str(t) for t in key_topics[:20]],
                "key_topics_count": len(key_topics),
                "entities_count": len(entities),
            }

            task = create_taskresult(
                task_id=task_id,
                question=f"수집된 문서에서 '{topic}' 관련 핵심 주제와 엔티티를 분석하라.",
                response=response_text,
                ground_truth=topic,          # topic 키워드 포함 여부로 정렬도 측정
                execution_time=elapsed,
                task_type="information_retrieval",
                has_error=has_error,
                error_message=error_msg,
                extra=extra,
            )
            self._monitor.record_task(task)

        return result

    def __getattr__(self, name: str):
        return getattr(self._agent, name)


class QualityEvaluatorAdapter:
    """
    QualityEvaluator.evaluate()를 계측한다.

    기존 6차원 점수(content_completeness, logical_flow, time_alignment,
    level_appropriateness, visual_quality, technical_accuracy)를
    extra 필드로 전달해 agent-evaluator 대시보드에서 함께 조회할 수 있게 한다.

    QualityEvaluator는 규칙 기반 메트릭을 계산하므로 execution_time이 매우 짧다(<0.1s).
    SLA Gate D 관리 대상에서 제외하고, 품질 게이팅 결과(passed/failed)를 기록한다.

    측정 항목
    ─────────
    Gate C  GracefulDegradationConfig 해당:
            overall_score ≥ threshold 여부 → TCR(태스크 완료율) 에 반영.
            revision 루프 반복 횟수는 create.py 에서 extra 로 기록된다.
    """

    def __init__(self, evaluator, monitor: PerformanceMonitor) -> None:
        self._evaluator = evaluator
        self._monitor = monitor

    def evaluate(self, lecture, threshold: int = 80):
        task_id = (
            f"quality_{getattr(lecture, 'topic', 'unknown')[:30].replace(' ', '_')}"
        )
        start = time.perf_counter()
        result = self._evaluator.evaluate(lecture, threshold)
        elapsed = time.perf_counter() - start

        overall = getattr(result, "overall_score", 0.0)
        passed = getattr(result, "passed", False)
        dim_scores: dict = getattr(result, "dimension_scores", {})

        # Gate C: threshold 미달 시 has_error=True 로 기록 → TCR에 반영
        quality_failed = not passed

        response_text = (
            f"품질 점수 {overall:.1f}/100. "
            f"{'통과' if passed else '미통과'} (임계값 {threshold}). "
            + (
                f"6차원 점수: "
                + ", ".join(f"{k}={v:.1f}" for k, v in dim_scores.items())
                if dim_scores
                else ""
            )
        )

        extra = {
            "phase": "quality_evaluation",
            "overall_score": overall,
            "passed": passed,
            "threshold": threshold,
            **{f"dim_{k}": v for k, v in dim_scores.items()},
        }

        task = create_taskresult(
            task_id=task_id,
            question=(
                f"강의 '{getattr(lecture, 'topic', '')}' 품질을 "
                f"{threshold}점 기준으로 평가하라."
            ),
            response=response_text,
            ground_truth=f"품질 점수 {threshold} 이상",
            execution_time=elapsed,
            task_type="qa",
            has_error=quality_failed,      # Gate C: 품질 미달 = 태스크 실패
            error_message=(
                f"품질 점수 {overall:.1f} < 임계값 {threshold}"
                if quality_failed
                else None
            ),
            extra=extra,
        )
        self._monitor.record_task(task)
        return result

    def __getattr__(self, name: str):
        return getattr(self._evaluator, name)
