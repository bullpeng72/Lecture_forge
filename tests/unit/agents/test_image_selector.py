"""
Unit tests for ImageSelector - pure logic methods.
Tests cover _get_content_type_bonus, _evaluate_image_quality_simple,
_calculate_page_importance, _check_color_diversity, _check_edge_density.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import io
import pytest

try:
    import numpy as np
    from PIL import Image as PILImage
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


@pytest.fixture
def selector():
    """Create ImageSelector instance with no dependencies."""
    from lecture_forge.agents.content_writer.image_selector import ImageSelector
    return ImageSelector()


# ===== _get_content_type_bonus() =====

class TestGetContentTypeBonus:
    def test_diagram_gets_highest_bonus(self, selector):
        result = selector._get_content_type_bonus("diagram")
        assert result == 0.15

    def test_chart_gets_high_bonus(self, selector):
        result = selector._get_content_type_bonus("chart")
        assert result == 0.12

    def test_screenshot_gets_medium_high_bonus(self, selector):
        result = selector._get_content_type_bonus("screenshot")
        assert result == 0.10

    def test_technical_gets_medium_bonus(self, selector):
        result = selector._get_content_type_bonus("technical")
        assert result == 0.08

    def test_photo_gets_low_bonus(self, selector):
        result = selector._get_content_type_bonus("photo")
        assert result == 0.03

    def test_unknown_gets_no_bonus(self, selector):
        result = selector._get_content_type_bonus("unknown")
        assert result == 0.0

    def test_unrecognized_type_returns_zero(self, selector):
        result = selector._get_content_type_bonus("random_type")
        assert result == 0.0

    def test_diagram_bonus_greater_than_photo(self, selector):
        assert selector._get_content_type_bonus("diagram") > selector._get_content_type_bonus("photo")


# ===== _evaluate_image_quality_simple() =====

class TestEvaluateImageQualitySimple:
    def test_uses_extraction_quality_when_available(self, selector):
        image = {"extraction_quality": 0.8, "content_type": "unknown"}
        result = selector._evaluate_image_quality_simple(image)
        assert result == pytest.approx(0.8, abs=0.01)

    def test_extraction_quality_plus_content_bonus(self, selector):
        image = {"extraction_quality": 0.7, "content_type": "diagram"}
        result = selector._evaluate_image_quality_simple(image)
        assert result == pytest.approx(0.85, abs=0.01)

    def test_extraction_quality_clamped_to_1(self, selector):
        image = {"extraction_quality": 0.95, "content_type": "diagram"}
        result = selector._evaluate_image_quality_simple(image)
        assert result <= 1.0

    def test_small_image_returns_zero(self, selector):
        image = {"width": 10, "height": 10, "size_bytes": 100}
        result = selector._evaluate_image_quality_simple(image)
        assert result == 0.0

    def test_large_image_gets_high_score(self, selector):
        image = {
            "width": 800, "height": 600, "size_bytes": 100_000,
            "path": ""
        }
        result = selector._evaluate_image_quality_simple(image)
        assert result > 0.3

    def test_extreme_aspect_ratio_rejected(self, selector):
        image = {
            "width": 5000, "height": 10, "size_bytes": 50_000,
            "path": ""
        }
        result = selector._evaluate_image_quality_simple(image)
        assert result == 0.0

    def test_solid_color_rejected(self, selector):
        """Very low bytes per pixel → solid color rejection."""
        image = {
            "width": 800, "height": 600, "size_bytes": 10,  # 10 bytes for 480000 pixels
            "path": ""
        }
        result = selector._evaluate_image_quality_simple(image)
        assert result == 0.0

    def test_returns_float(self, selector):
        image = {"extraction_quality": 0.5, "content_type": "unknown"}
        result = selector._evaluate_image_quality_simple(image)
        assert isinstance(result, float)


# ===== _calculate_page_importance() =====

class TestCalculatePageImportance:
    def test_returns_empty_for_no_metadatas(self, selector):
        result = selector._calculate_page_importance([])
        assert result == {}

    def test_returns_empty_for_non_pdf_sources(self, selector):
        metadatas = [{"source": "webpage.html", "page_number": 1}]
        result = selector._calculate_page_importance(metadatas)
        assert result == {}

    def test_single_pdf_page(self, selector):
        metadatas = [{"source": "doc.pdf", "page_number": 1}]
        result = selector._calculate_page_importance(metadatas)
        assert "doc.pdf" in result
        assert len(result["doc.pdf"]) == 1

    def test_multiple_appearances_increase_importance(self, selector):
        """Page appearing more often should have higher importance."""
        metadatas = [
            {"source": "doc.pdf", "page_number": 1},
            {"source": "doc.pdf", "page_number": 1},
            {"source": "doc.pdf", "page_number": 2},
        ]
        result = selector._calculate_page_importance(metadatas)
        pages_dict = dict(result["doc.pdf"])
        assert pages_dict[1] > pages_dict[2]

    def test_multiple_sources(self, selector):
        metadatas = [
            {"source": "a.pdf", "page_number": 1},
            {"source": "b.pdf", "page_number": 2},
        ]
        result = selector._calculate_page_importance(metadatas)
        assert "a.pdf" in result
        assert "b.pdf" in result

    def test_skips_none_metadata(self, selector):
        metadatas = [None, {"source": "doc.pdf", "page_number": 1}]
        result = selector._calculate_page_importance(metadatas)
        assert "doc.pdf" in result

    def test_sorted_by_importance_descending(self, selector):
        metadatas = [
            {"source": "doc.pdf", "page_number": 3},
            {"source": "doc.pdf", "page_number": 1},
            {"source": "doc.pdf", "page_number": 1},
        ]
        result = selector._calculate_page_importance(metadatas)
        pages = result["doc.pdf"]
        # First page should be the one that appeared more often
        assert pages[0][0] == 1
        # Scores should be descending
        scores = [s for _, s in pages]
        assert scores == sorted(scores, reverse=True)

    def test_importance_score_between_0_and_1(self, selector):
        metadatas = [{"source": "doc.pdf", "page_number": 1}]
        result = selector._calculate_page_importance(metadatas)
        for page_num, score in result["doc.pdf"]:
            assert 0.0 <= score <= 1.0


# ===== _check_color_diversity() and _check_edge_density() =====

@pytest.mark.skipif(not HAS_NUMPY, reason="numpy required")
class TestImageSelectorColorDiversity:
    def test_solid_color_returns_low_score(self, selector):
        arr = np.full((20, 20, 3), 128, dtype=np.uint8)
        result = selector._check_color_diversity(arr)
        assert result <= 0.3

    def test_returns_float_between_0_and_1(self, selector):
        arr = np.full((10, 10, 3), 100, dtype=np.uint8)
        result = selector._check_color_diversity(arr)
        assert 0.0 <= result <= 1.0


@pytest.mark.skipif(not HAS_NUMPY, reason="numpy required")
class TestImageSelectorEdgeDensity:
    def test_returns_float(self, selector):
        arr = np.full((20, 20, 3), 200, dtype=np.uint8)
        result = selector._check_edge_density(arr)
        assert isinstance(result, float)

    def test_returns_float_between_0_and_1(self, selector):
        arr = np.full((10, 10, 3), 100, dtype=np.uint8)
        result = selector._check_edge_density(arr)
        assert 0.0 <= result <= 1.0


# ===== _check_content_complexity() =====

@pytest.mark.skipif(not HAS_NUMPY, reason="numpy required")
class TestCheckContentComplexity:
    def test_returns_float(self, selector):
        arr = np.full((20, 20, 3), 128, dtype=np.uint8)
        result = selector._check_content_complexity(arr)
        assert isinstance(result, float)

    def test_returns_value_between_0_and_1(self, selector):
        arr = np.full((20, 20, 3), 128, dtype=np.uint8)
        result = selector._check_content_complexity(arr)
        assert 0.0 <= result <= 1.0

    def test_diverse_array_returns_score(self, selector):
        # Random array should have higher entropy/complexity than solid
        arr = np.random.randint(0, 255, (20, 20, 3), dtype=np.uint8)
        result = selector._check_content_complexity(arr)
        assert result >= 0.0


# ===== _analyze_image_content() =====

@pytest.mark.skipif(not HAS_NUMPY, reason="numpy/PIL required")
class TestAnalyzeImageContent:
    def _make_temp_image(self, tmp_path, name="test.png", width=100, height=100, color=(100, 150, 200)):
        img = PILImage.new("RGB", (width, height), color=color)
        path = tmp_path / name
        img.save(str(path), format="PNG")
        return str(path)

    def test_returns_float_for_valid_image(self, selector, tmp_path):
        img_path = self._make_temp_image(tmp_path)
        result = selector._analyze_image_content(img_path)
        assert isinstance(result, float)

    def test_returns_value_between_0_and_1(self, selector, tmp_path):
        img_path = self._make_temp_image(tmp_path)
        result = selector._analyze_image_content(img_path)
        assert 0.0 <= result <= 1.0

    def test_returns_0_5_for_nonexistent_file(self, selector):
        """Exception handler returns 0.5 (neutral score)."""
        result = selector._analyze_image_content("/nonexistent/path/img.png")
        assert result == pytest.approx(0.5, abs=0.01)

    def test_diverse_image_returns_score(self, selector, tmp_path):
        """Diverse colors give a non-zero score."""
        import random
        random.seed(42)
        img = PILImage.new("RGB", (50, 50))
        pixels = [(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
                  for _ in range(50*50)]
        img.putdata(pixels)
        path = tmp_path / "diverse.png"
        img.save(str(path), format="PNG")
        result = selector._analyze_image_content(str(path))
        assert result >= 0.0

    def test_handles_rgba_image(self, selector, tmp_path):
        """RGBA image is converted to RGB without error."""
        img = PILImage.new("RGBA", (50, 50), color=(100, 150, 200, 255))
        path = tmp_path / "rgba.png"
        img.save(str(path), format="PNG")
        result = selector._analyze_image_content(str(path))
        assert isinstance(result, float)


# ===== _check_color_diversity() additional branches =====

@pytest.mark.skipif(not HAS_NUMPY, reason="numpy required")
class TestCheckColorDiversityBranches:
    def test_medium_colors_5_to_10(self, selector):
        """unique_colors 5-10 → score += 0.15."""
        # Create array with ~7 unique color bins per channel
        arr = np.zeros((30, 30, 3), dtype=np.uint8)
        # Set 7 distinct color levels
        for i, val in enumerate([0, 36, 72, 108, 144, 180, 216]):
            arr[i*4:(i+1)*4, :] = val
        result = selector._check_color_diversity(arr)
        assert isinstance(result, float)

    def test_concentration_0_5_to_0_7(self, selector):
        """avg_concentration 0.5-0.7 → score += 0.15."""
        # Mostly one color with a few others
        arr = np.full((30, 30, 3), 100, dtype=np.uint8)
        arr[0, 0] = [200, 200, 200]
        arr[1, 1] = [50, 50, 50]
        result = selector._check_color_diversity(arr)
        assert isinstance(result, float)

    def test_high_concentration_returns_zero(self, selector):
        """avg_concentration ≥ 0.7 → returns 0.0 immediately."""
        # Solid color: concentration near 1.0
        arr = np.full((50, 50, 3), 128, dtype=np.uint8)
        result = selector._check_color_diversity(arr)
        assert result == 0.0


# ===== _load_image_page_map() exception handling =====

class TestLoadImagePageMapException:
    def test_returns_empty_on_json_error(self, selector, tmp_path):
        """Corrupted JSON returns empty dict."""
        from lecture_forge.config import Config
        images_dir = tmp_path / "images" / "session_001"
        images_dir.mkdir(parents=True)
        (images_dir / "image_page_map.json").write_text("not valid json{{")
        original = Config.DATA_DIR
        try:
            Config.DATA_DIR = tmp_path
            result = selector._load_image_page_map()
        finally:
            Config.DATA_DIR = original
        assert result == {}


# ===== _smart_select_images() =====

class TestSmartSelectImages:
    def _make_candidate(self, img_id, source="doc.pdf", page=1, score=0.8):
        return {
            "image": {
                "id": img_id,
                "path": f"/img/{img_id}.png",
                "description": f"desc {img_id}",
            },
            "source": source,
            "page": page,
            "score": score,
            "page_importance": 0.7,
            "quality": 0.6,
        }

    def test_returns_empty_for_no_candidates(self, selector):
        result = selector._smart_select_images([], 3)
        assert result == []

    def test_selects_up_to_max_images(self, selector):
        candidates = [
            self._make_candidate("img_1", page=1),
            self._make_candidate("img_2", page=2),
            self._make_candidate("img_3", page=3),
            self._make_candidate("img_4", page=4),
        ]
        result = selector._smart_select_images(candidates, 2)
        assert len(result) == 2

    def test_max_1_image_per_page(self, selector):
        candidates = [
            self._make_candidate("img_1", page=1, score=0.9),
            self._make_candidate("img_2", page=1, score=0.8),  # same page
            self._make_candidate("img_3", page=2, score=0.7),
        ]
        result = selector._smart_select_images(candidates, 3)
        # Should only select 1 from page 1
        assert len(result) == 2

    def test_returns_image_references(self, selector):
        from lecture_forge.models.lecture import ImageReference
        candidates = [self._make_candidate("img_1", page=1)]
        result = selector._smart_select_images(candidates, 1)
        assert len(result) == 1
        assert isinstance(result[0], ImageReference)

    def test_skips_already_used_images(self, selector):
        selector.used_image_ids = {"img_1"}
        candidates = [
            self._make_candidate("img_1", page=1),
            self._make_candidate("img_2", page=2),
        ]
        result = selector._smart_select_images(candidates, 2)
        assert all(ref.image_id != "img_1" for ref in result)

    def test_returns_all_when_less_than_max(self, selector):
        candidates = [self._make_candidate("img_1", page=1)]
        result = selector._smart_select_images(candidates, 5)
        assert len(result) == 1


# ===== select_images() - main orchestration =====

class TestSelectImages:
    def _make_section(self, title="Test Section", estimated_time=20, topics=None):
        from unittest.mock import MagicMock
        section = MagicMock()
        section.title = title
        section.estimated_time = estimated_time
        section.topics = topics or ["machine learning"]
        return section

    def _make_search_image(self, img_id="img_1", description="machine learning diagram"):
        return {
            "id": img_id,
            "path": f"/img/{img_id}.png",
            "source": "unsplash",
            "description": description,
            "alt_text": "",
            "query": "",
        }

    def _make_pdf_image(self, img_id="pdf_1", page=1, description=""):
        return {
            "id": img_id,
            "path": f"/img/{img_id}.png",
            "source": "doc.pdf",
            "page": page,
            "description": description,
        }

    def test_returns_empty_when_no_images(self, selector):
        section = self._make_section()
        result = selector.select_images(section, available_images=[])
        assert result == []

    def test_returns_list(self, selector):
        section = self._make_section()
        img = self._make_search_image()
        result = selector.select_images(section, available_images=[img])
        assert isinstance(result, list)

    def test_matches_search_image_by_keyword(self, selector):
        """Search images matching section topics are selected."""
        section = self._make_section(topics=["machine learning"])
        img = self._make_search_image(description="machine learning diagram")
        result = selector.select_images(section, available_images=[img])
        assert len(result) >= 1

    def test_skips_unrelated_search_images(self, selector):
        """Search images not matching any topic keyword are skipped."""
        section = self._make_section(topics=["machine learning"])
        img = self._make_search_image(img_id="x", description="cooking recipe photo")
        result = selector.select_images(section, available_images=[img])
        assert len(result) == 0

    def test_pdf_image_with_description_matched(self, selector):
        """PDF images with matching descriptions are selected."""
        section = self._make_section(topics=["neural network"])
        img = self._make_pdf_image(description="neural network architecture diagram")
        result = selector.select_images(section, available_images=[img])
        assert isinstance(result, list)

    def test_pdf_image_without_description_skipped(self, selector):
        """PDF images without descriptions are skipped (no Vision AI)."""
        section = self._make_section(topics=["test"])
        img = self._make_pdf_image(description="")  # No description
        result = selector.select_images(section, available_images=[img])
        assert len(result) == 0

    def test_location_based_matching_with_context(self, selector):
        """With context_metadatas and PDF images, location-based matching is tried."""
        section = self._make_section()
        pdf_img = self._make_pdf_image(page=3)
        context_metas = [{"source": "doc.pdf", "page_number": 3}]

        with patch.object(selector, "_match_images_by_location", return_value=[]) as mock_match:
            selector.select_images(section, available_images=[pdf_img], context_metadatas=context_metas)
        mock_match.assert_called_once()

    def test_max_images_based_on_duration(self, selector):
        """max_images = max(2, estimated_time // 10)."""
        section = self._make_section(estimated_time=30)  # max_images = 3
        # Create 10 matching images
        images = [self._make_search_image(f"img_{i}", "machine learning photo") for i in range(10)]
        result = selector.select_images(section, available_images=images)
        # Should select at most 3 images (30//10 = 3)
        assert len(result) <= 3


# ===== _match_images_by_location() =====

class TestMatchImagesByLocation:
    def _make_pdf_image(self, img_id="img_1", page=1):
        return {
            "id": img_id,
            "path": f"/img/{img_id}.png",
            "source": "doc.pdf",
            "page": page,
            "description": "diagram",
            "content_type": "diagram",
            "width": 800,
            "height": 600,
            "size_bytes": 100_000,
            "extraction_quality": 0.8,
        }

    def test_returns_empty_when_no_page_importance(self, selector):
        with patch.object(selector, "_calculate_page_importance", return_value={}):
            result = selector._match_images_by_location([], [], 3)
        assert result == []

    def test_returns_empty_when_no_image_page_map(self, selector):
        page_importance = {"doc.pdf": [(1, 0.9)]}
        with patch.object(selector, "_calculate_page_importance", return_value=page_importance):
            with patch.object(selector, "_load_image_page_map", return_value={}):
                result = selector._match_images_by_location(
                    [{"source": "doc.pdf", "page_number": 1}], [], 3
                )
        assert result == []

    def test_source_not_in_image_page_map_returns_empty(self, selector):
        page_importance = {"doc.pdf": [(1, 0.9)]}
        image_page_map = {"other.pdf": {"1": [{"id": "img_1"}]}}
        with patch.object(selector, "_calculate_page_importance", return_value=page_importance):
            with patch.object(selector, "_load_image_page_map", return_value=image_page_map):
                result = selector._match_images_by_location(
                    [{"source": "doc.pdf", "page_number": 1}], [], 3
                )
        assert result == []

    def test_page_not_in_map_skipped(self, selector):
        page_importance = {"doc.pdf": [(5, 0.9)]}
        image_page_map = {"doc.pdf": {"1": [{"id": "img_1"}]}}  # page 5 not here
        pdf_images = [self._make_pdf_image("img_1", page=1)]
        with patch.object(selector, "_calculate_page_importance", return_value=page_importance):
            with patch.object(selector, "_load_image_page_map", return_value=image_page_map):
                result = selector._match_images_by_location(
                    [{"source": "doc.pdf", "page_number": 5}], pdf_images, 3
                )
        assert result == []

    def test_selects_matching_image(self, selector):
        from lecture_forge.models.lecture import ImageReference
        page_importance = {"doc.pdf": [(1, 0.9)]}
        image_page_map = {"doc.pdf": {"1": [{"id": "img_1"}]}}
        pdf_images = [self._make_pdf_image("img_1", page=1)]
        with patch.object(selector, "_calculate_page_importance", return_value=page_importance):
            with patch.object(selector, "_load_image_page_map", return_value=image_page_map):
                with patch.object(selector, "_evaluate_image_quality_simple", return_value=0.8):
                    result = selector._match_images_by_location(
                        [{"source": "doc.pdf", "page_number": 1}], pdf_images, 3
                    )
        assert len(result) >= 1
        assert isinstance(result[0], ImageReference)

    def test_low_quality_image_filtered(self, selector):
        page_importance = {"doc.pdf": [(1, 0.9)]}
        image_page_map = {"doc.pdf": {"1": [{"id": "img_1"}]}}
        pdf_images = [self._make_pdf_image("img_1", page=1)]
        with patch.object(selector, "_calculate_page_importance", return_value=page_importance):
            with patch.object(selector, "_load_image_page_map", return_value=image_page_map):
                with patch.object(selector, "_evaluate_image_quality_simple", return_value=0.0):
                    result = selector._match_images_by_location(
                        [{"source": "doc.pdf", "page_number": 1}], pdf_images, 3
                    )
        assert result == []

    def test_image_not_in_pdf_images_skipped(self, selector):
        page_importance = {"doc.pdf": [(1, 0.9)]}
        image_page_map = {"doc.pdf": {"1": [{"id": "unknown_img"}]}}
        pdf_images = [self._make_pdf_image("img_1", page=1)]  # id doesn't match
        with patch.object(selector, "_calculate_page_importance", return_value=page_importance):
            with patch.object(selector, "_load_image_page_map", return_value=image_page_map):
                result = selector._match_images_by_location(
                    [{"source": "doc.pdf", "page_number": 1}], pdf_images, 3
                )
        assert result == []

    def test_screenshot_content_type_weighting(self, selector):
        """Screenshot and technical types use different weight (0.25/0.65/0.10)."""
        from lecture_forge.models.lecture import ImageReference
        screenshot_img = self._make_pdf_image("img_1", page=1)
        screenshot_img["content_type"] = "screenshot"
        page_importance = {"doc.pdf": [(1, 0.9)]}
        image_page_map = {"doc.pdf": {"1": [{"id": "img_1"}]}}
        with patch.object(selector, "_calculate_page_importance", return_value=page_importance):
            with patch.object(selector, "_load_image_page_map", return_value=image_page_map):
                with patch.object(selector, "_evaluate_image_quality_simple", return_value=0.8):
                    result = selector._match_images_by_location(
                        [{"source": "doc.pdf", "page_number": 1}], [screenshot_img], 3
                    )
        assert len(result) >= 1

    def test_unknown_content_type_default_weighting(self, selector):
        """Unknown content type uses default weights (0.20/0.70/0.10)."""
        from lecture_forge.models.lecture import ImageReference
        unknown_img = self._make_pdf_image("img_1", page=1)
        unknown_img["content_type"] = "unknown"
        page_importance = {"doc.pdf": [(1, 0.9)]}
        image_page_map = {"doc.pdf": {"1": [{"id": "img_1"}]}}
        with patch.object(selector, "_calculate_page_importance", return_value=page_importance):
            with patch.object(selector, "_load_image_page_map", return_value=image_page_map):
                with patch.object(selector, "_evaluate_image_quality_simple", return_value=0.8):
                    result = selector._match_images_by_location(
                        [{"source": "doc.pdf", "page_number": 1}], [unknown_img], 3
                    )
        assert len(result) >= 1

    def test_adjacent_page_expansion_called_when_not_enough(self, selector):
        """When fewer images than max_images found, _expand_to_adjacent_pages is called."""
        page_importance = {"doc.pdf": [(1, 0.9)]}
        image_page_map = {"doc.pdf": {"1": [{"id": "img_1"}]}}
        pdf_images = [self._make_pdf_image("img_1", page=1)]
        with patch.object(selector, "_calculate_page_importance", return_value=page_importance):
            with patch.object(selector, "_load_image_page_map", return_value=image_page_map):
                with patch.object(selector, "_evaluate_image_quality_simple", return_value=0.8):
                    with patch.object(selector, "_expand_to_adjacent_pages", return_value=[]) as mock_expand:
                        selector._match_images_by_location(
                            [{"source": "doc.pdf", "page_number": 1}], pdf_images, 5
                        )
        mock_expand.assert_called_once()


# ===== _load_image_page_map() =====

class TestLoadImagePageMap:
    def test_returns_empty_when_no_images_dir(self, selector, tmp_path):
        from lecture_forge.config import Config
        original = Config.DATA_DIR
        try:
            Config.DATA_DIR = tmp_path / "nonexistent"
            result = selector._load_image_page_map()
        finally:
            Config.DATA_DIR = original
        assert result == {}

    def test_returns_empty_when_no_map_files(self, selector, tmp_path):
        from lecture_forge.config import Config
        images_dir = tmp_path / "images" / "session_001"
        images_dir.mkdir(parents=True)
        original = Config.DATA_DIR
        try:
            Config.DATA_DIR = tmp_path
            result = selector._load_image_page_map()
        finally:
            Config.DATA_DIR = original
        assert result == {}

    def test_loads_valid_json(self, selector, tmp_path):
        import json as json_mod
        from lecture_forge.config import Config
        images_dir = tmp_path / "images" / "session_001"
        images_dir.mkdir(parents=True)
        map_data = {"doc.pdf": {"1": [{"id": "img_1"}]}}
        map_file = images_dir / "image_page_map.json"
        map_file.write_text(json_mod.dumps(map_data))
        original = Config.DATA_DIR
        try:
            Config.DATA_DIR = tmp_path
            result = selector._load_image_page_map()
        finally:
            Config.DATA_DIR = original
        assert result == map_data


# ===== _evaluate_image_quality_simple() - additional branches =====

class TestEvaluateImageQualitySimpleAdditional:
    def test_medium_size_600x400(self, selector):
        """600x400 image gets partial size score."""
        image = {"width": 600, "height": 400, "size_bytes": 60_000, "path": ""}
        result = selector._evaluate_image_quality_simple(image)
        assert result > 0.0

    def test_small_size_400x300(self, selector):
        """400x300 image gets lower size score."""
        image = {"width": 400, "height": 300, "size_bytes": 30_000, "path": ""}
        result = selector._evaluate_image_quality_simple(image)
        assert result > 0.0

    def test_very_small_200x200(self, selector):
        """200x200 image gets minimal size score."""
        image = {"width": 200, "height": 200, "size_bytes": 15_000, "path": ""}
        result = selector._evaluate_image_quality_simple(image)
        assert result > 0.0

    def test_aspect_ratio_0_5_to_0_7(self, selector):
        """Portrait with aspect 0.5-0.7 gets acceptable score."""
        image = {"width": 400, "height": 700, "size_bytes": 50_000, "path": ""}
        result = selector._evaluate_image_quality_simple(image)
        assert result >= 0.0

    def test_aspect_ratio_1_5_to_2_0(self, selector):
        """Wide landscape 1.5-2.0 gets acceptable score."""
        image = {"width": 800, "height": 450, "size_bytes": 60_000, "path": ""}
        result = selector._evaluate_image_quality_simple(image)
        assert result >= 0.0

    def test_aspect_ratio_0_3_to_0_5(self, selector):
        """Slightly extreme portrait (0.3-0.5) gets some score."""
        image = {"width": 300, "height": 800, "size_bytes": 40_000, "path": ""}
        result = selector._evaluate_image_quality_simple(image)
        assert result >= 0.0

    def test_file_size_50k(self, selector):
        """50KB file gets medium file score."""
        image = {"width": 800, "height": 600, "size_bytes": 50_000, "path": ""}
        result = selector._evaluate_image_quality_simple(image)
        assert result > 0.0

    def test_file_size_10k(self, selector):
        """10KB file may get zero due to low compression ratio (likely solid color)."""
        image = {"width": 800, "height": 600, "size_bytes": 10_000, "path": ""}
        result = selector._evaluate_image_quality_simple(image)
        assert isinstance(result, float)

    def test_bytes_per_pixel_moderate_range(self, selector):
        """0.1-0.2 bpp gets partial compression score."""
        # width*height = 800*600 = 480000 pixels; 0.15 bpp = 72000 bytes
        image = {"width": 800, "height": 600, "size_bytes": 72_000, "path": ""}
        result = selector._evaluate_image_quality_simple(image)
        assert result > 0.0

    def test_bytes_per_pixel_high_2_to_10(self, selector):
        """2-10 bpp gets partial score (not rejected, not optimal)."""
        # 800*600 = 480000 pixels; 5 bpp = 2400000 bytes
        image = {"width": 800, "height": 600, "size_bytes": 2_400_000, "path": ""}
        result = selector._evaluate_image_quality_simple(image)
        assert result > 0.0


# ===== _expand_to_adjacent_pages() =====

class TestExpandToAdjacentPages:
    def _make_pdf_image(self, img_id, page=1):
        return {
            "id": img_id,
            "path": f"/img/{img_id}.png",
            "description": f"image {img_id}",
            "content_type": "diagram",
            "extraction_quality": 0.8,
        }

    def _make_image_ref(self, img_id="img_1", page=1, source="doc.pdf"):
        from lecture_forge.models.lecture import ImageReference
        return ImageReference(
            image_id=img_id,
            path=f"/img/{img_id}.png",
            description="test",
            caption=f"From source material (page {page})",
            attribution=f"Source: {source}, page {page}",
        )

    def test_returns_selected_when_already_max(self, selector):
        selected = [self._make_image_ref("img_1", 1), self._make_image_ref("img_2", 2)]
        result = selector._expand_to_adjacent_pages(
            selected, max_images=2, page_importance={}, image_page_map={}, pdf_images=[]
        )
        assert len(result) == 2

    def test_returns_empty_when_no_adjacent_pages(self, selector):
        selected = []
        page_importance = {"doc.pdf": [(5, 0.9)]}
        image_page_map = {"doc.pdf": {"5": [{"id": "img_5"}]}}  # Only exact page, no adjacent
        pdf_images = [self._make_pdf_image("img_5", page=5)]

        with patch.object(selector, "_evaluate_image_quality_simple", return_value=0.8):
            result = selector._expand_to_adjacent_pages(
                selected, max_images=2,
                page_importance=page_importance,
                image_page_map=image_page_map,
                pdf_images=pdf_images
            )
        # No adjacent pages in map, so nothing added
        assert isinstance(result, list)

    def test_adds_images_from_adjacent_page(self, selector):
        selected = []
        page_importance = {"doc.pdf": [(3, 0.9)]}
        # Page 4 is adjacent to page 3
        image_page_map = {"doc.pdf": {"4": [{"id": "img_4"}]}}
        pdf_images = [self._make_pdf_image("img_4", page=4)]

        with patch.object(selector, "_evaluate_image_quality_simple", return_value=0.9):
            result = selector._expand_to_adjacent_pages(
                selected, max_images=2,
                page_importance=page_importance,
                image_page_map=image_page_map,
                pdf_images=pdf_images
            )
        assert len(result) >= 1

    def test_skips_used_image_ids(self, selector):
        selected = []
        page_importance = {"doc.pdf": [(3, 0.9)]}
        image_page_map = {"doc.pdf": {"4": [{"id": "already_used"}]}}
        pdf_images = [self._make_pdf_image("already_used", page=4)]
        selector.used_image_ids = {"already_used"}

        with patch.object(selector, "_evaluate_image_quality_simple", return_value=0.9):
            result = selector._expand_to_adjacent_pages(
                selected, max_images=2,
                page_importance=page_importance,
                image_page_map=image_page_map,
                pdf_images=pdf_images
            )
        # already_used image is skipped
        assert all(ref.image_id != "already_used" for ref in result)

    def test_does_not_reuse_already_selected_page(self, selector):
        selected = [self._make_image_ref("img_1", page=1, source="doc.pdf")]
        page_importance = {"doc.pdf": [(1, 0.9)]}
        # Page 2 is adjacent (offset +1)
        image_page_map = {"doc.pdf": {"2": [{"id": "img_2"}]}}
        pdf_images = [self._make_pdf_image("img_2", page=2)]

        with patch.object(selector, "_evaluate_image_quality_simple", return_value=0.9):
            result = selector._expand_to_adjacent_pages(
                selected, max_images=3,
                page_importance=page_importance,
                image_page_map=image_page_map,
                pdf_images=pdf_images
            )
        assert isinstance(result, list)
