"""Acceptance checks for the standalone public CATIA teaching bundle."""
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
import runpy
import unittest
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'web_portal/catia'


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.assets = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == 'script' and values.get('src'):
            self.assets.append(values['src'])
        if tag == 'link' and values.get('rel') == 'stylesheet':
            self.assets.append(values['href'])


class CatiaPublicSiteAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files, cls.data = runpy.run_path(str(ROOT / 'tools/build_catia_site.py'))['build']()

    def test_nine_complete_lessons_with_practical_evidence(self):
        counts = Counter(lesson['stage_id'] for lesson in self.data['lessons'])
        self.assertEqual(set(counts.values()), {3})
        self.assertEqual(len(counts), 3)
        for lesson in self.data['lessons']:
            with self.subTest(lesson=lesson['id']):
                self.assertGreaterEqual(len(lesson['steps']), 5)
                self.assertGreaterEqual(len(lesson['knowledge']), 2)
                self.assertGreaterEqual(len(lesson['pitfalls']), 2)
                self.assertEqual(len(lesson['quiz']), 2)
                self.assertTrue(all(step['evidence'].strip() and step['checkpoint'].strip() for step in lesson['steps']))
                self.assertTrue(all(urlsplit(source['url']).scheme == 'https' for source in lesson['sources']))

    def test_sixty_practice_items_have_stable_unique_identifiers(self):
        ids = [quiz['id'] for lesson in self.data['lessons'] for quiz in lesson['quiz']]
        for stage in self.data['stages']:
            ids.extend(quiz['id'] for quiz in stage['quizzes'])
            self.assertEqual(set(stage['prompts']), {str(step) for step in range(1, 7)})
            for prompts in stage['prompts'].values():
                self.assertEqual(len(prompts), 2)
                ids.extend(prompt['id'] for prompt in prompts)
        self.assertEqual(len(ids), 60)
        self.assertEqual(len(set(ids)), 60)

    def test_generated_artifacts_match_sources_and_exclude_runtime(self):
        for name, content in self.files.items():
            self.assertEqual((SITE / name).read_text(encoding='utf8'), content)
            self.assertNotIn('127.0.0.1', content)
            self.assertNotIn('initial-admin.txt', content)
            self.assertNotIn('graphics_tutor.sqlite3', content)
            self.assertNotIn('GRAPHICS_ADMIN_PASSWORD', content)
        self.assertGreaterEqual(len(self.data['glossary']), 12)

    def test_all_page_assets_resolve_under_a_project_subpath(self):
        parser = Links()
        parser.feed((SITE / 'index.html').read_text(encoding='utf8'))
        self.assertGreaterEqual(len(parser.assets), 3)
        for asset in parser.assets:
            self.assertFalse(urlsplit(asset).scheme, asset)
            self.assertFalse(asset.startswith('/'), asset)
            self.assertTrue((SITE / asset).is_file(), asset)
        self.assertTrue((SITE / 'practice-worksheet.txt').is_file())


if __name__ == '__main__':
    unittest.main()
