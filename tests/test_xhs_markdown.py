import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("xhs_markdown", Path(__file__).resolve().parents[1] / "scripts/xhs_markdown.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class MarkdownTests(unittest.TestCase):
    def test_replies_and_duplicates(self):
        comment = {"id": "1", "content": "第一行\n第二行", "user_info": {"nickname": "甲"},
                   "sub_comments": [{"id": "2", "content": "回复"}]}
        self.assertEqual(module.comment_lines([comment, comment]),
                         ["- 甲：第一行\n  第二行", "  - 匿名：回复"])

    def test_note_archive_and_missing_comments(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root)
            (directory / "manifest.json").write_text(json.dumps({"metadata": [{"title": "标题", "description": "正文\n下一行"}], "media": [str(directory / "图片 1.jpg")]}), encoding="utf-8")
            module.save(directory, "123", "https://example.com", {})
            text = (directory / "post.md").read_text(encoding="utf-8")
            self.assertIn("# 标题", text)
            self.assertIn("正文\n下一行", text)
            self.assertIn("无法判断是否没有评论", text)
            self.assertIn("%20", text)
