#!/usr/bin/env python

# tinderbox build client script for continuously building a project and
# reporting to a tinderbox server
# This new scrip is run from the "cycle.py" script
# The cycle.py script does the hardhat updates, so any changes
# to the main script can be picked up

import hardhatutil, time, smtplib, os, sys
from optparse import OptionParser

whereAmI = os.path.dirname(os.path.abspath(hardhatutil.__file__))
hardhatFile = os.path.join(whereAmI, "hardhat.py")

homeDir = os.environ['HOME']
buildDir = os.path.join(homeDir, "tinderbuild")
logFile = os.path.join(buildDir, "build.log")
HHlogFile = os.path.join(buildDir, "hardhat.log")
stopFile = os.path.join(buildDir, "stop")
fromAddr = "builds"
mailtoAddr = "buildreport"
alertAddr = "buildman"
adminAddr = "builds"
defaultDomain = "@osafoundation.org"
defaultRsyncServer = "192.168.101.46"      #  IP of current server

def main():
    global buildscriptFile, fromAddr, mailtoAddr, alertAddr, adminAddr, defaultDomain, defaultRsyncServer
    
    parser = OptionParser(usage="%prog [options] buildName", version="%prog 1.2")
    parser.add_option("-t", "--toAddr", action="store", type="string", dest="toAddr",
      default=mailtoAddr, help="Where to mail script reports\n"
      " [default] " + mailtoAddr + defaultDomain)
    parser.add_option("-p", "--project", action="store", type="string", dest="project",
      default="newchandler", help="Name of script to use (without .py extension)\n"
      "[default] newchandler")
    parser.add_option("-o", "--output", action="store", type="string", dest="outputDir",
      default=os.path.join(os.environ['HOME'],"output"), help="Name of temp output directory\n"
      " [default] ~/output")
    parser.add_option("-a", "--alert", action="store", type="string", dest="alertAddr",
      default=alertAddr, help="E-mail to notify on build errors \n"
      " [default] " + alertAddr + defaultDomain)
    parser.add_option("-r", "--rsyncServer", action="store", type="string", dest="rsyncServer",
      default=defaultRsyncServer, help="Net address of server where builds get uploaded \n"
      " [default] " + defaultRsyncServer)
    parser.add_option("-s", "--skipRSync", action="store_true", dest="skipRsync",
      default=False, help="Skip rsync step \n"
      " [default] False")
    parser.add_option("-u", "--uploadStaging", action="store_true", dest="uploadStaging",
      default=False, help="Upload tarballs to staging area \n"
      " [default] False")
    parser.add_option("-S", "--skipTests", action="store_true", dest="skipTests",
      default=False, help="Skip Unit Tests \n"
      " [default] False")

    (options, args) = parser.parse_args()
    if len(args) < 1:
        parser.print_help()
        parser.error("You must at least provide a name for your build")

    buildName = args[0]
    fromAddr += defaultDomain
    mailtoAddr = options.toAddr
    alertAddr = options.alertAddr
    if mailtoAddr.find('@') == -1:
        mailtoAddr += defaultDomain
    if alertAddr.find('@') == -1:
        alertAddr += defaultDomain
    skipRsync = options.skipRsync
    uploadStaging = options.uploadStaging
        
    curDir = os.path.abspath(os.getcwd())
    buildscriptFile = os.path.join("buildscripts", options.project + ".py")

    outputDir = os.path.abspath(options.outputDir)
    if not os.path.exists(outputDir):
        os.mkdir(outputDir)

    if not os.path.exists(buildDir):
        os.mkdir(buildDir)

    path = os.environ.get('PATH', os.environ.get('path'))
    cvsProgram = hardhatutil.findInPath(path, "cvs")
    print "cvs =", cvsProgram
    rsyncProgram = hardhatutil.findInPath(path, "rsync")
    print "rsync =", rsyncProgram

    startInt = int(time.time())
    startTime = str(startInt)
    os.chdir(curDir)

    nowString = time.strftime("%Y-%m-%d %H:%M:%S")
    buildVersion = hardhatutil.RemovePunctuation(nowString)
    print "Starting:", nowString, buildVersion

    log = open(logFile, "w")
    log.write("Start: " + nowString + "\n")

    try:
        # load (or reload) the buildscript file for the project
        mod = hardhatutil.ModuleFromFile(buildscriptFile, "buildscript")

        treeName = mod.treeName

        SendMail(fromAddr, mailtoAddr, startTime, buildName, "building", 
         treeName, None)

        ret = mod.Start(hardhatFile, buildDir, "-D'"+ nowString + "'", 
         buildVersion, 0, log, upload=options.uploadStaging, skipTests=options.skipTests)

    except TinderbuildError, e:
        print e
        print "Tinderbuild:  Build failed"
        log.write("Tinderbuild:  Build failed\n")
        status = "build_failed"
        log.close()

        log = open(logFile, "r")
        logContents = log.read()
        log.close()
        SendMail(fromAddr, alertAddr, startTime, buildName,
                 "The build failed", treeName, None)
        SendMail(fromAddr, mailtoAddr, startTime, buildName, status, 
         treeName, logContents)
        log = open(logFile, "w")

    except Exception, e:
        print e
        print "Build failed"
        log.write("Build failed\n")
        status = "build_failed"
        log.close()

        log = open(logFile, "r")
        logContents = log.read()
        log.close()
        SendMail(fromAddr, alertAddr, startTime, buildName,
                 "The build failed", treeName, None)
        SendMail(fromAddr, mailtoAddr, startTime, buildName, status, 
         treeName, logContents)
        log = open(logFile, "w")

    else:
        if ret == "success-nochanges":
            print "There were no changes, and the tests were successful"
            log.write("There were no changes, and the tests were successful\n")
            status = "success"
        elif ret == "success-changes" or ret == "success-first-run":
            if ret == "success-first-run":
                print "First run of tinderbox, and the tests were successful"
                log.write("First run of tinderbox, and the tests were successful\n")
            else:
                print "There were changes, and the tests were successful"
                log.write("There were changes, and the tests were successful\n")

            status = "success"

            newDir = os.path.join(outputDir, buildVersion)
            print "Renaming " + os.path.join(buildDir, "output", buildVersion) + " to " + newDir 
            log.write("Renaming " + os.path.join(buildDir, "output", buildVersion) + " to " + newDir + "\n")
            os.rename(os.path.join(buildDir, "output", buildVersion), newDir)
            if os.path.exists(outputDir+os.sep+"index.html"):
                os.remove(outputDir+os.sep+"index.html")
            if os.path.exists(outputDir+os.sep+"time.js"):
                os.remove(outputDir+os.sep+"time.js")
            print "Calling CreateIndex with " + newDir
            log.write("Calling CreateIndex with " + newDir + "\n")
            CreateIndex(outputDir, buildVersion, nowString, buildName)
            print "Calling RotateDirectories"
            log.write("Calling RotateDirectories\n")
            RotateDirectories(outputDir)

            buildNameNoSpaces = buildName.replace(" ", "")
            
            if skipRsync:
                print "skipping rsync"
                log.write("skipping rsync")
            else:
                print "Rsyncing..."
                log.write('rsync -e ssh -avzp ' + outputDir + os.sep + ' ' +
                          options.rsyncServer + ':continuous/' +
                          buildNameNoSpaces)
                outputList = hardhatutil.executeCommandReturnOutputRetry(
                 [rsyncProgram, "-e", "ssh", "-avzp",
                 outputDir + os.sep, 
                 options.rsyncServer + ":continuous/" + buildNameNoSpaces])
                hardhatutil.dumpOutputList(outputList, log)

            if not uploadStaging:
                print "skipping rsync to staging area"
                log.write("skipping rsync to staging area")
            else:
                timestamp = nowString.replace("-", "")
                timestamp = timestamp.replace(":", "")
                timestamp = timestamp.replace(" ", "")

                if not os.path.isdir(timestamp):
                    print "skipping rsync to staging area, no dir", timestamp
                    log.write("skipping rsync to staging area, no dir")
                else:
                    if os.name == 'nt' or sys.platform == 'cygwin':
                        platform = 'windows'
                    elif sys.platform == 'darwin':
                        platform = 'macosx'
                    else:
                        platform = 'linux'

                    print "Rsyncing to staging area..."
                    log.write('rsync -e ssh -avzp ' + timestamp + ' ' +
                              options.rsyncServer + ':staging/' +
                              platform)
                    outputList = hardhatutil.executeCommandReturnOutputRetry(
                     [rsyncProgram, "-e", "ssh", "-avzp",
                     timestamp, 
                     options.rsyncServer + ":staging/" + platform])
                    hardhatutil.dumpOutputList(outputList, log)

                    completedFile = timestamp + os.sep + "completed"
                    open(completedFile, "w").close()

                    log.write('rsync -e ssh -avzp ' + completedFile + ' ' +
                              options.rsyncServer + ':staging/' +
                              platform + "/" + timestamp)
                    outputList = hardhatutil.executeCommandReturnOutputRetry(
                     [rsyncProgram, "-e", "ssh", "-avzp",
                     completedFile, 
                     options.rsyncServer + ":staging/" + platform + "/" + timestamp])
                    hardhatutil.dumpOutputList(outputList, log)

                    hardhatutil.rmdirRecursive(timestamp)

        elif ret[:12] == "build_failed":
            print "The build failed"
            log.write("The build failed\n")
            status = "build_failed"
            log.close()
    
            log = open(logFile, "r")
            logContents = log.read()
            log.close()
            SendMail(fromAddr, alertAddr, startTime, buildName,
                     "The build failed", treeName, None)
            SendMail(fromAddr, mailtoAddr, startTime, buildName, status, 
             treeName, logContents)
            log = open(logFile, "w")

        
        elif ret[:11] == "test_failed":
            print "Unit tests failed"
            log.write("Unit tests failed\n")
            status = "test_failed"
            log.close()
    
            log = open(logFile, "r")
            logContents = log.read()
            log.close()
            SendMail(fromAddr, alertAddr, startTime, buildName,
                     "Unit tests failed", treeName, None)
            SendMail(fromAddr, mailtoAddr, startTime, buildName, status, 
             treeName, logContents)
            log = open(logFile, "w")
        
        else:
            print "There were no changes"
            log.write("There were no changes in CVS\n")
            status = "not_running"

        log.write( "End = " + time.strftime("%Y-%m-%d %H:%M:%S") + "\n")

        log.close()

        log = open(logFile, "r")
        logContents = log.read()
        log.close()
        nowTime = str(int(time.time()))

        SendMail(fromAddr, mailtoAddr, startTime, buildName, status, treeName, 
         logContents)

def SendMail(fromAddr, toAddr, startTime, buildName, status, treeName, logContents):
    nowTime  = str(int(time.time()))
    subject = "[tinderbox] " + status + " from " + buildName
    msg  = ("From: %s\r\nTo: %s\r\nSubject: %s\r\n\r\n" % (fromAddr, toAddr, subject))
    msg += "tinderbox: tree: " + treeName + "\n"
    msg += "tinderbox: buildname: " + buildName + "\n"
    msg += "tinderbox: starttime: " + startTime + "\n"
    msg += "tinderbox: timenow: " + nowTime + "\n"
    msg += "tinderbox: errorparser: unix\n"
    msg += "tinderbox: status: " + status + "\n"
    msg += "tinderbox: administrator: " + adminAddr + defaultDomain + "\n"
    msg += "tinderbox: END\n"
    if logContents:
        msg += logContents

    try:
        server = smtplib.SMTP('mail.osafoundation.org')
        server.sendmail(fromAddr, toAddr, msg)
        server.quit()
    except Exception, e:
        print "SendMail error", e

def RotateDirectories(dir):
    """Removes all but the 3 newest subdirectories from the given directory;
    assumes the directories are named with timestamps (numbers) because it 
    uses normal sorting to determine the order."""

    dirs = os.listdir(dir)
    for anyDir in dirs:
        if not os.path.isdir(os.path.join(dir, anyDir)):
            dirs.remove(anyDir)

    dirs.sort()
    for subdir in dirs[:-3]:
        subdir = os.path.join(dir, subdir)
        if os.path.isdir(subdir):
            hardhatutil.rmdirRecursive(subdir)

_descriptions = {
    'enduser' : ["End-Users' distribution", "If you just want to use Chandler, this distribution contains everything you need -- just download, install and run."],
    'developer' : ["Developers' distribution", "If you're a developer and want to run Chandler in debugging mode, this distribution contains debug versions of the binaries.  Assertions are active, the __debug__ global is set to True, and memory leaks are listed upon exit.  You can also use this distribution to develop your own parcels (See <a href='http://wiki.osafoundation.org/bin/view/Chandler/ParcelLoading'>Parcel Loading</a> for details on loading your own parcels)."],
}


def CreateIndex(outputDir, newDirName, nowString, buildName):
    """
    Generates HTML files that contain links and hash information
    for downloadable files.
    """

    newPrefix = outputDir + os.sep + newDirName + os.sep

    head1 = '<html>\n<head>\n' +\
            '<META HTTP-EQUIV="Pragma" CONTENT="no-cache">\n' +\
            '<title>Download Chandler ' + buildName + ' ' + newDirName + '</title>\n' +\
            '<link rel="Stylesheet" ' +\
            'href="http://www.osafoundation.org/css/OSAF.css" ' +\
            'type="text/css" charset="iso-8859-1">\n'
    head2 = '</head>\n' +\
            '<body>\n' +\
            '<img src="http://www.osafoundation.org/images/OSAFLogo.gif" ' + 'alt="[OSAF Logo]">\n' +\
            '<h2>Chandler Build: ' + nowString + ' PDT (machine: ' + buildName + ')</h2>\n'
    cryptoblurb = '<p>This software is subject to the U.S. Export ' +\
                  'Administration Regulations and other U.S. law, and may ' +\
                  'not be exported or re-exported to certain countries ' +\
                  '(currently Cuba, Iran, Libya, North Korea, Sudan and ' +\
                  'Syria) or to persons or entities prohibited from ' +\
                  'receiving U.S. exports (including Denied Parties, ' +\
                  'Specially Designated Nationals, and entities on the ' +\
                  'Bureau of Industry and Security Entity List or involved ' +\
                  'with missile technology or nuclear, chemical or ' +\
                  'biological weapons).</p>\n'
    index = head1 + head2 + cryptoblurb

    for distro in ('enduser', 'developer'):
        lines = _readFile(os.path.join(outputDir, newDirName, distro))
        
        for line in lines:
            actualDistroFile = line.strip()
            actualDistro     = os.path.join(outputDir, newDirName, actualDistroFile)

            index += '<p>Download <a href="' + actualDistroFile + '"> ' +\
                     _descriptions[distro][0] + '</a> (' +\
                     hardhatutil.fileSize(actualDistro) + '): <br>\n' +\
                     ' MD5 checksum: ' + hardhatutil.MD5sum(actualDistro) +\
                     '<br>\n' +\
                     ' SHA checksum: ' + hardhatutil.SHAsum(actualDistro) +\
                     '<br>\n<p>' + _descriptions[distro][1] + '</p>\n'

    index += '</body></html>\n'

    fileOut = file(newPrefix + "index.html", "w")
    fileOut.write(index)
    fileOut.close()

    fileOut = file(outputDir + os.sep + "latest.html", "w")
    fileOut.write(head1 +\
                  '<meta http-equiv="refresh" content="0;URL=' + newDirName + '">\n' +\
                  head2 +\
                  '<h2>Latest Continuous ' + buildName + ' Build</h2>\n' +\
                  '<a href="' + newDirName + '">' + newDirName + '</a>\n' +\
                  '</body></html>\n')
    fileOut.close()

    # This file is used by:
    # - http://builds.osafoundation.org/index.html
    # - http://wiki.osafoundation.org/bin/view/Chandler/GettingChandler
    fileOut = file(outputDir+os.sep+"time.js", "w")
    fileOut.write("document.write('" + nowString + "');\n")
    fileOut.close()


def _readFile(path):
    fileIn = open(path, "r")
    lines = fileIn.readlines()
    fileIn.close()
    return lines


class TinderbuildError(Exception):
    def __init__(self, args=None):
        self.args = args


main()
