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


def p4_change():
    # If there are no files in the default changelist, alert user and quit.
    if len(p4_opened("default")) == 0:
        print "WARN: No files opened in default changelist."
        sys.exit()

    # Fallback editor is vi
    editor = "vi"

    # TODO: Can probably remove this
    p4 = "p4"

    # See if user has a favorite
    if "P4EDITOR" in os.environ:
        editor = os.environ["P4EDITOR"]
    else:
        if "EDITOR" in os.environ:
            editor = os.environ['EDITOR']

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


def check_config():
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


def get_review(change):
    """
    Given a perforce changelist number, get back a review object from server.
    Good luck.
    """
    server = get_server()
    print server.api_get(server.url + "/api/")


def get_server():
#    tool = postreview.PerforceClient(options=options)
    tool = postreview.PerforceClient(options=None)
    repository_info = tool.get_repository_info()
#    server_url = "https://crush.olympus.f5net.com"
    server_url = "http://giles"
    cookie_file = "/Users/sallan/.post-review-cookies.txt"
    server = postreview.ReviewBoardServer(server_url, repository_info, cookie_file)
    return server

def get_repositories(server):
    url = server.url + "api/get_repositories"
    request = postreview.HTTPRequest(url, method="GET")
    return request



def main():
    check_config()

    if len(sys.argv) > 1:
        change = sys.argv[1]
    else:
        change = p4_change()

    if change:
        cmd = "post-review %s" % change
        os.system(cmd)
    else:
        print "USAGE: blah, blah"


if __name__ == "__main__":
    homepath = os.path.expanduser("~")
    user_config, globals()['configs'] = postreview.load_config_files(homepath)
    args, globals()['options'] = postreview.parse_options(sys.argv[1:])
    server = get_server()
    server.check_api_version()
    print server.get_repositories()

# EOF
