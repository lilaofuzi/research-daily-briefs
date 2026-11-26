import copy
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from archive import (ROOT, EXCEL_NOTICE, daily_path, digest, identity, indexes, load,
                     normalize_doi, rebuild, save_brief, validate_brief)
from build_site import build
from generate_brief import (RemoteError, Reject, allowed, exact_pub_date, generate,
                            paper_evidence, policy_evidence, response, text_from_response)
from import_archive import import_records


def paper():
    # Deliberately synthetic; tests never write fixtures into production archive/.
    item = {"id": "doi:10.1234/test", "kind": "paper", "doi": "10.1234/test",
        "title": "Synthetic mechanobiology test paper", "journal": "TEST ONLY",
        "publication_date": "2026-11-24", "publication_date_basis": "test fixture",
        "topics": ["LLPS", "核力学"], "keywords": ["condensate", "nucleus"],
        "summary": "测试摘要，不是真实论文。", "significance": "测试", "limitations": "仅测试数据",
        "editors_pick": True, "pick_reason": "测试精选", "source_url": "https://doi.org/10.1234/test",
        "evidence_level": "摘要", "oa": {"status": "unavailable", "url": None, "evidence_url": None},
        "verification": {"status": "historical_unverified", "checked_at": "", "metadata_url": "", "evidence_url": "",
                         "evidence_quote": "", "fact_check": "test fixture"}}
    return item


def brief(day="2026-11-25"):
    return {"schema_version": 1, "date": day, "title": "TEST ONLY 归档", "source_label": "摘要",
        "period": {"start": day, "end": day},
        "origin": {"kind": "historical_import", "reference": "test fixture", "model": ""},
        "generated_at": day + "T08:30:00+08:00", "body": "TEST ONLY", "notes": ["仅测试数据"],
        "database_status": {"llps_excel": "unavailable", "notice": EXCEL_NOTICE},
        "search_sources": [], "items": [paper()]}


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        shutil.copy2(ROOT / "config.json", self.root / "config.json")
        shutil.copytree(ROOT / "site", self.root / "site")
        rebuild(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_doi_normalization_and_balanced_suffix(self):
        for value in [" HTTPS://DOI.ORG/10.1234/TEST. ", "doi:10.1234/test", "https://dx.doi.org/10.1234%2FTEST"]:
            self.assertEqual(normalize_doi(value), "10.1234/test")
        self.assertEqual(normalize_doi("10.1234/abc(def)"), "10.1234/abc(def)")
        self.assertEqual(normalize_doi("10.1234/test)"), "10.1234/test")
        for value in ["10.123/bad", "10.1234/white space", "https://evil.example/10.1234/test"]:
            with self.assertRaises(ValueError): normalize_doi(value)

    def test_versioning_idempotence_and_metadata_preservation(self):
        b = brief()
        self.assertTrue(save_brief(self.root, b))
        self.assertFalse(save_brief(self.root, b))
        revised = copy.deepcopy(b)
        revised["items"][0]["summary"] = "修订摘要"
        with self.assertRaises(ValueError): save_brief(self.root, revised)
        save_brief(self.root, revised, revise=True)
        next_day = brief("2026-11-26")
        save_brief(self.root, next_day)
        index, papers = rebuild(self.root)
        self.assertEqual(len(index["briefs"]), 2)
        self.assertEqual(len(index["briefs"][0]["versions"]), 2)
        self.assertEqual(len(papers["papers"]), 1)
        self.assertEqual(len(papers["papers"][0]["occurrences"]), 2)
        self.assertEqual(len(papers["papers"][0]["metadata_versions"]), 2)
        self.assertEqual(load(self.root / "history/2026-11-25" / (digest(b) + ".json")), b)

    def test_removed_paper_retained_in_prior_metadata(self):
        b = brief(); save_brief(self.root, b)
        b["items"] = []; save_brief(self.root, b, revise=True)
        _, papers = rebuild(self.root)
        self.assertEqual(papers["papers"][0]["occurrences"], [])
        self.assertTrue(papers["papers"][0]["metadata_versions"])

    def test_future_date_duplicate_and_unsafe_links_rejected_before_writing(self):
        cases = []
        b = brief(); b["items"][0]["publication_date"] = "2027-01-01"; cases.append(b)
        b = brief(); b["items"].append(paper()); cases.append(b)
        b = brief(); b["items"][0]["source_url"] = "javascript:alert(1)"; cases.append(b)
        b = brief(); b["items"][0]["oa"]["status"] = "verified"; cases.append(b)
        for b in cases:
            with self.assertRaises(ValueError): save_brief(self.root, b)
        self.assertFalse((self.root / "archive").exists())

    def test_stage_summary_does_not_create_daily_records(self):
        b = brief(); b["source_label"] = "阶段汇总"; b["period"] = {"start": "2026-10-01", "end": "2026-11-23"}
        save_brief(self.root, b)
        index, _ = rebuild(self.root)
        self.assertEqual([x["date"] for x in index["briefs"]], ["2026-11-25"])
        self.assertEqual(index["briefs"][0]["period"]["start"], "2026-10-01")

    def test_unknown_historical_publication_date_is_not_invented(self):
        b = brief(); b["items"][0]["publication_date"] = None
        validate_brief(b)
        b["origin"]["kind"] = "github_actions_independent"
        with self.assertRaises(ValueError): validate_brief(b)

    def test_batch_import_validates_all_before_writing(self):
        b = brief(); bad = brief("2026-11-26"); bad["origin"]["reference"] = ""
        path = self.root / "import.json"; path.write_text(json.dumps([b, bad]))
        with self.assertRaises(ValueError): import_records(path, self.root)
        self.assertFalse((self.root / "archive").exists())

    def test_hash_corruption_detected(self):
        b = brief(); save_brief(self.root, b)
        path = next((self.root / "history").rglob("*.json"))
        b["body"] = "tampered"; path.write_text(json.dumps(b))
        with self.assertRaisesRegex(ValueError, "Corrupt history"): indexes(self.root)

    def test_build_whitelist_and_stale_index_guard(self):
        (self.root / ".env").write_text("DO_NOT_PUBLISH=test")
        (self.root / "legacy").mkdir(); (self.root / "legacy/private.zip").write_bytes(b"test")
        save_brief(self.root, brief())
        with self.assertRaisesRegex(ValueError, "Stale"): build(self.root)
        rebuild(self.root); dist = build(self.root)
        self.assertFalse((dist / ".env").exists())
        self.assertFalse((dist / "legacy").exists())
        self.assertTrue((dist / "archive/2026/11/2026-11-25.json").exists())

    def test_missing_key_and_past_generation_leave_archive_unchanged(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RemoteError, "Missing repository Secret"): generate(self.root)
            with self.assertRaisesRegex(ValueError, "only for today"): generate(self.root, "2020-01-01")
        self.assertFalse((self.root / "archive").exists())

    def test_full_generation_pipeline_and_repeat_skip(self):
        day = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
        source = "https://example.org/research"
        title = "Synthetic mechanobiology test paper"
        evidence = "Synthetic test abstract describing condensate properties and nuclear mechanics. " * 5
        quote = "Synthetic test abstract describing condensate properties"
        pid = "doi:10.1234/test"
        calls = []
        def http_mock(url, hosts, payload=None, key=None):
            if "crossref.org" in url:
                return json.dumps({"message": {"DOI":"10.1234/test", "title":[title],
                    "type":"journal-article", "published-online":{"date-parts":[list(map(int, day.split('-')))]},
                    "container-title":["TEST"], "abstract":evidence}})
            if "ebi.ac.uk" in url:
                return json.dumps({"resultList":{"result":[{"doi":"10.1234/test", "isOpenAccess":"Y", "pmcid":"PMC123456"}]}})
            calls.append(payload)
            if len(calls) == 1:
                return json.dumps({"status":"completed", "output":[
                    {"type":"web_search_call", "status":"completed", "action":{"sources":[{"url":source}]}},
                    {"type":"message", "content":[{"type":"output_text", "text":"SYNTHETIC RESEARCH"}]}]})
            results = [None,
                {"candidates":[{"kind":"paper", "doi":"HTTPS://DOI.ORG/10.1234/TEST", "title":title,
                    "source_url":source,"publication_date":day,"evidence_quote":"", "topics":["LLPS"],"keywords":["condensate"]}]},
                {"drafts":[{"id":pid,"summary":"测试摘要", "significance":"测试意义", "limitations":"仅摘要证据",
                    "evidence_quote":quote, "editors_pick":True, "pick_reason":"测试精选"}]},
                {"reviews":[{"id":pid,"passed":True,"reason":"测试复核通过"}]}]
            result = results[len(calls)-1]
            return json.dumps({"status":"completed", "output":[{"type":"message", "content":[{"type":"output_text", "text":json.dumps(result)}]}]})
        with patch.dict(os.environ, {"OPENAI_API_KEY":"synthetic-test-key"}, clear=True), patch("generate_brief.http", side_effect=http_mock):
            self.assertTrue(generate(self.root))
            self.assertFalse(generate(self.root))
        self.assertEqual(len(calls), 4)
        self.assertEqual(calls[0]["tools"][0]["type"], "web_search")
        self.assertEqual(calls[0]["tool_choice"], "required")
        self.assertTrue(calls[1]["text"]["format"]["strict"])
        b = load(daily_path(self.root, day))
        self.assertEqual(b["items"][0]["oa"]["url"], "https://europepmc.org/articles/PMC123456")
        self.assertEqual(b["origin"]["kind"], "github_actions_independent")
        self.assertEqual(b["database_status"]["llps_excel"], "unavailable")
        self.assertNotIn("synthetic-test-key", json.dumps(b))
        build(self.root)

    def test_crossref_publication_not_deposit_and_no_partial_guess(self):
        metadata = {"published-online":{"date-parts":[[2026,11,2]]},
                    "deposited":{"date-parts":[[2026,11,26]]}}
        self.assertEqual(exact_pub_date(metadata)[0].isoformat(), "2026-11-02")
        with self.assertRaises(Reject): exact_pub_date({"published":{"date-parts":[[2026,11]]}})

    def test_title_mismatch_and_policy_unverified_date_rejected(self):
        with patch("generate_brief.http", return_value=json.dumps({"message": {"DOI":"10.1234/test","title":["An unrelated paper"]}})):
            with self.assertRaisesRegex(Reject,"title mismatch"):
                paper_evidence({"doi":"10.1234/test","title":"Correct different title"}, {}, None)
        c = {"source_url":"https://nsfc.gov.cn/test", "title":"测试基金通知", "publication_date":"2026-11-25", "evidence_quote":"测试的官方政策正文内容与日期"}
        with patch("generate_brief.http", return_value="<title>测试基金通知</title><p>2026-11-25 测试的官方政策正文内容与日期</p>"):
            with self.assertRaisesRegex(Reject, "date not independently verified"):
                policy_evidence(c, {"policy_domains":["nsfc.gov.cn"]}, None)

    def test_refusal_incomplete_and_missing_web_search_fail(self):
        for r in [{"status":"incomplete"}, {"status":"completed","output":[{"content":[{"type":"refusal"}]}]}]:
            with self.assertRaises(RemoteError): text_from_response(r)
        raw = json.dumps({"status":"completed","output":[{"content":[{"type":"output_text","text":"no search"}]}]})
        with patch("generate_brief.http", return_value=raw):
            with self.assertRaisesRegex(RemoteError, "search did not complete"):
                response(load(self.root / "config.json"), "test", "test", search=True)

    def test_official_domain_matching(self):
        self.assertTrue(allowed("https://www.nsfc.gov.cn/path", ["nsfc.gov.cn"]))
        for url in ["https://nsfc.gov.cn.evil.org", "http://nsfc.gov.cn", "https://x@nsfc.gov.cn", "https://nsfc.gov.cn:8080"]:
            self.assertFalse(allowed(url, ["nsfc.gov.cn"]))


if __name__ == "__main__":
    unittest.main()
