#!/usr/local/bin/python
from P4 import P4,P4Exception    # Import the P4 modules
import os, sys, inspect, subprocess, getopt, yaml, smtplib, traceback, datetime, string, re
import subprocess

class working_directory:
  """Context manager for changing the current working directory"""
  def __init__(self, newPath):
    self.newPath = newPath

  def __enter__(self):
    self.savedPath = os.getcwd()
    os.chdir(self.newPath)

  def __exit__(self, etype, value, traceback):
    os.chdir(self.savedPath)

branch = None
parent_branch = None
parent_path = None
client_name = None
email_recipients = None
branch_folder_name = None
branch_mapping = None
build_server_name = None
team_city_url = None
team_city_p4_client = None
revert_p4_files = None
gated_integration = None
skip_tube = None
build_only = None
config_file_path = "integ.yaml"

out_channel = sys.stdout
progress = ""

def email(subject, body):
  if not email_recipients:
    return

  mail_host = "smarthost.tsi.lan"

  try:
    mail_port = smtplib.SMTP(mail_host)
  except:
    print >> sys.stderr, "Unable to connect to SMTP host %s" % mail_host
  else:
    recipients = email_recipients.split(",")
    sender = recipients[0]
    message = """From: %s
To: %s
Subject: %s

%s""" % (sender, ", ".join(recipients), subject, body)

  try:
    failed = mail_port.sendmail(sender, recipients, message)
  except:
    failed = string.join(apply(traceback.format_exception, sys.exc_info()), '')
  if failed:
    print >> sys.stderr, "SMTP problem: \n%s" % failed

  try:
    mail_port.quit()
  except:
    print >> sys.stderr, "Error while doing SMTP quit command"

def email_error(error_message):
  subject = "Integration error from %s to %s. Branch owner intervention required." % (parent_branch, branch)
  body = """

    Error Message:\t\t%s

    Branch:\t\t\t%s
    Branch Mapping:\t\t%s
    P4 Client Used:\t\t%s
    Build Server:\t\t\t%s
    Workspace:\t\t\t%s
    Config File Path:\t\t%s
    TeamCity URL:\t\t%s

    ------
    %s
    """ % (error_message, branch, branch_mapping, team_city_p4_client, build_server_name, branch_folder_name, config_file_path, team_city_url, str(datetime.datetime.now()))
  email(subject, body)

def email_success():
  subject = "Integration succeeded using %s branch mapping - %s to %s." % (branch_mapping, parent_branch, branch)
  body = """
  Integration succeeded using:

  Branch Mapping:\t%s
  Build Server:\t\t%s
  P4 Client Used:\t%s
  Workspace:\t\t%s
  TeamCity URL:\t\t%s
  """ %(branch_mapping, build_server_name, team_city_p4_client, branch_folder_name, team_city_url)

  email(subject, body)

def email_send_to_gsub(cat_url):
  subject = "Integration has been sent to Gated build for %s" % (branch_mapping)
  body = """
  Integration Build has succeeded and has been passed to Gated build for Submission.
  BoxCat Url: \t%s
  The following parameters were used for the completed Auto Integration Job:
  Branch Mapping:\t%s
  Build Server:\t\t%s
  P4 Client Used:\t%s
  Workspace:\t\t%s
  TeamCity URL:\t\t%s
  """ %(cat_url, branch_mapping, build_server_name, team_city_p4_client, branch_folder_name, team_city_url)

  email(subject, body)

def email_noop():
  subject = "Nothing to integrate using %s branch mapping.  Integration aborted." % (branch_mapping)
  body = """
  No integration needed using %s branch mapping - from %s to %s

  Builder Server:\t%s
  P4 Client Used:\t%s
  Workspace:\t\t%s
  TeamCity URL:\t\t%s
  """ %(branch_mapping, parent_branch, branch, build_server_name, team_city_p4_client, branch_folder_name, team_city_url)
  email(subject, body)

def config_format():
  return """
    Please create config file (integ.yaml) first and save it to the same directory as integ-from-parent.py
    As an example, integ.conf for experience-dev contains:

    branch: experience-dev
    parent_branch: experience
    parent_path: //depot/teams/experience
    client_name: experience_dev_integration
  """

def config_info():

  return """
branch = %s
parent_branch = %s
parent_path = %s
parent_change = %s
client_name = %s
branch_folder_name = %s
config_file_path = %s
email_recipients = %s
branch_mapping = %s
build_server_name = %s
team_city_url = %s
team_city_p4_client = %s
revert_p4_files = %s
gated_integration = %s
skip_tube = %s
build_only = %s
""" % (branch, parent_branch, parent_path, parent_change, client_name, branch_folder_name, config_file_path, email_recipients,
       branch_mapping, build_server_name, team_city_url, team_city_p4_client, revert_p4_files, gated_integration, skip_tube, build_only)

def read_config():
  try:
    config_file = open(config_file_path, 'r')
    config = yaml.load(config_file)

    global branch
    branch = config["branch"]
    global parent_branch
    parent_branch = config["parent_branch"]
    global parent_path
    parent_path = config["parent_path"]
    global email_recipients
    email_recipients = config["email_recipients"]
    global branch_mapping
    branch_mapping = config.get("branch_mapping", False)
    global build_server_name
    build_server_name = config.get("build_server_name", False)
    global team_city_url
    team_city_url = config.get("team_city_url", False)
    global team_city_p4_client
    team_city_p4_client = config.get("p4_client", False)
    global revert_p4_files
    revert_p4_files = config.get("revert_perforce_files", False)
    global gated_integration
    gated_integration = config.get("gated_integration", False)
    global skip_tube
    if skip_tube is None:
      skip_tube = config.get("skip_tube", False)
    global build_only
    build_only = config.get("build_only", False)
    global parent_change
    parent_change = config.get("parent_change", None)

    global client_name
    if "client_name" not in config:
      client_name = None
    else:
      print >> out_channel, "Setting client_name in YAML is deprecated. Please set branch_folder_name instead (see integ.yaml) and create a .p4config with the right client-name"
      client_name = config["client_name"]

    global branch_folder_name
    branch_folder_name = config["branch_folder_name"] if "branch_folder_name" in config else client_name

    if (branch is None or parent_branch is None or parent_path is None or branch_folder_name is None):
      print >> out_channel, "%s" % config_info()
      print >> out_channel, config_format()
      sys.exit(2)
    else:
      global progress
      progress += "%s\n" % config_info()

  except IOError as e:
    print >> out_channel, e
    print >> out_channel, config_format()
    sys.exit(2)

  except KeyError as e:
    print >> out_channel, "Key %s missing or set incorrectly" % e
    print >> out_channel, config_format()
    sys.exit(2)

def sync(p4, sync_cl_no):
  try:
    global progress

    if sync_cl_no == 0:
      msg = "Syncing to head of %s ..." % branch
      progress += "%s\n" % msg
      print >> out_channel, msg
      p4.run_sync()
    else:
      msg = "Syncing to %s@%s" % (branch, sync_cl_no)
      progress += "%s\n" % msg
      print >> out_channel, msg
      p4.run_sync("...@%s" % sync_cl_no)
  except P4Exception:
    # File(s) up-to-date is a warning
    if len(p4.warnings) == 1 and ("file(s) up-to-date" in p4.warnings[0].lower()):
      progress += "%s\n" % p4.warnings[0]
      print >> out_channel, p4.warnings[0]
    else:
      error_message = "Failed to p4 sync. Integration aborted."
      email_error(error_message)
      raise RuntimeError(error_message)

def integ(p4, integ_cl_no):  # return the changelist number integrated to
  if integ_cl_no == 0:
    last_cl = p4.run("changes", "-m 1", "-t", "-s", "submitted", "%s/..." % parent_path)[0]
    last_cl_no = last_cl["change"]
    integ_cl_no = last_cl_no

  try:
    global progress

    msg = "Integrating %s@" % parent_branch + integ_cl_no + " ..."
    progress += "%s\n" % msg
    print >> out_channel, msg

    if branch_mapping:
        p4.run_integ("-b", "%s" % (branch_mapping), "-t", ("@%s" % integ_cl_no))
    else:
        p4.run_integ("-b", "%s_to_%s_branch" % (parent_branch, branch), "-t", ("@%s" % integ_cl_no))

    # p4python doesn't treat things like "can't branch without -d or -Dt flag" as warnings and merely
    # reports it as an info-level message. Explicitly ensure the absence of these warnings by checking p4 messages
    if not p4.messages:
      return integ_cl_no
    else:
      for m in p4.messages:
        print >> out_channel, m

  except P4Exception:
    if len(p4.warnings) == 1 and ("all revision(s) already integrated" in p4.warnings[0].lower()):
      progress += "%s\n" % p4.warnings[0]
      print >> out_channel, p4.warnings[0]
      return integ_cl_no
    else:
      for w in p4.warnings:
        print >> out_channel, w

      for w in p4.errors:
        print >> out_channel, w

  error_message = "Warnings exist after running p4 integ. Integration aborted. Please investigate -d and -i warnings before continuing."
  email_error(error_message)
  raise RuntimeError(error_message)


def get_command_output(command):
    """
    Execute a shell command and return its output..
    @param command: The command line to execute, list first element is program, remaining elements are args
    @return: dictionary of errorcode, stdout, and stderr data
    """
    sp = subprocess.Popen(command, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,
                          shell=True)
    out, err = sp.communicate()
    returnvalue = dict(errorcode=sp.returncode, stdout=out, stderr=err)
    return returnvalue


def resolve(p4):
  try:
    global progress

    msg = "Auto Resolving ..."
    progress += "%s\n" % msg
    print >> out_channel, msg
    p4.run_resolve("-am")
    results = get_command_output("p4 resolve -n")
    # exitcode <> 0 or something other than "No file(s) to resolve" being output is something to pay attention to.
    if results['errorcode'] != 0 or len(results['stdout']) or len(results['stderr']):
      if "No file(s) to resolve" in results['stderr']:
        print >> out_channel, results['stderr']
      else:
        error_message = "\nManual resolution required. Integration aborted.\nResume with\n"
        error_message = "{} {} -o -c {}".format(error_message, 
                                                os.path.normpath(__file__),
                                                os.path.normpath(config_file_path))
        error_message = "{}\n--------------------------\n".format(error_message)
        error_message = "{}\n{}".format(error_message, results['stdout'])
        error_message = "{}\n--------------------------\n".format(error_message)
        error_message = "{}\n{}".format(error_message, results['stderr'])
        email_error(error_message)
        raise RuntimeError(error_message)

  except P4Exception:
    if len(p4.warnings) == 1 and p4.warnings[0] == "No file(s) to resolve.":
      progress += p4.warnings[0]
      print >> out_channel, p4.warnings[0]
    else:
      for w in p4.warnings:
        print >> out_channel, w

      error_message = "Warnings exist after running p4 resolve. Integration aborted.\nResume with {} -o -c {}".format(__file__, config_file_path)
      error_message = "{}\n{}".format(error_message, p4.warnings)

      email_error(error_message)
      raise RuntimeError(error_message)

def change_and_lock(p4, integ_cl_no):
  global progress

  opened = p4.run_opened()
  if not opened:  # make sure files are open on the client
    email_noop()
    print >> out_channel, "No files Open for Edit.  Quitting."
    sys.exit(0)

  try:
    description = "Integrate %s@%s to %s" % (parent_branch, integ_cl_no, branch)
    msg = "Creating changelist '%s' ..." % description
    progress += "%s\n" % msg
    print >> out_channel, msg
    change = p4.fetch_change()
    change["Description"] = description
    change["Description"] += "\n%bypass_tfsid_check%\n"
    change["Description"] += "proof: %bypass_proof_check%\n"

    # To get the new changelist number, we need to parse the output from "save_change".
    # We use an example from http://forums.perforce.com/index.php?/topic/2737-p4python-create-a-pending-changelist-and-reference-its-number/.
    result = p4.save_change(change)
    r = re.compile("Change ([1-9][0-9]*) created.")
    m = r.match(result[0])
    change_id = "0"
    if m: change_id = m.group(1)
    msg = "Change: %s" % change_id
    print >> out_channel, msg
    if not gated_integration:
        msg = "Locking files for integration ..."
        progress += "%s\n" % msg
        print >> out_channel, msg
        p4.run_lock()
    return change_id

  except P4Exception:
    for e in p4.errors:            # Display errors
      print >> out_channel, e
    for e in p4.warnings:
      print >> out_channel, e

    error_message = "Error creating and locking a changelist for the pending changes. Integration aborted.\nResume with {} -o -c {}".format(__file__, config_file_path)
    email_error(error_message)
    raise RuntimeError(error_message)

def tube(p4, tube_clean, change_id, discard_cl_on_tube_failure):
  global progress

  tube_subfolder = "%s\\tableau-tools\\pipeline\\" % os.getcwd()

  # set TAB4_PROCESSES = 16 to use all 16 cores on the build machine during tube run
  os.environ["TAB4_PROCESSES"] = "16"

  msg = "Running tube.py ..."
  progress += "%s\n" % msg
  print >> out_channel, msg
  out_channel.flush()

  proc = subprocess.Popen(("python %stube.py %s -s %s -b -d -l" % (tube_subfolder, "-r" if tube_clean else "", "-T" if not build_only else "")), shell = True, stdout = out_channel)
  tube_ret = proc.wait()
  if tube_ret == 0:
      if gated_integration:
        print change_id
        _run_gsub(change_id)
        return
      else:
        msg = "Tube.py ran clean. Submitting integration ..."
        progress += "%s\n" % msg
        print >> out_channel, msg
        out_channel.flush()

        p4.run_submit("-c", str(change_id))
        email_success()
        return

  # discard and shelve the changes in the integration cl if this is desired
  if discard_cl_on_tube_failure:
    try:
      p4.run_shelve("-c", str(change_id))
      p4.run_revert("-c", str(change_id), "//...")
    except P4Exception:
      for e in p4.errors:            # Display errors and warnings
        print >> out_channel, e
      for e in p4.warnings:
        print >> out_channel, e

  error_message = "tube.py failed. The integration changelist is not submitted. See %s\\pipelog.txt on the build machine for details." % os.getcwd()
  email_error(error_message)
  raise RuntimeError(error_message)

def usage():
  return """
    Usage: %s [Options]

    If no options are specified, the script will
    * sync to head in %s
    * integrate from %s to %s
    * run tube.py -s -T -b -d -l
    * write to stdout
    * not email the recipients specified in integ.yaml

    Options:
    -c <file_path>         Path to config file

    -o                     Proceed even when there are open files on the client
    --opened               Proceed even when there are open files on the client

    -e                     Email the recipients in integ.yaml when manual intervention is needed
    --email                Email the recipients in integ.yaml when manual intervention is needed

    -l <log_file_name>     Write to log file instead of stdout
    --log=<log_file_name>  Write to log file instead of stdout

    -s <sync_cl_no>        Sync to <sync_cl_no> in %s
    --sync=<sync_cl_no>    Sync to <sync_cl_no> in %s

    -i <integ_cl_no>       Integrate from <integ_cl_no> in %s
    --integ=<integ_cl_no>  Integrate from <integ_cl_no> in %s

    -r                     Clean before build and test, i.e. run tube -r -s -T -b -d -l

    -d                     Discard and shelve integration CL if tube fails

    --skip-tube            Submit without running tube. Used for integrating assets, docs
                           and other special cases where a build isn't necessary or desired

    -h                     Usage
    --help                 Usage
  """ % (sys.argv[0], branch, parent_branch, branch, branch, branch, parent_branch, parent_branch)

def revert_p4(p4):
    if revert_p4_files:
        try:
            print ("Revert checked out P4 files is set to: {} " .format(str(revert_p4_files)))
            print ("Reverting files from p4 client: {}" .format(str(team_city_p4_client)))
            revert_files = subprocess.Popen('p4 revert //...', stdout=subprocess.PIPE)
            revert_output = revert_files.stdout.read()
            print revert_output
        except P4Exception:
            for e in p4.errors:            # Display errors and warnings
                print >> out_channel, e
            for e in p4.warnings:
                print >> out_channel, e

def _run_gsub(change_id):
    print("Starting Gsub integration with CL {}".format(change_id))
    os.chdir(os.path.join(os.getcwd(), "tableau-tools", "pipeline"))
    print os.getcwd()
    run_gsub = subprocess.check_output(['python', 'gsub.py', 'submit', change_id], stderr=subprocess.STDOUT)
    cat_url = run_gsub[run_gsub.find("http"):].strip()
    print cat_url
    email_send_to_gsub(cat_url)

def main(argv):
  p4 = None
  try:
    allow_open_files = False
    tube_clean = False
    discard_cl_on_tube_failure = False
    global skip_tube
    skip_tube = None
    sync_cl_no = 0
    integ_cl_no = 0

    opts, args = getopt.getopt(argv, "h:ore:s:i:l:c:d:", ["help", "open", "email", "sync=", "integ=", "log=", "skip-tube"])
    for opt, arg in opts:
      if opt in ("-h", "--help"):
        print usage()
        sys.exit()
      elif opt in ("-o", "--open"):
        allow_open_files = True
      elif opt in ("-r"):
        tube_clean = True
      elif opt in ("-e", "--email"):
        global email_recipients
        email_recipients = arg
      elif opt in ("-s", "--sync"):
        sync_cl_no = arg
      elif opt in ("-i", "--integ"):
        integ_cl_no = arg
      elif opt in ("-l", "--log"):
        global out_channel
        out_channel = open(arg, "a")
      elif opt in ("-c"):
        global config_file_path
        config_file_path = arg
      elif opt in ("-d"):
        discard_cl_on_tube_failure = True
      elif opt in ("--skip-tube"):
        skip_tube = True
      else:
        print >> out_channel, "Unknown command-line option: %s\n" % opt

    # Read config file
    read_config()

    # If integ_cl_no wasn't passed, look for parent_change in the
    # Yaml configuration file.
    if integ_cl_no == 0 and parent_change is not None:
      integ_cl_no = str(parent_change)
    print "integ_cl_no is set to: {}".format(integ_cl_no)

    with working_directory(branch_folder_name):
      p4 = P4()
      if not client_name is None:
        p4.client = client_name
      p4.connect()                   # Connect to the Perforce Server
      revert_p4(p4) # revert checked out files if running as custom build and set to p4_revert set to true



      # log the timestamp and config info
      print >> out_channel, "\n\n%s%s\n" % (str(datetime.datetime.now()), config_info())

      opened = p4.run_opened()
      if opened and (not allow_open_files):
        error_message = "Files open on this client. Integration aborted."
        email_error(error_message)
        raise RuntimeError(error_message)

      sync(p4, sync_cl_no)

      # Do the integration. If integ_cl_no not specified, integ()
      # will return the head change from the source branch.
      integ_cl_no = integ(p4, integ_cl_no)

      resolve(p4)

      change_id = change_and_lock(p4, integ_cl_no)

      out_channel.flush()

      if skip_tube:
        if gated_integration:
            print change_id
            _run_gsub(change_id)
            return
        msg = "Skip tube.py. Submitting integration ..."
        global progress
        progress += "%s\n" % msg
        print >> out_channel, msg
        out_channel.flush()
        p4.run_submit("-c", str(change_id))
        email_success()
      else:
        tube(p4, tube_clean, change_id, discard_cl_on_tube_failure)

  except getopt.GetoptError:
    print usage()
    sys.exit(2)

  except P4Exception:
    for e in p4.errors:            # Display errors
      print >> out_channel, e
    for e in p4.warnings:
      print >> out_channel, e
    sys.exit(1)

  except RuntimeError as re:
    print >> out_channel, re
    sys.exit(1)

  finally:
    out_channel.flush()
    out_channel.close()
    if p4:
      p4.disconnect()                # Disconnect from the Server

if __name__ == "__main__":
  main(sys.argv[1:])
