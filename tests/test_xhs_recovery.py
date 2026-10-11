import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import favorites_sync as sync
import xhs_markdown
import cdp
import browser_session


class RecoveryTests(unittest.TestCase):
    def test_note_capture_reconnects_after_broken_pipe(self):
        session = mock.Mock()
        session.harvest.side_effect = [cdp.CdpError('Broken pipe'), {'notes': {'id': {}}}]
        self.assertEqual(sync.harvest_note(session, 'https://example.com', 500), {'notes': {'id': {}}})
        session.close.assert_called_once()
        session.connect.assert_called_once()
        self.assertFalse(session._hook_installed)

    def test_browser_fallback_recovers_an_empty_extractor(self):
        args = sync.build_parser().parse_args(['sync', '--output-dir', 'unused'])
        note_id = '6a4a35e0000000001603e833'
        session = mock.MagicMock()
        session.__enter__.return_value = session
        session.harvest.return_value = {'notes': {note_id: {
            'title': 'a photo note', 'type': 'normal', 'images': ['https://cdn/full.jpg']}}}
        def transfer(source, destination, **kwargs):
            destination.write_bytes(b'full image')
            return 10
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(sync.sync_common, 'run_download', return_value=(False, 'no video formats were found')), mock.patch.object(sync, 'open_session', return_value=session), mock.patch.object(browser_session, 'download_url', side_effect=transfer):
            ok, detail = sync.xhs_download_fn(args)(Path('unused'), f'https://www.xiaohongshu.com/explore/{note_id}', Path(tmp), None, None)
            self.assertTrue(ok, detail)
            manifest = json.loads((Path(tmp) / 'manifest.json').read_text())
            self.assertEqual(manifest['kind'], 'images')
            self.assertEqual(len(manifest['media']), 1)

    def test_video_without_a_video_url_is_not_saved_as_cover(self):
        with tempfile.TemporaryDirectory() as tmp:
            ok, detail = sync.xhs_download({'type': 'video', 'images': ['https://cdn/cover.jpg']}, 'id', 'url', Path(tmp))
            self.assertFalse(ok)
            self.assertIn('refusing', detail)
            self.assertFalse((Path(tmp) / 'manifest.json').exists())

    def test_image_retry_reuses_completed_parts(self):
        record = {'type': 'normal', 'images': ['https://cdn/one.jpg', 'https://cdn/two.jpg']}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def transfer(source, destination, **kwargs):
                if source.endswith('two.jpg'):
                    raise browser_session.SessionError('network down')
                destination.write_bytes(b'one')
            with mock.patch.object(browser_session, 'download_url', side_effect=transfer):
                self.assertFalse(sync.xhs_download(record, 'id', 'url', root)[0])
            self.assertFalse((root / 'manifest.json').exists())
            def finish(source, destination, **kwargs):
                destination.write_bytes(b'two')
            with mock.patch.object(browser_session, 'download_url', side_effect=finish) as download:
                self.assertTrue(sync.xhs_download(record, 'id', 'url', root)[0])
                self.assertEqual(download.call_count, 1)
                self.assertEqual(download.call_args.args[0], 'https://cdn/two.jpg')

    def test_failed_comment_refresh_keeps_previous_comments(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'manifest.json').write_text(json.dumps({'metadata': [{'title': 'title'}]}))
            capture = {'comments': {'/api/comment': {'data': {'comments': [{'id': '1', 'content': 'keep me'}]}}}}
            xhs_markdown.save(root, 'id', 'url', capture)
            self.assertTrue(xhs_markdown.comments_cached(root))
            xhs_markdown.save(root, 'id', 'url', {}, error='Broken pipe')
            self.assertIn('keep me', (root / 'post.md').read_text())
            self.assertEqual(xhs_markdown.read_comments(root), capture['comments'])
            self.assertTrue(xhs_markdown.comments_cached(root))

    def test_retry_only_does_not_scroll_or_include_completed_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'sync-state.json').write_text(json.dumps({'items': {
                'failed': {'status': 'failed', 'url': 'https://example.com/failed'},
                'done': {'status': 'completed', 'url': 'https://example.com/done'}}}))
            args = sync.build_parser().parse_args(['sync', '--output-dir', tmp, '--retry-only', '--dry-run'])
            with mock.patch.object(sync.sync_common, 'sync_items', return_value=0) as engine, mock.patch.object(sync, 'open_session') as browser:
                self.assertEqual(sync._command_sync(args), 0)
            browser.assert_not_called()
            self.assertEqual(engine.call_args.args[0], [('xiaohongshu', 'failed', 'https://example.com/failed')])

    def test_archives_are_not_mistaken_for_downloaded_media(self):
        import download_media
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('post.md', 'comments.json', 'caption.txt', 'photo.jpg'):
                (root / name).write_bytes(b'data')
            self.assertEqual(download_media.collect_media(root), [str(root / 'photo.jpg')])

    def test_legacy_successful_comment_archive_is_reused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'post.md').write_text('existing archive')
            (root / 'comments.json').write_text(json.dumps({'/comment': {'data': {'comments': []}}}))
            self.assertTrue(xhs_markdown.comments_cached(root))
