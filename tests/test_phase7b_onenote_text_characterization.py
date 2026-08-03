"""Characterization tests for the pure OneNote content/matching helpers.

These lock the behaviour of the stateless helpers extracted from the legacy
web shell into ``cvstudio_onenote_text`` (Phase 7B-6a). They exercise the
module directly — no Flask, no network — so a regression in the parsing,
filtering or matching logic is caught in isolation.
"""

import unittest

import cvstudio_onenote_text as ot


class HtmlToTextTests(unittest.TestCase):
    def test_blocks_become_newlines_and_scripts_dropped(self):
        html = "<div>Alpha</div><p>Beta</p><script>ignore()</script><span>Gamma</span>"
        out = ot._onenote_html_to_text(html)
        self.assertIn("Alpha", out)
        self.assertIn("Beta", out)
        self.assertIn("Gamma", out)
        self.assertNotIn("ignore", out)

    def test_bytes_input_and_whitespace_collapse(self):
        out = ot._onenote_html_to_text(b"<p>One\t\tTwo</p>")
        self.assertEqual(out, "One Two")

    def test_br_does_not_double_space(self):
        out = ot._onenote_html_to_text("Line1<br/>Line2")
        self.assertNotIn("\n\n", out)

    def test_empty(self):
        self.assertEqual(ot._onenote_html_to_text(""), "")
        self.assertEqual(ot._onenote_html_to_text(None), "")


class GraphIdAndDateModeTests(unittest.TestCase):
    def test_graph_id_url_quotes(self):
        self.assertEqual(ot._onenote_graph_id("a b/c"), "a%20b%2Fc")
        self.assertEqual(ot._onenote_graph_id(None), "")

    def test_normalize_date_mode(self):
        self.assertEqual(ot._onenote_normalize_date_mode("modified"), "modified")
        self.assertEqual(ot._onenote_normalize_date_mode("lastModified"), "modified")
        self.assertEqual(ot._onenote_normalize_date_mode(""), "created")
        self.assertEqual(ot._onenote_normalize_date_mode("created"), "created")


class UrlHelpersTests(unittest.TestCase):
    def test_extract_urls_finds_http(self):
        urls = ot._onenote_extract_urls("see https://example.com/x and http://foo.test/y here")
        self.assertIn("https://example.com/x", urls)
        self.assertIn("http://foo.test/y", urls)

    def test_extract_urls_empty(self):
        self.assertEqual(ot._onenote_extract_urls(""), [])

    def test_url_parts_returns_dict_like(self):
        # Should not raise on plain text or a URL; returns a structure.
        result = ot._onenote_url_parts("https://example.com/path?q=1")
        self.assertIsNotNone(result)


class DateFilterTests(unittest.TestCase):
    def _items(self):
        return [
            {"id": "a", "createdDateTime": "2026-01-01T00:00:00Z", "lastModifiedDateTime": "2026-02-01T00:00:00Z"},
            {"id": "b", "createdDateTime": "2026-06-01T00:00:00Z", "lastModifiedDateTime": "2026-06-15T00:00:00Z"},
        ]

    def test_date_filtered_items_created_range(self):
        out = ot._onenote_date_filtered_items(self._items(), date_from_iso="2026-05-01", date_to_iso="2026-12-31", date_mode="created")
        ids = [i["id"] for i in out]
        self.assertEqual(ids, ["b"])

    def test_no_range_returns_all(self):
        out = ot._onenote_date_filtered_items(self._items())
        self.assertEqual(len(out), 2)

    def test_page_in_date_range_bounds(self):
        page = {"createdDateTime": "2026-06-01T00:00:00Z", "lastModifiedDateTime": "2026-06-15T00:00:00Z"}
        self.assertTrue(ot._onenote_page_in_date_range(page, "2026-01-01", "2026-12-31", "created"))
        self.assertFalse(ot._onenote_page_in_date_range(page, "2026-01-01", "2026-03-01", "created"))


class TextSearchAndMatchTests(unittest.TestCase):
    def test_text_search_items(self):
        items = [{"title": "Salary review"}, {"title": "Holiday"}]
        out = ot._onenote_text_search_items(items, "salary")
        self.assertEqual(len(out), 1)

    def test_manual_search_terms_splits(self):
        terms = ot._onenote_manual_search_terms("Alpha, Beta; Gamma")
        self.assertTrue(any("alpha" in t.lower() for t in terms))

    def test_match_notebook_from_manual(self):
        notebooks = [{"displayName": "Client Salaries", "id": "n1"}, {"displayName": "Personal", "id": "n2"}]
        match = ot._onenote_match_notebook_from_manual("client salaries", notebooks)
        self.assertEqual((match or {}).get("id"), "n1")

    def test_match_section_from_manual(self):
        sections = [{"displayName": "Bolttech", "id": "s1"}, {"displayName": "Other", "id": "s2"}]
        match = ot._onenote_match_section_from_manual("bolttech", sections)
        self.assertEqual((match or {}).get("id"), "s1")

    def test_link_hrefs_and_manual_candidates_do_not_raise(self):
        self.assertIsInstance(ot._onenote_link_hrefs({"links": {"oneNoteWebUrl": {"href": "https://x"}}}), list)
        candidates = ot._onenote_manual_candidates("Alpha / Beta")
        self.assertIsInstance(candidates, dict)
        self.assertIn("terms", candidates)


class XmlHelpersTests(unittest.TestCase):
    def test_xml_nodes_parses(self):
        xml = '<root xmlns="http://x"><Section name="S1" ID="{1}"/></root>'
        nodes = ot._onenote_xml_nodes(xml)
        self.assertIsInstance(nodes, list)

    def test_parse_sections_xml_returns_list(self):
        xml = '<one:Notebook xmlns:one="http://schemas.microsoft.com/office/onenote/2013/onenote" name="NB" ID="{nb}"><one:Section name="Sec" ID="{s}"/></one:Notebook>'
        out = ot._onenote_desktop_parse_sections_xml(xml, default_notebook_name="NB", default_notebook_id="{nb}")
        # Returns a (notebooks, sections) tuple of lists.
        self.assertIsInstance(out, tuple)
        self.assertEqual(len(out), 2)
        self.assertIsInstance(out[0], list)
        self.assertIsInstance(out[1], list)

    def test_iso_formats_datetime(self):
        from datetime import datetime
        s = ot._onenote_iso(datetime(2026, 1, 2, 3, 4, 5))
        self.assertIsInstance(s, str)
        self.assertIn("2026", s)


if __name__ == "__main__":
    unittest.main()
