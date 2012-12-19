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
    Provide necessary perforce data.

    """

    def __init__(self):
        """
        Create an object to interact with perforce using the user, port an client
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

    def new_change(self):
        """
        Create a numbered change list with all files in the default change list.

        Run p4 change on the default change list to create a new, numbered change
        and return the new change list number.

        Raise exception if there are no files in the default changelist.

        """
        if len(self.opened("default")) == 0:
            raise RBError("No files opened in default changelist.")

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

    def edit_change_i(self, change_number, text):
        change_list = self.get_change(change_number)
        change_list['Description'] += text

    def shelve(self, change_number=None):
        """Create a shelf either from default changelist or option change_number"""
        cmd = "shelve"
        if change_number:
            cmd += " -c %s" % change_number
        return self._p4_run(cmd)

    def update_shelf(self, change_number):
        """Update the shelved change_number"""
        cmd = "shelve -r -c %s" % change_number
        return self._p4_run(cmd)

    def shelved(self, change_number):
        """Return True if the change_number is a shelved change list"""
        return change_number in self.shelves()

    def shelves(self):
        """Return list of change list numbers that are currently shelved."""
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
        return int(output[-1]['submittedChange'])


class F5Review:
    """
    Encapsulate a review request.
    """

    def __init__(self, server, change_list, p4, options):
        """
        Create an instance of F5Review.

        Fields:
        server -- an instance of postreview.ReviewBoardServer
        change_list -- the perforce change list number
        options -- an options object as returned by optparse

        """

        self.server = server
        self.change_list = change_list
        self.p4 = p4
        self.options = options
        self.review_id = None

        # Create a PerforceClient object to create proper diffs. This comes from rbtools.
        self.p4client = perforce.PerforceClient(options=self.options)
        self.p4client.get_repository_info()

    @property
    def review_id(self):
        """Return the review board id number for this review."""
        if self.review_id is None:
            review_request = self.review_request
            self.review_id = review_request['id']
        return self.review_id

    @property
    def review_request(self):
        """Return the latest version of the review request and update id, changelist."""
        review_request = None
        if self.review_id:
            try:
                review_request = self.server.get_review_request(self.review_id)
                self.change_list = review_request['changenum']
            except rbtools.api.errors.APIError:
                raise RBError("Failed to retrieve review: %s." % self.review_id)
        else:
            if self.change_list:
                try:
                    review_request = get_review_from_changenum(self.server, self.change_list)
                    self.review_id  = review_request['id']
                except rbtools.api.errors.APIError:
                    raise RBError("Failed to find review for change list: %s." % self.change_list)
        return review_request

    def create(self):
        if options.shelve:
            self.p4.shelve(self.change_list)
        self.post_review()
        if options.shelve:
            self.add_shelve_comment()

    def edit(self):
        if options.shelve:
            self.post_review()
        self.p4.update_shelf(self.change_list)

        self.post_review()

        # TODO: We need better logic to decide when to update the comment. For now keep it simple.
        if options.shelve:
            self.add_shelve_comment()


    def post_review(self):
        p4 = self.p4
        server = self.server

        # Pass the options we care about along to postreview
        postreview.options.publish = self.options.publish
        postreview.options.target_people = self.options.target_people
        postreview.options.target_groups = self.options.target_groups
        postreview.options.publish = self.options.publish

        # Create our diff using rbtools
        diff, parent_diff = self.p4client.diff([self.change_list])

        if len(diff) == 0:
            raise RBError("There don't seem to be any diffs!")

        changenum = self.p4client.sanitize_changenum(options.changenum)

        if options.output_diff_only:
            # The comma here isn't a typo, but rather suppresses the extra newline
            print diff,
            sys.exit(0)

        # Post to review board server
        server.login()
        review_url = postreview.tempt_fate(server, self.p4client, changenum, diff_content=diff,
            parent_diff_content=parent_diff,
            submit_as=options.submit_as)

    def add_shelve_comment(self):
        # Review created, now post the shelve message.
        shelve_message = "This change has been shelved in changeset %s." % self.change_list
        shelve_message += "To unshelve this change into your workspace:\n\n\tp4 unshelve -s %s" % self.change_list
        self.server.set_review_request_field(self.review_request, 'changedescription', shelve_message)

    def submit(self):
        """Submit the change list to perforce and mark review as submitted."""
        review_id = self.review_id
        change_list = self.change_list
        options = self.options
        p4 = self.p4

        # Make sure we own this changelist
        change_owner = p4.changelist_owner(change_list)
        if p4.user != change_owner:
            raise RBError(
                "Perforce change %s is owned by %s - you are running as %s." % (change_list, change_owner, p4.user))

        if not options.force:
            # Inspect the review to make sure it meets requirements for submission.
            # If not, an RBError exception is raised with the reason for rejection.
            self.validate_review()

        if options.edit:
            p4.edit_change(change_list)

        if p4.shelved(change_list):
            print "Deleting shelve since --force option used."
            p4.unshelve(change_list)

        # We need to modify the change form to include additional information.
        # Example:
        #
        #         Reviewed by: Bill Walker, Michael Slass, Zach Carter
        #
        #         Reviewboard: 53662
        #
        # We have a perforce trigger add the ReviewBoard URL so that it gets
        # included even if the change is submitted without using this script.
        #

        # Get the change form
        # TODO: Can this code be modified to use the dicts?
        change_form = run_cmd("p4 change -o %s" % change_list)
        insert_here = change_form.index("Files:")

        # Add list of ship-its to the change list
        ship_its = self.get_ship_its()
        if ship_its:
            # Need to add this to change list:
            #
            #
            ship_it_line = "\tReviewed by: %s\n" % ", ".join(ship_its)
            change_form.insert(insert_here, ship_it_line)
            insert_here += 1

        review_id_line = "\tReviewboard: %s\n" % review_id
        change_form.insert(insert_here, review_id_line)

        # Write new form to temp file and submit
        change_form_file = tempfile.NamedTemporaryFile(mode="w", delete=False)
        for line in change_form:
            change_form_file.write(line + "\n")
        change_form_file.close()
        run_cmd("p4 change -i < %s" % change_form_file.name)
        submitted_changelist = p4.submit(change_list)

        postreview.debug("Setting review change list to %s and closing." % submitted_changelist)
        try:
            self.set_change_list(submitted_changelist)
            self.set_status("submitted")
            print "Change %s submitted." % submitted_changelist
            print "Review %s closed." % review_id
        except RBError, e:
            raise RBError("Failed to submit review.\n%s" % e)

    def validate_review(self):
        """
        Validate the review before submitting.

        To be valid the review must meet these requirements:
        * Must be pending
        * Must have a ship it unless -f
        * Can't have shelved files unless -f

        """

        # Review must be pending
        review_status = self.review_request['status']
        if  review_status != "pending":
            raise RBError("Can't submit a review with a '%s' status." % review_status)

        # Check for ship_its
        if not self.get_ship_its():
            raise RBError("Review %s has no 'Ship It' reviews. Use --force to submit anyway." % self.review_id)

        # Check for shelves
        if self.p4.shelved(self.change_list):
            msg = "\tError: Cannot submit a shelved change (%s).\n" % self.change_list
            msg += "\tYou may use --force to delete the shelved change automatically prior to submit."
            raise RBError(msg)

    def get_ship_its(self):
        """Get unique list of reviewers who gave a ship it."""
        reviews = self.get_reviews()['reviews']
        ship_its = [self.get_reviewer_name(r) for r in reviews if r['ship_it']]

        # Return just the unique elements
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
            'changenum': self.change_list,
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

    def get_review_draft(self):
        draft_url = self.review_request['links']['draft']['href']
        return self.server.api_get(draft_url)['draft']

    def save_draft(self):
        self.server.save_draft(self.review_request)

    def add_change_description(self, description):
        self.server.set_review_request_field(self.review_request, 'changedescription', description)
        self.save_draft()

    def set_review_description(self, description, append=False):
        if append:
            description = self.review_request['description'] + "\n" + description
        self.server.set_review_request_field(self.review_request, "description", description)

# End of F5Review class

#==============================================================================
# Create a new review - no server object needed for this.
#==============================================================================
def create(options, p4):
    """
    A thin wrapper to the rbtools post-review script.

    This stays here rather than F5Review because we don't create an F5Review
    object when creating a new review request. We just shell out to post-review.
    That may change in a future version of this script because I'd actually like
    to bypass all the other repository checks that post-review does. But that's a
    much larger scope than I want to take on for this version.
    """

    if options.changenum is None:
        # Create a new change list and capture the number.
        options.changenum = p4.new_change()
    else:
        # We we're given a change list number - make sure we're the owner.
        change_owner = p4.changelist_owner(options.changenum)
        if p4.user != change_owner:
            raise RBError("Perforce change %s is owned by %s - you are running as %s." % (
                options.changenum, change_owner, p4.user))

    if options.shelve:
        p4.shelve(options.changenum)

    options_string = convert_options(options)
    cmd = "post-review %s" % options_string
    pr_output = run_cmd(cmd)

    # Successful output will look like this:
    #
    # ['Review request #38 posted.', '', 'http://reviewboard/r/38/']
    #
    if len(pr_output) < 3:
        raise RBError("Unrecognized output from post-review: %s" % "\n".join(pr_output))
    posted_message = pr_output[0]
    posted_url = pr_output[2]
    if posted_message.endswith("posted."):
        review_id = posted_message.split()[2].strip()[1:]
    else:
        raise RBError("Unrecognized output from post-review: %s" % posted_message)

    if options.shelve:
        shelve_message = "This change has been shelved in changeset %s." % options.changenum
        shelve_message += "To unshelve this change into your workspace:\n\n\tp4 unshelve -s %s" % options.changenum
        print shelve_message
        # Add a comment to the review with shelving information
        # Hmm, to do this we'll need the rb id number. Maybe we need to
        # capture the output.
        # TODO: Crap! I need a server instance to do this!!
        # TODO: This function no longer prints a friendly message since
        #       you replaced os.system with run_cmd.

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
        # Need to support older pythons so can't use the 'with' statement
        f = open(old_rc_file, "r")
        old_rc = f.read().splitlines()
        f.close()
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
    if os.path.isfile(rbrc_file):
        if os.path.isfile(reviewboardrc_file):
            postreview.debug("Found .reviewboardrc and legacy .rbrc file. Using .reviewboardrc")
        else:
            print "Found legacy %s file." % rbrc_file
            print "Migrating to %s" % reviewboardrc_file
            migrate_rbrc_file(rbrc_file, reviewboardrc_file)


def get_server(user_config, options, cookie_file):
    """
    Create an instance of a ReviewBoardServer with our configuration settings.

    This is used by the F5Review class and is the workhorse for our customizations.

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


def get_review_from_changenum(server, changenum):
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


def convert_options(options):
    """Convert our options to post-review options string."""

    post_rev_opts = ""

    if options.debug:
        post_rev_opts += " --debug"

    if options.open:
        post_rev_opts += " --open"

    if options.output_diff:
        post_rev_opts += " --output-diff"

    if options.publish:
        post_rev_opts += " --publish"

    if options.server:
        post_rev_opts += " --server %s" % options.server

    if options.changenum:
        post_rev_opts += " %s" % options.changenum

    if options.target_people:
        post_rev_opts += " --target-people %s" % options.target_people

    if options.target_groups:
        post_rev_opts += " --target-groups %s" % options.target_groups

    if options.submit_as:
        post_rev_opts += " --submit-as %s" % options.submit_as

    return post_rev_opts.strip()


def parse_options():
    """
    Our options parser
    """

    description = """
Create, update and submit review requests.

This script is a wrapper to the post-review script that comes with Review Board.
It can only be used with perforce and provides some additional functionality related
to perforce.  The work flow is create/update/submit. The options for each are described
below.

"""

    parser = optparse.OptionParser(
        usage="%prog [OPTIONS] create|update|submit [change_list]",
        description=description
    )
    parser.add_option("-d", "--debug",
        dest="debug", action="store_true", default=False,
        help="Display debug output.")

#    parser.add_option("-c", "--change",
#        dest="changenum", metavar="<changenum>",
#        help="Alternative to using RB_ID.")

    parser.add_option("--server",
        dest="server", metavar="<server_name>",
        help="Use specified server. Default is the REVIEWBOARD_URL entry in .reviewboardrc file.")

    parser.add_option("--p4-port",
        dest="p4_port", metavar="<p4_port>",
        help="Specify P4PORT. Default is to use environment settings.")
    parser.add_option("--p4-client",
        dest="p4_client", metavar="<p4_client>",
        help="Specify P4CLIENT. Default is to use environment settings.")
    parser.add_option("--p4-user",
        dest="p4_user", metavar="<p4_user>",
        help="Specify P4USER. Default is to use environment settings.")
    parser.add_option("--p4-passwd",
        dest="p4_passwd", metavar="<p4_passwd>",
        help="Specify P4PASSWD. Not used but needed in options.")

    create_group = optparse.OptionGroup(parser, "Create Options")

#    create_group.add_option("-c", "--change",
#        dest="changenum", metavar="<changenum>",
#        help="Use this change list number for review instead of default change list.")

    create_group.add_option("-g", "--target-groups",
        dest="target_groups", metavar="<group [,groups]>",
        help="List of ReviewBoard groups to assign.")
    create_group.add_option("-u", "--target-people",
        dest="target_people", metavar="<user [,users]>",
        help="List of users to assign.")
    create_group.add_option("--shelve",
        dest="shelve", action="store_true", default=False,
        help="Run 'p4 shelve' on the files and then create review.")
    create_group.add_option("--submit-as",
        dest="submit_as", metavar="<user>",
        help="Create review with this username. Useful if review board name is different from p4 user name.")

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
    edit_group.add_option("-n", "--output-diff",
        dest="output_diff_only", action="store_true", default=False,
        help="Output diff to console and exit. Do not post.")
    edit_group.add_option("-o", "--open",
        dest="open", action="store_true", default=False,
        help="Open review in default web browser after creating/updating.")

    parser.add_option_group(edit_group)
    parser.add_option_group(create_group)
    parser.add_option_group(submit_group)
    return parser


def show_review_links(server, review_id):
    # This is a throwaway function I'm using as a development aid.
    review_request = server.get_review_request(review_id)
    for name in review_request['links']:
        print "%20s:  %s" % (name, review_request['links'][name]['href'])


def main():
    # Configuration and options
    global options
    global configs
    user_home = os.path.expanduser("~")

    # Check for a legacy .rbrc file and migrate it to .reviewboardrc if necessary
    try:
        check_config(user_home)
    except RBError, e:
        print e
        sys.exit(1)

    user_config, configs = postreview.load_config_files(user_home)
    parser = parse_options()
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit()

    # We need to call our option parser and then also call postreview's parse_options
    # because it sets global variables that we need for our operations.
    # We don't care about the return value of postreview's parse_options.
    options, args = parser.parse_args()
    postreview.parse_options(args)

    # Create a P4 object to interact with perforce
    try:
        p4 = P4()
    except P4Error:
        print "Failed to connect to the perforce server. Exiting."
        sys.exit(1)

    # Strip off legacy UI elements if present
    if args[0] == "rr" or args[0] == "reviewrequest":
        args = args[1:]
    action = args[0]
    change_list = None

    # See if we have a change list number
    if len(args) > 1:
        change_list = args[1]
    else:
        if action == "create":
            change_list = p4.new_change()

    if change_list is None:
        print "Need your perforce change list number for this review."
        sys.exit(1)

    options.changenum = change_list
    rb_cookies_file = os.path.join(user_home, ".post-review-cookies.txt")
    try:
        server = get_server(user_config, postreview.options, rb_cookies_file)

        # TODO: Do we need p4? Maybe we should decouple p4 and review?
        review = F5Review(server, change_list, p4, options)

        # Looking more and more like a simple dispatch table would go here.
        if action == "create":
            review.create()
            sys.exit()

        if action == "update":
            review.edit()
            sys.exit()

        if action == "submit":
            review.submit()
            sys.exit()

        print "Unknown action: %s" % action
        sys.exit(1)

    except P4Error, e:
        print e
        sys.exit(1)
    except RBError, e:
        print e
        sys.exit(1)


if __name__ == "__main__":
    main()

# EOF
