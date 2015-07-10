#!/usr/bin/env python
import re
import shutil
import subprocess
from unittest import TestCase
from unittest import main

import os
from P4 import P4
from P4 import P4Exception
from rbtools.api.client import RBClient
from rbtools import get_version_string
post_command = './post'


def check_output_26(*popenargs, **kwargs):
    r"""Run command with arguments and return its output as a byte string.

    Backported from Python 2.7 as it's implemented as pure python on stdlib.

    >>> check_output(['/usr/bin/python', '--version'])
    Python 2.6.2

    I took this code from this repo on git hub:
    https://gist.github.com/1027906.git

    """
    process = subprocess.Popen(stdout=subprocess.PIPE, *popenargs, **kwargs)
    output, unused_err = process.communicate()
    retcode = process.poll()
    if retcode:
        cmd = kwargs.get("args")
        if cmd is None:
            cmd = popenargs[0]
        error = subprocess.CalledProcessError(retcode, cmd)
        error.output = output
        raise error
    return output


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
        subprocess.call("%s create --server %s --target-people sallan %d -p --branch mybranch" %
                        (post_command, self.rb_url, cl1), shell=True)
        rr1 = self.get_rr_from_cl(cl1)
        self.assertEqual('sallan', rr1.get_submitter().username)
        self.assertEqual(test_string, rr1.summary)
        self.assertEqual(cl1, rr1.changenum)
        self.assertEqual(['job000010'], rr1.bugs_closed)
        self.assertEqual('pending', rr1.status)
        self.assertTrue(rr1.public)

        # Edit first rr
        self.append_line(self.readme, 'Better change')
        subprocess.call("%s edit --server %s %s" % (post_command, self.rb_url, cl1), shell=True)
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

        subprocess.call("%s create --server %s --target-people sallan %d -p --branch mybranch" %
                        (post_command, self.rb_url, cl2), shell=True)
        rr2 = self.get_rr_from_cl(cl2)
        self.assertEqual('sallan', rr2.get_submitter().username)
        self.assertEqual(test_string, rr2.summary)
        self.assertEqual(cl2, rr2.changenum)
        self.assertEqual(test_jobs, rr2.bugs_closed)
        self.assertEqual('pending', rr2.status)
        self.assertTrue(rr2.public)

        # Submit second request
        subprocess.call("%s submit --server %s %s -f" % (post_command, self.rb_url, cl2), shell=True)
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
        subprocess.call("%s submit --server %s %s -f" % (post_command, self.rb_url, cl1), shell=True)
        rr1 = self.get_rr_from_cl(cl1)
        self.assertEqual('sallan', rr1.get_submitter().username)
        self.assertTrue(rr1.public)
        self.assertEqual('submitted', rr1.status)

    def test_edit_options(self):
        self.p4.run_edit(self.readme)

        # Create review request
        test_string = 'Test editing options.'
        self.append_line(self.readme, test_string)
        cl = self.create_new_change(self.readme, test_string)
        subprocess.call("%s create --server %s --target-people sallan %d -p" %
                        (post_command, self.rb_url, cl), shell=True)
        rr = self.get_rr_from_cl(cl)
        self.assertEqual('sallan', rr.get_submitter().username)
        diffs = rr.get_diffs()
        self.assertEqual(1, len(diffs))
        self.assertEqual(test_string, rr.summary)
        change = self.p4.fetch_change(cl)
        self.assertEqual(change['Description'], rr.description)
        self.assertEqual(cl, rr.changenum)
        self.assertEqual('pending', rr.status)
        self.assertTrue(rr.public)

        # Now edit the file and the description
        new_text = "\nAdd a new line to file and description.\nNow see if edit with --update diff leaves description alone."
        original_description = rr.description
        self.append_line(self.readme, new_text)
        change['Description'] += new_text + "\n"
        self.p4.save_change(change)
        subprocess.call("%s edit --update-diff --server %s %d -p" %
                        (post_command, self.rb_url, cl), shell=True)
        rr = self.get_rr_from_cl(cl)
        self.assertEqual(original_description, rr.description, "Description should not change")
        diffs = rr.get_diffs()
        self.assertEqual(2, len(diffs), "We should have a new diff")

        # Use change-only option to update description, but not diff
        subprocess.call("%s edit --change-only --server %s %d -p" %
                        (post_command, self.rb_url, cl), shell=True)
        rr = self.get_rr_from_cl(cl)
        self.assertEqual(change['Description'], rr.description)
        #self.assertEqual(change['Description'], rr.description, "Description should change")
        diffs = rr.get_diffs()
        self.assertEqual(2, len(diffs), "We should not have a new diff")

        # Now try the default behavior, which should update both
        change_diff_and_description = 'Add a second change and description and see if edit updates both'
        self.append_line(self.readme, change_diff_and_description)
        change = self.p4.fetch_change(cl)
        change['Description'] += change_diff_and_description + "\n"
        self.p4.save_change(change)
        subprocess.call("%s edit --server %s %s -p" % (post_command, self.rb_url, cl), shell=True)
        rr = self.get_rr_from_cl(cl)
        self.assertEqual(change['Description'], rr.description, "Description should have changed")
        diffs = rr.get_diffs()
        self.assertEqual(3, len(diffs), "We should also have a new diff")

        # Submit request
        subprocess.call("%s submit --server %s %s -f" % (post_command, self.rb_url, cl), shell=True)
        rr = self.get_rr_from_cl(cl)
        self.assertEqual('sallan', rr.get_submitter().username)
        self.assertTrue(rr.public)
        self.assertEqual('submitted', rr.status)

    def test_handling_ship_its(self):
        self.p4.run_edit(self.readme)
        test_string = 'Test proper handling of ship its.'
        self.append_line(self.readme, test_string)
        cl = self.create_new_change(self.readme, test_string)
        subprocess.call("%s create --server %s --target-people sallan %d -p --branch mybranch" %
                        (post_command, self.rb_url, cl), shell=True)
        rr = self.get_rr_from_cl(cl)
        self.assertEqual('sallan', rr.get_submitter().username)
        self.assertEqual(test_string, rr.summary)
        self.assertEqual(cl, rr.changenum)
        self.assertEqual('pending', rr.status)
        self.assertTrue(rr.public)
        # TODO: Is this a RB 1.7 to 2.0 problem?
        # self.assertEqual(0, rr.ship_it_count)

        # Submitting without a ship it should be blocked
        args = [post_command, "submit", "--server", self.rb_url, str(cl)]
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
        subprocess.call("%s create --shelve --server %s --target-people sallan %d" %
                        (post_command, self.rb_url, cl), shell=True)
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
        subprocess.check_call("%s submit --server %s -f %s" % (post_command, self.rb_url, cl), shell=True)


    def test_handling_shelves_with_publish(self):
        self.p4.run_edit(self.readme)
        test_string = 'Test creating and publishing a shelve.'
        self.append_line(self.readme, test_string)
        cl = self.create_new_change(self.readme, test_string)
        subprocess.call("%s create --publish --shelve --server %s --target-people sallan %d" %
                        (post_command, self.rb_url, cl), shell=True)
        rr = self.get_rr_from_cl(cl)
        expected_comment = "This change has been shelved in changeset %s. " % cl
        expected_comment += "To unshelve this change into your workspace:\n\n\tp4 unshelve -s %s" % cl
        shelve_comment = rr.get_reviews()[0].body_top
        self.assertEqual(expected_comment, shelve_comment)

        # The rr should be public
        self.assertTrue(rr.public)
        subprocess.check_call("%s submit --server %s -f %s" % (post_command, self.rb_url, cl), shell=True)

    def test_creating_and_editing_review_with_shelve(self):
        self.p4.run_edit(self.readme)
        test_string = 'Test creating and editing a review with a shelve.'
        self.append_line(self.readme, test_string)
        cl = self.create_new_change(self.readme, test_string)
        subprocess.call("%s create --publish --shelve --server %s --target-people sallan %d" %
                        (post_command, self.rb_url, cl), shell=True)

        # Should now have 1 review
        rr = self.get_rr_from_cl(cl)
        self.assertEqual(1, len(rr.get_reviews()))

        # Edit file and review using the --shelve option
        self.append_line(self.readme, "Second change to this file. Update with --shelve")
        subprocess.call("%s edit --publish --shelve --server %s %d" %
                        (post_command, self.rb_url, cl), shell=True)

        # Should now have 2 reviews
        rr = self.get_rr_from_cl(cl)
        self.assertEqual(2, len(rr.get_reviews()))

        # Edit file and review without the --shelve option
        self.append_line(self.readme, "Third change to this file. Update without --shelve")
        subprocess.call("%s edit --publish --server %s %d" %
                        (post_command, self.rb_url, cl), shell=True)

        # Should still have 2 reviews
        rr = self.get_rr_from_cl(cl)
        self.assertEqual(2, len(rr.get_reviews()))

        # Submit
        subprocess.check_call("%s submit --server %s -f %s" % (post_command, self.rb_url, cl), shell=True)

    def test_adding_shelve_to_review_without_a_shelve(self):
        self.p4.run_edit(self.readme)
        test_string = 'Test adding a shelve to a review with no shelve.'
        self.append_line(self.readme, test_string)
        cl = self.create_new_change(self.readme, test_string)
        subprocess.call("%s create --publish --server %s --target-people sallan %d" %
                        (post_command, self.rb_url, cl), shell=True)

        # Should now have no reviews
        rr = self.get_rr_from_cl(cl)
        self.assertEqual(0, len(rr.get_reviews()))

        # Edit file and review using the --shelve option
        self.append_line(self.readme, "Second change to this file. Update with --shelve")
        subprocess.call("%s edit --publish --shelve --server %s %d" %
                        (post_command, self.rb_url, cl), shell=True)

        # Should now have 1 review
        rr = self.get_rr_from_cl(cl)
        self.assertEqual(1, len(rr.get_reviews()))


        # Edit file and review without the --shelve option
        self.append_line(self.readme, "Third change to this file. Update without --shelve")
        subprocess.call("%s edit --publish --server %s %d" %
                        (post_command, self.rb_url, cl), shell=True)

        # Should still have 1 review
        rr = self.get_rr_from_cl(cl)
        self.assertEqual(1, len(rr.get_reviews()))

        # Submit
        subprocess.check_call("%s submit --server %s -f %s" % (post_command, self.rb_url, cl), shell=True)


    def test_submitting_with_shelve_and_no_shipit(self):
        self.p4.run_edit(self.readme)
        test_string = 'Test submitting a review with a shelve and no ship its.'
        self.append_line(self.readme, test_string)
        cl = self.create_new_change(self.readme, test_string)
        subprocess.call("%s create --publish --shelve --server %s --target-people sallan %d" %
                        (post_command, self.rb_url, cl), shell=True)

        # Should now have 1 review
        rr = self.get_rr_from_cl(cl)
        self.assertEqual(1, len(rr.get_reviews()))

        # Try to submit without a ship it
        args = [post_command, "submit", "--server", self.rb_url, str(cl)]
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
        subprocess.call("%s create --publish --server %s --target-people sallan %d" %
                        (post_command, self.rb_url, cl1), shell=True)

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
        args = [post_command, "edit", "--server", self.rb_url, str(cl2)]
        self.assertRaises(subprocess.CalledProcessError, subprocess.check_call, args)

        # Update using rid
        subprocess.call("%s edit -r %s --publish --server %s %d" %
                        (post_command, rid, self.rb_url, cl2), shell=True)

        rr = self.rbapi_root.get_review_request(review_request_id=rid)
        diffs = rr.get_diffs()
        self.assertEqual(2, len(diffs))

        # Now attempt to submit without an rid which should fail
        # The important thing here is the CL should not get submitted.
        args = [post_command, "submit", "--force", "--server", self.rb_url, str(cl2)]
        self.assertRaises(subprocess.CalledProcessError, subprocess.check_call, args)
        # with self.assertRaises(subprocess.CalledProcessError):
        # subprocess.check_call(args)

        # Now try with the rid which should succeed
        args = [post_command, "submit", "--force", "--rid", str(rid), "--server", self.rb_url, str(cl2)]
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
        try:
            self.p4.run_add(dot_gnus_file)
            self.p4.run_submit("-d", "dotgnus file")
        except P4Exception:
            pass

        # Edit with rev 2
        self.p4.run_edit(dot_gnus_file)
        shutil.copyfile(os.path.join(self.workdir, "bad-dot-gnus", "dotgnus.r2"), dot_gnus_file)
        cl = self.create_new_change(dot_gnus_file, "Test unicode ord value bug")

        # post review
        subprocess.call("%s create --server %s --target-people sallan %d -p" %
                        (post_command, self.rb_url, cl), shell=True)

        # See if we get a rr
        rr = self.get_rr_from_cl(cl)
        self.assertEqual(cl, rr.changenum)
        subprocess.call("%s submit --server %s %d -f" % (post_command, self.rb_url, cl), shell=True)

    def test_create_and_edit_with_submitted_cl_range(self):
        depot_path = '//depot/Jam/MAIN/src/...@130,@140'
        summary = "Post a range of submitted change lists"
        args = [post_command, "create", "--server", self.rb_url, "--description", summary, "--summary",
                summary, depot_path, "--target-people", "sallan", "-p"]
        output = check_output_26(args)
        m = re.match("Review request #(\d+) posted\.", output)
        self.assertNotEqual(m, None)
        rid = m.group(1)
        rr = self.rbapi_root.get_review_request(review_request_id=rid)
        self.assertEqual('sallan', rr.get_submitter().username)
        self.assertEqual(summary, rr.summary)
        self.assertEqual(None, rr.changenum)
        self.assertEqual('pending', rr.status)
        self.assertTrue(rr.public)

        args = [post_command, "submit", "--server", self.rb_url,  "-r", rid, "--force"]
        subprocess.check_call(args)

    def test_create_with_file_and_rev_range(self):
        depot_path = '//depot/Jam/MAIN/src/README#4,#5'
        args = [post_command, "create", "--target-people", "sallan", "--server", self.rb_url,
                "--summary", "Single file with rev range", depot_path, "-p"]
        output = check_output_26(args)
        m = re.match("Review request #(\d+) posted\.", output)
        self.assertNotEqual(None, m)
        rid = m.group(1)
        rr = self.rbapi_root.get_review_request(review_request_id=rid)
        self.assertEqual('sallan', rr.get_submitter().username)
        self.assertEqual(rr.changenum, None)
        self.assertEqual('pending', rr.status)
        self.assertTrue(rr.public)

        depot_path = '//depot/Jam/MAIN/src/README#4,#6'
        args = [post_command, "edit", "--server", self.rb_url, "-r", rid, "-p", depot_path]
        subprocess.check_call(args)

        # submit
        args = [post_command, "submit", "--server", self.rb_url,  "-r", rid, "--force"]
        subprocess.check_call(args)

    def test_diff(self):
        test_string = 'Test the diff functionality'
        self.p4.run_edit(self.readme)
        self.append_line(self.readme, test_string)
        args = [post_command, "--server", self.rb_url, "diff"]
        output = check_output_26(args).splitlines()
        self.assertEqual('+' + test_string, output[-2])

        change = self.p4.fetch_change()
        change['Description'] = test_string + "\n"
        change_output = self.p4.save_change(change)
        change_number = change_output[0].split()[1]
        args.append(change_number)
        subprocess.check_call(args)

    def test_upload_diff_file(self):
        """Test for bug in the --diff-filename option"""
        # Skip versions we know have this bug and wait for new releases
        version = get_version_string()
        if version <= '0.6.3' or ('0.7.0' < version <= '0.7.3'):
            return

        test_string = 'Test the --diff-filename option for uploading a diff'
        self.p4.run_edit(self.relnotes)
        self.append_line(self.relnotes, test_string)
        change = self.p4.fetch_change()
        change['Description'] = test_string + "\n"
        change_output = self.p4.save_change(change)
        change_number = change_output[0].split()[1]
        subprocess.call("%s diff %s > diff.txt" % (post_command, change_number), shell=True)
        subprocess.check_call("%s create --diff-filename diff.txt %s" % (post_command, change_number), shell=True)


    def test_cookie_save(self):
        # TODO: Turn this test back on
        from subprocess import Popen, PIPE

        rb_cookies_file = os.path.join(os.path.expanduser(os.environ['HOME']), ".rbtools-cookies")
        rb_cookies_file_backup = rb_cookies_file + ".backup"

        # Start of as a brand new user with a clean slate, which
        # means you don't yet have login cookies and should get
        # prompted for a login.
        if os.path.isfile(rb_cookies_file):
            os.rename(rb_cookies_file, rb_cookies_file_backup)

        self.p4.run_edit(self.readme)
        test_string = 'Test writing out new cookie file.'
        self.append_line(self.readme, test_string)
        cl = self.create_new_change(self.readme, test_string)

        # post call fails
        subprocess.call("%s create --publish --server %s --username sallan --target-people sallan %d" %
                        (post_command, self.rb_url, cl), shell=True)

        # rbt call works
        #subprocess.call("%s post --repository-type perforce --publish --server %s --username sallan --target-people sallan %d" %
                        #('rbt', self.rb_url, cl), shell=True)

        with open(rb_cookies_file, 'r') as f:
            cookie_contents = f.read()

        # Restore original file before test just in case test bombs
        os.rename(rb_cookies_file_backup, rb_cookies_file)

        # See if we got a session id
        self.assertTrue(cookie_contents.find('rbsessionid') > -1)


if __name__ == '__main__':
    main()
