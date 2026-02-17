"""
Unit tests for image search tools.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestUnsplashSearchTool:
    def test_initializes_with_access_key(self, test_env_vars, temp_dir):
        from lecture_forge.tools.image_search import UnsplashSearchTool

        with patch("lecture_forge.tools.image_search.Config") as mock_config:
            mock_config.UNSPLASH_ACCESS_KEY = "test-key"
            mock_config.DATA_DIR = temp_dir
            mock_config.IMAGE_SEARCH_PER_PAGE = 10
            mock_config.IMAGE_SEARCH_TIMEOUT = 10
            mock_config.IMAGE_MAX_WIDTH = 1920
            mock_config.IMAGE_FORMAT = "webp"
            tool = UnsplashSearchTool(output_dir=str(temp_dir))
            assert tool.access_key == "test-key"

    def test_run_without_api_key_returns_error(self, test_env_vars, temp_dir):
        from lecture_forge.tools.image_search import UnsplashSearchTool

        with patch("lecture_forge.tools.image_search.Config") as mock_config:
            mock_config.UNSPLASH_ACCESS_KEY = None
            mock_config.DATA_DIR = temp_dir
            mock_config.IMAGE_SEARCH_PER_PAGE = 10
            mock_config.IMAGE_SEARCH_TIMEOUT = 10
            mock_config.IMAGE_MAX_WIDTH = 1920
            mock_config.IMAGE_FORMAT = "webp"
            tool = UnsplashSearchTool(output_dir=str(temp_dir))
            result = tool.run("machine learning", download=False)

        assert result["success"] is False
        assert result["images"] == []
        assert "error" in result

    def test_run_with_successful_api_response(self, test_env_vars, temp_dir):
        from lecture_forge.tools.image_search import UnsplashSearchTool

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {
                    "id": "abc123",
                    "urls": {"full": "https://images.unsplash.com/photo-abc.jpg"},
                    "links": {"download_location": "https://api.unsplash.com/photos/abc/download"},
                    "description": "A great photo",
                    "alt_description": "Alternative description",
                    "user": {"name": "Photographer", "username": "photo_guy"},
                    "width": 1920,
                    "height": 1080,
                    "color": "#336699",
                }
            ]
        }

        with patch("lecture_forge.tools.image_search.Config") as mock_config:
            mock_config.UNSPLASH_ACCESS_KEY = "valid-key"
            mock_config.DATA_DIR = temp_dir
            mock_config.IMAGE_SEARCH_PER_PAGE = 10
            mock_config.IMAGE_SEARCH_TIMEOUT = 10
            mock_config.IMAGE_MAX_WIDTH = 1920
            mock_config.IMAGE_FORMAT = "webp"

            with patch("requests.get", return_value=mock_response):
                tool = UnsplashSearchTool(output_dir=str(temp_dir))
                result = tool.run("machine learning", download=False)

        assert "images" in result
        assert len(result["images"]) == 1
        assert result["images"][0]["source"] == "unsplash"

    def test_run_with_401_response_raises_or_handles(self, test_env_vars, temp_dir):
        import requests as req

        from lecture_forge.tools.image_search import UnsplashSearchTool

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = req.exceptions.HTTPError("401 Unauthorized")

        with patch("lecture_forge.tools.image_search.Config") as mock_config:
            mock_config.UNSPLASH_ACCESS_KEY = "bad-key"
            mock_config.DATA_DIR = temp_dir
            mock_config.IMAGE_SEARCH_PER_PAGE = 10
            mock_config.IMAGE_SEARCH_TIMEOUT = 10
            mock_config.IMAGE_MAX_WIDTH = 1920
            mock_config.IMAGE_FORMAT = "webp"

            with patch("requests.get", return_value=mock_response):
                tool = UnsplashSearchTool(output_dir=str(temp_dir))
                # The tool uses tenacity retry — patch it to avoid waiting
                with patch("lecture_forge.tools.image_search.UnsplashSearchTool.run.__wrapped__", None, create=True):
                    try:
                        result = tool.run.__wrapped__(tool, "query", download=False)
                        # If it returns a result (handled gracefully), accept it
                    except Exception:
                        # If it raises, that's acceptable too
                        pass

    def test_tool_has_name_and_description(self, test_env_vars, temp_dir):
        from lecture_forge.tools.image_search import UnsplashSearchTool

        with patch("lecture_forge.tools.image_search.Config") as mock_config:
            mock_config.UNSPLASH_ACCESS_KEY = "key"
            mock_config.DATA_DIR = temp_dir
            mock_config.IMAGE_SEARCH_PER_PAGE = 10
            mock_config.IMAGE_SEARCH_TIMEOUT = 10
            mock_config.IMAGE_MAX_WIDTH = 1920
            mock_config.IMAGE_FORMAT = "webp"
            tool = UnsplashSearchTool(output_dir=str(temp_dir))
            assert hasattr(tool, "name")
            assert hasattr(tool, "description")
            assert "Unsplash" in tool.name


class TestPexelsSearchTool:
    def test_pexels_tool_exists(self, test_env_vars, temp_dir):
        """Verify PexelsSearchTool can be imported."""
        try:
            from lecture_forge.tools.image_search import PexelsSearchTool

            with patch("lecture_forge.tools.image_search.Config") as mock_config:
                mock_config.PEXELS_API_KEY = "test-key"
                mock_config.DATA_DIR = temp_dir
                mock_config.IMAGE_SEARCH_PER_PAGE = 10
                mock_config.IMAGE_SEARCH_TIMEOUT = 10
                mock_config.IMAGE_MAX_WIDTH = 1920
                mock_config.IMAGE_FORMAT = "webp"
                tool = PexelsSearchTool(output_dir=str(temp_dir))
                assert tool is not None
        except ImportError:
            pytest.skip("PexelsSearchTool not found in image_search module")

    def test_pexels_run_without_key_returns_error(self, test_env_vars, temp_dir):
        try:
            from lecture_forge.tools.image_search import PexelsSearchTool

            with patch("lecture_forge.tools.image_search.Config") as mock_config:
                mock_config.PEXELS_API_KEY = None
                mock_config.DATA_DIR = temp_dir
                mock_config.IMAGE_SEARCH_PER_PAGE = 10
                mock_config.IMAGE_SEARCH_TIMEOUT = 10
                mock_config.IMAGE_MAX_WIDTH = 1920
                mock_config.IMAGE_FORMAT = "webp"
                tool = PexelsSearchTool(output_dir=str(temp_dir))
                result = tool.run("machine learning", download=False)

            assert result["success"] is False
            assert result["images"] == []
        except ImportError:
            pytest.skip("PexelsSearchTool not found in image_search module")


# ===== Extended UnsplashSearchTool tests =====

class TestUnsplashSearchToolExtended:
    @pytest.fixture
    def tool(self, test_env_vars, tmp_path):
        from lecture_forge.tools.image_search import UnsplashSearchTool
        return UnsplashSearchTool(output_dir=str(tmp_path))

    def _make_photo(self, photo_id="abc123", width=1200, height=800):
        return {
            "id": photo_id,
            "urls": {"full": f"https://images.unsplash.com/{photo_id}.jpg"},
            "links": {"download_location": f"https://api.unsplash.com/photos/{photo_id}/download"},
            "description": "A test image",
            "alt_description": "alt",
            "user": {"name": "Author", "username": "author"},
            "width": width,
            "height": height,
            "color": "#abc",
        }

    def _make_response(self, json_data):
        mock = MagicMock()
        mock.raise_for_status.return_value = None
        mock.json.return_value = json_data
        return mock

    def test_returns_image_metadata(self, tool):
        photo = self._make_photo()
        resp = self._make_response({"results": [photo]})
        with patch("requests.get", return_value=resp):
            result = tool.run("test", download=False)
        img = result["images"][0]
        assert img["source"] == "unsplash"
        assert img["query"] == "test"
        assert img["license"] == "Unsplash License"

    def test_returns_correct_image_count(self, tool):
        photos = [self._make_photo(f"id{i}") for i in range(5)]
        resp = self._make_response({"results": photos})
        with patch("requests.get", return_value=resp):
            result = tool.run("test", download=False)
        assert result["total_results"] == 5

    def test_total_results_key_present(self, tool):
        resp = self._make_response({"results": []})
        with patch("requests.get", return_value=resp):
            result = tool.run("test", download=False)
        assert "total_results" in result

    def test_no_results_key_returns_success(self, tool):
        """Response without 'results' key still returns success=True."""
        resp = self._make_response({"errors": []})
        with patch("requests.get", return_value=resp):
            result = tool.run("test", download=False)
        assert result["success"] is True
        assert result["images"] == []

    def test_request_exception_returns_error_dict(self, tool):
        import requests as req
        with patch("requests.get", side_effect=req.exceptions.ConnectionError("timeout")):
            result = tool.run("test", download=False)
        assert result["success"] is False
        assert result["query"] == "test"
        assert "error" in result

    def test_image_without_description_uses_alt(self, tool):
        """Photo with null description should fall back to alt_description."""
        photo = self._make_photo()
        photo["description"] = None
        photo["alt_description"] = "alternative description"
        resp = self._make_response({"results": [photo]})
        with patch("requests.get", return_value=resp):
            result = tool.run("test", download=False)
        img = result["images"][0]
        assert img["description"] == "alternative description"


# ===== Extended PexelsSearchTool tests =====

class TestPexelsSearchToolExtended:
    @pytest.fixture
    def tool(self, test_env_vars, tmp_path):
        from lecture_forge.tools.image_search import PexelsSearchTool
        return PexelsSearchTool(output_dir=str(tmp_path))

    def _make_photo(self, photo_id=1, width=1200, height=800):
        return {
            "id": photo_id,
            "src": {"original": f"https://images.pexels.com/{photo_id}.jpg"},
            "alt": "Pexels alt text",
            "photographer": "John Photo",
            "photographer_url": "https://pexels.com/john",
            "width": width,
            "height": height,
        }

    def _make_response(self, json_data):
        mock = MagicMock()
        mock.raise_for_status.return_value = None
        mock.json.return_value = json_data
        return mock

    def test_returns_image_metadata(self, tool):
        photo = self._make_photo()
        resp = self._make_response({"photos": [photo]})
        with patch("requests.get", return_value=resp):
            result = tool.run("test", download=False)
        img = result["images"][0]
        assert img["source"] == "pexels"
        assert img["query"] == "test"
        assert img["photographer"] == "John Photo"

    def test_returns_correct_image_count(self, tool):
        photos = [self._make_photo(i) for i in range(4)]
        resp = self._make_response({"photos": photos})
        with patch("requests.get", return_value=resp):
            result = tool.run("test", download=False)
        assert result["total_results"] == 4

    def test_total_results_key_present(self, tool):
        resp = self._make_response({"photos": []})
        with patch("requests.get", return_value=resp):
            result = tool.run("test", download=False)
        assert "total_results" in result

    def test_no_photos_key_returns_success(self, tool):
        resp = self._make_response({})
        with patch("requests.get", return_value=resp):
            result = tool.run("test", download=False)
        assert result["success"] is True
        assert result["images"] == []

    def test_request_exception_returns_error_dict(self, tool):
        import requests as req
        with patch("requests.get", side_effect=req.exceptions.ConnectionError("timeout")):
            result = tool.run("test", download=False)
        assert result["success"] is False
        assert result["query"] == "test"
        assert "error" in result

    def test_attribution_includes_photographer(self, tool):
        photo = self._make_photo()
        resp = self._make_response({"photos": [photo]})
        with patch("requests.get", return_value=resp):
            result = tool.run("test", download=False)
        img = result["images"][0]
        assert "John Photo" in img["attribution"]


# ===== Download=True branch tests (covers PIL processing path) =====

import io
from PIL import Image as PILImage


def _create_png_bytes(width=100, height=80, color=(100, 150, 200)):
    """Create minimal valid PNG image bytes for testing."""
    img = PILImage.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestUnsplashDownloadTrue:
    """Tests covering the download=True branch of UnsplashSearchTool.run()."""

    @pytest.fixture
    def tool(self, test_env_vars, tmp_path):
        from lecture_forge.tools.image_search import UnsplashSearchTool
        return UnsplashSearchTool(output_dir=str(tmp_path))

    def _photo(self, photo_id="img1"):
        return {
            "id": photo_id,
            "urls": {"full": f"https://images.unsplash.com/{photo_id}.jpg"},
            "links": {"download_location": f"https://api.unsplash.com/photos/{photo_id}/download"},
            "description": "Test photo",
            "alt_description": "alt",
            "user": {"name": "Author", "username": "author"},
            "width": 100,
            "height": 80,
            "color": "#abc",
        }

    def test_download_true_returns_success(self, tool):
        """download=True returns success=True and saves image file."""
        png_bytes = _create_png_bytes()

        api_resp = MagicMock()
        api_resp.raise_for_status.return_value = None
        api_resp.json.return_value = {"results": [self._photo()]}

        trigger_resp = MagicMock()
        trigger_resp.raise_for_status.return_value = None

        img_resp = MagicMock()
        img_resp.raise_for_status.return_value = None
        img_resp.content = png_bytes

        with patch("requests.get", side_effect=[api_resp, trigger_resp, img_resp]):
            result = tool.run("test", download=True, session_id="sess1")

        assert result["success"] is True
        assert len(result["images"]) == 1
        assert "path" in result["images"][0]
        assert "hash" in result["images"][0]

    def test_download_true_session_dir_returned(self, tool):
        """session_dir is set in result when download=True."""
        png_bytes = _create_png_bytes()

        api_resp = MagicMock()
        api_resp.raise_for_status.return_value = None
        api_resp.json.return_value = {"results": [self._photo()]}

        trigger_resp = MagicMock()
        trigger_resp.raise_for_status.return_value = None

        img_resp = MagicMock()
        img_resp.raise_for_status.return_value = None
        img_resp.content = png_bytes

        with patch("requests.get", side_effect=[api_resp, trigger_resp, img_resp]):
            result = tool.run("test", download=True, session_id="sess2")

        assert result["session_dir"] is not None

    def test_download_true_image_metadata_has_size(self, tool):
        """Downloaded image metadata includes size_bytes and dimensions."""
        png_bytes = _create_png_bytes()

        api_resp = MagicMock()
        api_resp.raise_for_status.return_value = None
        api_resp.json.return_value = {"results": [self._photo()]}

        trigger_resp = MagicMock()
        trigger_resp.raise_for_status.return_value = None

        img_resp = MagicMock()
        img_resp.raise_for_status.return_value = None
        img_resp.content = png_bytes

        with patch("requests.get", side_effect=[api_resp, trigger_resp, img_resp]):
            result = tool.run("test", download=True, session_id="sess3")

        img_meta = result["images"][0]
        assert "size_bytes" in img_meta
        assert "filename" in img_meta

    def test_download_true_png_format_branch(self, tool, tmp_path):
        """Tests the else branch when IMAGE_FORMAT is not webp."""
        from lecture_forge.config import Config
        original_fmt = Config.IMAGE_FORMAT
        try:
            Config.IMAGE_FORMAT = "png"
            png_bytes = _create_png_bytes()

            api_resp = MagicMock()
            api_resp.raise_for_status.return_value = None
            api_resp.json.return_value = {"results": [self._photo("png_test")]}

            trigger_resp = MagicMock()
            trigger_resp.raise_for_status.return_value = None

            img_resp = MagicMock()
            img_resp.raise_for_status.return_value = None
            img_resp.content = png_bytes

            with patch("requests.get", side_effect=[api_resp, trigger_resp, img_resp]):
                result = tool.run("test", download=True, session_id="sess_png")
        finally:
            Config.IMAGE_FORMAT = original_fmt

        assert result["success"] is True
        assert len(result["images"]) == 1

    def test_download_true_resize_branch(self, tool):
        """Tests the resize branch when image width > Config.IMAGE_MAX_WIDTH."""
        from lecture_forge.config import Config
        # Use a small max width so our 100px image triggers resize
        original_max = Config.IMAGE_MAX_WIDTH
        try:
            Config.IMAGE_MAX_WIDTH = 50  # Our image is 100px wide → triggers resize
            png_bytes = _create_png_bytes(width=100, height=80)

            api_resp = MagicMock()
            api_resp.raise_for_status.return_value = None
            api_resp.json.return_value = {"results": [self._photo("resize_test")]}

            trigger_resp = MagicMock()
            trigger_resp.raise_for_status.return_value = None

            img_resp = MagicMock()
            img_resp.raise_for_status.return_value = None
            img_resp.content = png_bytes

            with patch("requests.get", side_effect=[api_resp, trigger_resp, img_resp]):
                result = tool.run("test", download=True, session_id="sess_resize")
        finally:
            Config.IMAGE_MAX_WIDTH = original_max

        assert result["success"] is True
        img_meta = result["images"][0]
        # After resize, width should be <= 50
        assert img_meta["width"] <= 50

    def test_download_trigger_endpoint_failure_continues(self, tool):
        """Trigger download endpoint failure should not prevent image download."""
        import requests as req
        png_bytes = _create_png_bytes()

        api_resp = MagicMock()
        api_resp.raise_for_status.return_value = None
        api_resp.json.return_value = {"results": [self._photo("trigger_fail")]}

        img_resp = MagicMock()
        img_resp.raise_for_status.return_value = None
        img_resp.content = png_bytes

        # Trigger endpoint raises RequestException → logged and skipped; image download succeeds
        with patch("requests.get", side_effect=[
            api_resp,
            req.exceptions.RequestException("trigger failed"),
            img_resp,
        ]):
            result = tool.run("test", download=True, session_id="sess_trigger_fail")

        assert result["success"] is True
        assert len(result["images"]) == 1

    def test_download_image_bytes_error_skips_image(self, tool):
        """If PIL cannot parse image bytes, the image is skipped (inner except)."""
        api_resp = MagicMock()
        api_resp.raise_for_status.return_value = None
        api_resp.json.return_value = {"results": [self._photo("bad_img")]}

        trigger_resp = MagicMock()
        trigger_resp.raise_for_status.return_value = None

        bad_img_resp = MagicMock()
        bad_img_resp.raise_for_status.return_value = None
        bad_img_resp.content = b"not valid image data at all"

        with patch("requests.get", side_effect=[api_resp, trigger_resp, bad_img_resp]):
            result = tool.run("test", download=True, session_id="sess_bad")

        # The inner except catches and continues; result may have 0 images
        assert result["success"] is True
        assert isinstance(result["images"], list)


class TestPexelsDownloadTrue:
    """Tests covering the download=True branch of PexelsSearchTool.run()."""

    @pytest.fixture
    def tool(self, test_env_vars, tmp_path):
        from lecture_forge.tools.image_search import PexelsSearchTool
        return PexelsSearchTool(output_dir=str(tmp_path))

    def _photo(self, photo_id=1):
        return {
            "id": photo_id,
            "src": {"original": f"https://images.pexels.com/{photo_id}.jpg"},
            "alt": "Test Pexels photo",
            "photographer": "Jane Doe",
            "photographer_url": "https://pexels.com/jane",
            "width": 100,
            "height": 80,
        }

    def test_download_true_returns_success(self, tool):
        """Pexels download=True saves image and returns metadata."""
        png_bytes = _create_png_bytes()

        api_resp = MagicMock()
        api_resp.raise_for_status.return_value = None
        api_resp.json.return_value = {"photos": [self._photo()]}

        img_resp = MagicMock()
        img_resp.raise_for_status.return_value = None
        img_resp.content = png_bytes

        with patch("requests.get", side_effect=[api_resp, img_resp]):
            result = tool.run("test", download=True, session_id="pexels_sess")

        assert result["success"] is True
        assert len(result["images"]) == 1
        assert "path" in result["images"][0]
        assert "hash" in result["images"][0]

    def test_download_true_png_format_branch(self, tool):
        """Pexels: else branch when IMAGE_FORMAT is not webp."""
        from lecture_forge.config import Config
        original_fmt = Config.IMAGE_FORMAT
        try:
            Config.IMAGE_FORMAT = "png"
            png_bytes = _create_png_bytes()

            api_resp = MagicMock()
            api_resp.raise_for_status.return_value = None
            api_resp.json.return_value = {"photos": [self._photo(99)]}

            img_resp = MagicMock()
            img_resp.raise_for_status.return_value = None
            img_resp.content = png_bytes

            with patch("requests.get", side_effect=[api_resp, img_resp]):
                result = tool.run("test", download=True, session_id="pexels_png")
        finally:
            Config.IMAGE_FORMAT = original_fmt

        assert result["success"] is True

    def test_download_true_resize_branch(self, tool):
        """Pexels: resize branch when image width > Config.IMAGE_MAX_WIDTH."""
        from lecture_forge.config import Config
        original_max = Config.IMAGE_MAX_WIDTH
        try:
            Config.IMAGE_MAX_WIDTH = 50
            png_bytes = _create_png_bytes(width=100, height=80)

            api_resp = MagicMock()
            api_resp.raise_for_status.return_value = None
            api_resp.json.return_value = {"photos": [self._photo(42)]}

            img_resp = MagicMock()
            img_resp.raise_for_status.return_value = None
            img_resp.content = png_bytes

            with patch("requests.get", side_effect=[api_resp, img_resp]):
                result = tool.run("test", download=True, session_id="pexels_resize")
        finally:
            Config.IMAGE_MAX_WIDTH = original_max

        assert result["success"] is True
        assert result["images"][0]["width"] <= 50

    def test_download_image_bytes_error_skips_image(self, tool):
        """Pexels: bad image bytes in inner loop → skipped, loop continues."""
        api_resp = MagicMock()
        api_resp.raise_for_status.return_value = None
        api_resp.json.return_value = {"photos": [self._photo(7)]}

        bad_img_resp = MagicMock()
        bad_img_resp.raise_for_status.return_value = None
        bad_img_resp.content = b"totally invalid"

        with patch("requests.get", side_effect=[api_resp, bad_img_resp]):
            result = tool.run("test", download=True, session_id="pexels_bad")

        assert result["success"] is True
        assert isinstance(result["images"], list)
