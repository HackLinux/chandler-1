# build client script for building a project

# must be run from the hardhat directory, which will be updated to the
# appropriate CVS vintage by this script, so it's a good idea to first
# bring the hardhat directory (or at least this file) up to the latest
# vintage with a "cvs update -A" before running it, since after running
# it, it may get reverted to an earlier version

import hardhatutil, time, smtplib, os, sys, getopt

# args:  toAddr, buildName, project, vintage
def usage():
    print "python singlebuild.py [OPTION]..."
    print ""
    print "-b BUILDVER    string to put into the buildversion encoded in app"
    print "-d DATE        date to use for CVS checkout"
    print "-i RELEASE-ID  what string to encode into filenames for release"
    print "-m MAILTO      who to email when build is finished"
    print "-p PROJECT     name of project, must have a buildscript"
    print "-t TAG         tag to use for CVS checkout"


def main():

    nowString = time.strftime("%Y-%m-%d %H:%M:%S")
    nowShort = RemovePunctuation(nowString)
    # nowString is the current time, in a CVS-compatible format
    print nowString
    # nowShort is nowString without punctuation or whitespace
    print nowShort

    try:
        opts, args = getopt.getopt(sys.argv[1:], "b:d:i:m:p:t:")
    except getopt.GetoptError:
        usage()
        sys.exit(1)

    buildVersionArg = None
    cvsDateArg = None
    releaseIdArg = None
    toAddrArg = None
    projectArg = None
    cvsTagArg = None

    for opt, arg in opts:

        if opt == "-b":
            buildVersionArg = arg

        if opt == "-d":
            cvsDateArg = arg

        if opt == "-i":
            releaseIdArg = arg

        if opt == "-m":
            toAddrArg = arg

        if opt == "-p":
            projectArg = arg

        if opt == "-t":
            cvsTagArg = arg

    if cvsDateArg and cvsTagArg:
        print "Please choose either a cvs date or tag, not both"
        sys.exit(1)

    # defaults:
    project = "chandler"
    toAddr  = "morgen@osafoundation.org"
    buildVersion = nowString
    releaseId = nowShort

    # default is "-D now", but override with date; override that with tag
    cvsVintage = "-D '" + nowString + "'"
    if cvsDateArg:
        cvsVintage = "-D " + cvsDateArg
        buildVersion = cvsDateArg
        releaseId = RemovePunctuation(buildVersion)
    if cvsTagArg:
        cvsVintage = "-R " + cvsTagArg
        buildVersion = cvsTagArg
        releaseId = RemovePunctuation(buildVersion)
    if buildVersionArg:
        buildVersion = buildVersionArg
        releaseId = RemovePunctuation(buildVersion)
    if releaseIdArg:
        releaseId = releaseIdArg

    print "nowString", nowString
    print "nowShort", nowShort
    print "cvsVintage", cvsVintage
    print "buildVersion", buildVersion
    print "releaseId", releaseId

    # cvsVintage is what is used to do a checkout
    # buildVersion is encoded into the application's internal version
    # releaseId is encoded into the distribution filenames

    whereAmI = os.path.dirname(os.path.abspath(hardhatutil.__file__))
    hardhatFile = os.path.join(whereAmI, "hardhat.py")

    homeDir = os.environ['HOME']
    buildDir = os.path.join(homeDir, "singlebuild")
    logFile = os.path.join(buildDir, "build.log")
    buildscriptFile = os.path.join("buildscripts", project + ".py")
    fromAddr = "builds@osafoundation.org"

    curDir = os.path.abspath(os.getcwd())

    if not os.path.exists(buildDir):
        os.mkdir(buildDir)

    path = os.environ.get('PATH', os.environ.get('path'))
    cvsProgram = hardhatutil.findInPath(path, "cvs")
    # print "CVS =", cvsProgram

    log = open(logFile, "w+")
    try:
        # bring this hardhat directory up to date
        outputList = hardhatutil.executeCommandReturnOutput(
         [cvsProgram, "update", "-D '"+ nowString + "'"])

        # load the buildscript file for the project
        mod = hardhatutil.ModuleFromFile(buildscriptFile, "buildscript")

        # SendMail(fromAddr, toAddr, startTime, buildName, "building", 
        #  treeName, None)

        mod.Start(hardhatFile, buildDir, cvsVintage, buildVersion, 1, log)

    except Exception, e:
        print e
        print "something failed"
        log.write("something failed")
        status = "build_failed"
    else:
        print "all is well"
        log.write("all is well")
        status = "success"
    log.close()

    log = open(logFile, "r")
    logContents = log.read()
    log.close()
    nowTime = str(int(time.time()))

    # SendMail(fromAddr, toAddr, startTime, buildName, status, treeName, 
    # logContents)

def SendMail(fromAddr, toAddr, startTime, buildName, status, treeName, logContents):
    nowTime  = str(int(time.time()))
    msg      = ("From: %s\r\nTo: %s\r\n\r\n" % (fromAddr, toAddr))
    msg      = msg + "tinderbox: tree: " + treeName + "\n"
    msg      = msg + "tinderbox: buildname: " + buildName + "\n"
    msg      = msg + "tinderbox: starttime: " + startTime + "\n"
    msg      = msg + "tinderbox: timenow: " + nowTime + "\n"
    msg      = msg + "tinderbox: errorparser: unix\n"
    msg      = msg + "tinderbox: status: " + status + "\n"
    msg      = msg + "tinderbox: administrator: builds@osafoundation.org\n"
    msg      = msg + "tinderbox: END\n"
    if logContents:
        msg  = msg + logContents

    server = smtplib.SMTP('mail.osafoundation.org')
    server.sendmail(fromAddr, toAddr, msg)
    server.quit()

def RemovePunctuation(str):
    s = str.replace("-", "")
    s = s.replace(" ", "")
    s = s.replace(":", "")
    return s

main()
