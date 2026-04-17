"""
LectureForge Web Editor - Flask API Server.

Serves the editor SPA and provides REST endpoints for editing lecture HTML files.
Runs locally on port 5757.
"""

import base64
import mimetypes
import os
import threading
import uuid
from pathlib import Path
from typing import Optional

from flask import Flask, jsonify, request, send_file

from lecture_forge.config import Config
from lecture_forge.editor.html_editor import LectureHTMLEditor
from lecture_forge.tools.image_editor import ImageEditor
from lecture_forge.utils import logger

_UPLOAD_DIR = Config.DATA_DIR / "images" / "_uploaded"
_ALLOWED_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
# Resolve template path at import time using this file's location,
# independent of Flask's template discovery (works with any install method).
_INDEX_TEMPLATE = Path(__file__).parent.parent / "templates" / "editor" / "index.html"


def create_app(html_path: str, output_path: Optional[str] = None) -> Flask:
    """
    Create and configure the Flask application.

    Args:
        html_path: Path to the HTML lecture file to edit.
        output_path: Where to save the edited file (default: <stem>_edited.html)
    """
    template_dir = str(Config.TEMPLATES_DIR / "editor")
    app = Flask(
        __name__,
        template_folder=template_dir,
        static_folder=template_dir,
        static_url_path="/static",
    )
    app.config["SECRET_KEY"] = os.urandom(24)

    # Determine default output path
    html_p = Path(html_path)
    if output_path is None:
        output_path = str(html_p.parent / f"{html_p.stem}_edited{html_p.suffix}")

    # Shared editor state
    html_editor = LectureHTMLEditor(html_path)
    image_editor = ImageEditor(html_path)

    # ------------------------------------------------------------------ #
    #  SPA                                                                  #
    # ------------------------------------------------------------------ #

    @app.route("/")
    def index():
        filename = Path(html_path).name
        content = _INDEX_TEMPLATE.read_text(encoding="utf-8")
        return content.replace("{{ filename }}", filename)

    # ------------------------------------------------------------------ #
    #  Lecture meta                                                         #
    # ------------------------------------------------------------------ #

    @app.route("/api/lecture")
    def api_lecture():
        try:
            meta = html_editor.get_lecture_meta()
            return jsonify(meta)
        except Exception as exc:
            logger.error(f"api_lecture error: {exc}")
            return jsonify({"error": str(exc)}), 500

    # ------------------------------------------------------------------ #
    #  Section CRUD                                                         #
    # ------------------------------------------------------------------ #

    @app.route("/api/sections/<section_id>", methods=["GET"])
    def api_get_section(section_id: str):
        try:
            data = html_editor.get_section_content(section_id)
            if "error" in data:
                return jsonify(data), 404
            return jsonify(data)
        except Exception as exc:
            logger.error(f"api_get_section error: {exc}")
            return jsonify({"error": str(exc)}), 500

    @app.route("/api/sections/<section_id>", methods=["POST"])
    def api_update_section(section_id: str):
        try:
            body = request.get_json(force=True)
            md_text = body.get("markdown", "")
            title = body.get("title")
            result = html_editor.update_section_content(section_id, md_text, title)
            if not result.get("success"):
                return jsonify(result), 404
            return jsonify(result)
        except Exception as exc:
            logger.error(f"api_update_section error: {exc}")
            return jsonify({"error": str(exc)}), 500

    @app.route("/api/sections/<section_id>/images", methods=["GET"])
    def api_get_pending_images(section_id: str):
        """Return staged image additions for a section (with thumbnails)."""
        try:
            additions = html_editor.get_pending_additions(section_id)
            enriched = []
            for i, item in enumerate(additions):
                enriched.append({
                    "index": i,
                    "path": item["path"],
                    "caption": item.get("caption", ""),
                    "thumbnail": _encode_image_thumbnail(item["path"]),
                })
            return jsonify({"additions": enriched})
        except Exception as exc:
            logger.error(f"api_get_pending_images error: {exc}")
            return jsonify({"error": str(exc)}), 500

    @app.route("/api/sections/<section_id>/images", methods=["POST"])
    def api_add_image_to_section(section_id: str):
        """Stage an image addition to a section."""
        try:
            body = request.get_json(force=True)
            image_path = body.get("path", "")
            caption = body.get("caption", "")
            if not image_path:
                return jsonify({"error": "No image path provided"}), 400
            if not image_path.startswith("data:") and not Path(image_path).exists():
                return jsonify({"error": "Image file not found"}), 400
            ok = html_editor.stage_add_image(section_id, image_path, caption)
            if not ok:
                return jsonify({"error": f"Section not found: {section_id}"}), 404
            thumbnail = _encode_image_thumbnail(image_path)
            additions = html_editor.get_pending_additions(section_id)
            return jsonify({"success": True, "index": len(additions) - 1, "thumbnail": thumbnail})
        except Exception as exc:
            logger.error(f"api_add_image_to_section error: {exc}")
            return jsonify({"error": str(exc)}), 500

    @app.route("/api/sections/<section_id>/images/<int:img_index>", methods=["DELETE"])
    def api_remove_pending_image(section_id: str, img_index: int):
        """Unstage a pending image addition."""
        try:
            ok = html_editor.unstage_add_image(section_id, img_index)
            if not ok:
                return jsonify({"error": "Pending image not found"}), 404
            return jsonify({"success": True})
        except Exception as exc:
            logger.error(f"api_remove_pending_image error: {exc}")
            return jsonify({"error": str(exc)}), 500

    @app.route("/api/sections/<section_id>", methods=["DELETE"])
    def api_delete_section(section_id: str):
        try:
            ok = html_editor.delete_section(section_id)
            if not ok:
                return jsonify({"error": f"Section not found: {section_id}"}), 404
            return jsonify({"success": True, "section_id": section_id})
        except Exception as exc:
            logger.error(f"api_delete_section error: {exc}")
            return jsonify({"error": str(exc)}), 500

    # ------------------------------------------------------------------ #
    #  Visual elements (images + diagrams)                                  #
    # ------------------------------------------------------------------ #

    @app.route("/api/elements")
    def api_elements():
        try:
            elements = image_editor.list_elements()
            return jsonify({"elements": elements})
        except Exception as exc:
            logger.error(f"api_elements error: {exc}")
            return jsonify({"error": str(exc)}), 500

    @app.route("/api/elements/<int:display_idx>", methods=["PATCH"])
    def api_toggle_element(display_idx: int):
        """Toggle delete/keep for an image or diagram."""
        try:
            elements = image_editor.list_elements()
            el = next((e for e in elements if e["display_index"] == display_idx), None)
            if not el:
                return jsonify({"error": "Element not found"}), 404

            body = request.get_json(force=True) or {}
            action = body.get("action", "toggle")  # "delete" | "undelete" | "toggle"

            if el["kind"] == "image":
                idx = el["img_index"]
                current_status = el["status"]
                if action == "delete" or (action == "toggle" and current_status != "delete"):
                    image_editor.mark_delete(idx)
                else:
                    image_editor.unmark_delete(idx)
            else:
                idx = el["dgm_index"]
                current_status = el["status"]
                if action == "delete" or (action == "toggle" and current_status != "delete"):
                    image_editor.mark_delete_diagram(idx)
                else:
                    image_editor.unmark_delete_diagram(idx)

            # Return updated element list
            updated = image_editor.list_elements()
            return jsonify({"elements": updated})
        except Exception as exc:
            logger.error(f"api_toggle_element error: {exc}")
            return jsonify({"error": str(exc)}), 500

    # ------------------------------------------------------------------ #
    #  Image alternatives & replacement                                     #
    # ------------------------------------------------------------------ #

    @app.route("/api/images/<int:img_idx>/alternatives")
    def api_image_alternatives(img_idx: int):
        try:
            alts = image_editor.find_alternative_images(img_idx, max_results=5)
            # Enrich with base64 thumbnail for browser display
            enriched = []
            for alt in alts:
                item = dict(alt)
                item["thumbnail"] = _encode_image_thumbnail(alt.get("path", ""))
                enriched.append(item)
            return jsonify({"alternatives": enriched})
        except Exception as exc:
            logger.error(f"api_image_alternatives error: {exc}")
            return jsonify({"error": str(exc)}), 500

    @app.route("/api/images/<int:img_idx>/replace", methods=["POST"])
    def api_replace_image(img_idx: int):
        try:
            body = request.get_json(force=True)
            new_path = body.get("path", "")
            if not new_path or not Path(new_path).exists():
                return jsonify({"error": "Invalid image path"}), 400
            ok = image_editor.replace_image(img_idx, new_path)
            if not ok:
                return jsonify({"error": "Replace failed"}), 400
            return jsonify({"success": True})
        except Exception as exc:
            logger.error(f"api_replace_image error: {exc}")
            return jsonify({"error": str(exc)}), 500

    # ------------------------------------------------------------------ #
    #  Gallery                                                              #
    # ------------------------------------------------------------------ #

    @app.route("/api/gallery")
    def api_gallery():
        """Return available images from outputs/*_images/ (v0.5.9+) and legacy data/images/."""
        try:
            page = int(request.args.get("page", 1))
            per_page = int(request.args.get("per_page", 24))
            query = request.args.get("q", "").lower()

            all_images = []
            seen_paths: set = set()

            def _collect_dir(base: Path):
                if not base.exists():
                    return
                for session_dir in sorted(base.iterdir(), key=lambda d: d.stat().st_mtime, reverse=True):
                    if not session_dir.is_dir() or session_dir.name.startswith("."):
                        continue
                    for img_file in sorted(session_dir.rglob("*")):
                        if not img_file.is_file():
                            continue
                        if img_file.suffix.lower() not in _ALLOWED_EXTS:
                            continue
                        if img_file in seen_paths:
                            continue
                        if query and query not in img_file.name.lower() and query not in session_dir.name.lower():
                            continue
                        seen_paths.add(img_file)
                        all_images.append({
                            "path": str(img_file),
                            "name": img_file.name,
                            "session": session_dir.name,
                            "size": img_file.stat().st_size,
                        })

            # Primary: outputs/*_images/ (v0.5.9+ single-copy layout)
            _collect_dir(Config.OUTPUT_DIR)
            # Legacy: data/images/*/
            _collect_dir(Config.DATA_DIR / "images")

            total = len(all_images)
            start = (page - 1) * per_page
            page_images = all_images[start: start + per_page]

            # Encode thumbnails
            for item in page_images:
                item["thumbnail"] = _encode_image_thumbnail(item["path"])

            return jsonify({
                "images": page_images,
                "total": total,
                "page": page,
                "per_page": per_page,
                "pages": max(1, (total + per_page - 1) // per_page),
            })
        except Exception as exc:
            logger.error(f"api_gallery error: {exc}")
            return jsonify({"error": str(exc)}), 500

    # ------------------------------------------------------------------ #
    #  Serve image by index (for visual panel thumbnails)                   #
    # ------------------------------------------------------------------ #

    @app.route("/api/images/by-index/<int:img_index>")
    def api_serve_image_by_index(img_index: int):
        """Serve an image by its 1-based index in image_editor.images.

        If a replacement is staged for this index, serve the replacement path
        so the visual panel reflects the pending change before saving.
        """
        if not (1 <= img_index <= len(image_editor.images)):
            return "Not found", 404

        # Use replacement path when one is staged
        replacement = image_editor.changes["replace"].get(img_index)
        if replacement:
            repl_path = Path(replacement["new_path"]).resolve()
            if repl_path.exists():
                mime = mimetypes.guess_type(str(repl_path))[0] or "image/jpeg"
                return send_file(repl_path, mimetype=mime)

        img = image_editor.images[img_index - 1]
        src = img.get("src", "")
        if not src:
            return "No source", 404

        # Data URI — decode and stream bytes
        if src.startswith("data:"):
            try:
                import base64 as _b64
                from flask import Response
                header, data = src.split(",", 1)
                mime = header.split(";")[0].replace("data:", "") or "image/jpeg"
                return Response(_b64.b64decode(data), mimetype=mime)
            except Exception:
                return "Invalid data URI", 400

        # File path — resolve relative paths against the HTML's parent dir
        img_path = Path(src)
        if not img_path.is_absolute():
            img_path = (Path(html_path).parent / src).resolve()
        else:
            img_path = img_path.resolve()

        if not img_path.exists():
            return "Not found", 404

        mime = mimetypes.guess_type(str(img_path))[0] or "image/jpeg"
        return send_file(img_path, mimetype=mime)

    # ------------------------------------------------------------------ #
    #  Serve local image file                                               #
    # ------------------------------------------------------------------ #

    @app.route("/api/images/serve")
    def api_serve_image():
        """Serve a local image file securely (path whitelist check)."""
        path_str = request.args.get("path", "")
        if not path_str:
            return "Missing path", 400

        img_path = Path(path_str).resolve()

        # Security: path must reside under one of the known image roots.
        # - html_path.parent covers outputs/ (where {stem}_images/ lives, v0.5.9+)
        # - DATA_DIR/images covers legacy sessions
        # - UPLOAD_DIR covers user uploads
        allowed_roots = [
            Path(html_path).parent.resolve(),
            Config.DATA_DIR.resolve() / "images",
            _UPLOAD_DIR.resolve(),
        ]
        if not any(str(img_path).startswith(str(r)) for r in allowed_roots):
            return "Forbidden", 403

        if not img_path.exists():
            return "Not found", 404

        mime = mimetypes.guess_type(str(img_path))[0] or "image/jpeg"
        return send_file(img_path, mimetype=mime)

    # ------------------------------------------------------------------ #
    #  Upload                                                               #
    # ------------------------------------------------------------------ #

    @app.route("/api/images/upload", methods=["POST"])
    def api_upload_image():
        """Accept a file upload and save it to the upload directory."""
        try:
            if "file" not in request.files:
                return jsonify({"error": "No file provided"}), 400

            f = request.files["file"]
            if not f.filename:
                return jsonify({"error": "Empty filename"}), 400

            ext = Path(f.filename).suffix.lower()
            if ext not in _ALLOWED_EXTS:
                return jsonify({"error": f"Unsupported file type: {ext}"}), 400

            _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            unique_name = f"{uuid.uuid4().hex}{ext}"
            save_path = _UPLOAD_DIR / unique_name
            f.save(str(save_path))

            thumbnail = _encode_image_thumbnail(str(save_path))
            return jsonify({
                "success": True,
                "path": str(save_path),
                "name": unique_name,
                "thumbnail": thumbnail,
            })
        except Exception as exc:
            logger.error(f"api_upload_image error: {exc}")
            return jsonify({"error": str(exc)}), 500

    # ------------------------------------------------------------------ #
    #  Save                                                                 #
    # ------------------------------------------------------------------ #

    @app.route("/api/save", methods=["POST"])
    def api_save():
        """Apply all staged changes and write to output_path."""
        try:
            # Apply section-level edits → modifies html_editor.soup in-place
            updated_soup = html_editor.apply_all_changes()

            # Re-sync image_editor's tag references to the updated soup.
            # image_editor was initialised from the same file but holds its own
            # BeautifulSoup instance; its images[*]["tag"] and diagrams[*]["container"]
            # still point into that stale tree.  decompose() on stale nodes has no
            # effect on updated_soup, so image deletions would be silently lost.
            # Re-map by src (images) and code fingerprint (diagrams) to live nodes.
            from collections import defaultdict
            src_map: dict = defaultdict(list)
            for tag in updated_soup.find_all("img"):
                src_map[tag.get("src", "")].append(tag)
            for img_info in image_editor.images:
                live = src_map.get(img_info["src"], [])
                if live:
                    img_info["tag"] = live.pop(0)

            for dgm in image_editor.diagrams:
                prefix = dgm["mermaid_code"][:40]
                for div in updated_soup.find_all("div", class_="mermaid"):
                    if prefix in div.get_text(strip=True):
                        dgm["mermaid_div"] = div
                        dgm["container"] = div.find_parent("div", class_="my-8") or div
                        break

            image_editor.soup = updated_soup

            # Save via ImageEditor (handles image delete/replace + stats update)
            saved_path = image_editor.save_changes(output_path)

            return jsonify({"success": True, "path": saved_path})
        except Exception as exc:
            logger.error(f"api_save error: {exc}")
            return jsonify({"error": str(exc)}), 500

    # ------------------------------------------------------------------ #
    #  Shutdown                                                             #
    # ------------------------------------------------------------------ #

    @app.route("/api/shutdown", methods=["POST"])
    def api_shutdown():
        """Gracefully shut down the Flask server."""
        def _stop():
            import time
            time.sleep(0.3)
            os._exit(0)

        threading.Thread(target=_stop, daemon=True).start()
        return jsonify({"success": True, "message": "Server shutting down"})

    return app


# ------------------------------------------------------------------ #
#  Utilities                                                           #
# ------------------------------------------------------------------ #

def _encode_image_thumbnail(path: str, max_size: int = 200) -> str:
    """
    Return a base64 data-URI for a local image.

    Resizes to max_size px on the longest side. Falls back to empty string
    if the file is not a valid image or Pillow is unavailable.
    """
    if not path or not Path(path).exists():
        return ""
    try:
        from PIL import Image
        import io

        with Image.open(path) as img:
            img.thumbnail((max_size, max_size))
            buf = io.BytesIO()
            fmt = img.format or "JPEG"
            if fmt not in ("JPEG", "PNG", "WEBP", "GIF"):
                fmt = "JPEG"
            img.save(buf, format=fmt)
            buf.seek(0)
            b64 = base64.b64encode(buf.read()).decode()
            mime = mimetypes.guess_type(path)[0] or "image/jpeg"
            return f"data:{mime};base64,{b64}"
    except Exception as exc:
        logger.debug(f"Thumbnail encode failed for {path}: {exc}")
        return ""


def run_editor(html_path: str, output_path: Optional[str] = None, port: int = 5757, open_browser: bool = True) -> None:
    """
    Launch the web editor server and optionally open the browser.

    Args:
        html_path: Path to the HTML lecture file.
        output_path: Where to save edited file.
        port: Port number (default: 5757).
        open_browser: Whether to open the browser automatically.
    """
    app = create_app(html_path, output_path)

    if open_browser:
        import webbrowser

        def _open():
            import time
            time.sleep(0.8)
            webbrowser.open(f"http://localhost:{port}")

        threading.Thread(target=_open, daemon=True).start()

    print(f"\n🌐  LectureForge 편집기 시작됨")
    print(f"   URL   : http://localhost:{port}")
    print(f"   파일  : {Path(html_path).name}")
    print(f"   저장  : {output_path or Path(html_path).stem + '_edited.html'}")
    print(f"\n   종료  : 브라우저에서 '종료' 버튼 클릭, 또는 Ctrl+C\n")

    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
