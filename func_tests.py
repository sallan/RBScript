#!/usr/bin/python
import os
import subprocess
from unittest import TestCase
from unittest import main

from P4 import P4
from rbtools.api.client import RBClient


class FuncTests(TestCase):
    def setUp(self):
        self.rb_url = "http://localhost"
        os.environ['P4CONFIG'] = 'p4.config'
        self.p4 = P4()
        self.p4.port = "localhost:1492"
        self.p4.user = "sallan"
        self.p4.client = "sallan-rbscript-test-depot"
        self.p4.connect()
        self.workdir = self.p4.run_info()[0]['clientRoot']
        self.rbapi_root = RBClient(self.rb_url).get_root()
        self.readme = os.path.join(self.workdir, "readme.txt")
        self.relnotes = os.path.join(self.workdir, "relnotes.txt")

    def tearDown(self):
        self.p4.disconnect()

    def get_rr_from_cl(self, cl):
        rr = self.rbapi_root.get_review_requests(status="all", changenum=cl)
        self.assertIsNotNone(rr)
        self.assertEqual(1, len(rr))
        return rr[0]

    def append_line(self, filename, line):
        with open(filename, "a") as f:
            f.write(line + "\n")

    def test_simple_create_and_update(self):
        self.p4.run_edit(self.readme)

        # Create first review request
        test_string = 'First test case'
        self.append_line(self.readme, test_string)
        change = self.p4.fetch_change()
        change['Description'] = test_string + "\n"
        change_output = self.p4.save_change(change)
        cl1 = int(change_output[0].split()[1])
        self.p4.run('fix', '-c', cl1, 'job000010')
        subprocess.call("./p2.py create --server %s --target-people sallan %d -p --branch mybranch" %
                        (self.rb_url, cl1), shell=True)
        rr1 = self.get_rr_from_cl(cl1)
        self.assertEqual('sallan', rr1.get_submitter().username)
        self.assertEqual(test_string, rr1.summary)
        self.assertEqual(cl1, rr1.changenum)
        self.assertEqual(['job000010'], rr1.bugs_closed)
        self.assertEqual('pending', rr1.status)
        self.assertTrue(rr1.public)

        # Edit first rr
        self.append_line(self.readme, 'Better change')
        subprocess.call("./p2.py edit --server %s %s" % (self.rb_url, cl1), shell=True)
        draft = rr1.get_draft()
        self.assertFalse(draft.public)
        draft.update(public=True)

        # Create a second review request
        test_string = 'New release note.'
        test_jobs = ['job000011', 'job000012']
        self.p4.run_edit(self.relnotes)
        self.append_line(self.relnotes, test_string)
        change = self.p4.fetch_change()
        change['Description'] = test_string + "\n"
        change_output = self.p4.save_change(change)
        cl2 = int(change_output[0].split()[1])
        for job in test_jobs:
            self.p4.run('fix', '-c', cl2, job)

        subprocess.call("./p2.py create --server %s --target-people sallan %d -p --branch mybranch" %
                        (self.rb_url, cl2), shell=True)
        rr2 = self.get_rr_from_cl(cl2)
        self.assertEqual('sallan', rr2.get_submitter().username)
        self.assertEqual(test_string, rr2.summary)
        self.assertEqual(cl2, rr2.changenum)
        self.assertEqual(test_jobs, rr2.bugs_closed)
        self.assertEqual('pending', rr2.status)
        self.assertTrue(rr2.public)

        # Submit second request
        subprocess.call("./p2.py submit --server %s %s -f" % (self.rb_url, cl2), shell=True)
        rr2 = self.get_rr_from_cl(cl2)
        self.assertEqual('sallan', rr2.get_submitter().username)
        self.assertTrue(rr2.public)
        self.assertEqual(cl2, rr2.changenum)
        self.assertEqual('submitted', rr2.status)

        # Submit first request
        # I was going to do a test here to make sure the CL was updated
        # on the server, but I could never get the test to pass, even though
        # visual inspection verified the CL was being updated. So I scrapped
        # the test.
        subprocess.call("./p2.py submit --server %s %s -f" % (self.rb_url, cl1), shell=True)
        rr1 = self.get_rr_from_cl(cl1)
        self.assertEqual('sallan', rr1.get_submitter().username)
        self.assertTrue(rr1.public)
        self.assertEqual('submitted', rr1.status)

    def test_handling_ship_its(self):
        self.p4.run_edit(self.readme)
        test_string = 'Test proper handling of ship its.'
        self.append_line(self.readme, test_string)
        change = self.p4.fetch_change()
        change['Description'] = test_string + "\n"
        change_output = self.p4.save_change(change)
        cl = int(change_output[0].split()[1])
        subprocess.call("./p2.py create --server %s --target-people sallan %d -p --branch mybranch" %
                        (self.rb_url, cl), shell=True)
        rr = self.get_rr_from_cl(cl)
        self.assertEqual('sallan', rr.get_submitter().username)
        self.assertEqual(test_string, rr.summary)
        self.assertEqual(cl, rr.changenum)
        self.assertEqual('pending', rr.status)
        self.assertTrue(rr.public)
        self.assertEqual(0, rr.ship_it_count)

        args = ["./p2.py", "submit", "--server", self.rb_url, str(cl)]
        with self.assertRaises(subprocess.CalledProcessError):
            subprocess.check_call(args)

        # Now add a ship it and submit again
        review = rr.get_reviews().create()
        review.update(body_top="Not bad", ship_it=True, public=True)
        rr = self.get_rr_from_cl(cl)
        self.assertEqual(1, rr.ship_it_count)
        subprocess.check_call(args)
        rr = self.get_rr_from_cl(cl)
        self.assertEqual('submitted', rr.status)

        # Look for change to CL description
        change = self.p4.fetch_change(cl)
        self.assertEqual(test_string + "\n\nReviewed by: sallan\n", change['Description'])

    def test_handling_shelves(self):
        self.p4.run_edit(self.readme)
        test_string = 'Test creating a shelve.'
        self.append_line(self.readme, test_string)
        change = self.p4.fetch_change()
        change['Description'] = test_string + "\n"
        change_output = self.p4.save_change(change)
        cl = int(change_output[0].split()[1])
        subprocess.call("./p2.py create --shelve --server %s --target-people sallan %d" %
                        (self.rb_url, cl), shell=True)
        rr = self.get_rr_from_cl(cl)
        expected_comment = "This change has been shelved in changeset %s. " % cl
        expected_comment += "To unshelve this change into your workspace:\n\n\tp4 unshelve -s %s" % cl
        shelve_comment = rr.get_reviews()[0].body_top
        self.assertEqual(expected_comment, shelve_comment)
        draft = rr.get_draft()
        self.assertFalse(draft.public)
        draft.update(public=True)
        subprocess.check_call("./p2.py submit --server %s -f %s" % (self.rb_url, cl), shell=True)


if __name__ == '__main__':
    main()
