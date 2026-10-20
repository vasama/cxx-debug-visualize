import os
import tempfile
import unittest

from cxx_debug_visualize.runner import discover_test_lines


class DiscoverTestLinesTests(unittest.TestCase):
    def scan(self, text):
        with tempfile.NamedTemporaryFile("w", suffix=".cpp", delete=False) as f:
            f.write(text)
        try:
            return [(c.line, c.identifier) for c in discover_test_lines(f.name)]
        finally:
            os.unlink(f.name)

    def test_only_whole_line_calls(self):
        self.assertEqual(
            self.scan(
                "int main() {\n"
                "  visualize(v);\n"
                "\tvisualize( m_2 ) ;  \n"
                "  visualize(v); // comment\n"
                "  if (x) visualize(v);\n"
                "  visualize(v.x);\n"
                "  visualize(a, b);\n"
                "  // visualize(v);\n"
                "  my_visualize(v);\n"
                "  visualize(v)\n"
                "}\n"
            ),
            [(2, "v"), (3, "m_2")],
        )
