import importlib.util
import io
import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location("cms", Path(__file__).resolve().parents[1] / "server/cms_mcp.py")
cms = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cms)


class Response(io.BytesIO):
    def __init__(self, data, content_type):
        super().__init__(data)
        self.headers = {"Content-Type": content_type}


class LiveCMS(unittest.TestCase):
    def test_transport_accepts_sse_and_skips_notifications(self):
        data = b'event: message\ndata: {"jsonrpc":"2.0","method":"progress"}\n\nevent: message\ndata: {"jsonrpc":"2.0","id":1,"result":{"docs":[]}}\n\n'
        client = cms.CMSClient()
        client.token = "local-test-only"
        client.opener = Mock()
        client.opener.open.return_value = Response(data, "text/event-stream")
        self.assertEqual(client.rpc("tools/list"), {"docs": []})
        request = client.opener.open.call_args.args[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer local-test-only")

    def test_transport_accepts_json(self):
        client = cms.CMSClient()
        client.opener = Mock()
        client.opener.open.return_value = Response(b'{"id":1,"result":{"tools":[]}}', "application/json")
        self.assertEqual(client.rpc("tools/list"), {"tools": []})

    def test_private_collections_and_unknown_tools_are_blocked(self):
        store = cms.StoreTools()
        store.client.call = Mock()
        for name, args in (("raw_get", {"collection": "orders", "id": 1}),
                           ("delete_products", {"ids": [1]}),
                           ("get_shop_info", {"collection": "users"}),
                           ("get_shop_info", {"collection": "payments"})):
            with self.subTest(name=name, args=args), self.assertRaises(cms.MCPError):
                store.call(name, args)
        store.client.call.assert_not_called()

    def test_product_payload_excludes_hidden_and_internal_fields(self):
        store = cms.StoreTools()
        store.client.call = Mock(return_value={"totalDocs": 3, "docs": [
            {"id": 1, "visible": False, "title": "hidden"},
            {"id": 2, "visible": True, "notForSale": True, "title": "not for sale"},
            {"id": 3, "visible": True, "title": "visible", "supplierCost": 99,
             "variants": [{"price": 250000, "stockCount": 10, "cost": 123}]},
        ]})
        result = json.loads(store.call("find_products", {"query": "visible"})["content"][0]["text"])
        self.assertEqual([p["id"] for p in result["docs"]], [3])
        self.assertNotIn("supplierCost", result["docs"][0])
        self.assertNotIn("cost", result["docs"][0]["variants"][0])

    def test_repeated_lookups_refresh_the_result(self):
        store = cms.StoreTools()
        store.client.call = Mock(side_effect=[
            {"docs": [{"id": 1, "visible": True, "variants": [{"stockCount": 10}]}]},
            {"docs": [{"id": 1, "visible": True, "variants": [{"stockCount": 0}]}]},
        ])
        answers = [json.loads(store.call("get_products", {"ids": [1]})["content"][0]["text"]) for _ in range(2)]
        self.assertEqual([x["docs"][0]["variants"][0]["stockCount"] for x in answers], [10, 0])

    def test_upstream_failure_does_not_become_empty_stock(self):
        store = cms.StoreTools()
        store.client.call = Mock(side_effect=cms.MCPError("Unavailable"))
        with self.assertRaises(cms.MCPError):
            store.call("find_products", {"query": "test"})

    def test_shop_content_uses_public_ids_and_authenticated_mcp_documents(self):
        store = cms.StoreTools()
        store.client.opener = Mock()
        store.client.opener.open.return_value = Response(b'{"docs":[{"id":1}],"totalPages":1}', "application/json")
        store.client.call = Mock(return_value={"doc": {"id": 1, "name": "Store", "address": "Current address", "internalNote": "private"}})
        result = json.loads(store.call("get_shop_info", {"collection": "store-locations"})["content"][0]["text"])
        self.assertEqual(result["docs"][0]["address"], "Current address")
        self.assertNotIn("internalNote", result["docs"][0])
        store.client.call.assert_called_once_with("raw_get", {"collection": "store-locations", "id": 1, "locale": "vi", "depth": 0})


if __name__ == "__main__":
    unittest.main()
