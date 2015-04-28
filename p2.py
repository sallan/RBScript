#!/usr/bin/env python
import getpass
import os
import subprocess
from subprocess import CalledProcessError
import sys
import optparse
import tempfile
import marshal
import ssl

from rbtools.commands import diff
from rbtools.commands import close
from rbtools.api.client import RBClient
from rbtools.api.errors import APIError, AuthorizationError



# Newer versions of Python are more strict about ssl verification
# and need to have verification turned off
if hasattr(ssl, '_create_unverified_context'):
    # noinspection PyProtectedMember
    ssl._create_default_https_context = ssl._create_unverified_context

POST_VERSION = "2.0"
RBTOOLS_RC_FILENAME = ".reviewboardrc"

# PDTools usage tracking
LOGHOST = ("REMOVED", "FIXME")
USERNAME = os.environ.get('LOGNAME', os.environ.get('USER', 'UNKNOWN'))
MSG_FMT = '%s:[PDTOOLS TRACKING]:%%s:%s:%%s' % (USERNAME, os.path.realpath(sys.argv[0]))

# Error codes
NO_ACTION = 0  # not an error, just print help
MISSING_RBTOOLS = 1
UNSUPPORTED_RBTOOLS = 2
UNSUPPORTED_OS = 3
UNSUPPORTED_PYTHON = 4
CONFIG_ERROR = 5
UNKNOWN_ACTION = 6
P4_EXCEPTION = 7
RB_EXCEPTION = 8
ARG_PARSER = 9

# Required Versions
PYTHON_VERSION = (2, 6)
PYTHON_VERSION_STR = '2.6'
RBTOOLS_MIN_VERSION = (0, 6, 0)
RBTOOLS_MIN_VERSION_STR = '0.6.0'
RBTOOLS_VERSION_MSG = """
Use of this script requires:

  RBTools version %s or greater
  Python %s or greater

To install the latest version of RBTools:

    $ sudo easy_install -U RBTools

""" % (RBTOOLS_MIN_VERSION_STR, PYTHON_VERSION_STR)

try:
    # noinspection PyUnresolvedReferences
    from rbtools.commands import post
    from rbtools import VERSION
    from rbtools.clients import perforce
    import rbtools.api.errors
except ImportError:
    sys.stderr.write(RBTOOLS_VERSION_MSG)
    raise SystemExit(MISSING_RBTOOLS)
else:
    if rbtools.VERSION < RBTOOLS_MIN_VERSION:
        sys.stderr.write("\nERROR: Found old version of RBTools: Version %s\n" % rbtools.get_package_version())
        sys.stderr.write(RBTOOLS_VERSION_MSG)
        raise SystemExit(UNSUPPORTED_RBTOOLS)

ACTIONS = ['create', 'edit', 'submit', 'diff']


class RBError(Exception):
    pass


class P4Error(Exception):
    pass


class RBArgParser(object):
    """Manage options and arguments for review requests"""

    def __init__(self, args):
        """Create argument parser with input argument list"""
        # self.raw_args = args[1:]
        self.edit_changelist = False
        self.shelve = False
        self.force = False
        self.debug = False
        self.publish = False
        self.parser = RBArgParser._option_parser()
        self.opts, self.args = self.parser.parse_args(args[1:])
        self.server_url = self.opts.server

        if not self.args:
            self.action = None
            return

        # Process the arguments to get action and change list number
        self.action = []
        for action in ACTIONS:
            if action in self.args:
                self.action.append(action)
                self.args.remove(action)

        if len(self.action) != 1:
            raise RBError("Please provide exactly one action: " + ' | '.join(ACTIONS))
        else:
            self.action = self.action[0]
        if len(self.args) > 1:
            raise RBError("Please provide 1 action and at most 1 change list number")
        if len(self.args) == 1:
            self.change_number = self.args[0]
        else:
            self.change_number = None
        if self.change_number is None and self.action != 'create':
            raise RBError("Need a change list number")

        # The f5_options list holds options that we don't pass on to rbt.
        self.f5_options = ['shelve', 'publish', 'force', 'edit_changelist']

        # rbt uses rid when closing a review instead of cl, so we need
        # a special case for that.
        if self.action == "submit":
            self.f5_options.append("rid")

        # These options used by us and rbt
        self.rid = self.opts.rid
        self.debug = self.opts.debug
        self.username = self.opts.username

        # Process the options separating those we handle and those we pass to rbt
        self.rbt_args = ['rbt', self.action]
        for opt, value in vars(self.opts).iteritems():
            if value:
                if opt in self.f5_options:
                    setattr(self, opt, value)
                else:
                    self.rbt_args.extend(RBArgParser._opt_to_string(opt, value))

        # The close function from rbt takes a rid, not a cl so leave the cl off
        # and add the rid later when we actually have an rid
        if self.action != 'submit' and self.change_number is not None:
            self.rbt_args.append(self.change_number)

    @staticmethod
    def _opt_to_string(opt, value):
        # Private method to convert an option name and value back to command line strings
        boolean = ['version', 'debug', 'shelve', 'force', 'edit_changelist', 'publish', 'diff_only', 'change_only']
        option_string = {
            'debug': '--debug',
            'version': '--version',
            'server': '--server',
            'shelve': '--shelve',
            'force': '--force',
            'diff_only': '--update-diff',
            'change_only': '--change-only',
            'edit_changelist': '--edit-changelist',
            'publish': '--publish',
            'target_people': '--target-people',
            'target_groups': '--target-groups',
            'branch': '--branch',
            'testing_done': '--testing-done',
            'testing_file': '--testing-done-file',
            'rid': '--review-request-id',
            'username': '--username',
        }
        args = [option_string[opt]]
        if opt not in boolean:
            args.append(value)
        return args

    @staticmethod
    def _option_parser():
        # Private method to instantiate an option parser for post
        description = """
    Create, update and submit review requests.

    This script is a wrapper to the rbt commands that come with RBTools. It
    can only be used with perforce and provides some additional functionality
    related to perforce.  The work flow is create/edit/submit. Alternatively,
    the diff command will print a Review Board compatible diff of a change list
    to STDOUT without creating or modify a review.

    The options for each command are described below.

    """

        parser = optparse.OptionParser(
            usage="%prog [OPTIONS] create|edit|submit|diff [changenum]",
            description=description
        )
        parser.add_option("-v", "--version",
                          default=False, dest="version", action="store_true",
                          help="Display version and exit.")
        parser.add_option("-d", "--debug",
                          dest="debug", action="store_true", default=False,
                          help="Display debug output.")
        parser.add_option("--server",
                          dest="server", metavar="<server_name>",
                          help="Use specified server. Default is the REVIEWBOARD_URL entry in your "
                               + RBTOOLS_RC_FILENAME + " file.")

        submit_group = optparse.OptionGroup(parser, "Submit Options")
        submit_group.add_option("-f", "--force",
                                dest="force", action="store_true", default=False,
                                help="Submit even if the review doesn't meet all requirements.")
        submit_group.add_option("-e", "--edit-changelist",
                                dest="edit_changelist", action="store_true", default=False,
                                help="Edit the change list before submitting.")

        edit_group = optparse.OptionGroup(parser, "Create and Edit Options")
        edit_group.add_option("-p", "--publish",
                              dest="publish", action="store_true", default=False,
                              help="Publish the review.")
        edit_group.add_option("-n", "--output-diff",
                              dest="output_diff_only", action="store_true", default=False,
                              help="Output diff to console and exit. Do not post.")
        edit_group.add_option("--target-groups",
                              dest="target_groups", metavar="<group [,groups]>",
                              help="Assign or replace ReviewBoard groups for this review.")
        edit_group.add_option("--target-people",
                              dest="target_people", metavar="<user [,users]>",
                              help="Assign or replace reviewers for this review.")
        edit_group.add_option("--branch",
                              dest="branch", metavar="<branch [,branch]>",
                              help="Assign or replace branches for this review. Accepts any string.")

        edit_group.add_option("--shelve",
                              dest="shelve", action="store_true", default=False,
                              help="Create or update p4 shelve for the files in the review.")
        edit_group.add_option("--update-diff",
                              dest="diff_only", action="store_true", default=False,
                              help="Uploads a new diff, but does not update information from change list.")
        edit_group.add_option("--change-only",
                              dest="change_only", action="store_true", default=False,
                              help="Updates info from change list, but does not upload diff.")
        edit_group.add_option("--testing-done",
                              dest="testing_done", metavar="<string>",
                              help="Description of testing done.")
        edit_group.add_option("--testing-done-file",
                              dest="testing_file", metavar="<filename>",
                              help="Text file containing description of testing done.")
        edit_group.add_option("-r", "--rid",
                              dest="rid", metavar="<ID>",
                              help="Upload changes to specific review by ID. Use this if your change list is different from the one associated with ID.")

        edit_group.add_option("--username",
                              dest="username", metavar="<user>",
                              help="Switch to this Review Board username. Useful if different from p4 username (e.g. mergeit). " +
                                   "The new login credentials will remain in effect until you use --username again.")

        parser.add_option_group(edit_group)
        parser.add_option_group(submit_group)
        return parser

    def print_help(self):
        """Print usage"""
        self.parser.print_help()


class P4(object):
    """
    Encapsulate perforce environment and handle calls to the perforce server.

    """

    def __init__(self, user=None, port=None, client=None):
        """
        Create an object to interact with perforce using the user, port and client
        settings provided. If any are missing, use those from the environment.
        """
        self.user = user
        self.port = port
        self.client = client
        if not all([user, port, client]):
            p4_info = self.info()
            self.user = p4_info['userName']
            self.port = p4_info['serverAddress']
            self.client = p4_info['clientName']

    def info(self):
        p4_info = self.run_G("info")
        if not p4_info:
            raise P4Error("Could not talk to the perforce server.")
        return p4_info[0]

    @staticmethod
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

    def run(self, cmd):
        """Run perforce cmd and return output as a list of output lines."""

        # Use the user, port, client settings in self if not None
        c = "p4 "
        if self.user is not None:
            c += "-u %s " % self.user
        if self.port is not None:
            c += "-p %s " % self.port
        if self.client is not None:
            c += "-c %s " % self.client
        c += cmd

        try:
            if sys.version_info < (2, 7):
                output = P4.check_output_26(c, shell=True)
            else:
                output = subprocess.check_output(c, shell=True)
        except CalledProcessError as e:
            raise P4Error("Perforce command '%s' failed\n%s" % (c, e))
        return output.splitlines()

    # noinspection PyPep8Naming
    def run_G(self, cmd, args=None, p4_input=0):
        """
        Run perforce command and marshal the IO. Returns stdout as a  dict.

        This code was copied from this perforce knowledge base page:

        http://kb.perforce.com/article/585/using-p4-g

        I modified it slightly for error checking.
        """

        # Use the user, port, client settings in self if not None
        c = "p4 -G "
        if self.user is not None:
            c += "-u %s " % self.user
        if self.port is not None:
            c += "-p %s " % self.port
        if self.client is not None:
            c += "-c %s " % self.client
        c += cmd

        # All input to this method should be internal to this program, so
        # if we don't have either None or a list, something is very wrong.
        if args is not None:
            if isinstance(args, list):
                c = c + " " + " ".join(args)
            else:
                raise P4Error(
                    "Program Error: run_G unexpectedly received a non-list value for 'args'.\nPlease contact CM.")

        if sys.version_info < (2, 6):
            (pi, po) = os.popen2(c, "b")
        else:
            from subprocess import Popen, PIPE

            p = Popen(c, stdin=PIPE, stdout=PIPE, shell=True)
            (pi, po) = (p.stdin, p.stdout)

        if p4_input:
            marshal.dump(p4_input, pi, 0)
            pi.close()

        results = []
        try:
            while 1:
                x = marshal.load(po)
                results.append(x)
        except EOFError:
            pass
        po.close()

        # check for known perforce errors
        for r in results:
            if r['code'] == 'error':
                msg = "\n'%s' command failed.\n\n" % c
                msg += "%s\n" % r['data']
                raise P4Error(msg)
        return results

    def __str__(self):
        return "user: %s port: %s client: %s" % (self.user, self.port, self.client)

    def opened(self, change_number=None):
        """Return a dict with opened files for user."""
        if change_number:
            cmd = "opened -c %s" % change_number
        else:
            cmd = "opened"
        return self.run_G(cmd)

    def changes(self, status=None):
        """Return a dict with changes for user."""
        cmd = "changes -u %s" % self.user
        if status:
            cmd += " -s %s" % status
        return self.run_G(cmd)

    def changelist_owner(self, change_number):
        """Return the user name of the change list owner"""
        change_list = self.get_change(change_number)
        return change_list['User']

    def verify_owner(self, change_list):
        """Raise exception if we are not the owner of the change list."""
        change_owner = self.changelist_owner(change_list)
        if self.user != change_owner:
            raise P4Error(
                "Perforce change %s is owned by %s - you are running as %s." % (change_list, change_owner, self.user))

    def new_change(self):
        """
        Create a numbered change list with all files in the default change list.

        Run p4 change on the default change list to create a new, numbered change
        and return the new change list number.

        Raise exception if there are no files in the default changelist.

        """
        if len(self.opened("default")) == 0:
            raise P4Error("No files opened in default changelist.")

        # Capture a change template with files opened in the default change list
        change_template = self.run("change -o")

        try:
            # Create a temp file and dump the p4 change to it.
            file_descriptor, file_name = tempfile.mkstemp(prefix="p4.change.")
            change_form = os.fdopen(file_descriptor, "w")
            for line in change_template:
                change_form.write(line + os.linesep)
            change_form.close()

            # Open the file in the users editor
            self.edit_file(file_name)
        except OSError, e:
            raise RBError("Error creating new change list.\n%s" % e)

        # Use 2.4 compatible version because we have so many CentOS 5 users
        f = None
        try:
            f = open(file_name, "r")
            new_change_form = [s.rstrip() for s in f.readlines()]
        except IOError, e:
            if os.path.isfile(file_name):
                f.close()
                os.remove(file_name)
            if f:
                f.close()
            raise RBError("Couldn't read the saved change list form.\n%s" % e)

        # The user may have changed their mind, so see if the file changed at all.
        if change_template == new_change_form:
            if os.path.isfile(file_name):
                f.close()
                os.remove(file_name)
            raise RBError("No changes made to change list.")
        else:
            # Use 2.4 compatible syntax since we have so many CentOS 5 users.
            try:
                try:
                    change_output = self.run("change -i < %s" % file_name)
                except P4Error, e:
                    # Give user a chance to fix the problem
                    print "Error in change specification:\n%s" % e
                    confirm = raw_input("Try again? n|[y]: ")
                    if confirm == '' or confirm.lower() == 'y':
                        self.edit_file(file_name)
                        change_output = self.run("change -i < %s" % file_name)
                    else:
                        raise P4Error("Change specification errors not fixed.")
            finally:
                if os.path.isfile(file_name):
                    f.close()
                    os.remove(file_name)
            return change_output[0].split()[1]

    def get_change(self, change_number):
        """Return dict with change_number change list"""
        return self.run_G("change -o %s" % change_number)[0]

    def edit_change(self, change_number):
        os.system("p4 change %s" % change_number)

    def shelve(self, change_number, update=False):
        """Create or update a p4 shelve from change_number"""
        if update:
            cmd = "shelve -f -c %s" % change_number
        else:
            cmd = "shelve -c %s" % change_number
        return self.run_G(cmd)

    def update_shelf(self, change_number):
        """Update the shelved change_number"""
        cmd = "shelve -r -c %s" % change_number
        return self.run_G(cmd)

    def shelved(self, change_number):
        """Return True if the change_number is a shelved change list"""
        return int(change_number) in self.shelves()

    def shelves(self):
        """Return list of change list numbers for user that are currently shelved."""
        shelved_changes = self.changes("shelved")
        return [int(sc['change']) for sc in shelved_changes]

    def unshelve(self, change_number):
        """Delete the shelf for the change_number"""
        cmd = "shelve -d -c %s" % change_number
        output = self.run_G(cmd)
        return output

    def get_jobs(self, change_number):
        """Return list of jobs associated with this change list number."""
        change = self.get_change(change_number)
        jobs = [change[k] for k in change.keys() if k.startswith('Jobs')]
        jobs.sort()
        return jobs

    def submit(self, change_number):
        """Submit change and return submitted change number"""
        cmd = "submit -c %s" % change_number
        output = self.run_G(cmd)

        # Check each dict in the output until we find submittedChange
        submitted_change = None
        for line in output:
            if "submittedChange" in line:
                submitted_change = int(line['submittedChange'])
                break
        if submitted_change is None:
            raise P4Error("Failed to determine submitted change list number.")
        return submitted_change

    def add_reviewboard_shipits(self, change_number, ship_its):
        """
        Add list of users who approved the review to the change list.

        """

        ship_it_line = "Reviewed by: %s" % (", ".join(ship_its))
        change = self.get_change(change_number)
        change_description = change['Description'].splitlines()

        # Look for a 'Reviewed by:' field in the description so we don't
        # end up with multiple entries.
        found = False
        for lineno in range(0, len(change_description)):
            if change_description[lineno].startswith("Reviewed by:"):
                change_description[lineno] = ship_it_line
                found = True
                break
        if not found:
            change_description.extend(['', ship_it_line])

        change['Description'] = "\n".join(change_description)

        self.run_G("change -i", p4_input=change)

    def set(self):
        """Return output of 'p4 set' as a dict."""
        set_list = self.run("set")
        set_dict = {}
        for item in set_list:
            k, v = item.split('=', 1)
            set_dict[k] = v
        return set_dict

    def get_editor(self):
        """
        Return the editor to use based on environment variables.

        Look at various environment variables to see if the user has
        specified a favorite and return that value.

        Default: vi on linux and mac, notepad on windows

        """

        p4set = self.set()
        if os.name == "nt":
            editor = "notepad"
        elif "P4EDITOR" in p4set:
            editor = p4set["P4EDITOR"]

            # If the editor is set in a p4.config file, the entry will end with (config)
            if editor.endswith(" (config)"):
                editor = editor[0:-9]
        elif "EDITOR" in os.environ:
            editor = os.environ["EDITOR"]
        else:
            editor = "vi"

        return editor

    def edit_file(self, file_name):
        """
        Open a file for editing
        """
        editor = self.get_editor()
        if os.name == "nt":
            from subprocess import call

            call([editor, file_name])
        else:
            os.system("%s %s" % (editor, file_name))


class F5Review(object):
    """Handle creation, updating and submitting of Review Requests"""

    def __init__(self, url, arg_parser):
        """Instantiate F5Review object

        url : The url for the server

        arg_parser : holds all the options and arguments needed.
                     We pull them out to make the interface simpler.

        p4 : A P4 object allowing us to talk to the perforce server.
        """
        self.arg_parser = arg_parser
        self.action = arg_parser.action
        self.url = url
        self.change_number = arg_parser.change_number
        self.debug = arg_parser.debug
        self.shelve = arg_parser.shelve
        self.force = arg_parser.force
        self.publish = arg_parser.publish
        self.username = arg_parser.username
        self.bugs = None
        self.edit_changelist = arg_parser.edit_changelist
        self.rbt_args = arg_parser.rbt_args

        # rid will be accessed through property methods
        self.rid = arg_parser.rid

        # Get api root object
        self.rbt_api = self._get_rbt_api()

    def _get_rbt_api(self):
        # Login if needed and return the api root
        rbclient = RBClient(self.url)
        try:
            rbt_api = rbclient.get_root()
        except AuthorizationError as e:
            try:
                self._rblogin(rbclient)
                rbt_api = rbclient.get_root()
            except AuthorizationError as e:
                raise RBError("Authentication failed for %s on %s" % (self.username, self.url))
        return rbt_api

    def _rblogin(self, rbclient):
        # Prompt user for name if not already provided and password
        # We should actually never get here because rbt should handle this
        # for us.
        print "(p2.py): Please log in to the Review Board server at %s." % self.url
        if self.username is None:
            self.username = raw_input("Username: ")
        password = getpass.getpass("Password: ")
        rbclient.login(self.username, password)

    @property
    def rid(self):
        if self._rid is None:
            if self.change_number:
                if self.debug:
                    print "Getting RID using CL %s" % self.change_number
                self.rid = self.get_review_id_from_changenum()
            else:
                raise RBError("Review has no change list number and no ID number.")
        return self._rid

    @rid.setter
    def rid(self, value):
        self._rid = value

    @property
    def review_request(self):
        """
        Return the latest version of the review request and update id, changelist.

        We always get the latest version of the review from the server, we never store
        it in our object.
        """
        try:
            review_request = self.rbt_api.get_review_request(review_request_id=self.rid)
        except APIError:
            raise RBError("Failed to retrieve review number %s." % self.rid)
        return review_request

    @staticmethod
    def run(client, args):
        """Call the run_from_argv function and catch SystemExit"""
        try:
            client.run_from_argv(args)
        except SystemExit as e:
            if e.code != 0:
                raise RBError(e)

    def post(self):
        """Post a review to the review board server

        If an existing review is found for this CL/RID, it will be updated.
        If not a new review will be created.

        """
        extra_args = []
        if self.bugs:
            extra_args.extend(['--bugs-closed', ','.join(self.bugs)])

        if self.action != 'create':
            extra_args.extend(['--review-request-id', self.rid])

        # Squeeze the extra args in right before the change list number
        self.rbt_args[-1:-1] = extra_args

        p = post.Post()
        if self.debug:
            print self.rbt_args

        # Call the client run method to post the review
        F5Review.run(p, self.rbt_args)

        if self.shelve:
            shelve_message = "This change has been shelved in changeset %s. " % self.change_number
            shelve_message += "To unshelve this change into your workspace:\n\n\tp4 unshelve -s %s" % self.change_number
            if self.debug:
                print shelve_message
            review = self.review_request.get_reviews().create()
            review.update(body_top=shelve_message, public=True)

        if self.publish:
            draft = self.review_request.get_draft()
            draft.update(public=True)

    def diff(self):
        """Print diff for review to stdout"""
        d = diff.Diff()
        if self.debug:
            print self.rbt_args
        F5Review.run(d, self.rbt_args)

    def close(self, submitted_change_list=None):
        """Close the review in Review Board"""
        c = close.Close()
        self.rbt_args.append(self.rid)
        if self.debug:
            print self.rbt_args
        F5Review.run(c, self.rbt_args)

        if submitted_change_list:
            # TODO: Need to update the change list number in the review
            pass

    def get_ship_its(self):
        """Return hash of users who gave review a ship it.

        Hash keys are usernames and values are 'First Last', which
        may be an empty string (e.g. admin user)
        """
        reviews = self.review_request.get_reviews()
        users = [r.get_user() for r in reviews if r.ship_it]
        reviewers = {}
        for user in users:
            # Make sure these are strings and not unicode or we'll run into problems
            # later when we try to marshall these.
            reviewers[str(user.username)] = ("%s %s" % (str(user.first_name), str(user.last_name))).strip()
        ship_it_list = [reviewers[u] or u for u in reviewers.keys()]
        return ship_it_list

    def get_review_id_from_changenum(self, status="all"):
        """Find review board id associated with change list number.

        Query the rb server to see if there is a review associated with the
        given change list number.

        Return the id as a string, or None if not found. If more than 1 found,
        raise RBError.
        """
        rr = self.rbt_api.get_review_requests(changenum=self.change_number, status=status)
        if len(rr) == 0:
            raise RBError("Error: No reviews found associated with CL %s.\n"
                          "Either create a new review or use the --rid option." % self.change_number)
        if len(rr) > 1:
            raise RBError("Error: found %d reviews associated with CL %s" % (len(rr), self.change_number))
        return str(rr[0].id)


def migrate_rbrc_file(old_rc_file, new_rc_file):
    """
    Migrate any legacy .rbrc settings.

    Copy known compatible settings from the legacy .rbrc file to a new
    .reviewboardrc file. This function should only get called if there is
    not already an existing .reviewboardrc file.

    """

    try:
        with open(old_rc_file, "r") as f:
            old_rc = f.read().splitlines()
    except EnvironmentError, e:
        raise RBError("Can't read %s\n%s" % (old_rc_file, e))

    # We don't migrate the user name because doing so causes post-review
    # to prompt for a password each time. By leaving it out, you get prompted
    # once and then future requests use the cookies file.  In fact, the only
    # value we want to migrate is the server name and ssl setting.
    old_settings = {}
    for line in old_rc:
        k, v = [s.strip() for s in line.split("=")]
        old_settings[k] = v

    server_url = False
    if "server" in old_settings:
        server_name = old_settings["server"]
        protocol = "http"
        if "use_ssl" in old_settings and old_settings["use_ssl"] == "1":
            protocol = "https"
        server_url = protocol + "://" + server_name

    if server_url:
        try:
            with open(new_rc_file, "w") as f:
                f.write('REVIEWBOARD_URL = "%s"\n' % server_url)
        except EnvironmentError, e:
            raise RBError("Failed to write %s\n%s" % (new_rc_file, e))

        # Let the user know a new config file was created
        print "Wrote config file: %s" % new_rc_file


def check_config(user_home):
    """
    Reconcile old and new configuration files.

    If there is now .reviewboardrc file, but there is a legacy .rbrc file,
    migrate those settings to .reviewboardrc.
    """

    rbrc_file = os.path.join(user_home, ".rbrc")
    reviewboardrc_file = os.path.join(user_home, RBTOOLS_RC_FILENAME)
    if os.path.isfile(rbrc_file) and not os.path.isfile(reviewboardrc_file):
        print "Found legacy %s file." % rbrc_file
        print "Migrating to %s" % reviewboardrc_file
        migrate_rbrc_file(rbrc_file, reviewboardrc_file)


def get_url(arg_parser, config_file):
    """Return url to ReviewBoard server

    If the --server option was passed, that is returned.
    If not, look for the url in the user configuration file.
    Return None if nothing is found.
    """
    url = arg_parser.server_url
    if url:
        # Users used to using rb are accustomed to providing the server without
        # the protocol string. In that case, assume https.
        # noinspection PyAugmentAssignment,PyAugmentAssignment
        if not url.startswith('http'):
            url = 'https://' + url
    else:
        with open(config_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('#'):
                    continue
                k, v = line.split('=')
                k = k.strip()
                v = v.strip()
                if k == 'REVIEWBOARD_URL':
                    # Remove any quotes that may be surrounding the value
                    v = v.strip("\'\"")
                    url = v
                    break

    if url is None:
        raise RBError(
            "No server url found. Either set in your " + RBTOOLS_RC_FILENAME + " file or pass it with --server option.")
    return url


def create_review(f5_review):
    """Main function for creating a new review request"""
    p4 = P4()
    if f5_review.change_number is None:
        f5_review.change_number = p4.new_change()
        f5_review.rbt_args.append(f5_review.change_number)

    if f5_review.shelve:
        p4.shelve(f5_review.change_number, update=True)

    # Extract bugs from change list if any
    f5_review.bugs = p4.get_jobs(f5_review.change_number)

    f5_review.post()


def edit_review(f5_review):
    """Main function for editing an existing review"""
    if f5_review.change_number is None:
        raise RBError("The edit command requires a change list number.")

    p4 = P4()
    if f5_review.shelve:
        p4.shelve(f5_review.change_number, update=True)

    # If CL has been shelved add the shelve option automatically.
    f5_review.shelve = p4.shelved(f5_review.change_number)

    # Extract bugs from change list if any
    f5_review.bugs = p4.get_jobs(f5_review.change_number)

    f5_review.post()


def submit_review(f5_review):
    """Main function for submitting change list and closing review."""

    # Unless the force option is used, we want to block reviews with no ship it or with
    # only a Review Bot ship it.
    ship_it_list = f5_review.get_ship_its()
    if not f5_review.force:
        if not ship_it_list:
            raise RBError("Review %s has no 'Ship It' reviews. Use --force to submit anyway." % f5_review.rid)

        # The list of ship_its contains unique elements, so check the case where only 1.
        if len(ship_it_list) == 1 and 'Review Bot' in ship_it_list:
            raise RBError("Review %s has only a Review Bot 'Ship It'. Use --force to submit anyway." % f5_review.rid)

    # If CL is shelved, delete the shelve since the user has already indicated
    # a clear intention to submit the CL.
    p4 = P4()
    if p4.shelved(f5_review.change_number):
        p4.unshelve(f5_review.change_number)

    # Does the user want to edit the CL before submitting?
    if f5_review.edit_changelist:
        p4.edit_change(f5_review.change_number)

    # Add reviewers who gave ship its
    if ship_it_list:
        p4.add_reviewboard_shipits(f5_review.change_number, ship_it_list)

    submitted_change_list = p4.submit(f5_review.change_number)
    f5_review.close(submitted_change_list)


def diff_changes(f5_review):
    """Print diff to stdout"""
    raise NotImplementedError


def main():
    try:
        arg_parser = RBArgParser(sys.argv)
    except RBError as e:
        print e.message
        raise SystemExit(ARG_PARSER)
    if arg_parser.action is None:
        arg_parser.print_help()
        raise SystemExit(NO_ACTION)

    # Check the users configuration files. It's not an error
    # if there are none, but it is if we can't access it.
    user_home = os.path.expanduser("~")
    try:
        check_config(user_home)
    except RBError as e:
        print e
        raise SystemExit(CONFIG_ERROR)

    actions = {
        "create": create_review,
        "edit": edit_review,
        "submit": submit_review,
        "diff": diff_changes,
    }

    if arg_parser.action not in actions:
        print "Unknown action: %s. Try -h for usage." % arg_parser.action
        raise SystemExit(UNKNOWN_ACTION)

    try:
        url = get_url(arg_parser, os.path.join(user_home, RBTOOLS_RC_FILENAME))
        f5_review = F5Review(url, arg_parser)
        actions[arg_parser.action](f5_review)
    except P4Error as e:
        print e
        raise SystemExit(P4_EXCEPTION)
    except RBError as e:
        print e
        raise SystemExit(RB_EXCEPTION)


if __name__ == '__main__':
    main()
