import os
import tempfile
import unittest

from cxx_vistest.runner import discover_test_lines


class DiscoverTestLinesTests(unittest.TestCase):
    def scan(self, text):
        with tempfile.NamedTemporaryFile("w", suffix=".cpp", delete=False) as f:
            f.write(text)
        try:
            return [(c.line, c.identifier) for c in discover_test_lines(f.name)]
        finally:
            os.unlink(f.name)

    def test_only_whole_line_calls(self):
        self.assertEqual(self.scan("int main() {\n"
                                   "  check_visualizer(v);\n"
                                   "\tcheck_visualizer( m_2 ) ;  \n"
                                   "  check_visualizer(v); // comment\n"
                                   "  if (x) check_visualizer(v);\n"
                                   "  check_visualizer(v.x);\n"
                                   "  check_visualizer(a, b);\n"
                                   "  // check_visualizer(v);\n"
                                   "  my_check_visualizer(v);\n"
                                   "  check_visualizer(v)\n"
                                   "}\n"),
                         [(2, "v"), (3, "m_2")])


if __name__ == "__main__":
    unittest.main()
