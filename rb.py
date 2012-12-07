#!/usr/bin/env python
import optparse
import sys
import os
import tempfile
from rbtools import postreview
import rbtools.api.errors

class RBError(Exception): pass;


class F5Review:
    """
    Encapsulates a review request.
    """

    def __init__(self, server, review_id, options):
        self.server = server
        self.review_id = review_id
        self.options = options

        try:
            self.review_request = server.get_review_request(review_id)
            self.change_list =  self.review_request['changenum']
        except rbtools.api.errors.APIError:
            raise RBError("Failed to retrieve review: %s." % review_id)


    def submit(self):
        """Submit the change list to perforce and mark review as submitted."""
        review_id = self.review_id
        change_list = self.change_list
        options = self.options

        if not options.force:
            # Inspect the review to make sure it meets requirements for submission.
            # If not, an RBError exception is raised with the reason for rejection.
            self.validate_review()

        try:
            if options.edit:
                os.system("p4 change %s" % change_list)

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

            # Write new form to temp file
            change_form_file = tempfile.NamedTemporaryFile(mode="w", delete=False)
            for line in change_form:
                change_form_file.write(line + "\n")
            change_form_file.close()
            change_output = run_cmd("p4 change -i < %s" % change_form_file.name)

            # Submit change list to perforce
            submit_output = run_cmd("p4 submit -c %s" % change_list)
            postreview.debug("submit returned:")
            postreview.debug("\n".join(submit_output))
        except RuntimeError, e:
            raise RBError("ERROR: Unable to submit change %s\n%s" % (change_list, e))

        # Successful output will look like this:
        # ['Submitting change 816.', 'Locking 1 files ...', 'edit //depot/Jam/MAIN/src/README#27',
        # 'Change 816 submitted.']
        #
        # or
        #
        # ['Submitting change 816.', 'Locking 1 files ...', 'edit //depot/Jam/MAIN/src/README#27',
        # 'Change 828 renamed change 830 and submitted.']
        #
        if submit_output[-1].endswith("submitted."):
            # Figure out what change list number it went in with.
            submit_status_message = submit_output[-1]
            if submit_status_message == "Change %s submitted." % change_list:
                submitted_changelist = change_list
            else:
                if submit_status_message.startswith("Change %s renamed change" % change_list):
                    submitted_changelist = submit_status_message.split()[4]
                else:
                    raise RBError("Unrecognized output from p4 submit:\n%s" % "\n".join(submit_output))

            postreview.debug("Setting review change list to %s and closing." % submitted_changelist)
            try:
                self.set_change_list(submitted_changelist)
                self.set_status("submitted")
                print "Change %s submitted." % submitted_changelist
                print "Review %s closed." % review_id
            except RBError, e:
                raise RBError("Failed to submit review.\n" + e.message)
        else:
            raise RBError("Unrecognized p4 output: %s\nReview %s not closed." % ("\n".join(submit_output), review_id))

    def edit(self):
        """Edits the review."""
        # TODO: What other editing functions do we want to support?
        # TODO: What about all the other options?
        cmd = "post-review %s" % self.change_list
        if self.options.debug:
            cmd += " --debug"
        os.system(cmd)


    def validate_review(self):
        """
        To be valid must meets all the criteria for submission.
        * Must be pending
        * You must own the CL
        * Must have a ship it
        """
        review_status = self.review_request['status']
        if review_status != "pending":
            raise RBError("Can't submit a review with a '%s' status." % review_status)

        reviews = self.get_reviews()
        if reviews['total_results'] <= 0:
            raise RBError("Review %s has no 'Ship It' reviews. Use --force to submit anyway." % self.review_id)



    def set_change_list(self, new_change):
        """Assign new change list number to review request."""
        self.change_list = new_change
        self.server.api_put(self.review_request['links']['self']['href'], {
            'changenum': self.change_list,
        })


    def get_ship_its(self):
        """Get unique list of reviewers who gave a ship it."""
        reviews = self.get_reviews()['reviews']
        ship_its = [self.get_reviewer_name(r) for r in reviews if r['ship_it']]

        # Return just the unique elements
        return list(set(ship_its))


    def get_reviewer_name(self, review):
        """Returns First Last names for user who did given review."""
        user_id = review['links']['user']['title']
        user_url = self.server.url + "api/users/%s" % user_id
        user = self.server.api_get(user_url)
        return "%s %s" % (user['user']['first_name'], user['user']['last_name'])


    def set_status(self, status):
        """Set the status for this review request."""
        self.server.api_put(self.review_request['links']['self']['href'], {
            'status': status,
        })


    def get_reviews(self):
        """Return list of all reviews for this review request."""
        reviews_url = self.review_request['links']['reviews']['href']
        reviews = self.server.api_get(reviews_url)
        return reviews


#==============================================================================
# Utility functions
#==============================================================================
def run_cmd(cmd):
    """
    Run cmd and return output as a list of output lines.
    """
    child = os.popen(cmd)
    data = child.read().splitlines()
    err = child.close()
    if err:
        raise RuntimeError, "%r failed with return code: %d" % (cmd, err)
    return data


def p4_opened(change=None):
    """
    Return list of files opened in this workspace.
    """
    if change is None:
        cmd = "p4 opened"
    else:
        cmd = "p4 opened -c %s" % change
    return run_cmd(cmd)


def p4_change():
    """
    Create a numbered change list with all files in the default change list.
    Returns the new change list number.
    Raises RBError on failure.
    """
    # If there are no files in the default changelist, alert user and quit.
    if len(p4_opened("default")) == 0:
        raise RBError("No files opened in default changelist.")

    editor = get_editor()
    p4 = "p4"

    # TODO: Need to do more error checking in this function
    # Capture a change template with files opened in the default change list
    change_template = run_cmd("%s change -o" % p4)

    # Create a temp file and dump the p4 change to it.
    change_form = tempfile.NamedTemporaryFile(mode="w", delete=False)
    for line in change_template:
        change_form.write(line + "\n")
    change_form.close()

    # Open the file in the users editor
    os.system("%s %s" % (editor, change_form.name))

    # The user may have changed their mind, so see if the file changed at all.
    f = open(change_form.name, "r")
    new_change_form = [s.rstrip() for s in f.readlines()]
    f.close()

    if change_template == new_change_form:
        print "No changes made."
        change = None
    else:
        # Feed form to p4 change and capture the output
        change_output = run_cmd("%s change -i < %s" % (p4, change_form.name))
        change = change_output[0].split()[1]
    os.unlink(change_form.name)
    return change


def get_editor():
    """
    Determine the editor to use from the environment.
    """
    # Fallback editor is vi
    editor = "vi"

    # See if user has a favorite
    # TODO: What about p4.config settings? Note the old rb does not handle it either.
    if "P4EDITOR" in os.environ:
        editor = os.environ["P4EDITOR"]
    else:
        if "EDITOR" in os.environ:
            editor = os.environ['EDITOR']
    return editor


def migrate_rbrc_file(old_rc_file, new_rc_file):
    """
    Copies known compatible settings from the legacy .rbrc file to a new
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

    valid_keys = {"username" : "USERNAME",
                  "server" : "REVIEWBOARD_URL",
    }


    try:
        f = open(new_rc_file, "w")
        for line in old_rc:
            k, v = [ s.strip() for s in line.split("=") ]
            if k in valid_keys.keys():
                new_k = valid_keys[k]
                if new_k == "REVIEWBOARD_URL":
                    v = "https://" + v
                f.write('%s = "%s"\n'% (new_k, v))
        f.close()
    except IOError, e:
        print "Failed to write %s" % new_rc_file
        print e
    print "Wrote config file: %s" % new_rc_file


def check_config(user_home):
    """
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
            raise RBError("No server url found. Either set in your .reviewboardrc file or pass it with --server option.")

    repository_info = tool.get_repository_info()
    server = postreview.ReviewBoardServer(server_url, repository_info, cookie_file)
    server.check_api_version()
    return server



def create(options):
    """
    A thin wrapper to the rbtools post-review script.

    This stays here rather than F5Review be cause we don't create an F5Review
    object when creating a new review request. We just shell out to post-review.
    That may change in a future version of this script because I'd actually like
    to bypass all the other repository checks that post-review does. But that's a
    much larger scope than I want to take on for this version.
    """

    if options.changenum is None:
        change = p4_change()
    else:
        change = options.changenum

    if change is None:
        raise RBError("Can't determine the perforce change list number.")
    else:
        # TODO: Need to properly pass options to post-review
        cmd = "post-review -d %s" % change
        os.system(cmd)

def parse_options():
    """
    Our options parser
    """
    # TODO: Refine this usage statement
    parser = optparse.OptionParser(usage="%prog [OPTIONS] create|update|edit|submit [RB_ID]")
    parser.add_option("-d", "--debug",
        dest="debug", action="store_true", default=False,
        help="Display debug output.")
    parser.add_option("--server",
        dest="server", metavar="<server_name>",
        help="Use specified server. Default is entry in .reviewboardrc file.")
    # TODO: consider adding support for p4-port and p4-user


    create_group = optparse.OptionGroup(parser, "Create Options")
    create_group.add_option("-c", "--changeset",
        dest="changenum", metavar="<changeno>",
        help="Create review using an existing change list.")
    create_group.add_option("-b", "--bug",
        dest="bug_number", metavar="<bug_id>",
        help="Link to this bugzilla id.")
    create_group.add_option("-g", "--target-groups",
        dest="target_groups", metavar="<group [groups]>",
        help="List of ReviewBoard groups to assign.")
    create_group.add_option("-u", "--target-users",
        dest="target_people", metavar="<user [users]>",
        help="List of users to assign.")

    create_group.add_option("-p", "--publish",
        dest="publish", action="store_true", default=False,
        help="Publish the review.")
    create_group.add_option("-s", "--shelve",
        dest="shelve", action="store_true", default=False,
        help="Perform a 'p4 shelve' on the files.")

    create_group.add_option("--summary",
        dest="summary", metavar="<string>",
        help="Summary for the review. Default is change list description.")

    create_group.add_option("--description",
        dest="description", metavar="<string>",
        help="Description of the review. Default is change list description.")
    create_group.add_option("--submit-as",
        dest="submit_as", metavar="<user>",
        help="Create review with this username. Useful if different from p4 user name.")

    submit_group = optparse.OptionGroup(parser, "Submit Options")
    submit_group.add_option("-f", "--force",
        dest="force", action="store_true", default=False,
        help="Submit even if the review doesn't meet all requirements.")
    submit_group.add_option("-e", "--edit-changelist",
        dest="edit", action="store_true", default=False,
        help="Edit the change list before submitting.")

    # TODO: Do we want to support this? I don't see why.
    submit_group.add_option("-a", "--as-is",
        dest="asis", action="store_true", default=False,
        help="Don't add reviewer names to the change list.")

    edit_group = optparse.OptionGroup(parser, "Edit Options")
    edit_group.add_option("--update-diff",
        dest="update_diff", action="store_true", default=False,
        help="Upate the diffs for all files. The 'update' action is a shortcut for this.")

    # TODO: Does rb allow for a string option here or does it always read the changelist?
    # TODO: How important is it to support these?
    edit_group.add_option("--update-bugs",
        dest="update_bugs", action="store_true", default=False,
        help="Upate the bug (p4 Jobs) field.")
    edit_group.add_option("--update-summary",
        dest="update_summary", action="store_true", default=False,
        help="Upate the summary field.")
    edit_group.add_option("--update-all",
        dest="update_all", action="store_true", default=False,
        help="Upate all fields from information in the change list.")

    parser.add_option_group(create_group)
    parser.add_option_group(edit_group)
    parser.add_option_group(submit_group)
    return parser


def main():
    MISSING_RB_ID = "Need the ReviewBoard ID number."

    # Configuration and options
    global options
    global configs
    user_home = os.path.expanduser("~")

    # Check for a legacy .rbrc file and migrate it to .reviewboardrc if necessary
    try:
        check_config(user_home)
    except RBError, e:
        print e.message
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

    # Strip off legacy UI elements if present
    if args[0] == "rr" or args[0] == "reviewrequest":
        args = args[1:]
    action = args[0]

    # For creating a new review request, just hand everything off to post-review.
    if action == "create":
        create(options)
        sys.exit()

    # For everything else, we need to talk directly to the server, so we'll instantiate
    # an F5Review object with a server instance.
    if len(args) < 2:
        print MISSING_RB_ID
        sys.exit(1)

    review_id = args[1]
    rb_cookies_file = os.path.join(user_home, ".post-review-cookies.txt")
    try:
        server = get_server(user_config, postreview.options, rb_cookies_file)
        review = F5Review(server, review_id, options)

        if action == "edit":
            review.edit()
            sys.exit()

        if action == "submit":
            review.submit()
            sys.exit()

        print "Unknown action: %s" % action
        sys.exit(1)

    except RBError, e:
        print e.message
        sys.exit(1)


if __name__ == "__main__":
    main()

# EOF
