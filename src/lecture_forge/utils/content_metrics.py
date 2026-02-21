"""
Content Quality Metrics and Target Calculation.

Calculates target metrics for lecture content based on duration and difficulty.
"""

from typing import Dict

from lecture_forge.config import Config


def calculate_target_metrics(estimated_time: int, difficulty_level: str) -> Dict[str, int]:
    """
    Calculate target metrics for content based on lecture time and difficulty.

    Args:
        estimated_time: Minutes allocated for this section
        difficulty_level: beginner/intermediate/advanced

    Returns:
        Dictionary of target metrics
    """
    # Base calculation: words per minute (from Config)
    base_words_per_minute = Config.LECTURE_WORDS_PER_MINUTE

    # Difficulty multipliers (from Config)
    difficulty_multipliers = {
        "beginner": Config.DIFFICULTY_MULTIPLIER_BEGINNER,
        "intermediate": Config.DIFFICULTY_MULTIPLIER_INTERMEDIATE,
        "advanced": Config.DIFFICULTY_MULTIPLIER_ADVANCED,
    }

    multiplier = difficulty_multipliers.get(difficulty_level.lower(), 1.0)

    target_words = int(estimated_time * base_words_per_minute * multiplier)

    # Code examples calculation (from Config)
    code_examples_per_time = {
        "beginner": Config.CODE_EXAMPLES_PER_TIME_BEGINNER,
        "intermediate": Config.CODE_EXAMPLES_PER_TIME_INTERMEDIATE,
        "advanced": Config.CODE_EXAMPLES_PER_TIME_ADVANCED,
    }

    time_per_example = code_examples_per_time.get(difficulty_level.lower(), Config.CODE_EXAMPLES_PER_TIME_INTERMEDIATE)
    target_code_examples = max(1, estimated_time // time_per_example)

    # Practice problems (from Config)
    practice_per_time = {
        "beginner": Config.PRACTICE_PER_TIME_BEGINNER,
        "intermediate": Config.PRACTICE_PER_TIME_INTERMEDIATE,
        "advanced": Config.PRACTICE_PER_TIME_ADVANCED,
    }

    time_per_practice = practice_per_time.get(difficulty_level.lower(), Config.PRACTICE_PER_TIME_INTERMEDIATE)
    _ = time_per_practice  # kept for config reference
    target_practice_problems = 0  # practice problems disabled

    # Subsections: logical breaks in content (from Config)
    target_subsections = max(3, estimated_time // Config.SUBSECTION_MINUTES)

    # Visual elements (images/diagrams) (from Config)
    target_visuals = max(2, estimated_time // Config.VISUAL_PER_MINUTES)

    return {
        "target_words": target_words,
        "min_words": int(target_words * Config.MIN_WORDS_RATIO),
        "max_words": int(target_words * Config.MAX_WORDS_RATIO),
        "target_code_examples": target_code_examples,
        "min_code_examples": max(1, target_code_examples - 1),
        "target_practice_problems": target_practice_problems,
        "target_subsections": target_subsections,
        "min_subsections": max(2, target_subsections - 1),
        "target_visuals": target_visuals,
    }


def evaluate_content_quality(
    content: str,
    targets: Dict[str, int],
    code_block_count: int = 0,
    image_count: int = 0,
) -> Dict[str, any]:
    """
    Evaluate content against target metrics.

    Args:
        content: Markdown content
        targets: Target metrics from calculate_target_metrics
        code_block_count: Number of code blocks
        image_count: Number of images

    Returns:
        Quality evaluation results
    """
    # Count words
    word_count = len(content.split())

    # Count subsections (H3 headers)
    subsection_count = content.count("\n### ") + content.count("\n## ")

    # Count practice problems (look for keywords)
    practice_keywords = [
        "연습문제",
        "실습",
        "Practice",
        "Exercise",
        "문제",
        "과제",
        "Assignment",
    ]
    practice_count = sum(1 for kw in practice_keywords if kw in content)

    # Calculate scores (0-100)
    def calculate_score(actual: int, target: int, min_val: int = None) -> float:
        """Calculate score with threshold."""
        if min_val and actual < min_val:
            return (actual / min_val) * 50  # Cap at 50% if below minimum
        if actual >= target:
            return 100.0
        return (actual / target) * 100

    word_score = calculate_score(word_count, targets["target_words"], targets["min_words"])

    code_score = calculate_score(
        code_block_count,
        targets["target_code_examples"],
        targets.get("min_code_examples", 0),
    )

    structure_score = calculate_score(
        subsection_count,
        targets["target_subsections"],
        targets.get("min_subsections", 0),
    )

    practice_score = calculate_score(practice_count, targets["target_practice_problems"])

    visual_score = calculate_score(image_count, targets["target_visuals"])

    # Calculate overall score with weights
    overall_score = (
        word_score * 0.40  # 40% - content length
        + code_score * 0.25  # 25% - code examples
        + structure_score * 0.25  # 25% - structure
        + practice_score * 0.00  # 0% - practice problems (disabled)
        + visual_score * 0.10  # 10% - visuals
    )

    return {
        "overall_score": round(overall_score, 1),
        "meets_requirements": overall_score >= Config.QUALITY_THRESHOLD_SECTION,
        "word_count": word_count,
        "word_score": round(word_score, 1),
        "code_block_count": code_block_count,
        "code_score": round(code_score, 1),
        "subsection_count": subsection_count,
        "structure_score": round(structure_score, 1),
        "practice_count": practice_count,
        "practice_score": round(practice_score, 1),
        "image_count": image_count,
        "visual_score": round(visual_score, 1),
        "targets": targets,
    }


def format_quality_report(evaluation: Dict) -> str:
    """Format quality evaluation as readable report."""
    report = f"""
📊 Content Quality Report
{"="*50}

Overall Score: {evaluation['overall_score']}/100 {'✅' if evaluation['meets_requirements'] else '❌'}

Detailed Metrics:
--------------------------------------------------
📝 Word Count: {evaluation['word_count']:,} / {evaluation['targets']['target_words']:,}
   Score: {evaluation['word_score']}/100
   Range: {evaluation['targets']['min_words']:,} - {evaluation['targets']['max_words']:,}

💻 Code Examples: {evaluation['code_block_count']} / {evaluation['targets']['target_code_examples']}
   Score: {evaluation['code_score']}/100

🏗️  Structure (Subsections): {evaluation['subsection_count']} / {evaluation['targets']['target_subsections']}
   Score: {evaluation['structure_score']}/100

📚 Practice Problems: {evaluation['practice_count']} / {evaluation['targets']['target_practice_problems']}
   Score: {evaluation['practice_score']}/100

🖼️  Visuals: {evaluation['image_count']} / {evaluation['targets']['target_visuals']}
   Score: {evaluation['visual_score']}/100

{"="*50}
Status: {'PASS ✅' if evaluation['meets_requirements'] else 'NEEDS IMPROVEMENT ⚠️'}
"""
    return report
