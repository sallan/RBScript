from unittest import TestCase
import os

from p4_sample_depot import SampleDepot


class TestSampleDepot(TestCase):
    def setUp(self):
        self.p4root = os.path.join(os.getcwd(), "foobar", "PerforceSample")

        tarball = os.path.join(os.environ['HOME'], "Projects", "sample-depot", "p4sample-depot.tar.gz")
        sd = SampleDepot(tarball, "foobar")
        self.sd = sd


    def test_init(self):
        self.assertEqual(os.path.join(os.getcwd(), "foobar", "PerforceSample"), self.sd.p4root)


    def test_p4d_command(self):
        self.assertEqual("/usr/local/bin/p4d -r %s" % self.p4root, self.sd.p4d)


    def test_start_command(self):
        expected = "/usr/local/bin/p4d -r %s -p %d -d" % (self.p4root, 1492)
        self.assertEqual(expected, self.sd.start_cmd)


    def test_stop_command(self):
        self.assertEqual("/usr/local/bin/p4 -p 1492 admin stop", self.sd.stop_cmd)
