"""Offline safety checks for the public OpenCode catalogue gate."""

from copy import deepcopy
from datetime import datetime
import io
import json
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from tools.opencode import catalog


def model_fixture(model_id=catalog.DEFAULT_MODEL):
    """Minimal shape taken from the public catalogue, without real user data."""
    return {
        "id": model_id,
        "type": "chat",
        "limit": {"context": 200000, "output": 32000},
        "cost": {
            "text": {
                "input": {"price": 0, "cache": {"read": 0}},
                "output": {"price": 0},
            }
        },
        "api": {
            "chat-completions": {
                "base_url": catalog.INFERENCE_BASE_URL,
            }
        },
        "description": "Synthetic metadata that must not be returned wholesale",
    }


class CatalogResponse(io.BytesIO):
    def __init__(self, body, *, status=200, url=catalog.CATALOG_URL):
        super().__init__(body)
        self.status = status
        self.url = url
        self.read_sizes = []

    def geturl(self):
        return self.url

    def read(self, size=-1):
        self.read_sizes.append(size)
        return super().read(size)


def response_for(document, **kwargs):
    body = document if isinstance(document, bytes) else json.dumps(document).encode("utf-8")
    return CatalogResponse(body, **kwargs)


class FreeCatalogTests(unittest.TestCase):
    def test_allowed_models_use_one_public_get_and_return_only_reviewed_metadata(self):
        for model_id in catalog.ALLOWED_MODELS:
            for cache_write in (None, 0):
                with self.subTest(model=model_id, cache_write=cache_write):
                    model = model_fixture(model_id)
                    if cache_write is not None:
                        model["cost"]["text"]["input"]["cache"]["write"] = cache_write
                    response = response_for({"data": [model]})
                    opener = Mock(return_value=response)
                    policy = catalog.MODEL_POLICIES[model_id]
                    result = catalog.verify_free_model(
                        model_id,
                        synthetic_demo=policy["synthetic_only"],
                        accept_model_policy=policy["requires_policy_consent"],
                        opener=opener,
                    )
                    opener.assert_called_once()
                    request = opener.call_args.args[0]
                    self.assertEqual(request.full_url, catalog.CATALOG_URL)
                    self.assertEqual(request.get_method(), "GET")
                    self.assertIsNone(request.data)
                    headers = {key.lower(): value for key, value in request.header_items()}
                    self.assertEqual(set(headers), {"user-agent", "accept"})
                    self.assertTrue(headers["user-agent"].startswith("Mozilla/5.0"))
                    self.assertEqual(headers["accept"], "application/json")
                    self.assertEqual(opener.call_args.kwargs, {"timeout": 15})
                    self.assertEqual(response.read_sizes, [catalog.MAX_CATALOG_BYTES + 1])
                    self.assertEqual(result["id"], model_id)
                    self.assertEqual(result["context_limit"], 200000)
                    self.assertEqual(result["output_limit"], 32000)
                    self.assertEqual(
                        result["prices"],
                        {"input": 0, "output": 0, "cache_read": 0, "cache_write": cache_write},
                    )
                    self.assertEqual(result["source"], catalog.CATALOG_URL)
                    self.assertEqual(result["policy_source"], catalog.POLICY_URL)
                    self.assertIn("no constituye una auditoría independiente", result["privacy"])
                    self.assertEqual(result["model_policy"], dict(policy))
                    self.assertEqual(result["policy_fingerprint"], catalog.policy_fingerprint(model_id))
                    self.assertEqual(result["synthetic_only"], policy["synthetic_only"])
                    self.assertEqual(result["requires_policy_consent"], policy["requires_policy_consent"])
                    self.assertIsNotNone(datetime.fromisoformat(result["verified_at"]).utcoffset())
                    self.assertNotIn("description", result)
                    self.assertNotIn("api", result)
                    self.assertNotIn("data", result)

    def test_unreviewed_models_are_rejected_before_any_request(self):
        for model_id in (
            "glm-5.3-flash", "jev", "opencode/glm-5.3-flash-free",
            "glm-5.3-flash-free ", "https://example.invalid/model", "", None, True, [],
        ):
            with self.subTest(model=model_id):
                opener = Mock()
                with self.assertRaises(catalog.CatalogVerificationError):
                    catalog.verify_free_model(model_id, opener=opener)
                opener.assert_not_called()

    def test_all_present_prices_must_be_numeric_zero_including_new_cost_dimensions(self):
        paths = (
            ("text", "input", "price"),
            ("text", "output", "price"),
            ("text", "input", "cache", "read"),
            ("text", "input", "cache", "write"),
            ("images", "input", "price"),
        )
        for path in paths:
            for bad_value in (0.01, -1, True, False, "0", None, [], float("nan"), float("inf")):
                with self.subTest(path=path, price=bad_value):
                    model = model_fixture()
                    target = model["cost"]
                    for key in path[:-1]:
                        target = target.setdefault(key, {})
                    target[path[-1]] = bad_value
                    with self.assertRaises(catalog.CatalogVerificationError):
                        catalog.verify_free_model(
                            opener=Mock(return_value=response_for({"data": [model]}))
                        )

    def test_missing_ambiguous_retired_or_malformed_entries_fail_closed(self):
        documents = [
            {}, {"data": None}, {"data": {}}, {"data": []}, {"data": [None]},
            {"data": [model_fixture(), model_fixture()]},
        ]
        modifications = (
            (("cost",), None),
            (("cost", "text", "input", "cache"), {}),
            (("cost", "text", "output"), {}),
            (("api",), None),
            (("limit", "context"), True),
            (("limit", "context"), "200000"),
            (("limit", "output"), 0),
            (("limit", "output"), -1),
            (("status",), "deprecated"),
            (("status",), "disabled"),
            (("status",), "unknown"),
            (("status",), []),
            (("type",), "decision"),
        )
        for path, value in modifications:
            model = model_fixture()
            target = model
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            documents.append({"data": [model]})
        for document in documents:
            with self.subTest(document=document):
                with self.assertRaises(catalog.CatalogVerificationError):
                    catalog.verify_free_model(
                        opener=Mock(return_value=response_for(document))
                    )

    def test_invalid_ambiguous_or_oversized_json_is_not_accepted(self):
        payloads = (
            b"not JSON", b"\xff", b'{"data":[],"data":[]}',
            b'{"data":[],"unexpected":NaN}',
            b'{"data":[],"unexpected":Infinity}',
            b" " * (catalog.MAX_CATALOG_BYTES + 1),
        )
        for payload in payloads:
            with self.subTest(payload_prefix=payload[:50]):
                response = response_for(payload)
                with self.assertRaises(catalog.CatalogVerificationError):
                    catalog.verify_free_model(opener=Mock(return_value=response))
                self.assertEqual(response.read_sizes, [catalog.MAX_CATALOG_BYTES + 1])

    def test_production_opener_refuses_redirects_and_metadata_cannot_change_destination(self):
        production_opener = Mock()
        production_opener.open.return_value = response_for({"data": [model_fixture()]})
        with patch.object(catalog, "build_opener", return_value=production_opener) as builder:
            catalog.verify_free_model()
        redirect_handler = builder.call_args.args[0]
        self.assertIsNone(
            redirect_handler.redirect_request(None, None, 302, "Found", {}, "https://example.invalid/")
        )
        for status, url in ((302, catalog.CATALOG_URL), (403, catalog.CATALOG_URL),
                            (200, "https://example.invalid/catalog")):
            with self.subTest(status=status, url=url):
                with self.assertRaises(catalog.CatalogVerificationError):
                    catalog.verify_free_model(
                        opener=Mock(return_value=response_for({"data": [model_fixture()]}, status=status, url=url))
                    )
        for destination in (
            "http://opencode.ai/inference/openai/v1", "https://example.invalid/v1",
            catalog.INFERENCE_BASE_URL + "/", catalog.INFERENCE_BASE_URL + "?token=fake",
        ):
            with self.subTest(destination=destination):
                model = model_fixture()
                model["api"]["chat-completions"]["base_url"] = destination
                with self.assertRaises(catalog.CatalogVerificationError):
                    catalog.verify_free_model(
                        opener=Mock(return_value=response_for({"data": [model]}))
                    )

    def test_transport_failure_stops_without_retry_or_exposing_details(self):
        marker = "synthetic-private-error-marker"
        for error in (
            URLError(marker), TimeoutError(marker),
            HTTPError(catalog.CATALOG_URL, 429, marker, {}, io.BytesIO(marker.encode())),
        ):
            with self.subTest(error=type(error).__name__):
                opener = Mock(side_effect=error)
                with self.assertRaises(catalog.CatalogVerificationError) as caught:
                    catalog.verify_free_model(opener=opener)
                opener.assert_called_once()
                self.assertNotIn(marker, str(caught.exception))
                self.assertIsNone(caught.exception.__cause__)

    def test_price_change_is_rechecked_each_run_without_reusing_a_previous_success(self):
        free = model_fixture()
        changed = deepcopy(free)
        changed["cost"]["text"]["output"]["price"] = 0.001
        opener = Mock(side_effect=(response_for({"data": [free]}), response_for({"data": [changed]})))
        first = catalog.verify_free_model(opener=opener)
        self.assertEqual(first["prices"]["output"], 0)
        with self.assertRaises(catalog.CatalogVerificationError):
            catalog.verify_free_model(opener=opener)
        self.assertEqual(opener.call_count, 2)

    def test_new_model_policies_require_both_synthetic_data_and_explicit_consent_before_io(self):
        restricted = [
            model_id for model_id, policy in catalog.MODEL_POLICIES.items()
            if policy["requires_policy_consent"]
        ]
        self.assertEqual(set(restricted), {
            "longcat-2.5-free", "beam-free", "mimo-v2.6-flash-free",
            "nemotron-3.5-lightning-free",
            "big-pickle", "iceman-free", "inkling-2-small-free", "flint-40b-free",
            "nemotron-3-ultra-free", "nemotron-3.5-super-vl-free",
        })
        for model_id in restricted:
            for synthetic, consent in (
                (False, False), (True, False), (False, True),
                (1, True), (True, 1), ("true", True), (True, "true"),
            ):
                with self.subTest(model=model_id, synthetic=synthetic, consent=consent):
                    opener = Mock()
                    with self.assertRaises(catalog.CatalogVerificationError):
                        catalog.verify_free_model(
                            model_id, synthetic_demo=synthetic,
                            accept_model_policy=consent, opener=opener,
                        )
                    opener.assert_not_called()

    def test_consent_never_bypasses_price_or_model_availability_checks(self):
        for model_id, policy in catalog.MODEL_POLICIES.items():
            if not policy["requires_policy_consent"]:
                continue
            for changed in ("paid", "missing"):
                with self.subTest(model=model_id, changed=changed):
                    model = model_fixture(model_id)
                    model["cost"]["text"]["output"]["price"] = 0.001
                    document = {"data": [model] if changed == "paid" else []}
                    opener = Mock(return_value=response_for(document))
                    with self.assertRaises(catalog.CatalogVerificationError):
                        catalog.verify_free_model(
                            model_id, synthetic_demo=True,
                            accept_model_policy=True, opener=opener,
                        )
                    opener.assert_called_once()

    def test_model_privacy_exceptions_are_not_given_the_original_zero_retention_claim(self):
        self.assertEqual(set(catalog.ALLOWED_MODELS), {
            "glm-5.3-flash-free", "deepseek-v4.1-flash-free", "minimax-m3.1-flash-free",
            "longcat-2.5-free", "beam-free", "mimo-v2.6-flash-free", "nemotron-3.5-lightning-free",
            "big-pickle", "iceman-free", "inkling-2-small-free", "flint-40b-free",
            "nemotron-3-ultra-free", "nemotron-3.5-super-vl-free",
        })
        self.assertEqual(set(catalog.ALLOWED_MODELS), set(catalog.MODEL_POLICIES))
        for policy in catalog.MODEL_POLICIES.values():
            self.assertEqual(policy["policy_reviewed_on"], "2026-11-15")
        original_ids = {
            "glm-5.3-flash-free", "deepseek-v4.1-flash-free", "minimax-m3.1-flash-free",
        }
        for model_id in original_ids:
            policy = catalog.MODEL_POLICIES[model_id]
            self.assertFalse(policy["synthetic_only"])
            self.assertFalse(policy["requires_policy_consent"])
            self.assertEqual(policy["training_use"], "not_used_declared")
            self.assertIn("el proveedor no conserva", policy["retention_note"])
        beam = catalog.MODEL_POLICIES["beam-free"]
        self.assertIn("30 días", beam["retention_note"])
        self.assertIn("no se eliminan de inmediato", beam["retention_note"])
        mimo = catalog.MODEL_POLICIES["mimo-v2.6-flash-free"]
        self.assertEqual(mimo["training_use"], "model_improvement_possible")
        self.assertIn("podrían utilizarse para mejorar", mimo["privacy"])
        nvidia = catalog.MODEL_POLICIES["nemotron-3.5-lightning-free"]
        self.assertEqual(nvidia["training_use"], "security_and_product_improvement_logging")
        self.assertIn("Solo para pruebas", nvidia["privacy"])
        longcat = catalog.MODEL_POLICIES["longcat-2.5-free"]
        self.assertIn("China", longcat["hosting_note"])
        self.assertIn("100 solicitudes al día", longcat["quota_note"])
        self.assertIn("no aplica ni mide", longcat["quota_note"])

    def test_added_policies_preserve_their_specific_retention_training_and_regional_limits(self):
        for model_id in ("big-pickle", "iceman-free", "inkling-2-small-free", "flint-40b-free",
                         "nemotron-3-ultra-free", "nemotron-3.5-super-vl-free"):
            with self.subTest(model=model_id):
                policy = catalog.MODEL_POLICIES[model_id]
                self.assertIs(policy["synthetic_only"], True)
                self.assertIs(policy["requires_policy_consent"], True)
                self.assertNotIn("el proveedor no conserva", policy["retention_note"])
        big_pickle = catalog.MODEL_POLICIES["big-pickle"]
        self.assertEqual(big_pickle["training_use"], "model_improvement_possible")
        self.assertIn("no publica un plazo fijo", big_pickle["retention_note"])
        iceman = catalog.MODEL_POLICIES["iceman-free"]
        self.assertEqual(iceman["training_use"], "model_improvement_declared")
        self.assertIn("conserva datos", iceman["privacy"])
        self.assertIn("no publica un plazo fijo", iceman["retention_note"])
        inkling = catalog.MODEL_POLICIES["inkling-2-small-free"]
        self.assertEqual(inkling["training_use"], "training_and_monitoring_possible")
        self.assertIn("regiones", inkling["availability_note"])
        self.assertIn("monitorización", inkling["retention_note"])
        flint = catalog.MODEL_POLICIES["flint-40b-free"]
        self.assertIn("30 días", flint["retention_note"])
        self.assertEqual(flint["training_use"], "model_improvement_possible")
        lightning = catalog.MODEL_POLICIES["nemotron-3.5-lightning-free"]
        for model_id in ("nemotron-3-ultra-free", "nemotron-3.5-super-vl-free"):
            for key in ("privacy", "training_use", "retention_note", "availability_note"):
                with self.subTest(model=model_id, field=key):
                    self.assertEqual(catalog.MODEL_POLICIES[model_id][key], lightning[key])

    def test_policy_fingerprint_is_stable_distinct_by_model_and_independent_of_mapping_order(self):
        hashes = {model: catalog.policy_fingerprint(model) for model in catalog.ALLOWED_MODELS}
        self.assertEqual(len(set(hashes.values())), 13)
        for model_id, expected in hashes.items():
            with self.subTest(model=model_id):
                self.assertRegex(expected, r"^[0-9a-f]{64}$")
                self.assertEqual(catalog.policy_fingerprint(model_id), expected)
                reversed_policy = dict(reversed(list(catalog.MODEL_POLICIES[model_id].items())))
                with patch.object(catalog, "MODEL_POLICIES", {model_id: reversed_policy}):
                    self.assertEqual(catalog.policy_fingerprint(model_id), expected)

    def test_every_policy_field_change_invalidates_the_previous_fingerprint(self):
        model_id = "big-pickle"
        original = dict(catalog.MODEL_POLICIES[model_id])
        fingerprint = catalog.policy_fingerprint(model_id)
        for key, value in original.items():
            changed = dict(original)
            changed[key] = not value if type(value) is bool else value + " (changed policy fixture)"
            with self.subTest(field=key), patch.object(catalog, "MODEL_POLICIES", {model_id: changed}):
                self.assertNotEqual(catalog.policy_fingerprint(model_id), fingerprint)
        with patch.object(catalog, "MODEL_POLICIES", {"other-approved-id": original}):
            self.assertNotEqual(catalog.policy_fingerprint("other-approved-id"), fingerprint)

    def test_policy_fingerprint_rejects_unknown_or_ambiguous_ids_without_io(self):
        with patch.object(catalog, "build_opener") as opener:
            for model_id in ("jev", "opencode/big-pickle", "big-pickle ", "", None, True, []):
                with self.subTest(model=model_id), self.assertRaises(catalog.CatalogVerificationError):
                    catalog.policy_fingerprint(model_id)
            opener.assert_not_called()

    def test_model_policies_are_immutable_and_returned_metadata_cannot_relax_future_checks(self):
        with self.assertRaises(TypeError):
            catalog.MODEL_POLICIES["paid-model"] = {}
        with self.assertRaises(TypeError):
            catalog.MODEL_POLICIES["beam-free"]["requires_policy_consent"] = False
        result = catalog.verify_free_model(
            "beam-free", synthetic_demo=True, accept_model_policy=True,
            opener=Mock(return_value=response_for({"data": [model_fixture("beam-free")]})),
        )
        result["model_policy"]["requires_policy_consent"] = False
        result["model_policy"]["privacy"] = "overridden fixture"
        opener = Mock()
        with self.assertRaises(catalog.CatalogVerificationError):
            catalog.verify_free_model("beam-free", synthetic_demo=True, opener=opener)
        opener.assert_not_called()


if __name__ == "__main__":
    unittest.main()
