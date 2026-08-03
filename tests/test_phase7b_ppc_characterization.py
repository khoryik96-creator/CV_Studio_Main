"""Characterization tests for the PPC placement helpers.

Locks the behaviour of the helpers extracted into ``cvstudio_ppc`` (Phase 7B):
date/name/int normalisation, placement-record normalisation, the per-run detail
cache, and the two JobAdder-client network helpers (exercised through a fake
client so no network or credentials are involved). This is a verbatim move, so
these assertions equally describe the legacy web-shell behaviour.
"""

import unittest

import cvstudio_ppc as ppc


class CleanDateTests(unittest.TestCase):
    def test_valid_date_is_isoformatted(self):
        self.assertEqual(ppc._ppc_clean_date("2026-08-03T10:30:00Z"), "2026-08-03")
        self.assertEqual(ppc._ppc_clean_date("2026-08-03"), "2026-08-03")

    def test_blank_and_invalid_return_empty(self):
        self.assertEqual(ppc._ppc_clean_date(""), "")
        self.assertEqual(ppc._ppc_clean_date(None), "")
        self.assertEqual(ppc._ppc_clean_date("not-a-date"), "")


class PersonNameTests(unittest.TestCase):
    def test_prefers_name_then_display_then_first_last(self):
        self.assertEqual(ppc._ppc_person_name({"name": "Ada Lovelace"}), "Ada Lovelace")
        self.assertEqual(ppc._ppc_person_name({"displayName": "Ada L"}), "Ada L")
        self.assertEqual(ppc._ppc_person_name({"firstName": "Ada", "lastName": "Lovelace"}), "Ada Lovelace")

    def test_non_dict_and_empty(self):
        self.assertEqual(ppc._ppc_person_name(None), "")
        self.assertEqual(ppc._ppc_person_name("Ada"), "")
        self.assertEqual(ppc._ppc_person_name({}), "")


class IntTests(unittest.TestCase):
    def test_parses_or_defaults(self):
        self.assertEqual(ppc._ppc_int("42"), 42)
        self.assertEqual(ppc._ppc_int(7), 7)
        self.assertIsNone(ppc._ppc_int("x"))
        self.assertEqual(ppc._ppc_int(None, 0), 0)


class NormalizePlacementTests(unittest.TestCase):
    def test_full_record_projection(self):
        raw = {
            "placementId": 100,
            "candidate": {"candidateId": 5, "firstName": "Grace", "lastName": "Hopper", "email": "g@example.com"},
            "job": {"jobId": 9, "jobTitle": "Engineer", "company": {"companyId": 3, "name": "Acme"}},
            "status": {"statusId": 2, "name": "Active"},
            "type": "Permanent",
            "startDate": "2026-01-15T00:00:00Z",
            "approved": True,
            "recruiters": [{"userId": 11, "name": "Rec One", "feeSplit": 100}],
            "salary": {"fee": 5000},
            "updatedAt": "2026-02-01T00:00:00Z",
        }
        out = ppc._ppc_normalize_placement(raw)
        self.assertEqual(out["placement_id"], 100)
        self.assertEqual(out["candidate_name"], "Grace Hopper")
        self.assertEqual(out["company_name"], "Acme")
        self.assertEqual(out["job_title"], "Engineer")
        self.assertEqual(out["status_name"], "Active")
        self.assertEqual(out["start_date"], "2026-01-15")
        self.assertTrue(out["approved"])
        self.assertEqual(out["recruiter_ids"], [11])
        self.assertEqual(out["placed_by_id"], 11)
        self.assertEqual(out["placed_by"], "Rec One")
        self.assertEqual(out["placement_fee"], 5000)
        self.assertEqual(out["updated_at"], "2026-02-01T00:00:00Z")

    def test_missing_names_use_fallbacks(self):
        out = ppc._ppc_normalize_placement({"candidate": {"candidateId": 7}})
        self.assertEqual(out["candidate_name"], "Candidate 7")
        out2 = ppc._ppc_normalize_placement({})
        self.assertEqual(out2["candidate_name"], "Unknown candidate")

    def test_company_falls_back_to_job_company(self):
        out = ppc._ppc_normalize_placement({"job": {"company": {"companyId": 8, "name": "JobCo"}}})
        self.assertEqual(out["company_id"], 8)
        self.assertEqual(out["company_name"], "JobCo")

    def test_multiple_recruiters_do_not_set_single_placed_by_id(self):
        out = ppc._ppc_normalize_placement({"recruiters": [{"userId": 1, "name": "A"}, {"userId": 2, "name": "B"}]})
        self.assertEqual(out["recruiter_ids"], [1, 2])
        self.assertIsNone(out["placed_by_id"])
        self.assertEqual(out["placed_by"], "A, B")

    def test_non_dict_input(self):
        self.assertEqual(ppc._ppc_normalize_placement(None)["candidate_name"], "Unknown candidate")


class DetailCacheTests(unittest.TestCase):
    def test_clear_empties_shared_cache(self):
        ppc._ppc_detail_cache[("ns", "1", "u")] = {"x": 1}
        self.assertTrue(ppc._ppc_detail_cache)
        ppc._ppc_detail_cache_clear()
        self.assertEqual(ppc._ppc_detail_cache, {})


class _FakeClient:
    """Minimal JobAdder-client stand-in recording calls, no network."""

    def __init__(self, request_json_payload=None, paginate_result=None, raise_http=None):
        self._request_json_payload = request_json_payload or {}
        self._paginate_result = paginate_result or ([], {})
        self._raise_http = raise_http
        self.request_json_calls = []
        self.paginate_calls = []

    def request_json(self, path, params=None, token=None, timeout=None, fallback=None, retries=None):
        self.request_json_calls.append({"path": path, "params": params, "token": token, "timeout": timeout, "retries": retries})
        if self._raise_http is not None:
            raise self._raise_http
        return 200, self._request_json_payload

    def paginate_offset(self, path, **kwargs):
        self.paginate_calls.append({"path": path, "kwargs": kwargs})
        return self._paginate_result


class GetJsonTests(unittest.TestCase):
    def test_returns_payload_and_forwards_retry_flag(self):
        client = _FakeClient(request_json_payload={"totalCount": 3})
        out = ppc.ppc_get_json(client, "tok", "placements", params=[("Limit", 0)], timeout=35)
        self.assertEqual(out, {"totalCount": 3})
        call = client.request_json_calls[0]
        self.assertEqual(call["token"], "tok")
        self.assertEqual(call["retries"], 1)

    def test_retry_429_false_disables_retries(self):
        client = _FakeClient(request_json_payload={})
        ppc.ppc_get_json(client, "tok", "placements", retry_429=False)
        self.assertEqual(client.request_json_calls[0]["retries"], 0)

    def test_http_error_becomes_runtime_error_with_code(self):
        import io
        import urllib.error

        http_err = urllib.error.HTTPError("u", 429, "Too Many", {"Retry-After": "5"}, io.BytesIO(b"rate limited"))
        client = _FakeClient(raise_http=http_err)
        with self.assertRaises(RuntimeError) as ctx:
            ppc.ppc_get_json(client, "tok", "placements")
        self.assertEqual(getattr(ctx.exception, "http_code", None), 429)
        self.assertEqual(getattr(ctx.exception, "retry_after", None), "5")


class FetchTypeCollectionTests(unittest.TestCase):
    def test_counts_and_diagnostics(self):
        rows = [{"placementId": 1}, {"placementId": 2}]
        client = _FakeClient(
            request_json_payload={"totalCount": 2},
            paginate_result=(rows, {"reported_total": 2, "pages": 1, "codes": []}),
        )
        get_json_calls = []

        def get_json(token, path, params=None, timeout=None, retry_429=True):
            get_json_calls.append({"token": token, "path": path, "params": params})
            return ppc.ppc_get_json(client, token, path, params=params, timeout=timeout, retry_429=retry_429)

        out_rows, diag = ppc.ppc_fetch_type_collection(client, get_json, "tok", "Permanent", [("Approved", "true")], 100)
        self.assertEqual(out_rows, rows)
        self.assertEqual(diag["type"], "Permanent")
        self.assertEqual(diag["expected"], 2)
        self.assertEqual(diag["returned"], 2)
        self.assertTrue(diag["complete"])
        self.assertFalse(diag["truncated"])
        # Count call goes through the injected get_json with the Type param appended.
        self.assertIn(("Type", "Permanent"), get_json_calls[0]["params"])


class SmokeTests(unittest.TestCase):
    def test_expected_symbols_present(self):
        for name in [
            "_ppc_clean_date", "_ppc_person_name", "_ppc_int",
            "_ppc_normalize_placement", "_ppc_detail_cache_clear",
            "ppc_get_json", "ppc_fetch_type_collection",
        ]:
            self.assertTrue(callable(getattr(ppc, name)), name)
        self.assertEqual(ppc._PPC_PLACEMENT_TYPES, ("Permanent", "Contract", "Temporary", "Credit"))


class ModuleHygieneTests(unittest.TestCase):
    def test_module_does_not_import_app(self):
        self.assertNotIn("app", getattr(ppc, "__dict__", {}))


if __name__ == "__main__":
    unittest.main()
