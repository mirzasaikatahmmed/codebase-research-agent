import os
import tempfile
from django.test import TestCase

from agent.tools.code_explorer import get_file_summary, list_files, read_file, search_code

SAMPLE_PY = """\
class Foo:
    def bar(self):
        return 42

    def baz(self, x):
        return x * 2


def standalone(a, b):
    return a + b
"""


class ListFilesTest(TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        with open(os.path.join(self.tmpdir, "sample.py"), "w") as f:
            f.write(SAMPLE_PY)
        os.makedirs(os.path.join(self.tmpdir, "subdir"))

    def test_lists_files_and_dirs(self):
        result = list_files(self.tmpdir, ".")
        self.assertIn("sample.py", result)
        self.assertIn("subdir", result)
        self.assertIn("[DIR]", result)
        self.assertIn("[FILE]", result)

    def test_nonexistent_path(self):
        result = list_files(self.tmpdir, "nope")
        self.assertIn("not found", result.lower())


class ReadFileTest(TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "sample.py")
        with open(self.path, "w") as f:
            f.write(SAMPLE_PY)

    def test_reads_full_file(self):
        result = read_file(self.tmpdir, "sample.py")
        self.assertIn("class Foo", result)
        self.assertIn("def bar", result)
        self.assertIn("def standalone", result)

    def test_reads_line_range(self):
        result = read_file(self.tmpdir, "sample.py", start_line=1, end_line=3)
        self.assertIn("class Foo", result)
        self.assertNotIn("standalone", result)

    def test_path_traversal_blocked(self):
        result = read_file(self.tmpdir, "../../etc/passwd")
        self.assertIn("Error", result)
        self.assertIn("traversal", result)

    def test_nonexistent_file(self):
        result = read_file(self.tmpdir, "ghost.py")
        self.assertIn("not found", result.lower())


class SearchCodeTest(TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        with open(os.path.join(self.tmpdir, "sample.py"), "w") as f:
            f.write(SAMPLE_PY)

    def test_finds_string(self):
        result = search_code(self.tmpdir, "return 42")
        self.assertIn("sample.py", result)
        self.assertIn("return 42", result)

    def test_no_results(self):
        result = search_code(self.tmpdir, "xyzzy_not_found_abc")
        self.assertIn("No results", result)

    def test_file_pattern_filter(self):
        result = search_code(self.tmpdir, "return 42", file_pattern="*.py")
        self.assertIn("sample.py", result)

    def test_file_pattern_no_match(self):
        result = search_code(self.tmpdir, "return 42", file_pattern="*.js")
        self.assertIn("No results", result)


class GetFileSummaryTest(TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        with open(os.path.join(self.tmpdir, "sample.py"), "w") as f:
            f.write(SAMPLE_PY)

    def test_summary_contains_class_and_functions(self):
        result = get_file_summary(self.tmpdir, "sample.py")
        self.assertIn("class Foo", result)
        self.assertIn("def bar", result)
        self.assertIn("def standalone", result)

    def test_summary_shows_line_count(self):
        result = get_file_summary(self.tmpdir, "sample.py")
        self.assertIn("Lines:", result)
