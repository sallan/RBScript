#!/usr/bin/python
import os
import sys
import optparse
import tempfile
import marshal

from rbtools.commands import diff
from rbtools.commands import post


ACTIONS = ['create', 'edit', 'submit', 'diff']


class RBError(Exception):
    pass


class P4Error(Exception):
    pass


class RBArgParser:
    """Manage options and arguments for review requests"""

    def __init__(self, args):
        """Create argument parser with input argument list"""
        # self.raw_args = args[1:]
        self.edit_changelist = False
        self.shelve = False
        self.force = False
        self.debug = False
        self.parser = RBArgParser._option_parser()
        self.opts, self.args = self.parser.parse_args(args[1:])

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
        # If the shelve option is used, we need to intercept the publish
        # option so we can add the shelve comment after rbt runs, but
        # before publishing, so we add it to f5_options.
        # We also make sure to save the publish option here.
        self.f5_options = ['shelve', 'force', 'edit_changelist']
        if self.opts.shelve:
            self.f5_options.append('publish')
        self.publish = self.opts.publish

        # These options used by us and rbt
        self.rid = self.opts.rid
        self.debug = self.opts.debug

        # Process the options separating those we handle and those we pass to rbt
        opts_dict = {k: v for k, v in vars(self.opts).iteritems() if v}
        self.rbt_args = ['rbt', self.action]
        for opt, value in opts_dict.iteritems():
            if opt in self.f5_options:
                setattr(self, opt, value)
            else:
                self.rbt_args.extend(RBArgParser._opt_to_string(opt, value))

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
            'rid': '--rid',
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
                          help="Use specified server. Default is the REVIEWBOARD_URL entry in .reviewboardrc file.")

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


class P4:
    """
    Encapsulate perforce environment and handle calls to the perforce server.

    """

    def __init__(self, user=None, port=None, client=None):
        """
        Create an object to interact with perforce using the user, port and client
        settings provided. If any are missing, use those from the environment.
        """
        if not all([user, port, client]):
            p4_info = self.info()
            self.user = p4_info['userName']
            self.port = p4_info['serverAddress']
            self.client = p4_info['clientName']
        else:
            self.user = user
            self.port = port
            self.client = client

    def info(self):
        p4_info = self.run_G("info")
        if not p4_info:
            raise P4Error("Could not talk to the perforce server.")
        return p4_info[0]

    def run(self, cmd):
        """Run perforce cmd and return output as a list of output lines."""
        cmd = "p4 " + cmd
        child = os.popen(cmd)
        data = child.read().splitlines()
        err = child.close()
        if err:
            raise P4Error("Perforce command '%s' failed.\n" % cmd)
        return data

    def run_G(self, cmd, args=None, p4_input=0):
        """
        Run perforce command and marshal the IO. Returns stdout as a  dict.

        This code was copied from this perforce knowledge base page:

        http://kb.perforce.com/article/585/using-p4-g

        I modified it slightly for error checking.
        """

        c = "p4 -G " + cmd

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
            if line.has_key("submittedChange"):
                submitted_change = int(line['submittedChange'])
                break
        if submitted_change is None:
            raise P4Error("Failed to determine submitted change list number.")
        return submitted_change

    def add_reviewboard_shipits(self, review, ship_its):
        """
        Add list of users who approved the review to the change list.

        """

        ship_it_line = "Reviewed by: %s" % (", ".join(ship_its))
        change = self.get_change(review.change_list)
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
        elif p4set.has_key("P4EDITOR"):
            editor = p4set["P4EDITOR"]

            # If the editor is set in a p4.config file, the entry will end with (config)
            if editor.endswith(" (config)"):
                editor = editor[0:-9]
        elif os.environ.has_key("EDITOR"):
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


class F5Review:
    """Handle creation, updating and submitting of Review Requests"""

    def __init__(self, arg_parser, p4):
        self.arg_parser = arg_parser
        self.p4 = p4
        self.change_number = arg_parser.change_number
        self.rid = arg_parser.rid
        self.debug = arg_parser.debug
        self.shelve = arg_parser.shelve
        self.rbt_args = arg_parser.rbt_args

    def post(self):
        bugs = self.p4.get_jobs(self.change_number)
        if bugs:
            self.rbt_args[-1:] = ['--bugs-closed', ','.join(bugs), self.change_number]
        p = post.Post()
        if self.debug:
            print self.rbt_args
        p.run_from_argv(self.rbt_args)


    def diff(self):
        d = diff.Diff()
        if self.debug:
            print self.rbt_args
        d.run_from_argv(self.rbt_args)


def create_review(f5_review):
    if f5_review.change_number is None:
        p4 = P4()
        f5_review.change_number = p4.new_change()
    f5_review.post()


def edit_review(f5_review):
    if f5_review.change_number is None:
        raise RBError("The edit command requires a change list number.")

    if f5_review.shelve:
        p4 = P4()
        p4.shelve(f5_review.change_number, update=True)
    f5_review.post()


def submit_review(f5_review):
    pass


def run_diff(f5_review):
    pass


def main():
    try:
        arg_parser = RBArgParser(sys.argv)
    except RBError as e:
        print e.message
        raise SystemExit(1)
    if arg_parser.action is None:
        arg_parser.print_help()
        raise SystemExit(0)

    p4 = P4()
    f5_review = F5Review(arg_parser, p4)
    if arg_parser.action == 'diff':
        run_diff(f5_review)
    elif arg_parser.action == 'edit':
        edit_review(f5_review)
    elif arg_parser.action == 'create':
        create_review(f5_review)
    elif arg_parser.action == 'submit':
        submit_review(f5_review)


if __name__ == '__main__':
    main()
