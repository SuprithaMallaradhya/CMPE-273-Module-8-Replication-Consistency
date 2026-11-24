"""Behavioral checks for asynchronous replication and recovery."""

import unittest

from inventory import InventorySystem


class InventoryTests(unittest.TestCase):
    def test_successful_replication(self):
        with InventorySystem() as system:
            write = system.update(11)
            self.assertEqual(system.read("primary"), write)
            system.wait_for_version(write.version)
            self.assertEqual(system.read("secondary"), write)

    def test_stale_read_and_recovery(self):
        with InventorySystem() as system:
            system.pause_replication()
            write = system.update(9)
            self.assertEqual(system.read("primary").stock, 9)
            self.assertEqual(system.read("secondary").stock, 10)
            with self.assertRaises(TimeoutError):
                system.wait_for_version(write.version, timeout=0.02)
            system.resume_replication()
            system.wait_for_version(write.version)
            self.assertEqual(system.read("primary"), system.read("secondary"))

    def test_queued_writes_converge_to_latest_version(self):
        with InventorySystem() as system:
            system.pause_replication()
            for stock in (9, 8, 7, 10):
                write = system.update(stock)
            self.assertEqual(system.read("secondary").version, 0)
            system.resume_replication()
            system.wait_for_version(write.version)
            self.assertEqual(system.read("secondary"), write)
            self.assertEqual(write.version, 4)

    def test_invalid_inputs(self):
        with InventorySystem() as system:
            for stock in (-1, 1.5, True, "9"):
                with self.assertRaises(ValueError):
                    system.update(stock)
            with self.assertRaises(ValueError):
                system.read("unknown")


if __name__ == "__main__":
    unittest.main()
