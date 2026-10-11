"""Archive note text and the comments actually returned to the browser."""
import json
import tempfile
from pathlib import Path
from urllib.parse import quote


def comment_lines(comments, seen=None, depth=0):
    seen = seen if seen is not None else set()
    lines = []
    for comment in comments:
        if not isinstance(comment, dict):
            continue
        key = comment.get("id") or comment.get("comment_id")
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        author = (comment.get("user_info") or comment.get("user") or {}).get("nickname", "匿名")
        content = str(comment.get("content") or "").replace("\r\n", "\n")
        prefix = "  " * depth
        lines.append(f"{prefix}- {author}：" + content.replace("\n", "\n" + prefix + "  "))
        lines.extend(comment_lines(comment.get("sub_comments") or [], seen, depth + 1))
    return lines


def read_comments(directory: Path) -> dict:
    try:
        data = json.loads((directory / "comments.json").read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def comments_cached(directory: Path) -> bool:
    if not (directory / "post.md").is_file():
        return False
    try:
        status = json.loads((directory / "comments-status.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # Recognize successful archives created before cache metadata existed.
        return _captured(read_comments(directory))
    return isinstance(status, dict) and status.get("status") == "captured" and _captured(read_comments(directory))


def save(directory: Path, note_id: str, url: str, capture: dict, error=""):
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    metadata = next(iter(manifest.get("metadata") or []), {})
    note = (capture.get("notes") or {}).get(note_id) or metadata
    title = note.get("title") or note_id
    description = note.get("description") or ""
    responses = capture.get("comments") or {}
    # A disconnected refresh must not erase a previous successful archive.
    previous = read_comments(directory)
    if previous:
        merged = dict(previous)
        for key, response in responses.items():
            if key in previous and _captured({key: previous[key]}) and not _captured({key: response}):
                continue
            merged[key] = response
        responses = merged
    comments = []
    for response_url, response in responses.items():
        # Responses belong to this note navigation; retain raw pagination evidence.
        if not isinstance(response, dict) or response.get("success") is False:
            continue
        comments.extend((response.get("data") or {}).get("comments") or [])
    lines = comment_lines(comments)
    status = "已保存页面返回的评论；未保证全部评论及回复已加载。"
    if not responses:
        status = "未采集到评论响应，无法判断是否没有评论。"
    if error:
        status += "\n采集错误：" + error
    text = [f"# {title}", "", f"来源：[{note_id}]({url})", "",
            f"作者：{note.get('author') or note.get('uploader') or '未知'}", "",
            "## 正文", "", description or "（未获取到正文）", "",
            "## 评论", "", status, "", *lines, "", "## 媒体", ""]
    for media in manifest.get("media") or []:
        name = Path(media).name
        link = quote(name)
        text.append(f"![{name}]({link})" if Path(name).suffix.lower() in
                    {".jpg", ".jpeg", ".png", ".webp"} else f"[{name}]({link})")
    (directory / "post.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    _write_json(directory / "comments.json", responses)
    captured = _captured(responses)
    _write_json(directory / "comments-status.json", {
        "status": "captured" if captured else "missing", "last_error": error,
    })


def _write_json(path: Path, data: dict) -> None:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    temporary.replace(path)


def _captured(responses: dict) -> bool:
    return any(isinstance(response, dict) and response.get("success") is not False
               and isinstance(response.get("data"), dict)
               and isinstance(response["data"].get("comments"), list)
               for response in responses.values())
