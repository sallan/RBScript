#!/usr/bin/env python
import sys
import os
import tempfile
import postreview

def run_cmd(cmd):
    child = os.popen(cmd)
    data = child.read().splitlines()
    err = child.close()
    if err:
        raise RuntimeError, "%r failed with return code: %d" % (cmd, err)
    return data


def p4_opened(change=None):
    if change is None:
        cmd = "p4 opened"
    else:
        cmd = "p4 opened -c %s" % change
    return run_cmd(cmd)


def get_editor():
    # Fallback editor is vi
    editor = "vi"

    # See if user has a favorite
    # TODO: What about p4.config settings?
    if "P4EDITOR" in os.environ:
        editor = os.environ["P4EDITOR"]
    else:
        if "EDITOR" in os.environ:
            editor = os.environ['EDITOR']
    return editor


def p4_change():
    # If there are no files in the default changelist, alert user and quit.
    if len(p4_opened("default")) == 0:
        print "WARN: No files opened in default changelist."
        sys.exit()

    editor = get_editor()
    p4 = "p4"

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
        print "Can't read %s" % old_rc_file
        print e
        sys.exit(1)

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
    user_home = os.path.expanduser("~")
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
    tool = postreview.PerforceClient(options=options)

    # TODO: What happens here if there is no user config file yet?
    server_url = user_config["REVIEWBOARD_URL"]
    repository_info = tool.get_repository_info()
    server = postreview.ReviewBoardServer(server_url, repository_info, cookie_file)
    server.check_api_version()
    return server


def get_user(server, user):
    url = server.url + "api/users/%s" % user
    return server.api_get(url)


def new_review(server, change="default"):
    if change == "default":
        # Create a numbered change list
        change = p4_change()

    if change is None:
        print "Can't determine the perforce change list number."
        sys.exit(1)
    else:
        cmd = "post-review -d %s" % change
        os.system(cmd)


def submit(server, review_id, edit=False):
    review = server.get_review_request(review_id)
    change_list = review['changenum']

    submit_output = None
    try:
        if edit:
            os.system("p4 change %s" % change_list)
        submit_output = run_cmd("p4 submit -c %s" % change_list)
    except RuntimeError, e:
        print "ERROR: Unable to submit change %s" % change_list
        print e

    # Successful output will look like this:
    # ['Submitting change 816.', 'Locking 1 files ...', 'edit //depot/Jam/MAIN/src/README#27', 'Change 816 submitted.']
    submitted_changelist = None
    if submit_output[-1].endswith("submitted."):
        submitted_changelist = submit_output[-1].split()[1]
        set_status(server, review_id, "submitted")
    else:
        print "WARN: unrecognized p4 output: %s" "\n".join(submit_output)
    return submitted_changelist


def set_status(server, review_id, status):
    review = server.get_review_request(review_id)
    server.api_put(review['links']['self']['href'], {
        'status': status,
    })


def main():
    # Every function needs this
    global options
    global configs
    user_home = os.path.expanduser("~")
    check_config(user_home)
    rb_cookies_file = os.path.join(user_home, ".post-review-cookies.txt")
    user_config, configs = postreview.load_config_files(user_home)
    args, options = postreview.parse_options(sys.argv[1:])
    server = get_server(user_config, options, rb_cookies_file)

    # Here's where we need to pass things off to other functions.
    # TODO: Hack this in for now so I can test
    action = args[0]
    print args

    if action == "create" or action == "new":
        if args[1]:
            new_review(server, args[1])
        else:
            new_review(server)

    if action == "repos":
        print server.get_repositories()

    if action == "show":
        thing, thing_id = args[1:]
        if thing == "user":
            print get_user(server, thing_id)
        if thing == "review":
            print server.get_review_request(thing_id)

    if action == "submit":
        review_id = args[1]
        submit(server, review_id)

if __name__ == "__main__":
    main()

# EOF
