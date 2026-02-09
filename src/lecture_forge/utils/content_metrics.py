"""
Content Quality Metrics and Target Calculation.

Calculates target metrics for lecture content based on duration and difficulty.
"""

from typing import Dict


def calculate_target_metrics(estimated_time: int, difficulty_level: str) -> Dict[str, int]:
    """
    Calculate target metrics for content based on lecture time and difficulty.

    Args:
        estimated_time: Minutes allocated for this section
        difficulty_level: beginner/intermediate/advanced

    Returns:
        Dictionary of target metrics
    """
    # Base calculation: words per minute
    # For lecture content, account for:
    # - Speaking time (~60% of total)
    # - Example demonstrations (~20%)
    # - Student questions/interaction (~20%)
    # Target: 120 words per minute (realistic for actual lecture delivery)
    # Note: Reading speed is 200-250 wpm, but lectures are slower due to:
    #   - Pauses for comprehension
    #   - Code demonstrations
    #   - Interactive elements

    base_words_per_minute = 120  # Realistic lecture speed (was 250 - too high!)

    # Difficulty multipliers
    # Beginner needs more explanation = more words
    # Advanced can move faster but needs deeper content
    difficulty_multipliers = {
        "beginner": 1.3,  # More verbose explanations
        "intermediate": 1.0,  # Balanced
        "advanced": 1.1,  # Dense content with nuance
    }

    multiplier = difficulty_multipliers.get(difficulty_level.lower(), 1.0)

    target_words = int(estimated_time * base_words_per_minute * multiplier)

    # Code examples calculation
    # Beginner: more, simpler examples
    # Advanced: fewer but more complex examples
    code_examples_per_time = {
        "beginner": 20,  # 1 example per 20 minutes
        "intermediate": 15,  # 1 per 15 minutes
        "advanced": 12,  # 1 per 12 minutes
    }

    time_per_example = code_examples_per_time.get(difficulty_level.lower(), 15)
    target_code_examples = max(1, estimated_time // time_per_example)

    # Practice problems
    # Should have enough for assessment but not overwhelming
    practice_per_time = {
        "beginner": 25,  # 1 per 25 minutes
        "intermediate": 20,  # 1 per 20 minutes
        "advanced": 30,  # 1 per 30 minutes (more complex problems)
    }

    time_per_practice = practice_per_time.get(difficulty_level.lower(), 20)
    target_practice_problems = max(1, estimated_time // time_per_practice)

    # Subsections: logical breaks in content
    # Aim for 10-15 minutes per subsection
    target_subsections = max(3, estimated_time // 12)

    # Visual elements (images/diagrams)
    # 1 per 10 minutes is a good rule of thumb
    target_visuals = max(2, estimated_time // 10)

    return {
        "target_words": target_words,
        "min_words": int(target_words * 0.75),  # Allow 25% under
        "max_words": int(target_words * 1.3),  # Allow 30% over
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
        word_score * 0.30  # 30% - content length
        + code_score * 0.25  # 25% - code examples
        + structure_score * 0.20  # 20% - structure
        + practice_score * 0.15  # 15% - practice problems
        + visual_score * 0.10  # 10% - visuals
    )

    return {
        "overall_score": round(overall_score, 1),
        "meets_requirements": overall_score >= 75,  # 75% threshold
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
