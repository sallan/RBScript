#!/usr/bin/env python
import sys
import os
import tempfile

# from postreview import *
# from rbtools.clients.perforce import PerforceClient


def run_cmd(cmd):
    child = os.popen(cmd)
    data = child.read().splitlines()
    err = child.close()
    if err:
        raise RuntimeError, "%r failed with return code: %d" % (cmd, err)
    return data


def p4_change():
    # TODO: What if there are no files in the default change list?

    # Fallback editor is vi
    editor = "vi"

    # TODO: hard-coded hack needs fixing
    #p4 = "/usr/local/bin/p4 -p 1492"
    p4 = "/usr/local/bin/p4 "

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
    # print change_form.name

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

    # Clean up
    os.unlink(change_form.name)

    return change

def create_review(change=None):
    # If we weren't provided a change list number, then
    # create a new change from the default change list.
    if change is None:
        print "Need to get change"
        change = p4_change()

    # Now call post-review with our changelist number
    print "Creating review for change %s" % change
    post_review = run_cmd("post-review %s" % change)
    print post_review


def list_reviews(user):
    print "Looking for reviews from %s" % user



def post_main():
    """
    Copied the main() routine directly from postreview.py and hacked it up.
    Why? So that I can save all the checks for SCM type and go right to
    perforce. Plus it saves me forking another python process.
    """
    if 'APPDATA' in os.environ:
        homepath = os.environ['APPDATA']
    elif 'HOME' in os.environ:
        homepath = os.environ["HOME"]
    else:
        homepath = ''
    # If we end up creating a cookie file, make sure it's only readable by the
    # user.
    os.umask(0077)

    # Load the config and cookie files
    cookie_file = os.path.join(homepath, ".post-review-cookies.txt")
    user_config, globals()['configs'] = load_config_files(homepath)
    args, globals()['options'] = parse_options(sys.argv[1:])

    print "global options: "
    print globals()['options']

    debug('RBTools %s' % get_version_string())
    debug('Python %s' % sys.version)
    debug('Running on %s' % (platform.platform()))
    debug('Home = %s' % homepath)
    debug('Current Directory = %s' % os.getcwd())

    debug('Checking the repository type. Errors shown below are mostly harmless.')

    # NOTE: This is the line I replaced with a direct call to PerforceClient
    # repository_info, tool = scan_usable_client(options)
    tool = PerforceClient(options=options)
    # TODO: These need to come from environment or config.
    tool.p4_client = "sallan-buffy-sample-depot"
    tool.p4_port = "localhost:1492"
    repository_info = tool.get_repository_info()
    debug('Finished checking the repository type.')

    tool.user_config = user_config
    tool.configs = configs

    # Verify that options specific to an SCM Client have not been mis-used.
    # Don't need this check.
    # tool.check_options()

    # Try to find a valid Review Board server to use.
    # For some reason options is no longer global. How to get to it?
    if options.server:
        server_url = options.server
    else:
        # TODO: Should we skip this? We don't need to be this nice
        server_url = tool.scan_for_server(repository_info)

    if not server_url:
        print "Unable to find a Review Board server for this source code tree."
        sys.exit(1)

    # NOTE: This is the key line where we create our server. If you get this
    # right you're golden!
    server = ReviewBoardServer(server_url, repository_info, cookie_file)
    server.check_api_version()

    # Handle the case where /api/ requires authorization (RBCommons).
    if not server.check_api_version():
        die("Unable to log in with the supplied username and password.")

    print "Made it this far!"

    # TODO: Need to decide now - are we going to support CVS? Please no!
    # If that's the case, we don't need the conditional. In fact, much of
    # the logic in all this gets simplified if we only support perforce.
    #
    # Instead, we check for a changelist argument and if we don't have one we
    # assume default changelist and create a numbered changelist. We should be
    # able to do away with the need to use RB ID for interactions. Aw, probably
    # should keep that part of the rb interface the same. If they want the other,
    # use post-review directly. I'd prefer that anyway :)
    if repository_info.supports_changesets:
        changenum = tool.get_changenum(args)
    else:
        changenum = p4_change()

    if options.revision_range:
        diff, parent_diff = tool.diff_between_revisions(options.revision_range, args,
            repository_info)
    elif options.svn_changelist:
        diff, parent_diff = tool.diff_changelist(options.svn_changelist)
    elif options.diff_filename:
        parent_diff = None

        if options.diff_filename == '-':
            diff = sys.stdin.read()
        else:
            try:
                fp = open(os.path.join(origcwd, options.diff_filename), 'r')
                diff = fp.read()
                fp.close()
            except IOError, e:
                die("Unable to open diff filename: %s" % e)
    else:
        diff, parent_diff = tool.diff(args)

    if len(diff) == 0:
        die("There don't seem to be any diffs!")
    else:
        print "Cool, made it this far now!"

    sys.exit()

    if (isinstance(tool, PerforceClient) or
        isinstance(tool, PlasticClient)) and changenum is not None:
        changenum = tool.sanitize_changenum(changenum)

        # NOTE: In Review Board 1.5.2 through 1.5.3.1, the changenum support
        #       is broken, so we have to force the deprecated API.
        if (parse_version(server.rb_version) >= parse_version('1.5.2') and
            parse_version(server.rb_version) <= parse_version('1.5.3.1')):
            debug('Using changenums on Review Board %s, which is broken. '
                  'Falling back to the deprecated 1.0 API' % server.rb_version)
            server.deprecated_api = True

    if options.output_diff_only:
        # The comma here isn't a typo, but rather suppresses the extra newline
        print diff,
        sys.exit(0)

    # Let's begin.
    server.login()

    review_url = tempt_fate(server, tool, changenum, diff_content=diff,
        parent_diff_content=parent_diff,
        submit_as=options.submit_as)

    # Load the review up in the browser if requested to:
    if options.open_browser:
        try:
            import webbrowser

            if 'open_new_tab' in dir(webbrowser):
                # open_new_tab is only in python 2.5+
                webbrowser.open_new_tab(review_url)
            elif 'open_new' in dir(webbrowser):
                webbrowser.open_new(review_url)
            else:
                os.system('start %s' % review_url)
        except:
            print 'Error opening review URL: %s' % review_url

def migrate_rbrc_file(old_rc_file, new_rc_file):
    """
    Copies known compatible settings from the legacy .rbrc file to a new
    .reviewboardrc file. This function should only get called if there is
    not already an existing .reviewboardrc file.
    """
    if os.path.isfile(new_rc_file):
        # TODO: Is this really necessary?
        print "I refused to overwrite existing file: %s" % new_rc_file
        sys.exit(1)

    try:
        # Need to support older pythons so can't use the with statement
        f = open(old_rc_file, "r")
        old_rc = f.read().splitlines()
        f.close()
    except IOError, e:
        print "Can't read %s" % old_rc_file
        print e

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



def main():
    check_config()

    if len(sys.argv) > 1:
        change = sys.argv[1]
        print change
    else:
        change = p4_change()

    if change:
        cmd = "post-review %s" % change
        os.system(cmd)


if __name__ == "__main__":
    # create_review("815")
    # list_reviews("sallan")
    # api = PR.api_get("https://crush.olympus.f5net.com/api/")
    # user_config, globals()['configs'] = PR.load_config_files(homepath)
    # config = {"username": "sallan", "REVIEWBOARD_URL" : "https://crush.olympus.f5net.com/" }
    # PR.options.username = "sallan"
    # p4 = PerforceClient(user_config=user_config)
    # server = PR.ReviewBoardServer("https://crush.olympus.f5net.com", p4, "/Users/sallan/.post-review-cookies.txt")
    # print server.check_api_version()
    # post_main()
    main()

