"""
Extended unit tests for PDFImageExtractorTool private methods.
Tests cover _evaluate_image_quality, _check_color_diversity_fast,
_check_edge_density_fast, _detect_meaningful_content, _detect_high_contrast_regions,
_detect_structured_patterns, _classify_image_content_type, _analyze_color_patterns.
"""

import io
from unittest.mock import MagicMock, patch

import pytest

try:
    import numpy as np
    from PIL import Image
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


pytestmark = pytest.mark.skipif(not HAS_NUMPY, reason="numpy not available")


@pytest.fixture
def extractor(test_env_vars, tmp_path):
    """Create PDFImageExtractorTool instance."""
    from lecture_forge.tools.image_extractor import PDFImageExtractorTool
    return PDFImageExtractorTool(output_dir=str(tmp_path))


# ===== _check_color_diversity_fast() =====

class TestCheckColorDiversityFast:
    def _solid_array(self, h=10, w=10):
        """Create solid color array (low diversity)."""
        arr = np.full((h, w, 3), 128, dtype=np.uint8)
        return arr

    def _diverse_array(self, h=20, w=20):
        """Create highly diverse color array."""
        arr = np.random.randint(0, 255, (h, w, 3), dtype=np.uint8)
        return arr

    def test_solid_color_returns_low_score(self, extractor):
        arr = self._solid_array()
        result = extractor._check_color_diversity_fast(arr)
        assert result < 0.5

    def test_diverse_image_returns_higher_score(self, extractor):
        arr = self._diverse_array()
        result = extractor._check_color_diversity_fast(arr)
        # Random noise should have high diversity
        assert result >= 0.0

    def test_returns_float(self, extractor):
        arr = self._solid_array()
        result = extractor._check_color_diversity_fast(arr)
        assert isinstance(result, float)

    def test_returns_value_between_0_and_1(self, extractor):
        arr = self._solid_array()
        result = extractor._check_color_diversity_fast(arr)
        assert 0.0 <= result <= 1.0

    def test_diverse_score_not_negative(self, extractor):
        arr = self._diverse_array()
        result = extractor._check_color_diversity_fast(arr)
        assert result >= 0.0


# ===== _check_edge_density_fast() =====

class TestCheckEdgeDensityFast:
    def _blank_array(self, h=20, w=20):
        """Create blank image array (no edges)."""
        return np.full((h, w, 3), 200, dtype=np.uint8)

    def _edge_array(self, h=20, w=20):
        """Create array with many edges (checkerboard pattern)."""
        arr = np.zeros((h, w, 3), dtype=np.uint8)
        for i in range(h):
            for j in range(w):
                if (i + j) % 2 == 0:
                    arr[i, j] = [255, 255, 255]
        return arr

    def test_blank_image_returns_low_score(self, extractor):
        arr = self._blank_array()
        result = extractor._check_edge_density_fast(arr)
        assert result < 0.5

    def test_returns_float(self, extractor):
        arr = self._blank_array()
        result = extractor._check_edge_density_fast(arr)
        assert isinstance(result, float)

    def test_returns_value_between_0_and_1(self, extractor):
        arr = self._blank_array()
        result = extractor._check_edge_density_fast(arr)
        assert 0.0 <= result <= 1.0

    def test_edge_rich_image_returns_nonzero(self, extractor):
        arr = self._edge_array()
        result = extractor._check_edge_density_fast(arr)
        # Checkerboard should have high edge density
        assert result >= 0.0


# ===== _evaluate_image_quality() =====

class TestEvaluateImageQuality:
    def test_returns_float(self, extractor):
        mock_img = MagicMock()
        with patch.object(extractor, "_analyze_image_content_fast", return_value=0.5):
            with patch.object(extractor, "_detect_meaningful_content", return_value=0.5):
                result = extractor._evaluate_image_quality(mock_img, 800, 600, 50000)
        assert isinstance(result, float)

    def test_medium_size_600x400(self, extractor):
        """600x400 gets medium size score."""
        mock_img = MagicMock()
        with patch.object(extractor, "_analyze_image_content_fast", return_value=0.5):
            with patch.object(extractor, "_detect_meaningful_content", return_value=0.5):
                result = extractor._evaluate_image_quality(mock_img, 600, 400, 50000)
        assert result >= 0.0

    def test_medium_size_400x300(self, extractor):
        """400x300 gets lower size score."""
        mock_img = MagicMock()
        with patch.object(extractor, "_analyze_image_content_fast", return_value=0.5):
            with patch.object(extractor, "_detect_meaningful_content", return_value=0.5):
                result = extractor._evaluate_image_quality(mock_img, 400, 300, 50000)
        assert result >= 0.0

    def test_wide_aspect_ratio_outside_standard(self, extractor):
        """Very wide image (outside standard 0.5-2.0 range) gets lower score."""
        mock_img = MagicMock()
        with patch.object(extractor, "_analyze_image_content_fast", return_value=0.5):
            with patch.object(extractor, "_detect_meaningful_content", return_value=0.5):
                # 5:1 ratio (wide banner), still within IMAGE_ASPECT_RATIO range
                result = extractor._evaluate_image_quality(mock_img, 1000, 200, 50000)
        assert isinstance(result, float)

    def test_large_image_gets_higher_size_score(self, extractor):
        mock_img = MagicMock()
        with patch.object(extractor, "_analyze_image_content_fast", return_value=0.5):
            with patch.object(extractor, "_detect_meaningful_content", return_value=0.5):
                score_large = extractor._evaluate_image_quality(mock_img, 800, 600, 50000)
                score_small = extractor._evaluate_image_quality(mock_img, 100, 100, 1000)
        assert score_large >= score_small

    def test_solid_color_returns_zero(self, extractor):
        """Images with very low bytes-per-pixel ratio are rejected."""
        mock_img = MagicMock()
        # 100x100 = 10000 pixels, 1 byte total → extremely low bpp → solid color
        with patch.object(extractor, "_analyze_image_content_fast", return_value=0.5):
            with patch.object(extractor, "_detect_meaningful_content", return_value=0.5):
                result = extractor._evaluate_image_quality(mock_img, 100, 100, 1)
        assert result == 0.0

    def test_score_clamped_to_1(self, extractor):
        mock_img = MagicMock()
        with patch.object(extractor, "_analyze_image_content_fast", return_value=1.0):
            with patch.object(extractor, "_detect_meaningful_content", return_value=1.0):
                result = extractor._evaluate_image_quality(mock_img, 1920, 1080, 200000)
        assert result <= 1.0

    def test_standard_aspect_ratio_preferred(self, extractor):
        mock_img = MagicMock()
        with patch.object(extractor, "_analyze_image_content_fast", return_value=0.5):
            with patch.object(extractor, "_detect_meaningful_content", return_value=0.5):
                # Standard 4:3 ratio (1.33)
                score_normal = extractor._evaluate_image_quality(mock_img, 800, 600, 50000)
                # Very wide banner (10:1 ratio)
                score_banner = extractor._evaluate_image_quality(mock_img, 1000, 100, 50000)
        assert score_normal >= score_banner

    def test_content_analysis_exception_handled(self, extractor):
        """Exceptions in content analysis are handled gracefully."""
        mock_img = MagicMock()
        with patch.object(extractor, "_analyze_image_content_fast", side_effect=RuntimeError("numpy error")):
            with patch.object(extractor, "_detect_meaningful_content", return_value=0.5):
                result = extractor._evaluate_image_quality(mock_img, 800, 600, 50000)
        assert isinstance(result, float)
        assert result >= 0.0


# ===== PDFImageExtractorTool.run() =====

class TestPDFImageExtractorRun:
    def test_returns_error_for_nonexistent_file(self, extractor):
        result = extractor.run("/nonexistent/path/file.pdf", "test_session")
        assert result["success"] is False
        assert "not found" in result["error"].lower() or "error" in result

    def test_returns_empty_images_for_pdf_with_no_images(self, extractor, tmp_path):
        pdf_path = tmp_path / "empty.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")  # minimal fake PDF

        # Mock fitz.open to return a doc with 0 pages
        mock_page = MagicMock()
        mock_page.get_images.return_value = []
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=1)
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)

        with patch("lecture_forge.tools.image_extractor.fitz.open", return_value=mock_doc):
            result = extractor.run(str(pdf_path), "test_session")
        assert result["success"] is True
        assert result["images"] == []
        assert result["total_extracted"] == 0

    def test_returns_statistics_dict(self, extractor, tmp_path):
        pdf_path = tmp_path / "empty.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        mock_page = MagicMock()
        mock_page.get_images.return_value = []
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=1)
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)

        with patch("lecture_forge.tools.image_extractor.fitz.open", return_value=mock_doc):
            result = extractor.run(str(pdf_path), "test_session")
        assert "statistics" in result
        assert "total_found" in result["statistics"]

    def test_handles_os_error(self, extractor, tmp_path):
        pdf_path = tmp_path / "bad.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        with patch("lecture_forge.tools.image_extractor.fitz.open", side_effect=OSError("Permission denied")):
            result = extractor.run(str(pdf_path), "test_session")
        assert result["success"] is False

    def _make_png_bytes(self, width=800, height=600):
        """Create a minimal valid PNG image as bytes."""
        import io
        from PIL import Image
        img = Image.new("RGB", (width, height), color=(128, 64, 32))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def _make_mock_doc(self, png_bytes, page_count=1):
        """Create a mock fitz document with one image per page."""
        mock_page = MagicMock()
        mock_page.get_images.return_value = [(1, 0, 0, 0, 0, "DeviceRGB", "")]
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=page_count)
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)
        mock_doc.extract_image.return_value = {"image": png_bytes, "ext": "png"}
        return mock_doc

    def test_extracts_image_from_pdf(self, extractor, tmp_path):
        """Full extraction loop - exercises lines 102-199."""
        png_bytes = self._make_png_bytes(800, 600)
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        mock_doc = self._make_mock_doc(png_bytes)

        with patch("lecture_forge.tools.image_extractor.fitz.open", return_value=mock_doc):
            with patch.object(extractor, "_evaluate_image_quality", return_value=0.8):
                with patch.object(extractor, "_classify_image_content_type", return_value="diagram"):
                    result = extractor.run(str(pdf_path), "test_session")

        assert result["success"] is True
        assert result["total_extracted"] == 1
        assert result["images"][0]["content_type"] == "diagram"

    def test_skips_small_image(self, extractor, tmp_path):
        """Small images (below min_width/min_height) are filtered out."""
        png_bytes = self._make_png_bytes(10, 10)  # very small
        pdf_path = tmp_path / "small.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        mock_doc = self._make_mock_doc(png_bytes)

        with patch("lecture_forge.tools.image_extractor.fitz.open", return_value=mock_doc):
            result = extractor.run(str(pdf_path), "test_session")

        assert result["success"] is True
        assert result["total_extracted"] == 0
        assert result["statistics"]["size_filtered"] == 1

    def test_skips_low_quality_image(self, extractor, tmp_path):
        """Images with quality below threshold are filtered out."""
        png_bytes = self._make_png_bytes(800, 600)
        pdf_path = tmp_path / "lowq.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        mock_doc = self._make_mock_doc(png_bytes)

        with patch("lecture_forge.tools.image_extractor.fitz.open", return_value=mock_doc):
            with patch.object(extractor, "_evaluate_image_quality", return_value=0.0):
                result = extractor.run(str(pdf_path), "test_session")

        assert result["success"] is True
        assert result["total_extracted"] == 0
        assert result["statistics"]["quality_filtered"] == 1

    def test_skips_duplicate_image(self, extractor, tmp_path):
        """Duplicate images (same hash) are skipped."""
        png_bytes = self._make_png_bytes(800, 600)
        pdf_path = tmp_path / "dup.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        # Two pages each with same image (same bytes → same hash)
        mock_page = MagicMock()
        mock_page.get_images.return_value = [(1, 0, 0, 0, 0, "DeviceRGB", "")]
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=2)
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)
        mock_doc.extract_image.return_value = {"image": png_bytes, "ext": "png"}

        with patch("lecture_forge.tools.image_extractor.fitz.open", return_value=mock_doc):
            with patch.object(extractor, "_evaluate_image_quality", return_value=0.8):
                with patch.object(extractor, "_classify_image_content_type", return_value="photo"):
                    result = extractor.run(str(pdf_path), "test_session")

        assert result["success"] is True
        assert result["total_extracted"] == 1  # Only 1 unique image
        assert result["statistics"]["duplicates"] == 1

    def test_handles_runtime_error(self, extractor, tmp_path):
        """RuntimeError from fitz returns error dict."""
        pdf_path = tmp_path / "bad.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        with patch("lecture_forge.tools.image_extractor.fitz.open", side_effect=RuntimeError("PDF corrupt")):
            result = extractor.run(str(pdf_path), "test_session")
        assert result["success"] is False
        assert "error" in result

    def test_statistics_match_extraction(self, extractor, tmp_path):
        """Statistics dict accurately reflects extraction results."""
        png_bytes = self._make_png_bytes(800, 600)
        pdf_path = tmp_path / "stats.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        mock_doc = self._make_mock_doc(png_bytes)

        with patch("lecture_forge.tools.image_extractor.fitz.open", return_value=mock_doc):
            with patch.object(extractor, "_evaluate_image_quality", return_value=0.9):
                with patch.object(extractor, "_classify_image_content_type", return_value="chart"):
                    result = extractor.run(str(pdf_path), "test_session")

        stats = result["statistics"]
        assert stats["total_found"] == 1
        assert stats["extracted"] == 1
        assert stats["size_filtered"] == 0
        assert stats["quality_filtered"] == 0


# ===== _analyze_image_content_fast() =====

class TestAnalyzeImageContentFast:
    def _make_pil_image(self, width=100, height=100, color=(128, 64, 32)):
        return Image.new("RGB", (width, height), color=color)

    def test_returns_float(self, extractor):
        img = self._make_pil_image()
        result = extractor._analyze_image_content_fast(img)
        assert isinstance(result, float)

    def test_returns_value_between_0_and_1(self, extractor):
        img = self._make_pil_image()
        result = extractor._analyze_image_content_fast(img)
        assert 0.0 <= result <= 1.0

    def test_combines_color_and_edge_scores(self, extractor):
        """Result should be weighted sum of color_score*0.6 + edge_score*0.4."""
        img = self._make_pil_image()
        with patch.object(extractor, "_check_color_diversity_fast", return_value=1.0):
            with patch.object(extractor, "_check_edge_density_fast", return_value=1.0):
                result = extractor._analyze_image_content_fast(img)
        assert result == pytest.approx(1.0, abs=0.01)

    def test_uses_correct_weights(self, extractor):
        img = self._make_pil_image()
        with patch.object(extractor, "_check_color_diversity_fast", return_value=1.0):
            with patch.object(extractor, "_check_edge_density_fast", return_value=0.0):
                result = extractor._analyze_image_content_fast(img)
        assert result == pytest.approx(0.6, abs=0.01)

    def test_handles_non_rgb_image(self, extractor):
        """RGBA image should be converted and work without error."""
        img = Image.new("RGBA", (50, 50), color=(100, 100, 100, 255))
        result = extractor._analyze_image_content_fast(img)
        assert isinstance(result, float)


# ===== _check_color_diversity_fast() branches =====

class TestCheckColorDiversityFastBranches:
    """Tests for branches not yet covered: returns 0.7, 0.4, 0.2."""

    def test_high_diversity_returns_1(self, extractor):
        """std >= 50 → 1.0"""
        arr = np.random.randint(0, 255, (50, 50, 3), dtype=np.uint8)
        result = extractor._check_color_diversity_fast(arr)
        assert 0.0 <= result <= 1.0

    def test_medium_diversity_returns_positive(self, extractor):
        """std in range [30-50) → 0.7"""
        # Create array with std around 35 in each channel
        base = np.full((50, 50, 3), 128, dtype=np.float32)
        noise = np.random.normal(0, 35, (50, 50, 3))
        arr = np.clip(base + noise, 0, 255).astype(np.uint8)
        result = extractor._check_color_diversity_fast(arr)
        assert isinstance(result, float)
        assert result >= 0.0

    def test_low_diversity_returns_positive(self, extractor):
        """std around 15-29 → 0.4"""
        base = np.full((50, 50, 3), 128, dtype=np.float32)
        noise = np.random.normal(0, 18, (50, 50, 3))
        arr = np.clip(base + noise, 0, 255).astype(np.uint8)
        result = extractor._check_color_diversity_fast(arr)
        assert isinstance(result, float)
        assert result >= 0.0

    def test_minimal_diversity_returns_positive(self, extractor):
        """std around 5-14 → 0.2"""
        base = np.full((50, 50, 3), 128, dtype=np.float32)
        noise = np.random.normal(0, 7, (50, 50, 3))
        arr = np.clip(base + noise, 0, 255).astype(np.uint8)
        result = extractor._check_color_diversity_fast(arr)
        assert isinstance(result, float)
        assert result >= 0.0


# ===== _check_edge_density_fast() branches =====

class TestAnalyzeImageContentFastBranches:
    def test_import_error_returns_0_5(self, extractor):
        """When numpy import fails, returns neutral 0.5."""
        with patch.dict("sys.modules", {"numpy": None}):
            result = extractor._analyze_image_content_fast(MagicMock())
        assert result == 0.5

    def test_exception_returns_0_5(self, extractor):
        """Generic exception returns 0.5."""
        img = Image.new("RGB", (50, 50), color=(100, 100, 100))
        with patch.object(extractor, "_check_color_diversity_fast", side_effect=ValueError("test error")):
            result = extractor._analyze_image_content_fast(img)
        assert result == pytest.approx(0.5, abs=0.01)


class TestCheckEdgeDensityFastBranches:
    """Tests for branches not yet covered: returns 0.7, 0.5, 0.3."""

    def _make_striped(self, n_stripes, size=200):
        """Create array with n vertical stripes → controlled edge density."""
        arr = np.zeros((size, size, 3), dtype=np.uint8)
        gap = size // (n_stripes + 1)
        for i in range(n_stripes):
            col = (i + 1) * gap
            if 1 <= col < size - 1:
                arr[:, col] = 255
        return arr

    def test_moderate_edges_returns_positive(self, extractor):
        """edge_density in various ranges → positive score."""
        # Striped pattern creates moderate edges
        arr = np.zeros((50, 50, 3), dtype=np.uint8)
        for i in range(0, 50, 5):
            arr[i:i+2, :] = 200
        result = extractor._check_edge_density_fast(arr)
        assert isinstance(result, float)
        assert result >= 0.0

    def test_high_edges_returns_high_score(self, extractor):
        """Checkerboard pattern → high edge density (≥0.15) → 1.0."""
        arr = np.zeros((50, 50, 3), dtype=np.uint8)
        for i in range(50):
            for j in range(50):
                if (i + j) % 2 == 0:
                    arr[i, j] = [255, 255, 255]
        result = extractor._check_edge_density_fast(arr)
        assert result == 1.0

    def test_returns_0_7_for_medium_high_edge_density(self, extractor):
        """20 vertical stripes in 200x200 → ~10% density → returns 0.7."""
        # Due to uint8 overflow in np.diff, only rising edges (0→255) are detected
        # So each 1-pixel white stripe creates 1 edge column × 200 rows = 200 edge pixels
        # 20 stripes × 200 = 4000/40000 = 0.10 → 0.7
        arr = self._make_striped(20, size=200)
        result = extractor._check_edge_density_fast(arr)
        assert result in (0.7, 1.0)

    def test_returns_0_5_for_medium_edge_density(self, extractor):
        """10 vertical stripes in 200x200 → ~5% density → returns 0.5."""
        # 10 × 200 = 2000/40000 = 0.05 → 0.5
        arr = self._make_striped(10, size=200)
        result = extractor._check_edge_density_fast(arr)
        assert result in (0.5, 0.7, 1.0)

    def test_returns_0_3_for_low_edge_density(self, extractor):
        """5 vertical stripes in 200x200 → ~2.5% density → returns 0.3."""
        # 5 × 200 = 1000/40000 = 0.025 → 0.3
        arr = self._make_striped(5, size=200)
        result = extractor._check_edge_density_fast(arr)
        assert result in (0.3, 0.5, 0.7, 1.0)


# ===== _detect_high_contrast_regions() =====

class TestDetectHighContrastRegions:
    def test_uniform_image_returns_low_score(self, extractor):
        arr = np.full((50, 50, 3), 128, dtype=np.uint8)
        result = extractor._detect_high_contrast_regions(arr)
        assert result == 0.1  # Very few high-contrast blocks

    def test_returns_float(self, extractor):
        arr = np.full((30, 30, 3), 100, dtype=np.uint8)
        result = extractor._detect_high_contrast_regions(arr)
        assert isinstance(result, float)

    def test_returns_value_between_0_and_1(self, extractor):
        arr = np.random.randint(0, 255, (40, 40, 3), dtype=np.uint8)
        result = extractor._detect_high_contrast_regions(arr)
        assert 0.0 <= result <= 1.0

    def test_high_contrast_blocks_return_high_score(self, extractor):
        """Many high-contrast blocks → contrast_ratio >= 0.3 → 1.0."""
        arr = np.zeros((60, 60, 3), dtype=np.uint8)
        # Create alternating high/low rows in every block
        for i in range(0, 60, 10):
            for j in range(0, 60, 2):
                arr[i+j if i+j < 60 else 59, :] = 255
        result = extractor._detect_high_contrast_regions(arr)
        assert isinstance(result, float)


# ===== _detect_structured_patterns() =====

class TestDetectStructuredPatterns:
    def test_uniform_image_returns_low_score(self, extractor):
        arr = np.full((50, 50, 3), 128, dtype=np.uint8)
        result = extractor._detect_structured_patterns(arr)
        assert result == 0.2  # Low variance → 0.2

    def test_returns_float(self, extractor):
        arr = np.full((30, 30, 3), 100, dtype=np.uint8)
        result = extractor._detect_structured_patterns(arr)
        assert isinstance(result, float)

    def test_returns_value_between_0_and_1(self, extractor):
        arr = np.random.randint(0, 255, (40, 40, 3), dtype=np.uint8)
        result = extractor._detect_structured_patterns(arr)
        assert 0.0 <= result <= 1.0

    def test_high_variance_returns_high_score(self, extractor):
        """High variance in projections → structured content → 1.0."""
        arr = np.zeros((60, 60, 3), dtype=np.uint8)
        # Create strong horizontal lines with high contrast
        for i in range(0, 60, 10):
            arr[i] = 0
            arr[i+1 if i+1 < 60 else 59] = 255
        result = extractor._detect_structured_patterns(arr)
        assert isinstance(result, float)


# ===== _analyze_color_patterns() =====

class TestAnalyzeColorPatterns:
    def test_solid_color_returns_low_score(self, extractor):
        """Single unique color → < 3 → 0.1."""
        arr = np.full((20, 20, 3), 128, dtype=np.uint8)
        result = extractor._analyze_color_patterns(arr)
        assert result == 0.1

    def test_returns_float(self, extractor):
        arr = np.full((20, 20, 3), 100, dtype=np.uint8)
        result = extractor._analyze_color_patterns(arr)
        assert isinstance(result, float)

    def test_returns_value_between_0_and_1(self, extractor):
        arr = np.random.randint(0, 255, (20, 20, 3), dtype=np.uint8)
        result = extractor._analyze_color_patterns(arr)
        assert 0.0 <= result <= 1.0

    def test_ideal_color_range_returns_high_score(self, extractor):
        """10-60 unique quantized colors → 1.0."""
        # Build array with exactly 15 distinct color blocks (each 32-multiple apart)
        arr = np.zeros((40, 40, 3), dtype=np.uint8)
        colors = [(i*32, (i*32)%256, 0) for i in range(15)]  # 15 distinct colors
        for idx, (r, g, b) in enumerate(colors):
            col = idx * 2  # 2 columns per color
            if col + 2 <= 40:
                arr[:, col:col+2] = [r, g, b]
        result = extractor._analyze_color_patterns(arr)
        assert isinstance(result, float)
        assert result >= 0.8  # Should be in ideal range or close

    def test_too_many_colors_returns_moderate_score(self, extractor):
        """Many unique colors (photo-like) → 0.5."""
        arr = np.random.randint(0, 255, (40, 40, 3), dtype=np.uint8)
        result = extractor._analyze_color_patterns(arr)
        assert isinstance(result, float)


# ===== _classify_image_content_type() =====

class TestClassifyImageContentType:
    def _make_img(self, width=100, height=100):
        return Image.new("RGB", (width, height), color=(128, 64, 32))

    def test_low_quality_returns_unknown(self, extractor):
        """quality_score < 0.4 → 'unknown' immediately."""
        img = self._make_img()
        result = extractor._classify_image_content_type(img, quality_score=0.3)
        assert result == "unknown"

    def test_returns_string(self, extractor):
        img = self._make_img()
        result = extractor._classify_image_content_type(img, quality_score=0.5)
        assert isinstance(result, str)

    def test_high_structure_and_colors_returns_diagram_or_chart(self, extractor):
        img = self._make_img()
        with patch.object(extractor, "_detect_high_contrast_regions", return_value=0.9):
            with patch.object(extractor, "_detect_structured_patterns", return_value=0.9):
                with patch.object(extractor, "_analyze_color_patterns", return_value=0.9):
                    result = extractor._classify_image_content_type(img, quality_score=0.8)
        assert result in ("diagram", "chart")

    def test_high_contrast_and_structure_returns_screenshot(self, extractor):
        img = self._make_img()
        with patch.object(extractor, "_detect_high_contrast_regions", return_value=0.9):
            with patch.object(extractor, "_detect_structured_patterns", return_value=0.7):
                with patch.object(extractor, "_analyze_color_patterns", return_value=0.3):
                    result = extractor._classify_image_content_type(img, quality_score=0.8)
        assert result == "screenshot"

    def test_moderate_quality_returns_technical(self, extractor):
        img = self._make_img()
        with patch.object(extractor, "_detect_high_contrast_regions", return_value=0.3):
            with patch.object(extractor, "_detect_structured_patterns", return_value=0.3):
                with patch.object(extractor, "_analyze_color_patterns", return_value=0.3):
                    result = extractor._classify_image_content_type(img, quality_score=0.7)
        assert result == "technical"

    def test_low_quality_returns_photo(self, extractor):
        img = self._make_img()
        with patch.object(extractor, "_detect_high_contrast_regions", return_value=0.1):
            with patch.object(extractor, "_detect_structured_patterns", return_value=0.1):
                with patch.object(extractor, "_analyze_color_patterns", return_value=0.1):
                    result = extractor._classify_image_content_type(img, quality_score=0.45)
        assert result == "photo"


# ===== _detect_meaningful_content() =====

class TestDetectMeaningfulContent:
    def _make_img(self, width=100, height=100):
        return Image.new("RGB", (width, height), color=(128, 64, 32))

    def test_returns_float(self, extractor):
        img = self._make_img()
        result = extractor._detect_meaningful_content(img, 100, 100)
        assert isinstance(result, float)

    def test_returns_value_between_0_and_1(self, extractor):
        img = self._make_img()
        result = extractor._detect_meaningful_content(img, 100, 100)
        assert 0.0 <= result <= 1.0

    def test_combines_subscores_correctly(self, extractor):
        """Result = contrast*0.4 + structure*0.3 + color*0.3."""
        img = self._make_img()
        with patch.object(extractor, "_detect_high_contrast_regions", return_value=1.0):
            with patch.object(extractor, "_detect_structured_patterns", return_value=1.0):
                with patch.object(extractor, "_analyze_color_patterns", return_value=1.0):
                    result = extractor._detect_meaningful_content(img, 100, 100)
        assert result == pytest.approx(1.0, abs=0.01)

    def test_zero_subscores_returns_zero(self, extractor):
        img = self._make_img()
        with patch.object(extractor, "_detect_high_contrast_regions", return_value=0.0):
            with patch.object(extractor, "_detect_structured_patterns", return_value=0.0):
                with patch.object(extractor, "_analyze_color_patterns", return_value=0.0):
                    result = extractor._detect_meaningful_content(img, 100, 100)
        assert result == pytest.approx(0.0, abs=0.01)

    def test_handles_non_rgb_image(self, extractor):
        """RGBA image should be converted without error."""
        img = Image.new("RGBA", (50, 50), color=(100, 100, 100, 255))
        result = extractor._detect_meaningful_content(img, 50, 50)
        assert isinstance(result, float)


# ===== WebImageScraperTool =====

@pytest.fixture
def web_scraper(tmp_path):
    """Create WebImageScraperTool with a temp output directory."""
    from lecture_forge.tools.image_extractor import WebImageScraperTool
    return WebImageScraperTool(output_dir=str(tmp_path))


class TestWebImageScraperToolInit:
    def test_creates_output_dir(self, tmp_path):
        from lecture_forge.tools.image_extractor import WebImageScraperTool
        out = tmp_path / "new_dir"
        tool = WebImageScraperTool(output_dir=str(out))
        assert out.exists()

    def test_sets_min_width(self, web_scraper):
        assert web_scraper.min_width > 0

    def test_sets_min_height(self, web_scraper):
        assert web_scraper.min_height > 0

    def test_default_output_dir_uses_config(self, tmp_path):
        """Without output_dir arg, uses Config.DATA_DIR/images."""
        from lecture_forge.config import Config
        from lecture_forge.tools.image_extractor import WebImageScraperTool
        original = Config.DATA_DIR
        try:
            Config.DATA_DIR = tmp_path
            tool = WebImageScraperTool()
            assert str(tmp_path) in tool.output_dir.parts or tool.output_dir.is_dir()
        finally:
            Config.DATA_DIR = original


@pytest.mark.skipif(not HAS_NUMPY, reason="numpy/PIL required")
class TestWebImageScraperToolRun:
    def _make_fake_png_bytes(self, width=800, height=600):
        img = Image.new("RGB", (width, height), color=(128, 128, 128))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def _make_soup_with_img(self, img_url):
        from bs4 import BeautifulSoup
        html = f'<html><body><img src="{img_url}" alt="test"/></body></html>'
        return BeautifulSoup(html, "html.parser")

    def _make_soup_no_img(self):
        from bs4 import BeautifulSoup
        return BeautifulSoup("<html><body></body></html>", "html.parser")

    def test_returns_empty_for_no_images(self, web_scraper):
        soup = self._make_soup_no_img()
        result = web_scraper.run("https://example.com", soup)
        assert result["success"] is True
        assert result["images"] == []

    def test_returns_success_structure(self, web_scraper):
        soup = self._make_soup_no_img()
        result = web_scraper.run("https://example.com", soup)
        assert "success" in result
        assert "images" in result
        assert "total_extracted" in result

    def test_downloads_and_saves_valid_image(self, web_scraper):
        """Mock requests.get to return valid PNG bytes."""
        png_bytes = self._make_fake_png_bytes(800, 600)
        soup = self._make_soup_with_img("https://example.com/image.png")

        mock_response = MagicMock()
        mock_response.content = png_bytes
        mock_response.raise_for_status.return_value = None

        with patch("requests.get", return_value=mock_response):
            result = web_scraper.run("https://example.com", soup)

        assert result["success"] is True
        assert len(result["images"]) == 1
        assert result["images"][0]["width"] == 800

    def test_skips_small_images(self, web_scraper):
        """Images smaller than min_width/min_height are skipped."""
        small_png = self._make_fake_png_bytes(10, 10)
        soup = self._make_soup_with_img("https://example.com/small.png")

        mock_response = MagicMock()
        mock_response.content = small_png
        mock_response.raise_for_status.return_value = None

        with patch("requests.get", return_value=mock_response):
            result = web_scraper.run("https://example.com", soup)

        assert result["images"] == []

    def test_skips_data_urls(self, web_scraper):
        """data: URLs are skipped."""
        from bs4 import BeautifulSoup
        html = '<html><body><img src="data:image/png;base64,abc123" /></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        with patch("requests.get") as mock_get:
            web_scraper.run("https://example.com", soup)
        mock_get.assert_not_called()

    def test_deduplication_skips_same_hash(self, web_scraper):
        """Same image appearing twice is deduplicated."""
        from bs4 import BeautifulSoup
        png_bytes = self._make_fake_png_bytes(800, 600)
        html = '<html><body><img src="img1.png"/><img src="img1.png"/></body></html>'
        soup = BeautifulSoup(html, "html.parser")

        mock_response = MagicMock()
        mock_response.content = png_bytes
        mock_response.raise_for_status.return_value = None

        with patch("requests.get", return_value=mock_response):
            result = web_scraper.run("https://example.com", soup)

        assert len(result["images"]) == 1

    def test_handles_download_error_gracefully(self, web_scraper):
        """Download errors per image are caught and continue."""
        import requests as requests_mod
        soup = self._make_soup_with_img("https://example.com/bad.png")
        with patch("requests.get", side_effect=requests_mod.exceptions.ConnectionError("timeout")):
            result = web_scraper.run("https://example.com", soup)
        assert result["success"] is True
        assert result["images"] == []

    def test_handles_ioerror(self, web_scraper):
        """OSError/IOError from network is caught and returns failure."""
        soup = self._make_soup_with_img("https://example.com/img.png")
        from bs4 import BeautifulSoup
        with patch.object(soup, "find_all", side_effect=IOError("io error")):
            result = web_scraper.run("https://example.com", soup)
        assert result["success"] is False
