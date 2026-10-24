import unittest

from install_offline_model import _links_to_urls, _unique_urls


class OfflineInstallerHelperTests(unittest.TestCase):
    def test_https_links_are_preserved(self):
        self.assertEqual(_links_to_urls(["https://example.org/model.argosmodel"]), ["https://example.org/model.argosmodel"])

    def test_ipfs_links_use_two_gateways(self):
        urls = _links_to_urls(["ipfs://QmExampleCid"])
        self.assertEqual(urls, [
            "https://ipfs.io/ipfs/QmExampleCid",
            "https://dweb.link/ipfs/QmExampleCid",
        ])

    def test_url_list_is_deduplicated(self):
        self.assertEqual(_unique_urls(["https://a", "", "https://a", "https://b"]), ["https://a", "https://b"])


if __name__ == "__main__":
    unittest.main()
