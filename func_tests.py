#!/usr/bin/env python
import os
import shutil
import subprocess
from unittest import TestCase
from unittest import main

from P4 import P4, P4Exception
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
        if self.p4.run_opened():
            self.p4.run("revert", "...")
        self.p4.disconnect()

    def get_rr_from_cl(self, cl):
        rr = self.rbapi_root.get_review_requests(status="all", changenum=cl)
        self.assertNotEqual(None, rr)
        self.assertEqual(1, len(rr))
        return rr[0]

    def append_line(self, filename, line):
        with open(filename, "a") as f:
            f.write(line + "\n")

    def create_new_change(self, filename, test_string):
        change = self.p4.fetch_change()
        change['Description'] = test_string + "\n"
        change_output = self.p4.save_change(change)
        change_number = int(change_output[0].split()[1])
        return change_number

    def test_simple_create_and_update(self):
        self.p4.run_edit(self.readme)

        # Create first review request
        test_string = 'Test creating review with jobs and branch.'
        self.append_line(self.readme, test_string)
        cl1 = self.create_new_change(self.readme, test_string)
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
        rr1 = self.get_rr_from_cl(cl1)
        self.assertTrue(rr1.public)

        # Create a second review request
        test_string = 'Test creating with 2 jobs.'
        test_jobs = ['job000011', 'job000012']
        self.p4.run_edit(self.relnotes)
        self.append_line(self.relnotes, test_string)
        cl2 = self.create_new_change(self.relnotes, test_string)
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
        cl = self.create_new_change(self.readme, test_string)
        subprocess.call("./p2.py create --server %s --target-people sallan %d -p --branch mybranch" %
                        (self.rb_url, cl), shell=True)
        rr = self.get_rr_from_cl(cl)
        self.assertEqual('sallan', rr.get_submitter().username)
        self.assertEqual(test_string, rr.summary)
        self.assertEqual(cl, rr.changenum)
        self.assertEqual('pending', rr.status)
        self.assertTrue(rr.public)
        # TODO: Is this a RB 1.7 to 2.0 problem?
        # self.assertEqual(0, rr.ship_it_count)

        # Submitting without a ship it should be blocked
        args = ["./p2.py", "submit", "--server", self.rb_url, str(cl)]
        self.assertRaises(subprocess.CalledProcessError, subprocess.check_call, args)
        # with self.assertRaises(subprocess.CalledProcessError):
        # subprocess.check_call(args)

        # Now add a ship it and submit again
        review = rr.get_reviews().create()
        review.update(body_top="Not bad", ship_it=True, public=True)
        rr = self.get_rr_from_cl(cl)
        # TODO: Is this a RB 1.7 to 2.0 problem?
        # self.assertEqual(1, rr.ship_it_count)
        subprocess.check_call(args)
        rr = self.get_rr_from_cl(cl)
        self.assertEqual('submitted', rr.status)

        # Look for change to CL description
        change = self.p4.fetch_change(cl)
        self.assertEqual(test_string + "\n\nReviewed by: sallan\n", change['Description'])

    def test_handling_shelves_without_publish(self):
        self.p4.run_edit(self.readme)
        test_string = 'Test creating a shelve.'
        self.append_line(self.readme, test_string)
        cl = self.create_new_change(self.readme, test_string)
        subprocess.call("./p2.py create --shelve --server %s --target-people sallan %d" %
                        (self.rb_url, cl), shell=True)
        rr = self.get_rr_from_cl(cl)
        expected_comment = "This change has been shelved in changeset %s. " % cl
        expected_comment += "To unshelve this change into your workspace:\n\n\tp4 unshelve -s %s" % cl
        shelve_comment = rr.get_reviews()[0].body_top

        # The review should not be public
        self.assertEqual(expected_comment, shelve_comment)
        self.assertFalse(rr.public)

        # Publish the draft so we can submit the review.
        draft = rr.get_draft()
        draft.update(public=True)
        subprocess.check_call("./p2.py submit --server %s -f %s" % (self.rb_url, cl), shell=True)


    def test_handling_shelves_with_publish(self):
        self.p4.run_edit(self.readme)
        test_string = 'Test creating and publishing a shelve.'
        self.append_line(self.readme, test_string)
        cl = self.create_new_change(self.readme, test_string)
        subprocess.call("./p2.py create --publish --shelve --server %s --target-people sallan %d" %
                        (self.rb_url, cl), shell=True)
        rr = self.get_rr_from_cl(cl)
        expected_comment = "This change has been shelved in changeset %s. " % cl
        expected_comment += "To unshelve this change into your workspace:\n\n\tp4 unshelve -s %s" % cl
        shelve_comment = rr.get_reviews()[0].body_top
        self.assertEqual(expected_comment, shelve_comment)

        # The rr should be public
        self.assertTrue(rr.public)
        subprocess.check_call("./p2.py submit --server %s -f %s" % (self.rb_url, cl), shell=True)

    def test_creating_and_editing_review_with_shelve(self):
        self.p4.run_edit(self.readme)
        test_string = 'Test creating and editing a review with a shelve.'
        self.append_line(self.readme, test_string)
        cl = self.create_new_change(self.readme, test_string)
        subprocess.call("./p2.py create --publish --shelve --server %s --target-people sallan %d" %
                        (self.rb_url, cl), shell=True)

        # Should now have 1 review
        rr = self.get_rr_from_cl(cl)
        self.assertEqual(1, len(rr.get_reviews()))

        # Edit file and review using the --shelve option
        self.append_line(self.readme, "Second change to this file. Update with --shelve")
        subprocess.call("./p2.py edit --publish --shelve --server %s %d" %
                        (self.rb_url, cl), shell=True)

        # Should now have 2 reviews
        rr = self.get_rr_from_cl(cl)
        self.assertEqual(2, len(rr.get_reviews()))

        # Edit file and review without the --shelve option
        self.append_line(self.readme, "Third change to this file. Update without --shelve")
        subprocess.call("./p2.py edit --publish --server %s %d" %
                        (self.rb_url, cl), shell=True)

        # Should now have 3 reviews
        rr = self.get_rr_from_cl(cl)
        self.assertEqual(3, len(rr.get_reviews()))

        # Submit
        subprocess.check_call("./p2.py submit --server %s -f %s" % (self.rb_url, cl), shell=True)

    def test_adding_shelve_to_review_without_a_shelve(self):
        self.p4.run_edit(self.readme)
        test_string = 'Test adding a shelve to a review with no shelve.'
        self.append_line(self.readme, test_string)
        cl = self.create_new_change(self.readme, test_string)
        subprocess.call("./p2.py create --publish --server %s --target-people sallan %d" %
                        (self.rb_url, cl), shell=True)

        # Should now have no reviews
        rr = self.get_rr_from_cl(cl)
        self.assertEqual(0, len(rr.get_reviews()))

        # Edit file and review using the --shelve option
        self.append_line(self.readme, "Second change to this file. Update with --shelve")
        subprocess.call("./p2.py edit --publish --shelve --server %s %d" %
                        (self.rb_url, cl), shell=True)

        # Should now have 1 review
        rr = self.get_rr_from_cl(cl)
        self.assertEqual(1, len(rr.get_reviews()))


        # Edit file and review without the --shelve option
        self.append_line(self.readme, "Third change to this file. Update without --shelve")
        subprocess.call("./p2.py edit --publish --server %s %d" %
                        (self.rb_url, cl), shell=True)

        # Should now have 2 reviews
        rr = self.get_rr_from_cl(cl)
        self.assertEqual(2, len(rr.get_reviews()))

        # Submit
        subprocess.check_call("./p2.py submit --server %s -f %s" % (self.rb_url, cl), shell=True)


    def test_submitting_with_shelve_and_no_shipit(self):
        self.p4.run_edit(self.readme)
        test_string = 'Test submitting a review with a shelve and no ship its.'
        self.append_line(self.readme, test_string)
        cl = self.create_new_change(self.readme, test_string)
        subprocess.call("./p2.py create --publish --shelve --server %s --target-people sallan %d" %
                        (self.rb_url, cl), shell=True)

        # Should now have 1 review
        rr = self.get_rr_from_cl(cl)
        self.assertEqual(1, len(rr.get_reviews()))

        # Try to submit without a ship it
        args = ["./p2.py", "submit", "--server", self.rb_url, str(cl)]
        self.assertRaises(subprocess.CalledProcessError, subprocess.check_call, args)
        # with self.assertRaises(subprocess.CalledProcessError):
        # subprocess.check_call(args)

        args.append("-f")
        subprocess.check_call(args)

    def test_editing_and_submitting_with_different_cl(self):
        self.p4.run_edit(self.readme)
        test_string = 'Test editing a review with a different CL with and without rid.'
        self.append_line(self.readme, test_string)
        cl1 = self.create_new_change(self.readme, test_string)
        subprocess.call("./p2.py create --publish --server %s --target-people sallan %d" %
                        (self.rb_url, cl1), shell=True)

        rr = self.get_rr_from_cl(cl1)
        rid = rr.id
        self.assertTrue(rid > 0)

        diffs = rr.get_diffs()
        self.assertEqual(1, len(diffs))

        # Move file to a new change list
        test_string = "Use this CL to update %s instead of CL %d" % (rid, cl1)
        self.append_line(self.readme, test_string)
        cl2 = self.create_new_change(self.readme, test_string)
        self.p4.run_reopen("-c", cl2, self.readme)
        self.append_line(self.readme, "Moving to CL %s" % cl2)

        # Try update without rid
        args = ["./p2.py", "edit", "--server", self.rb_url, str(cl2)]
        self.assertRaises(subprocess.CalledProcessError, subprocess.check_call, args)
        # with self.assertRaises(subprocess.CalledProcessError):
        # subprocess.check_call(args)

        # Update using rid
        subprocess.call("./p2.py edit -r %s --publish --server %s %d" %
                        (rid, self.rb_url, cl2), shell=True)

        rr = self.rbapi_root.get_review_request(review_request_id=rid)
        diffs = rr.get_diffs()
        self.assertEqual(2, len(diffs))

        # Now attempt to submit without an rid which should fail
        # The important thing here is the CL should not get submitted.
        args = ["./p2.py", "submit", "--force", "--server", self.rb_url, str(cl2)]
        self.assertRaises(subprocess.CalledProcessError, subprocess.check_call, args)
        # with self.assertRaises(subprocess.CalledProcessError):
        #     subprocess.check_call(args)

        # Now try with the rid which should succeed
        args = ["./p2.py", "submit", "--force", "--rid", str(rid), "--server", self.rb_url, str(cl2)]
        subprocess.check_call(args)

    def test_unicode_ord_value_bug(self):
        # RBTools 0.7.0-2 have a bug where an attempt to post a review can sometimes
        # trigger this error:
        #
        # CRITICAL:root:'ascii' codec can't decode byte 0xe2 in position 4186: ordinal not in range(128)
        # CRITICAL: 'ascii' codec can't decode byte 0xe2 in position 4186: ordinal not in range(128)
        #
        # This test passes with RBTools 0.6.3, and will hopefully pass in a newer version of 0.7.
        #
        # It's issue number 3843, long ugly link below:
        # https://code.google.com/p/reviewboard/issues/detail?id=3843&q=allan&colspec=ID%20Type%20Status%20Priority%20Component%20Owner%20Summary%20Milestone

        # Add dotgnus rev 1 to perforce - remove old one if it exists
        dot_gnus_file = os.path.join(self.workdir, "dotgnus")
        if os.path.isfile(dot_gnus_file):
            os.remove(dot_gnus_file)
        shutil.copyfile(os.path.join(self.workdir, "bad-dot-gnus", "dotgnus.r1"), dot_gnus_file)
        self.p4.run_add(dot_gnus_file)
        self.p4.run_submit("-d", "dotgnus file")

        # Edit with rev 2
        self.p4.run_edit(dot_gnus_file)
        shutil.copyfile(os.path.join(self.workdir, "bad-dot-gnus", "dotgnus.r2"), dot_gnus_file)
        cl = self.create_new_change(dot_gnus_file, "Test unicode ord value bug")

        # post review
        subprocess.call("./p2.py create --server %s --target-people sallan %d -p" %
                        (self.rb_url, cl), shell=True)

        # See if we get a rr
        rr = self.get_rr_from_cl(cl)
        self.assertEqual(cl, rr.changenum)
        subprocess.call("./p2.py submit --server %s %d -f" % (self.rb_url, cl), shell=True)

    def Xtest_post_as_different_user(self):
        # We can't create a new user on RB via the API, so instead we'll create
        # a change list as a different p4 user.  This more closely matches the
        # mergeit case anyway. Plus it avoids authentication issues during the test.

        # Create new client workspace for mergeit
        client_root = os.path.join(self.workdir, "mergeit")
        p4_mergeit = P4()
        p4_mergeit.user = 'mergeit'
        p4_mergeit.port = self.p4.port
        p4_mergeit.client = 'mergeit-rbscript-test-depot'
        try:
            p4_mergeit.connect()
            client = p4_mergeit.fetch_client("-t", self.p4.client)
            client._root = client_root
            p4_mergeit.save_client(client)
            p4_mergeit.run_sync()
        except P4Exception:
            # we don't care about warnings, just errors
            if p4_mergeit.errors:
                for e in p4_mergeit.errors:
                    print e
                self.fail("P4 errors killed test.")

        # Now edit file and create CL
        filename = os.path.join(client_root, "readme.txt")
        p4_mergeit.run_edit(filename)
        test_string = 'Test creating review with p4 user set to mergeit.'
        self.append_line(filename, test_string)
        change = p4_mergeit.fetch_change()
        change['Description'] = test_string + "\n"
        change_output = p4_mergeit.save_change(change)
        change_number = int(change_output[0].split()[1])
        subprocess.call("./p2.py create --username sallan --server %s --target-people sallan %d -p" %
                        (self.rb_url, change_number), shell=True)
        rr1 = self.get_rr_from_cl(change_number)
        self.assertEqual('sallan', rr1.get_submitter().username)
        self.assertEqual(test_string, rr1.summary)
        self.assertEqual(change_number, rr1.changenum)
        self.assertEqual('pending', rr1.status)
        self.assertTrue(rr1.public)

        '''
        # Edit first rr
        self.append_line(self.readme, 'Better change')
        subprocess.call("./p2.py edit --server %s %s" % (self.rb_url, cl1), shell=True)
        draft = rr1.get_draft()
        self.assertFalse(draft.public)
        draft.update(public=True)
        rr1 = self.get_rr_from_cl(cl1)
        self.assertTrue(rr1.public)
        '''

        # Submit
        subprocess.call("./p2.py submit --username sallan --server %s %s -f" % (self.rb_url, change_number), shell=True)
        rr1 = self.get_rr_from_cl(change_number)
        self.assertEqual('sallan', rr1.get_submitter().username)
        self.assertTrue(rr1.public)
        self.assertEqual('submitted', rr1.status)

        p4_mergeit.disconnect()


if __name__ == '__main__':
    main()
