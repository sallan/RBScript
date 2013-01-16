#!/usr/bin/env python
import optparse
import sys
import os
import tempfile
import marshal
from rbtools import postreview
from rbtools.clients import perforce
import rbtools.api.errors

class RBError(Exception): pass;


class P4Error(Exception): pass;


class P4:
    """
    Encapsulate perforce environment and handle calls to the perforce server.

    """

    def __init__(self):
        """
        Create an object to interact with perforce using the user, port and client
        settings from the environment.
        """
        info = self._p4_info()
        self.user = info['userName']
        self.port = info['serverAddress']
        self.client = info['clientName']

    def _p4_info(self):
        info = self._p4_run("info")
        if not info:
            raise P4Error("Could not talk to the perforce server.")
        return info[0]

    def _p4_run(self, cmd):
        """Run supplied perforce command and return output as a list of dictionaries."""
        results = []
        if sys.version_info[1] < 6:
            pipe = os.popen('p4 -G ' + cmd, 'r')
        else: # os.popen is deprecated in Python 2.6+
            from subprocess import Popen, PIPE

            pipe = Popen(["p4", "-G"] + cmd.split(), stdout=PIPE).stdout
        try:
            while 1:
                record = marshal.load(pipe)
                results.append(record)
        except EOFError, e:
            pass
        pipe.close()

        # check for known perforce errors
        for r in results:
            if r['code'] == 'error':
                msg = "\n'p4 %s' command failed.\n\n" % cmd
                msg += "%s\n" % r['data']
                msg += "Please fix problem and try again."
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
        return self._p4_run(cmd)

    def changes(self, status=None):
        """Return a dict with changes for user."""
        cmd = "changes -u %s" % self.user
        if status:
            cmd += " -s %s" % status
        return self._p4_run(cmd)

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
        change_template = run_cmd("p4 change -o")

        # Create a temp file and dump the p4 change to it.
        change_form = tempfile.NamedTemporaryFile(mode="w", delete=False)
        for line in change_template:
            change_form.write(line + "\n")
        change_form.close()

        # Open the file in the users editor
        editor = get_editor()
        os.system("%s %s" % (editor, change_form.name))

        # The user may have changed their mind, so see if the file changed at all.
        # TODO: Protect against parse error. Maybe give user 2 tries
        f = open(change_form.name, "r")
        new_change_form = [s.rstrip() for s in f.readlines()]
        f.close()

        if change_template == new_change_form:
            print "No changes made."
            change = None
        else:
            change_output = run_cmd("p4 change -i < %s" % change_form.name)
            change = change_output[0].split()[1]
        os.unlink(change_form.name)
        return change

    def get_change(self, change_number):
        """Return dict with change_number change list"""
        return self._p4_run("change -o %s" % change_number)[0]

    def edit_change(self, change_number):
        os.system("p4 change %s" % change_number)

    def shelve(self, change_number):
        """Create a p4 shelve from change_number"""
        cmd = "shelve -c %s" % change_number
        return self._p4_run(cmd)

    def update_shelf(self, change_number):
        """Update the shelved change_number"""
        cmd = "shelve -r -c %s" % change_number
        return self._p4_run(cmd)

    def shelved(self, change_number):
        """Return True if the change_number is a shelved change list"""
        return change_number in self.shelves()

    def shelves(self):
        """Return list of change list numbers for user that are currently shelved."""
        shelved_changes = self.changes("shelved")
        return [int(sc['change']) for sc in shelved_changes]

    def unshelve(self, change_number):
        """Delete the shelf for the change_number"""
        cmd = "shelve -d -c %s" % change_number
        output = self._p4_run(cmd)
        return output

    def submit(self, change_number):
        """Submit change and return submitted change number"""
        cmd = "submit -c %s" % change_number
        output = self._p4_run(cmd)

        # Check each dict in the output until we find submittedChange
        submitted_change = None
        for line in output:
            if line.has_key("submittedChange"):
                submitted_change = int(line['submittedChange'])
                break
        if submitted_change is None:
            raise P4Error("Failed to determine submitted change list number.")
        return submitted_change

    def add_reviewboard_info(self, review):
        """
        Add review board ID and list of users who approved the review to the change list.

        Example:

                 Reviewed by: Bill Walker, Michael Slass, Zach Carter

                 Reviewboard: 53662

        Note: We have a perforce trigger that adds the ReviewBoard URL so that it gets
        included even if the change is submitted without using this script. So once that's
        proven to be working with the new server, we can leave out this extra ReviewBoard
        line.

        """

        # Get the change form
        # TODO: Can this code be modified to use the dicts?
        change_form = run_cmd("p4 change -o %s" % review.change_list)
        insert_here = change_form.index("Files:")

        # Add list of ship-its to the change list
        ship_its = review.get_ship_its()
        if ship_its:
            ship_it_line = "\tReviewed by: %s\n" % ", ".join(ship_its)
            change_form.insert(insert_here, ship_it_line)
            insert_here += 1

        # Add review board id
        # TODO: How important is this since we add the url? Probably cruft. Remove after new trigger is working.
        review_id_line = "\tReviewboard: %s\n" % review.review_id
        change_form.insert(insert_here, review_id_line)

        # Write new form to temp file and submit
        change_form_file = tempfile.NamedTemporaryFile(mode="w", delete=False)
        for line in change_form:
            change_form_file.write(line + "\n")
        change_form_file.close()
        run_cmd("p4 change -i < %s" % change_form_file.name)


class F5Review:
    """
    Encapsulate a review request and handle interaction with Review Board server.
    """

    def __init__(self, server, change_list):
        """
        Create an instance of F5Review.

        Fields:
        server -- an instance of postreview.ReviewBoardServer
        change_list -- the perforce change list number
        review_id  -- the review board id number

        We only need a server and change_list to instantiate the object.
        The review_id is obtained from the server via the change_list

        """

        self.server = server
        self.change_list = change_list
        self.review_id = None

        # Create a PerforceClient object to create proper diffs. This comes from rbtools.
        self.p4client = perforce.PerforceClient(options=options)
        self.p4client.get_repository_info()

    @property
    def review_id(self):
        """Return the review board id number for this review."""
        if self.review_id is None:
            review_request = self.review_request
            self.review_id = review_request['id']
        return self.review_id

    @review_id.setter
    def review_id(self, value):
        self.review_id = value

    @property
    def review_request(self):
        """
        Return the latest version of the review request and update id, changelist.

        We always get the latest version of the review from the server, we never store
        it in our object.
        """
        review_request = None
        try:
            if not self.review_id:
                if self.change_list:
                    self.review_id = get_review_id_from_changenum(self.server, self.change_list)
                else:
                    raise RBError("Review has no change list number and no ID number.")
            review_request = self.server.get_review_request(self.review_id)
            self.change_list = review_request['changenum']
        except rbtools.api.errors.APIError:
            raise RBError("Failed to retrieve review number %s." % self.review_id)
        return review_request

    def post_review(self):
        """Main method for creating and updating reviews on the Review Board Server."""

        # Pass the options we care about over to postreview.options
        postreview.options.publish = options.publish
        postreview.options.target_people = options.target_people
        postreview.options.target_groups = options.target_groups
        postreview.options.server = options.server
        postreview.options.diff_only = options.diff_only
        postreview.options.change_only = options.change_only
        postreview.options.testing_done = options.testing_done
        postreview.options.testing_file = options.testing_file
        postreview.options.debug = options.debug

        # I decided against supporting the username option. I think it's confusing
        # and there's rarely a need for it. On those occasions where it's
        # needed, we can run post-review.  Leaving the code in for now in
        # case I change my mind. Delete on 06/01/13 if still commented out.
        # -sallan
        # postreview.options.username = options.username

        # Create our diff using rbtools
        diff, parent_diff = self.p4client.diff([self.change_list])

        if len(diff) == 0:
            raise RBError("There don't seem to be any diffs!")

        if options.output_diff_only:
            # The comma here isn't a typo, but rather suppresses the extra newline
            print diff,
            sys.exit(0)

        # Post to review board server
        changenum = self.p4client.sanitize_changenum(self.change_list)
        self.server.login()
        review_url = postreview.tempt_fate(self.server, self.p4client, changenum, diff_content=diff,
            parent_diff_content=parent_diff,
            submit_as=options.submit_as)

        if options.shelve:
            self.add_shelve_comment()
        if options.publish:
            self.save_draft()

    def add_shelve_comment(self):
        """Add comment to review regarding the shelved change list."""
        shelve_message = "This change has been shelved in changeset %s. " % self.change_list
        shelve_message += "To unshelve this change into your workspace:\n\n\tp4 unshelve -s %s" % self.change_list
        self.server.set_review_request_field(self.review_request, 'changedescription', shelve_message)

    def submit(self, submitted_changelist):
        """Submit the change list to perforce and mark review as submitted."""
        review_id = self.review_id
        try:
            self.set_change_list(submitted_changelist)
            self.set_status("submitted")
            print "Change %s submitted." % submitted_changelist
            print "Review %s closed." % review_id
        except RBError, e:
            raise RBError("Failed to submit review.\n%s" % e)

    def get_ship_its(self):
        """Get unique list of reviewers who gave a ship it."""
        reviews = self.get_reviews()['reviews']
        ship_its = [self.get_reviewer_name(r) for r in reviews if r['ship_it']]

        # Idiom for extracting unique elements from list
        return list(set(ship_its))

    def get_review_summary(self):
        return self.review_request['summary']

    def get_reviewer_name(self, review):
        """Returns First Last names for user who did given review."""
        user_id = review['links']['user']['title']
        user_url = self.server.url + "api/users/%s" % user_id
        user = self.server.api_get(user_url)
        return "%s %s" % (user['user']['first_name'], user['user']['last_name'])

    def set_change_list(self, new_change):
        """Assign new change list number to review request."""

        # We can't use server.set_review_request_field here. I don't know why.
        # At any rate, this works.
        self.change_list = new_change
        self.server.api_put(self.review_request['links']['self']['href'], {
            'changenum': new_change,
        })

    def set_status(self, status):
        """Set the status for this review request."""

        # We can't use server.set_review_request_field here. I don't know why.
        # At any rate, this works.
        self.server.api_put(self.review_request['links']['self']['href'], {
            'status': status,
        })

    def get_reviews(self):
        """Return list of all reviews for this review request."""
        reviews_url = self.review_request['links']['reviews']['href']
        reviews = self.server.api_get(reviews_url)
        return reviews

    def save_draft(self):
        """Save current review draft. This is used when --publish option is passed."""
        self.server.save_draft(self.review_request)


    # The methods below are currently not used. But I may need them later
    # so I'm leaving them in for now.
    # TODO: Delete these if not used by 06/13.
    def get_review_draft(self):
        draft_url = self.review_request['links']['draft']['href']
        return self.server.api_get(draft_url)['draft']

    def add_change_description(self, description):
        self.server.set_review_request_field(self.review_request, 'changedescription', description)
        self.save_draft()

    def set_review_description(self, description, append=False):
        if append:
            description = self.review_request['description'] + "\n" + description
        self.server.set_review_request_field(self.review_request, "description", description)

# End of F5Review class


#==============================================================================
# Utility functions
#==============================================================================
def run_cmd(cmd):
    """Run cmd and return output as a list of output lines."""
    child = os.popen(cmd)
    data = child.read().splitlines()
    err = child.close()
    if err:
        raise RuntimeError, "%r failed with return code: %d" % (cmd, err)
    return data


def get_editor():
    """
    Return the editor to use based on environment variables.

    Look at various environment variables to see if the user has
    specified a favorite and return that value.

    Default: vi

    """

    editor = "vi"

    # See if user has a favorite
    if "P4EDITOR" in os.environ:
        editor = os.environ["P4EDITOR"]
    else:
        if "EDITOR" in os.environ:
            editor = os.environ['EDITOR']
    return editor


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
    except IOError, e:
        raise RBError("Can't read %s\n%s" % (old_rc_file, e))

    # We don't migrate the user name because doing so causes post-review
    # to prompt for a password each time. By leaving it out, you get prompted
    # once and then future requests use the cookies file.
    valid_keys = {"server": "REVIEWBOARD_URL"}

    try:
        f = open(new_rc_file, "w")
        for line in old_rc:
            k, v = [s.strip() for s in line.split("=")]
            if k in valid_keys.keys():
                new_k = valid_keys[k]
                if new_k == "REVIEWBOARD_URL":
                    v = "https://" + v
                f.write('%s = "%s"\n' % (new_k, v))
        f.close()
    except IOError, e:
        print "Failed to write %s" % new_rc_file
        print e
    print "Wrote config file: %s" % new_rc_file


def check_config(user_home):
    """
    Reconcile old and new configuration files.

    Look for a legacy .rbrc file in the user home directory and then for a .reviewboardrc.
    If you find both, warn the user and use .reviewboardrc. If only .rbrc, migrate those
    settings to .reviewboardrc.

    """
    rbrc_file = os.path.join(user_home, ".rbrc")
    reviewboardrc_file = os.path.join(user_home, ".reviewboardrc")
    if os.path.isfile(rbrc_file) and not os.path.isfile(reviewboardrc_file):
        print "Found legacy %s file." % rbrc_file
        print "Migrating to %s" % reviewboardrc_file
        migrate_rbrc_file(rbrc_file, reviewboardrc_file)


def get_server(user_config, cookie_file):
    """
    Create an instance of a ReviewBoardServer with our configuration settings.

    The server returned by this function is used by the F5Review class to talk
    directly to the Review Board server.

    """
    tool = postreview.PerforceClient(options=options)
    if options.server:
        server_url = options.server
    else:
        if user_config and user_config.has_key("REVIEWBOARD_URL"):
            server_url = user_config["REVIEWBOARD_URL"]
        else:
            raise RBError(
                "No server url found. Either set in your .reviewboardrc file or pass it with --server option.")

    repository_info = tool.get_repository_info()
    server = postreview.ReviewBoardServer(server_url, repository_info, cookie_file)
    server.check_api_version()
    return server


def get_review_id_from_changenum(server, changenum):
    """Return Review Board ID number for given changenum. Raises exception if not found."""
    url = "%sapi/review-requests?changenum=%s" % (server.url, changenum)
    try:
        review = server.api_get(url)
        if review['review_requests']:
            review_id = review['review_requests'][0]['id']
        else:
            raise RBError("Can't find an open review for change list: %s" % changenum)
    except rbtools.api.errors:
        raise RBError("Can't find an open review for change list: %s" % changenum)
    return review_id


def get_option_parser():
    """Options parser and usage."""

    description = """
Create, update and submit review requests.

This script is a wrapper to the post-review script that comes with Review Board.
It can only be used with perforce and provides some additional functionality related
to perforce.  The work flow is create/update/submit. The options for each are described
below.

"""

    parser = optparse.OptionParser(
        usage="%prog [OPTIONS] create|update|submit [changenum]",
        description=description
    )
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
        dest="edit", action="store_true", default=False,
        help="Edit the change list before submitting.")

    edit_group = optparse.OptionGroup(parser, "Create and Update Options")
    edit_group.add_option("-p", "--publish",
        dest="publish", action="store_true", default=False,
        help="Publish the review.")
    # TODO: Does -n work before review created? Will it force a numbered changelist?
    #       And if so, does it matter?
    edit_group.add_option("-n", "--output-diff",
        dest="output_diff_only", action="store_true", default=False,
        help="Output diff to console and exit. Do not post.")
    edit_group.add_option("-g", "--target-groups",
        dest="target_groups", metavar="<group [,groups]>",
        help="Assign or replace ReviewBoard groups for this review.")
    edit_group.add_option("-u", "--target-people",
        dest="target_people", metavar="<user [,users]>",
        help="Assign or replace reviewers for this review.")

    edit_group.add_option("--shelve",
        dest="shelve", action="store_true", default=False,
        help="Create or update p4 shelve for the files in the review.")
    # TODO: do diff-only and change-only work on new reviews? Should be only for updates
    edit_group.add_option("--diff-only",
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

    # I decided against supporting the username option. I think it's confusing
    # and there's rarely a need for it. On those occasions where it's
    # needed, we can run post-review.  Leaving the code in for now in
    # case I change my mind. Delete on 06/01/13 if still commented out.
    # -sallan
    #    edit_group.add_option("--username",
    #        dest="username", metavar="<user>",
    #        help="Switch to this Review Board username. Useful if different from p4 username (e.g. mergeit). " +
    #            "The new login credentials will remain in effect until you use --username again.")

    parser.add_option_group(edit_group)
    parser.add_option_group(submit_group)
    return parser


def parse_options(parser):
    """Parse command line options, strip of legacy UI elements and return args, optiions and action."""
    options, args = parser.parse_args()
    if args[0] == "rr" or args[0] == "reviewrequest":
        print "Use of 'rr' or 'reviewrequest' is no longer required."
        args = args[1:]
    action = args[0]
    args = args[1:]

    if options.testing_done and options.testing_file:
        sys.stderr.write("The --testing-done and --testing-done-file options "
                         "are mutually exclusive.\n")
        sys.exit(1)

    if options.testing_file:
        if os.path.exists(options.testing_file):
            fp = open(options.testing_file, "r")
            options.testing_done = fp.read()
            fp.close()
        else:
            sys.stderr.write("The testing file %s does not exist.\n" %
                             options.testing_file)
            sys.exit(1)

    # We expect these to be set in the environment. For that to work we
    # have to provide a value of None to these in the options namespace
    # because rbtools checks for it.
    options.p4_client = None
    options.p4_port = None

    # We don't support passing p4_passwd at all, so set it to None also.
    options.p4_passwd = None

    # This unsupported option also needs to be initialized
    options.submit_as = None

    return (options, args, action)


def get_changelist_number(p4, action, args):
    """Return change list number. Raise exception if we can't obtain one."""
    change_list = None
    if args:
        change_list = args[0]
    else:
        if action == "create":
            change_list = p4.new_change()
    if change_list is None:
        raise RBError("Need your perforce change list number for this review.")
    return change_list


def create_review(review, p4):
    """Create a new review request"""
    if options.shelve:
        p4.shelve(review.change_list)
    review.post_review()


def update_review(review, p4):
    """Update existing review request."""
    if options.shelve:
        p4.update_shelf(review.change_list)
    review.post_review()


def submit_review(review, p4):
    """Submit review request change list and mark review as submitted."""
    if not review.get_ship_its() and not options.force:
        raise RBError("Review %s has no 'Ship It' reviews. Use --force to submit anyway." % review.review_id)

    if p4.shelved(review.change_list):
        if options.force:
            print "Deleting shelve since --force option used."
            p4.unshelve(review.change_list)
        else:
            msg = "Cannot submit a shelved change (%s).\n" % review.change_list
            msg += "You may use --force to delete the shelved change automatically prior to submit."
            raise RBError(msg)

    if options.edit:
        p4.edit_change(review.change_list)

    p4.add_reviewboard_info(review)
    submitted_change_list = p4.submit(review.change_list)
    review.submit(submitted_change_list)


def main():
    # Configuration and options
    global options
    global configs
    user_home = os.path.expanduser("~")
    user_config, configs = postreview.load_config_files(user_home)
    parser = get_option_parser()
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit()

    # Check for a legacy .rbrc file and migrate it to .reviewboardrc if necessary
    try:
        check_config(user_home)
    except RBError, e:
        print e
        sys.exit(1)

    # We need to call our option parser and then also call postreview's parse_options
    # because it sets global variables that we need for our operations.
    # We don't care about the return value of postreview's parse_options.
    options, args, action = parse_options(parser)
    postreview.parse_options(args)

    actions = {
        "create": lambda: create_review(review, p4),
        "update": lambda: update_review(review, p4),
        "submit": lambda: submit_review(review, p4),
    }
    if not actions.has_key(action):
        print "Unknown action: %s" % action
        sys.exit(1)

    try:
        p4 = P4()
        change_list = get_changelist_number(p4, action, args)
        p4.verify_owner(change_list)
        rb_cookies_file = os.path.join(user_home, ".post-review-cookies.txt")
        server = get_server(user_config, rb_cookies_file)
        review = F5Review(server, change_list)
        actions[action]()
        sys.exit()
    except P4Error, e:
        print e
        sys.exit(1)
    except RBError, e:
        print e
        sys.exit(1)


if __name__ == "__main__":
    main()

# EOF
