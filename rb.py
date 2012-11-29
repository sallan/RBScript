#!/usr/bin/env python
import logging
import optparse
#from optparse import OptionParser
import sys
import os
import tempfile
from rbtools import postreview
import rbtools.api.errors
from rbtools.postreview import options

class RBError(Exception): pass;

def run_cmd(cmd):
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

    # TODO: Get full list by looking in our old rb script
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
            print "Found .reviewboardrc and legacy .rbrc file. Using .reviewboardrc"
        else:
            print "Found legacy %s file." % rbrc_file
            print "Migrating to %s" % reviewboardrc_file
            migrate_rbrc_file(rbrc_file, reviewboardrc_file)


def get_server(user_config, options, cookie_file):
    """
    Create an instance of a ReviewBoardServer with our configuration settings.
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


def get_user(server, user):
    """
    Return data for the given user.
    """
    url = server.url + "api/users/%s" % user
    try:
        user_data = server.api_get(url)
    except rbtools.api.errors.APIError, e:
        raise RBError("Failed to find data for user: %s." % user)
    return user_data


def get_review(server, review_id):
    try:
        review = server.get_review_request(review_id)
    except rbtools.api.errors.APIError, e:
        raise RBError("Failed to retrieve review: %s." % review_id)
    return review


def get_reviews(server, review_id):
    try:
        review = server.get_review_request(review_id)
    except rbtools.api.errors.APIError, e:
        raise RBError("Failed to retrieve review: %s." % review_id)

    reviews = server.api_get(review['links']['reviews']['href'])
    return reviews

def get_review_change_list(server, review_id):
    try:
        change = server.get_review_request(review_id)['changenum']
    except rbtools.api.errors.APIError, e:
        raise RBError("Can't determine changelist number for review %s" % review_id)
    return  change


def new_review(options):
    if options.changenum is None:
        change = p4_change()
    else:
        change = options.changenum

    if change is None:
        raise RBError("Can't determine the perforce change list number.")
    else:
        cmd = "post-review -d %s" % change
        os.system(cmd)


def update_review(server, review_id):
    # We're not going to error check review_id because get_review_change_list()
    # will do a better job of that and raise an error.
    #
    # Get change list number for this review.
    change = get_review_change_list(server, review_id)
    cmd = "post-review -d %s" % change
    postreview.debug(cmd)
    os.system(cmd)


def validate_review(server, review_id):
    """
    To be valid must meets all the criteria for submission.

    1. You must own the CL
    2. Must have a ship it
    3. Need to check for shelved files
    """

    reviews = get_reviews(server, review_id)
    if reviews['total_results'] <= 0:
        raise RBError("Review %s has no 'Ship It' reviews. Use --force to submit anyway." % review_id)


def submit(server, review_id, options):
    review = server.get_review_request(review_id)
    change_list = review['changenum']

    if not options.force:
        # Inspect the review to make sure it meets requirements for submission.
        # If not, an RBError exception is raised with the reason for rejection.
        validate_review(server, review_id)

    try:
        if options.edit:
            os.system("p4 change %s" % change_list)
        submit_output = run_cmd("p4 submit -c %s" % change_list)
        postreview.debug("submit returned:")
        postreview.debug("\n".join(submit_output))
    except RuntimeError, e:
        raise RBError("ERROR: Unable to submit change %s\n%s" % (change_list, e))

    # Successful output will look like this:
    # ['Submitting change 816.', 'Locking 1 files ...', 'edit //depot/Jam/MAIN/src/README#27', 'Change 816 submitted.']
    #
    # or
    #
    # ['Submitting change 816.', 'Locking 1 files ...', 'edit //depot/Jam/MAIN/src/README#27', 'Change 828 renamed change 830 and submitted.']
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
            set_change_list(server, review_id, submitted_changelist)
            set_status(server, review_id, "submitted")
            print "Change %s submitted." % submitted_changelist
            print "Review %s closed." % review_id
        except RBError, e:
            raise RBError("Failed to submit review.\n" + e.message)
    else:
        raise RBError("Unrecognized p4 output: %s\nReview %s not closed." % ("\n".join(submit_output), review_id))


def set_status(server, review_id, status):
    review = server.get_review_request(review_id)
    server.api_put(review['links']['self']['href'], {
        'status': status,
    })


def set_change_list(server, review_id, change_list):
    review = server.get_review_request(review_id)
    server.api_put(review['links']['self']['href'], {
        'changenum': change_list,
    })


def parse_options():
    # TODO: Refine this usage
    parser = optparse.OptionParser(usage = "%prog [OPTIONS] create|edit|submit [RB_ID]")
    # TODO: The --server needs more explanation
    parser.add_option("--server",
       dest="server", metavar="<server_name>",
       help="Use server specified by url.")
    parser.add_option("-d", "--debug",
        dest="debug", action="store_true", default=False,
        help="Display debug output.")
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
    submit_group.add_option("-a", "--as-is",
        dest="asis", action="store_true", default=False,
        help="No idea what this is for.")


    edit_group = optparse.OptionGroup(parser, "Edit Options")
    edit_group.add_option("--update-diff",
        dest="update_diff", action="store_true", default=False,
        help="Upate the diffs for all files.")

    # TODO: Does rb allow for a string option here are does it always read the changelist?
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



def Xparse_options(args):
    parser = RBOptionParser(usage="%prog [-pond] [-c changenum] [review_id]")

    parser.add_option("-f", "--force",
        dest="force", action="store_true",
        default=False, help="Submit even if the review doesn't meet all requirements.")

    parser.add_option("-e", "--edit",
        dest="edit", action="store_true",
        default=False, help="Edit the change list before submitting.")

    return  parser.parse_args(args)


class RBOptionParser(optparse.OptionParser):
    """
    Extended OptionParser so we can prevent an error on options we don't recognize.
    This will allow us to parse our options and then pass the unrecognized ones off
    to the postreview.parse_options() method.
    """
    def _process_args(self, largs, rargs, values):
        while rargs:
            try:
                optparse.OptionParser._process_args(self, largs, rargs, values)
            except (optparse.BadOptionError, optparse.AmbiguousOptionError), e:
                largs.append(e.opt_str)


def run_help(parser):
    parser.print_help()
    sys.exit()

def main():
    # constant error strings
    MISSING_RB_ID = "Need the ReviewBoard ID number."

    # Create our server object
    global options
    global configs
    user_home = os.path.expanduser("~")

    try:
        check_config(user_home)
    except RBError, e:
        print e.message
        sys.exit(1)

    rb_cookies_file = os.path.join(user_home, ".post-review-cookies.txt")
    user_config, configs = postreview.load_config_files(user_home)
    parser = parse_options()
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit()


    options, args = parser.parse_args()

    # TODO: What do we do with the post_review_args?
    post_review_args = postreview.parse_options(args)

#    print "My Args: ", args
#    print "My Opts: ", options
#    print "PR Args: ", post_review_args
#    sys.exit()

    # parse the left over arguments
#    action = post_review_args[0]

    action = args[0]
    if action == "create":
        new_review(options)
        sys.exit()


    if action == "rr" or action == "reviewrequest":
        rr_action = post_review_args[1]
        if rr_action == "create":
            if len(args) > 1:
                new_review(args[1])
            else:
                new_review()
        else:
            try:
                # TODO: Don't like doing this before we've checked all the args
                server = get_server(user_config, postreview.options, rb_cookies_file)
            except RBError, e:
                print e.message
                sys.exit(1)

            # TODO: We should probably convert this to the rb rr edit --update-* formats
            if rr_action == "update":
                if len(post_review_args) < 3:
                    print MISSING_RB_ID
                    sys.exit(1)
                review_id = post_review_args[2]
                update_review(server, review_id)

            if rr_action == "submit":
                if len(post_review_args) < 3:
                    print MISSING_RB_ID
                    sys.exit(1)
                review_id = post_review_args[2]
                try:
                    submit(server, review_id, options)
                except RBError, e:
                    print e.message
                    sys.exit(1)


#    try:
#        for repo in server.get_repositories():
#            print repo['path']
#
#        print get_user(server, "sallan")
#        print get_review(server, "20")
#        print get_reviews(server, "19")
#    except RBError, e:
#        print e.message

if __name__ == "__main__":
    main()

# EOF
