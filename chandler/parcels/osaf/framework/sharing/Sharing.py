__version__ = "$Revision$"
__date__ = "$Date$"
__copyright__ = "Copyright (c) 2004 Open Source Applications Foundation"
__license__ = "http://osafoundation.org/Chandler_0.1_license_terms.htm"

import application.Globals as Globals
import application.Parcel
import osaf.mail.message
import osaf.contentmodel.mail.Mail as Mail
import osaf.contentmodel.ContentModel as ContentModel
import osaf.contentmodel.contacts.Contacts as Contacts
import osaf.contentmodel.calendar.Calendar as Calendar
import osaf.contentmodel.ItemCollection as ItemCollection
import osaf.current.Current as Current
from chandlerdb.util.UUID import UUID
import application.dialogs.PublishCollection
from repository.item.Query import KindQuery
from repository.util.Lob import Lob
import repository.query.Query as Query
import repository
import logging
import wx
import time, StringIO, urlparse, libxml2, os, mx
import chandlerdb
import WebDAV, httplib
import AccountInfoPrompt

logger = logging.getLogger('Sharing')
logger.setLevel(logging.INFO)


SHARING = "http://osafoundation.org/parcels/osaf/framework/sharing"
EVENTS = "http://osafoundation.org/parcels/osaf/framework/blocks/Events"
CONTENT = "http://osafoundation.org/parcels/osaf/contentmodel"

class Parcel(application.Parcel.Parcel):

    def _errorCallback(self, error):
        # When we receive this event, display the error
        logger.info("_errorCallback: [%s]" % error)
        application.dialogs.Util.ok( \
         wx.GetApp().mainFrame, "Error", error)

# Non-blocking methods that the mail thread can use to call methods on the
# main thread:

def announceError(view, error):
    """ Call this method to announce an error. This method is non-blocking. """
    logger.info("announceError() received an error from mail: [%s]" % error)

    sharingParcel = \
     view.findPath("//parcels/osaf/framework/sharing")
    wx.GetApp().CallItemMethodAsync( sharingParcel,
     '_errorCallback', error)


# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

class Share(ContentModel.ChandlerItem):
    myKindID = None
    myKindPath = "//parcels/osaf/framework/sharing/Share"

    """ Represents a set of shared items, encapsulating contents, location,
        access method, data format, sharer and sharees. """

    def __init__(self, name=None, parent=None, kind=None, view=None,
                 contents=None, conduit=None, format=None):

        super(Share, self).__init__(name, parent, kind, view)

        self.contents = contents # ItemCollection
        self.setConduit(conduit)
        self.format = format

        self.sharer = None
        self.sharees = []

    def setConduit(self, conduit):
        self.conduit = conduit
        self.conduit.share = self

    def create(self):
        self.conduit.create()

    def destroy(self):
        self.conduit.destroy()

    def open(self):
        self.conduit.open()

    def close(self):
        self.conduit.close()

    def sync(self):
        self.conduit.sync()

    def put(self):
        self.conduit.put()

    def get(self):
        self.conduit.get()

    def exists(self):
        return self.conduit.exists()


class ShareConduit(ContentModel.ChandlerItem):
    myKindID = None
    myKindPath = "//parcels/osaf/framework/sharing/ShareConduit"

    """ Transfers items in and out. """

    def __init__(self, name=None, parent=None, kind=None, view=None):
        super(ShareConduit, self).__init__(name, parent, kind, view)

        self.__clearManifest()

    def setShare(self, share):
        self.share = share

    def sync(self):
        items = self.get()
        # @@@MOR For now, since server changes clobber local changes, don't
        # bother putting an item we have just fetched
        self.put(skipItems=items)

    def __conditionalPutItem(self, item, skipItems=None):
        # assumes that self.resourceList has been populated
        skip = False
        if skipItems and item in skipItems:
            skip = True
        if not skip:
            externalItemExists = self.__externalItemExists(item)
            itemVersion = item.getVersion()
            prevVersion = self.__lookupVersion(item)
            if itemVersion > prevVersion or not externalItemExists:
                logger.info("...putting '%s' %s (%d vs %d) (on server: %s)" % \
                 (item.getItemDisplayName(), item.itsUUID, itemVersion,
                 prevVersion, externalItemExists))
                data = self._putItem(item)
                self.__addToManifest(item, data, itemVersion)
                logger.info("...done, data: %s, version: %d" %
                 (data, itemVersion))
            else:
                pass
                # logger.info("Item is up to date")
        try:
            del self.resourceList[self._getItemPath(item)]
        except:
            logger.info("...external item didn't previously exist")

    def put(self, skipItems=None):
        """ Transfer entire 'contents', transformed, to server. """

        self.connect()

        location = self.getLocation()
        logger.info("Starting PUT of %s" % (location))

        self.itsView.commit() # Make sure locally modified items have had
                              # their version numbers bumped up.

        style = self.share.format.fileStyle()
        if style == ImportExportFormat.STYLE_DIRECTORY:

            self.resourceList = self._getResourceList(location)

            for item in self.share.contents:
                self.__conditionalPutItem(item, skipItems)

            self.__conditionalPutItem(self.share, skipItems)

            for (itemPath, value) in self.resourceList.iteritems():
                self._deleteItem(itemPath)

        elif style == ImportExportFormat.STYLE_SINGLE:
            #@@@MOR This should be beefed up to only publish if at least one
            # of the items has changed.
            self._putItem(self.share)

        self.itsView.commit()

        self.disconnect()

        logger.info("Finished PUT of %s" % (location))

    def __conditionalGetItem(self, itemPath, into=None):
        # assumes self.resourceList is populated

        if itemPath not in self.resourceList:
            logger.info("...Not on server: %s" % itemPath)
            return None

        if not self.__haveLatest(itemPath):
            # logger.info("...getting: %s" % itemPath)
            (item, data) = self._getItem(itemPath, into)
            # The version is set to -1 to indicate it needs to be
            # set later on (by syncManifestVersions) because we won't
            # know the item version until *after* commit
            self.__addToManifest(item, data, -1)
            logger.info("...imported '%s' %s, data: %s" % \
             (item.getItemDisplayName(), item, data))
            return item
        else:
            pass
            # logger.info("...skipping")

        return None

    def get(self):

        self.connect()

        location = self.getLocation()
        logger.info("Starting GET of %s" % (location))

        if not self.exists():
            raise NotFound(message="%s does not exist" % location)

        retrievedItems = []
        self.resourceList = self._getResourceList(location)
        self.__resetSeen()

        itemPath = self._getItemPath(self.share)
        item = self.__conditionalGetItem(itemPath, into=self.share)
        if item is not None:
            retrievedItems.append(item)
        self.__setSeen(itemPath)
        try:
            del self.resourceList[itemPath]
        except:
            pass

        for itemPath in self.resourceList:
            item = self.__conditionalGetItem(itemPath)
            if item is not None:
                self.share.contents.add(item)
                retrievedItems.append(item)
            self.__setSeen(itemPath)

        # If an item was prevsiously on the server (it was in our manifest)
        # but is no longer on the server, remove it from the collection
        # locally:
        toRemove = []
        for unseenPath in self.__iterUnseen():
            uuid = self.manifest[unseenPath]['uuid']
            item = self.itsView.findUUID(uuid)
            if item is not None:
                logger.info("...removing %s from collection" % item)
                self.share.contents.remove(item)
                toRemove.append(unseenPath)
        for removePath in toRemove:
            self.__removeFromManifest(removePath)

        self.itsView.commit()
        # Now that we've committed all fetched items, we need to update
        # the versions in the manifest
        self.__syncManifestVersions()
        self.itsView.commit()

        logger.info("Finished GET of %s" % location)

        self.disconnect()

        return retrievedItems

    # Methods that subclasses *must* implement:

    def getLocation(self):
        """ Return a string representing where the share is being exported
            to or imported from, such as a URL or a filesystem path
        """
        pass

    def _getItemPath(self, item):
        """ Return a string that uniquely identifies a resource in the remote
            share, such as a URL path or a filesystem path.  These strings
            will be used for accessing the manfist and resourceList dicts.
        """
        pass

    def _getResourceList(self, location):
        """ Return a dictionary representing what items exist in the remote
            share. """
        # 'location' is a location returned from getLocation
        # The returned dictionary should be keyed on a string that uniquely
        # identifies a resource in the remote share.  For example, a url
        # path or filesystem path.  The values of the dictionary should
        # be dictionaries of the format { 'data' : <string> } where <string>
        # is some piece of data that encapsulates version information for
        # the remote resources (such as a last modified date, or an ETag).
        pass

    def _putItem(self, item, where):
        """ Must implement """
        pass

    def _deleteItem(self, itemPath):
        """ Must implement """
        pass

    def _getItem(self, itemPath, into=None):
        """ Must implement """
        pass

    def connect(self):
        pass

    def disconnect(self):
        pass

    def exists(self):
        pass

    def create(self):
        """ Create the share on the server. """
        pass

    def destroy(self):
        """ Remove the share from the server. """
        pass

    def open(self):
        """ Open the share for access. """
        pass

    def close(self):
        """ Close the share. """
        pass


    # Manifest mangement routines
    # The manifest keeps track of the state of shared items at the time of
    # last sync.  It is a dictionary keyed on "path" (not repo path, but
    # path at the external source), whose values are dictionaries containing
    # the item's internal UUID, external UUID, either a last-modified date
    # (if filesystem) or ETAG (if webdav), and the item's version (as in
    # what item.getVersion() returns)

    def __clearManifest(self):
        self.manifest = {}

    def __addToManifest(self, item, data, version):
        # data is an ETAG, or last modified date
        path = self._getItemPath(item)
        self.manifest[path] = {
         'uuid' : item.itsUUID,
         'data' : data,
         'version' : version,
        }

    def __removeFromManifest(self, path):
        del self.manifest[path]

    def __externalItemExists(self, item):
        itemPath = self._getItemPath(item)
        return itemPath in self.resourceList

    def __lookupVersion(self, item):
        try:
            return self.manifest[self._getItemPath(item)]['version']
        except:
            return -1

    def __haveLatest(self, path, data=None):
        """ Do we have the latest copy of this item? """
        if data == None:
            data = self.resourceList[path]['data']
        try:
            record = self.manifest[path]
            if record['data'] == data:
                # logger.info("haveLatest: Yes (%s %s)" % (path, data))
                return True
            else:
                # print "MISMATCH: local=%s, remote=%s" % (record['data'], data)
                logger.info("...don't have latest (%s local:%s remote:%s)" % (path,
                 record['data'], data))
                return False
        except KeyError:
            pass
            # print "%s is not in manifest" % path
        logger.info("...don't yet have %s" % path)
        return False

    def __resetSeen(self):
        for value in self.manifest.itervalues():
            value['seen'] = False

    def __setSeen(self, path):
        try:
            self.manifest[path]['seen'] = True
        except:
            pass

    def __iterUnseen(self):
        for (path, value) in self.manifest.iteritems():
            if not value['seen']:
                yield path

    def __syncManifestVersions(self):
        # Since repository version numbers change once you have committed,
        # we need to commit first and then run this routine which gets the
        # new version numbers for items we've just imported.
        for (path, value) in self.manifest.iteritems():
            if value['version'] == -1:
                item = self.itsView.findUUID(value['uuid'])
                if item is not None:
                    value['version'] = item.getVersion()



# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

class FileSystemConduit(ShareConduit):
    myKindID = None
    myKindPath = "//parcels/osaf/framework/sharing/FileSystemConduit"

    SHAREFILE = "share.xml"

    def __init__(self, name=None, parent=None, kind=None, view=None,
                 sharePath=None, shareName=None):
        super(FileSystemConduit, self).__init__(name, parent, kind, view)

        self.sharePath = sharePath
        self.shareName = shareName

        if not self.shareName:
            self.shareName = str(UUID())

        # @@@MOR What sort of processing should we do on sharePath for this
        # filesystem conduit?

        # @@@MOR Probably should remove any slashes, or warn if there are any?
        self.shareName = self.shareName.strip("/")

    def getLocation(self): # must implement
        if self.hasLocalAttributeValue("sharePath") and \
         self.hasLocalAttributeValue("shareName"):
            return os.path.join(self.sharePath, self.shareName)
        raise Misconfigured()

    def _getItemPath(self, item): # must implement
        extension = self.share.format.extension(item)
        style = self.share.format.fileStyle()
        if style == ImportExportFormat.STYLE_DIRECTORY:
            if isinstance(item, Share):
                fileName = self.SHAREFILE
            else:
                fileName = "%s.%s" % (item.itsUUID, extension)
            return os.path.join(self.getLocation(), fileName)

        elif style == ImportExportFormat.STYLE_SINGLE:
            return self.getLocation()

        else:
            print "@@@MOR Raise an exception here"

    def _putItem(self, item): # must implement
        path = self._getItemPath(item)
        text = self.share.format.exportProcess(item)
        out = file(path, 'w')
        out.write(text)
        out.close
        stat = os.stat(path)
        return stat.st_mtime

    def _deleteItem(self, itemPath): # must implement
        logger.info("...removing from disk: %s" % itemPath)
        os.remove(itemPath)

    def _getItem(self, itemPath, into=None): # must implement
        # logger.info("Getting item: %s" % itemPath)
        extension = os.path.splitext(itemPath)[1].strip(os.path.extsep)
        text = file(itemPath).read()
        item = self.share.format.importProcess(text, extension=extension,
         item=into)
        stat = os.stat(itemPath)
        return (item, stat.st_mtime)

    def _getResourceList(self, location):
        fileList = {}

        style = self.share.format.fileStyle()
        if style == ImportExportFormat.STYLE_DIRECTORY:
            for filename in os.listdir(location):
                fullPath = os.path.join(location, filename)
                stat = os.stat(fullPath)
                fileList[fullPath] = { 'data' : stat.st_mtime }

        elif style == ImportExportFormat.STYLE_SINGLE:
            stat = os.stat(location)
            fileList[location] = { 'data' : stat.st_mtime }

        else:
            print "@@@MOR Raise an exception here"

        return fileList


    def exists(self):
        super(FileSystemConduit, self).exists()

        style = self.share.format.fileStyle()
        if style == ImportExportFormat.STYLE_DIRECTORY:
            return os.path.isdir(self.getLocation())
        elif style == ImportExportFormat.STYLE_SINGLE:
            return os.path.isfile(self.getLocation())
        else:
            print "@@@MOR Raise an exception here"

    def create(self):
        super(FileSystemConduit, self).create()

        if self.exists():
            raise AlreadyExists()

        if self.sharePath is None or not os.path.isdir(self.sharePath):
            raise Misconfigured(message="Share path is not set, or path doesn't exist")

        style = self.share.format.fileStyle()
        if style == ImportExportFormat.STYLE_DIRECTORY:
            path = self.getLocation()
            if not os.path.exists(path):
                os.mkdir(path)

    def destroy(self):
        super(FileSystemConduit, self).destroy()

        path = self.getLocation()

        if not self.exists():
            raise NotFound(message="%s does not exist" % path)

        style = self.share.format.fileStyle()
        if style == ImportExportFormat.STYLE_DIRECTORY:
            for filename in os.listdir(path):
                os.remove(os.path.join(path, filename))
            os.rmdir(path)
        elif style == ImportExportFormat.STYLE_SINGLE:
            os.remove(path)


    def open(self):
        super(FileSystemConduit, self).open()

        path = self.getLocation()

        if not self.exists():
            raise NotFound(message="%s does not exist" % path)

# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

class WebDAVConduit(ShareConduit):
    myKindID = None
    myKindPath = "//parcels/osaf/framework/sharing/WebDAVConduit"

    def __init__(self, name=None, parent=None, kind=None, view=None,
                 shareName=None, account=None, host=None, port=80,
                 sharePath=None, username="", password="", useSSL=False):
        super(WebDAVConduit, self).__init__(name, parent, kind, view)

        # Use account, if provided.  Otherwise use host, port, username,
        # password and useSSL parameters instead.
        self.account = account
        if account is None:
            self.host = host
            self.port = port
            self.sharePath = sharePath
            self.username = username
            self.password = password
            self.useSSL = useSSL

        if not shareName:
            self.shareName = str(UUID())
        else:
            # @@@MOR Probably should remove any slashes, or warn if there are
            # any?
            self.shareName = shareName.strip("/")

        self.onItemLoad()

    def onItemLoad(self, view=None):
        # view is ignored
        self.client = None

    def __getSettings(self):
        if self.account is None:
            return (self.host, self.port, self.sharePath.strip("/"),
                    self.username, self.password, self.useSSL)
        else:
            return (self.account.host, self.account.port,
                    self.account.path.strip("/"), self.account.username,
                    self.account.password, self.account.useSSL)

    def __getClient(self):
        if self.client is None:
            logger.info("...creating new client")
            (host, port, sharePath, username, password, useSSL) = self.__getSettings()
            self.client = WebDAV.Client(host, port=port, username=username,
                                        password=password, useSSL=useSSL)
        return self.client

    def __releaseClient(self):
        self.client = None

    def getLocation(self):  # must implement
        """ Return the url of the share """

        (host, port, sharePath, username, password, useSSL) = self.__getSettings()
        scheme = "http"
        if useSSL:
            scheme = "https"

        if port == 80:
            url = "%s://%s" % (scheme, host)
        else:
            url = "%s://%s:%d" % (scheme, host, port)
        url = urlparse.urljoin(url, sharePath + "/")
        url = urlparse.urljoin(url, self.shareName)
        return url

    def _getItemPath(self, item): # must implement
        """ Return the path (not the full url) of an item given its external
        UUID """

        (host, port, sharePath, username, password, useSSL) = self.__getSettings()
        extension = self.share.format.extension(item)
        style = self.share.format.fileStyle()
        if style == ImportExportFormat.STYLE_DIRECTORY:
            if isinstance(item, Share):
                path = "/"
                if sharePath:
                    path += "%s/" % sharePath
                path += "%s/share.xml" % self.shareName
                return path
            else:
                path = "/"
                if sharePath:
                    path += "%s/" % sharePath
                path += "%s/%s.%s" % (self.shareName, item.itsUUID, extension)
                return path

        elif style == ImportExportFormat.STYLE_SINGLE:
            path = "/"
            if sharePath:
                path += "%s/" % sharePath
            path += self.shareName
            return path

        else:
            print "Error" #@@@MOR Raise something

    def __getItemURL(self, item):
        """ Return the full url of an item """
        path = self._getItemPath(item)
        return self.__URLFromPath(path)

    def __URLFromPath(self, path):
        # @@@MOR need to handle https

        (host, port, sharePath, username, password, useSSL) = self.__getSettings()
        if port == 80:
            url = "http://%s%s" % (host, path)
        else:
            url = "http://%s:%s%s" % (host, port, path)
        return url

    def exists(self):
        super(WebDAVConduit, self).exists()

        try:
            resp = self.__getClient().head(self.getLocation())
            resp.read()
        except WebDAV.ConnectionError, err:
            raise CouldNotConnect(message=err.message)

        if resp.status == httplib.UNAUTHORIZED:
            message = "Not authorized to PUT %s" % url
            raise NotAuthorized(message=message)

        if resp.status == httplib.NOT_FOUND:
            return False
        else:
            return True

    def create(self):
        super(WebDAVConduit, self).create()

        style = self.share.format.fileStyle()

        if style == ImportExportFormat.STYLE_DIRECTORY:
            url = self.getLocation()
            try:
                resp = self.__getClient().mkcol(url)
                resp.read() # Always need to read each response
            except WebDAV.ConnectionError, err:
                raise CouldNotConnect(message=err.message)

            if resp.status == httplib.METHOD_NOT_ALLOWED:
                # already exists
                message = "Collection at %s already exists" % url
                raise AlreadyExists(message=message)

            if resp.status == httplib.UNAUTHORIZED:
                # not authorized
                message = "Not authorized to create collection %s" % url
                raise NotAuthorized(message=message)

            if resp.status == httplib.CONFLICT:
                # this happens if you try to create a collection within a
                # nonexistent collection
                message = "Parent collection for %s not found" % url
                raise NotFound(message=message)

            if resp.status == httplib.FORBIDDEN:
                # the server doesn't allow the creation of a collection here
                message = "Server doesn't allow the creation of collections at %s" % url
                raise IllegalOperation(message=message)

            if resp.status != httplib.CREATED:
                 message = "WebDAV error, status = %d" % resp.status
                 raise IllegalOperation(message=message)

    def destroy(self):
        print " @@@MOR unimplemented"

    def open(self):
        super(WebDAVConduit, self).open()

    def _putItem(self, item): # must implement
        """ putItem should publish an item and return etag/date, etc.
        """
        url = self.__getItemURL(item)
        text = self.share.format.exportProcess(item)

        try:
            resp = self.__getClient().put(url, text)
            resp.read() # Always need to read each response
        except WebDAV.ConnectionError, err:
            raise CouldNotConnect(message=err.message)

        # 201 = new, 204 = overwrite

        if resp.status == httplib.UNAUTHORIZED:
            message = "Not authorized to PUT %s" % url
            raise NotAuthorized(message=message)

        if resp.status == httplib.FORBIDDEN or resp.status == httplib.CONFLICT:
            # seen if trying to PUT to a nonexistent collection (@@@MOR verify)
            message = "Parent collection for %s is not found" % url
            raise NotFound(message=message)

        etag = resp.getheader('ETag', None)
        if not etag:
            # mod_dav doesn't give us back an etag upon PUT

            try:
                resp = self.__getClient().head(url)
                resp.read() # Always need to read each response
            except WebDAV.ConnectionError, err:
                raise CouldNotConnect(message=err.message)

            etag = resp.getheader('ETag', None)
            if not etag:
                print "HEAD didn't give me an etag"
                raise SharingError() #@@@MOR
            etag = self.__cleanEtag(etag)
        return etag

    def __cleanEtag(self, etag):
        # Certain webdav servers use a weak etag for a few seconds after
        # putting a resource, and then change it to a strong etag.  This
        # tends to be confusing, because it appears that an item has changed
        # on the server, when in fact we were the last ones to touch it.
        # Let's ignore weak etags by stripping their leading W/
        if etag.startswith("W/"):
            return etag[2:]
        return etag

    def _deleteItem(self, itemPath): # must implement
        itemURL = self.__URLFromPath(itemPath)
        logger.info("...removing from server: %s" % itemURL)

        try:
            resp = self.__getClient().delete(itemURL)
            deleteResp = resp.read()
        except WebDAV.ConnectionError, err:
            raise CouldNotConnect(message=err.message)

    def _getItem(self, itemPath, into=None): # must implement
        itemURL = self.__URLFromPath(itemPath)

        try:
            resp = self.__getClient().get(itemURL)
            text = resp.read()
        except WebDAV.ConnectionError, err:
            raise CouldNotConnect(message=err.message)

        if resp.status == httplib.NOT_FOUND:
            message = "Not found: %s" % url
            raise NotFound(message=message)

        if resp.status == httplib.UNAUTHORIZED:
            message = "Not authorized to get %s" % url
            raise NotAuthorized(message=message)

        etag = resp.getheader('ETag', None)
        etag = self.__cleanEtag(etag)
        item = self.share.format.importProcess(text, item=into)
        return (item, etag)

    def _getResourceList(self, location): # must implement
        """ Return information (etags) about all resources within a collection
        """
        resourceList = {}

        style = self.share.format.fileStyle()

        if style == ImportExportFormat.STYLE_DIRECTORY:

            try:
                resources = self.__getClient().ls(location + "/")

            except WebDAV.ConnectionError, err:
                raise CouldNotConnect(message=err.message)

            except WebDAV.WebDAVException, e:

                if e.status == httplib.NOT_FOUND:
                    raise NotFound(message="Not found: %s" % location)

                if e.status == httplib.UNAUTHORIZED:
                    raise NotAllowed(message="Not allowed: %s" % location)

                raise

            for (path, etag) in resources:
                etag = self.__cleanEtag(etag)
                resourceList[path] = { 'data' : etag }

        elif style == ImportExportFormat.STYLE_SINGLE:

            try:
                resp = self.__getClient().head(location)
                resp.read() # Always need to read each response
            except WebDAV.ConnectionError, err:
                raise CouldNotConnect(message=err.message)

            if resp.status == httplib.NOT_FOUND:
                message = "Not found: %s" % url
                raise NotFound(message=message)

            if resp.status == httplib.UNAUTHORIZED:
                message = "Not authorized to get %s" % url
                raise NotAuthorized(message=message)

            etag = resp.getheader('ETag', None)
            etag = self.__cleanEtag(etag)
            path = urlparse.urlparse(location)[2]
            resourceList[path] = { 'data' : etag }

        return resourceList

    def connect(self):
        self.__releaseClient()
        self.__getClient()

    def disconnect(self):
        self.__releaseClient()


    def _dumpState(self):
        print " - - - - - - - - - "
        resourceList = self._getResourceList(self.getLocation())
        print
        print "Remote:"
        for (itemPath, value) in resourceList.iteritems():
            print itemPath, value
        print
        print "In manifest:"
        for (path, value) in self.manifest.iteritems():
            print path, value
        print
        print "In contents:"
        for item in self.share.contents:
            print item.getItemDisplayName(), item.itsUUID, item.getVersion(), item.getVersion(True)
        print " - - - - - - - - - "

# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

class SharingError(Exception):
    """ Generic Sharing exception. """
    def __init__(self, message=None):
        self.message = message

class AlreadyExists(SharingError):
    """ Exception raised if a share already exists. """

class NotFound(SharingError):
    """ Exception raised if a share/resource wasn't found. """

class NotAllowed(SharingError):
    """ Exception raised if we don't have access. """

class Misconfigured(SharingError):
    """ Exception raised if a share isn't properly configured. """

class CouldNotConnect(SharingError):
    """ Exception raised if a conduit can't connect to an external entity
        due to DNS/network problems.
    """

class IllegalOperation(SharingError):
    """ Exception raised if the entity a conduit is communicating with is
        denying an operation for some reason not covered by other exceptions.
    """

# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

class ImportExportFormat(ContentModel.ChandlerItem):
    myKindID = None
    myKindPath = "//parcels/osaf/framework/sharing/ImportExportFormat"

    STYLE_SINGLE = 'single'
    STYLE_DIRECTORY = 'directory'

    def fileStyle(self):
        """ Should return 'single' or 'directory' """
        pass


class CloudXMLFormat(ImportExportFormat):
    myKindID = None
    myKindPath = "//parcels/osaf/framework/sharing/CloudXMLFormat"

    # This dictionary helps convert XML nodes to items.  Its keys are XML
    # element names, and the values are dictionaries storing the corresponding
    # Kind and 'fingerprint' -- a fingerprint is a list of attributes that make
    # up the Kind's 'primary key'.  One item is considered to be the same as
    # another if all of the attributes in their fingerprint list have the
    # same values.  Set 'useFingerprintSearch' to True to enable this feature.
    # At the moment it is turned off because we have UUIDs in the XML and we
    # can simply look those up.

    # @@@MOR At some point, the __nodeDescriptors information might be better off
    # living inside the schema itself somewhere, rather than in this module.

    useFingerprintSearch = False

    __nodeDescriptors = {
        'CalendarEvent' : {
            'kind' : '//parcels/osaf/contentmodel/calendar/CalendarEvent',
            'fingerprint' : (
                'organizer.contactName.firstName',
                'organizer.contactName.lastName'
            ),
        },
        'Contact' : {
            'kind' : '//parcels/osaf/contentmodel/contacts/Contact',
            'fingerprint' : (
                'contactName.firstName',
                'contactName.lastName'
            ),
        },
        'ContactName' : {
            'kind' : '//parcels/osaf/contentmodel/contacts/ContactName',
            'fingerprint' : (
                'firstName',
                'lastName'
            ),
        },
        'EmailAddress' : {
            'kind' : '//parcels/osaf/contentmodel/mail/EmailAddress',
            'fingerprint' : (),
        },
        'EventTask' : {
            'kind' : '//parcels/osaf/contentmodel/EventTask',
            'fingerprint' : (),
        },
        'ItemCollection' : {
            'kind' : '//parcels/osaf/contentmodel/ItemCollection',
            'fingerprint' : (),
        },
        'Location' : {
            'kind' : '//parcels/osaf/contentmodel/calendar/Location',
            'fingerprint' : (),
        },
        'MailedEvent' : {
            'kind' : '//parcels/osaf/contentmodel/MailedEvent',
            'fingerprint' : (),
        },
        'MailedEventTask' : {
            'kind' : '//parcels/osaf/contentmodel/MailedEventTask',
            'fingerprint' : (),
        },
        'MailMessage' : {
            'kind' : '//parcels/osaf/contentmodel/mail/MailMessage',
            'fingerprint' : (),
        },
        'Note' : {
            'kind' : '//parcels/osaf/contentmodel/Note',
            'fingerprint' : (),
        },
        'Photo' : {
            'kind' : '//parcels/osaf/framework/webserver/servlets/photos/Photo',
            'fingerprint' : (),
        },
        'RSSChannel' : {
            'kind' : '//parcels/osaf/examples/zaobao/RSSChannel',
            'fingerprint' : (),
        },
        'RSSItem' : {
            'kind' : '//parcels/osaf/examples/zaobao/RSSItem',
            'fingerprint' : (),
        },
        'Share' : {
            'kind' : '//parcels/osaf/framework/sharing/Share',
            'fingerprint' : (),
        },
        'Task' : {
            'kind' : '//parcels/osaf/contentmodel/tasks/Task',
            'fingerprint' : (),
        },
    }

    def __init__(self, name=None, parent=None, kind=None, view=None,
                 cloudAlias='sharing'):
        super(CloudXMLFormat, self).__init__(name, parent, kind, view)

        self.cloudAlias = cloudAlias

    def fileStyle(self):
        return self.STYLE_DIRECTORY

    def extension(self, item):
        return "xml"

    def importProcess(self, text, extension=None, item=None):
        doc = libxml2.parseDoc(text)
        node = doc.children
        try:
            item = self.__importNode(node, item)
        except KeyError:
            print "Couldn't parse:", text

        doc.freeDoc()
        return item

    def exportProcess(self, item, depth=0):

        indent = "   "

        # print "export cloud for %s (%s)" % (item, item.itsKind)

        # Collect the set of attributes that are used in this format
        attributes = self.__collectAttributes(item)

        result = indent * depth
        result += "<%s uuid='%s'>\n" % (item.itsKind.itsName, item.itsUUID)

        depth += 1

        for (attrName, endpoint) in attributes.iteritems():

            if not hasattr(item, attrName):
                continue

            result += indent * depth
            result += "<%s>" % attrName

            otherName = item.getAttributeAspect(attrName, 'otherName')
            cardinality = item.getAttributeAspect(attrName, 'cardinality')

            if otherName: # it's a bidiref
                result += "\n"

                if cardinality == 'single':
                    value = item.getAttributeValue(attrName)

                    # @@@MOR avoid endless recursion in the case where an item
                    # has a reference to itself
                    if value is not item and value is not None:
                        result += self.exportProcess(value, depth+1)

                elif cardinality == 'list':
                    for value in item.getAttributeValue(attrName):
                        if value is not item:
                            result += self.exportProcess(value, depth+1)

                elif cardinality == 'dict':
                    # @@@MOR
                    pass

                result += indent * depth

            else: # it's a literal (@@@MOR could be SingleRef though)

                if cardinality == 'single':
                    value = item.getAttributeValue(attrName)
                    if isinstance(value, Lob):
                        value = value.getInputStream().read()
                    result += "<![CDATA[" + str(value) + "]]>"

                elif cardinality == 'list':
                    depth += 1
                    result += "\n"
                    for value in item.getAttributeValue(attrName):
                        result += indent * depth
                        result += "<value>%s</value>\n" % value
                    depth -= 1

                    result += indent * depth

                elif cardinality == 'dict':
                    # @@@MOR
                    pass

            result += "</%s>\n" % attrName

        depth -= 1
        result += indent * depth
        result += "</%s>\n" % item.itsKind.itsName
        return result


    def __collectAttributes(self, item):
        attributes = {}
        for cloud in item.itsKind.getClouds(self.cloudAlias):
            for (alias, endpoint, inCloud) in cloud.iterEndpoints(self.cloudAlias):
                # @@@MOR for now, don't support endpoint attribute 'chains'
                attrName = endpoint.attribute[0]
                attributes[attrName] = endpoint
        return attributes


    def __getNode(self, node, attribute):

        # @@@MOR This method only supports traversal of single-cardinality
        # attributes

        # attribute can be a dot-separated chain of attribute names
        chain = attribute.split(".")
        attribute = chain[0]
        remaining = chain[1:]

        child = node.children
        while child:
            if child.type == "element":
                if child.name == attribute:
                    if not remaining:
                        # we're at the end of the chain
                        return child
                    else:
                        # we need to recurse. @@@MOR for now, not supporting
                        # list
                        grandChild = child.children
                        while grandChild.type != "element":
                            # skip over non-elements
                            grandChild = grandChild.next
                        return self.__getNode(grandChild,
                         ".".join(remaining))

            child = child.next
        return None


    def __iterMatchingItems(self, node):

        query = Query.Query(self.itsView.repository, "")
        desc = self.__nodeDescriptors[node.name]

        kindPath = desc['kind']
        kind = self.itsView.findPath(kindPath)

        argString = ""  # everthing after 'where'
        args = {}       # the query.args dictionary
        i = 0
        for arg in desc['fingerprint']:    # build the query
            if i > 0:
                argString += " and "
            argString += "i.%s == $%d" % (arg, i)
            args[i] = self.__getNode(node, arg).content
            i += 1
        queryString = "for i in '%s' where %s" % (kindPath, argString)

        print "Fingerprint query with", args
        query.queryString = queryString
        query.args = args
        query.execute()

        for i in query:
            yield i

    def __getMatchingItems(self, node):
        results = []
        for item in self.__iterMatchingItems(node):
            results.append(item)
        return results

    def __importNode(self, node, item=None):
        desc = self.__nodeDescriptors[node.name]
        kindPath = desc['kind']
        kind = self.itsView.findPath(kindPath)

        if item is None:

            uuidNode = node.hasProp('uuid')
            if uuidNode:
                uuid = UUID(uuidNode.content)
                item = self.itsView.findUUID(uuid)
            else:
                uuid = None

            if self.useFingerprintSearch and item is None:
                # then look for items matching the "fingerprint"...
                matches = self.__getMatchingItems(node)
                length = len(matches)
                if length == 0:
                    pass
                elif length == 1:
                    # a single match; use that item
                    item = matches[0]
                else:
                    # multiple matches!  hmm, use the first
                    item = matches[0]
                if item is not None:
                    print "Fingerprint match found", item

        if item is None:
            # item searches turned up empty, so create an item...
            # print "Creating item of kind", kind.itsPath, kind.getItemClass()
            if uuid:
                # @@@MOR This needs to use the new defaultParent framework
                # to determine the parent
                parent = self.findPath("//userdata")
                item = kind.instantiateItem(None, parent, uuid,
                                            withInitialValues=True)
            else:
                item = kind.newItem(None, None)
            # print "created item", item.itsPath, item.itsKind
        else:
            # there is a chance that the incoming kind is different than the
            # item's kind
            item.itsKind = kind

        # we have an item, now set attributes
        attributes = self.__collectAttributes(item)
        for (attrName, endpoint) in attributes.iteritems():

            attrNode = self.__getNode(node, attrName)
            if attrNode is None:
                if item.hasLocalAttributeValue(attrName):
                    item.removeAttributeValue(attrName)
                continue

            otherName = item.getAttributeAspect(attrName, 'otherName')
            cardinality = item.getAttributeAspect(attrName, 'cardinality')
            type = item.getAttributeAspect(attrName, 'type')

            if otherName: # it's a bidiref

                if cardinality == 'single':
                    valueNode = attrNode.children
                    while valueNode and valueNode.type != "element":
                        # skip over non-elements
                        valueNode = valueNode.next
                    if valueNode:
                        valueItem = self.__importNode(valueNode)
                        item.setAttributeValue(attrName, valueItem)

                elif cardinality == 'list':
                    valueNode = attrNode.children
                    while valueNode:
                        if valueNode.type == "element":
                            valueItem = self.__importNode(valueNode)
                            item.addValue(attrName, valueItem)
                        valueNode = valueNode.next

                elif cardinality == 'dict':
                    pass

            else: # it's a literal (could be SingleRef though)

                if cardinality == 'single':
                    value = type.makeValue(attrNode.content)
                    item.setAttributeValue(attrName, value)

                elif cardinality == 'list':
                    values = []
                    valueNode = attrNode.children
                    while valueNode:
                        if valueNode.type == "element":
                            value = type.makeValue(valueNode.content)
                            values.append(value)
                        valueNode = valueNode.next
                    item.setAttributeValue(attrName, values)

                elif cardinality == 'dict':
                    pass

        return item


class MixedFormat(ImportExportFormat):
    """
    myKindID = None
    myKindPath = "//parcels/osaf/framework/sharing/MixedFormat"

    def __init__(self, name=None, parent=None, kind=None, view=None,
                 cloudAlias='sharing'):
        super(CloudXMLFormat, self).__init__(name, parent, kind, view)
        self.cloudAlias = cloudAlias

    def fileStyle(self):
        return self.STYLE_DIRECTORY

    handlers = (
        ('CalendarEvent', 'ics', iCalendarHandler),
        ('Contact', 'vcd', vCardHandler),
    )

    def extension(self, item):
        # search the handlers for appropriate extension

    def importProcess(self, text, extension=None, item=None):
        ### Import a chunk of text, need to figure out which handler to pass
        ### it to.

        # return item
        pass

    def exportProcess(self, item):
        ### Output an item
        pass
    """
    pass

# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
# Sharing helper methods

def newOutboundShare(view, collection, shareName=None, account=None):
    """ Create a new Share item for a collection this client is publishing.

    If account is provided, it will be used; otherwise, the default WebDAV
    account will be used.  If there is no default account, None will be
    returned.

    @param view: The repository view object
    @type view: L{repository.persistence.RepositoryView}
    @param collection: The ItemCollection that will be shared
    @type collection: ItemCollection
    @param account: The WebDAV Account item to use
    @type account: An item of kind WebDAVAccount
    @return: A Share item, or None if no WebDAV account could be found.
    """

    if account is None:
        # Find the default WebDAV account
        account = getWebDAVAccount(view)
        if account is None:
            return None

    conduit = WebDAVConduit(view=view, account=account, shareName=shareName)
    format = CloudXMLFormat(view=view)
    share = Share(view=view, conduit=conduit, format=format,
                  contents=collection)
    share.displayName = collection.displayName
    share.hidden = False # indicates that the DetailView should show this share
    share.sharer = Contacts.Contact.getCurrentMeContact(view)
    return share


def newInboundShare(view, url):
    """ Create a new Share item for a URL this client is subscribing to.

    Finds a WebDAV account which matches this URL; if none match then
    prompt the user for username/password for that URL.  If either of
    these result in finding/creating an account, then create a Share item
    and return it.

    @param view: The repository view object
    @type view: L{repository.persistence.RepositoryView}
    @param url: The url which points to a collection to import
    @type url: String
    @return: A Share item, or None if no WebDAV account could be found.
    """

    (useSSL, host, port, path, query, fragment) = __spliturl(url)

    parent = view.findPath("//userdata")

    account = findMatchingWebDAVAccount(view, url)

    if account is None:
        # Prompt user for account information then create an account

        # Get the parent directory of the given path:
        # '/dev1/foo/bar' becomes ['dev1', 'foo']
        parentPath = path.strip('/').split('/')[:-1]
        # ['dev1', 'foo'] becomes "dev1/foo"
        parentPath = "/".join(parentPath)

        # Examine the URL for scheme, host, port, path
        info = AccountInfoPrompt.PromptForNewAccountInfo(wx.GetApp().mainFrame,
                                                         host=host,
                                                         path=parentPath)
        if info is not None:
            (description, username, password) = info
            kindPath = "//parcels/osaf/framework/sharing/WebDAVAccount"
            webDAVAccountKind = view.findPath(kindPath)
            account = webDAVAccountKind.newItem(name=None, parent=parent)
            account.displayName = description
            account.host = host
            account.path = parentPath
            account.username = username
            account.password = password
            # account.isDefault = False
            account.useSSL = useSSL
            account.port = port

    share = None
    if account is not None:
        shareName = path.strip("/").split("/")[-1]
        conduit = WebDAVConduit(view=view, shareName=shareName,
                                account=account)
        format = CloudXMLFormat(view=view)
        share = Share(view=view, conduit=conduit, format=format)
        share.hidden = False
    return share


def getWebDAVAccount(view):
    """ Return the current default WebDAV account item.

    @param view: The repository view object
    @type view: L{repository.persistence.RepositoryView}
    @return: An account item, or None if no WebDAV account could be found.
    """
    return Current.Current.get(view, "WebDAVAccount")


def findMatchingWebDAVAccount(view, url):
    """ Find a WebDAV account which corresponds to a URL.

    The url being passed in is for a collection -- it will include the
    collection name in the url.  We need to find a webdav account who
    has been set up to operate on the parent directory of this collection.
    For example, if the url is http://pilikia.osafoundation.org/dev1/foo/
    we need to find an account whose schema+host+port match and whose path
    is /dev1

    Note: this logic assumes only one account will match; you aren't
    currently allowed to have to multiple webdav accounts pointing to the
    same scheme+host+port+path combination.

    @param view: The repository view object
    @type view: L{repository.persistence.RepositoryView}
    @param url: The url which points to a collection
    @type url: String
    @return: An account item, or None if no WebDAV account could be found.
    """

    webDAVAccountKind = view.findPath("//parcels/osaf/framework/sharing/WebDAVAccount")

    (useSSL, host, port, path, query, fragment) = __spliturl(url)

    # Get the parent directory of the given path:
    # '/dev1/foo/bar' becomes ['dev1', 'foo']
    path = path.strip('/').split('/')[:-1]
    # ['dev1', 'foo'] becomes "dev1/foo"
    path = "/".join(path)


    for account in KindQuery().run([webDAVAccountKind]):
        # Does this account's url info match?
        accountPath = account.path.strip('/')
        if account.useSSL == useSSL and account.host == host and account.port == port and accountPath == path:
            return account

    return None


def findMatchingShare(view, url):
    """ Find a Share which corresponds to a URL.

    @param view: The repository view object
    @type view: L{repository.persistence.RepositoryView}
    @param url: A url pointing at a WebDAV Collection
    @type url: String
    @return: A Share item, or None
    """

    account = findMatchingWebDAVAccount(view, url)
    if account is None:
        return None

    # If we found a matching account, that means *potentially* there is a
    # matching share; go through all conduits this account points to and look
    # for shareNames that match

    (useSSL, host, port, path, query, fragment) = __spliturl(url)

    # '/dev1/foo/bar' becomes 'bar'
    shareName = path.strip("/").split("/")[-1:]

    for conduits in account.conduits:
        if conduit.shareName == shareName:
            if conduit.share.hidden == False:
                return conduit.share

    return None


def __spliturl(url):
    (scheme, host, path, query, fragment) = urlparse.urlsplit(url)

    if scheme == 'https':
        port = 443
        useSSL = True
    else:
        port = 80
        useSSL = False

    if host.find(':') != -1:
        (host, port) = host.split(':')

    return (useSSL, host, port, path, query, fragment)


def isShared(collection):
    """ Return whether an ItemCollection has a Share item associated with it.

    @param collection: an ItemCollection
    @type collection: ItemCollection
    @return: True if collection does have a Share associated with it; False
        otherwise.
    """

    # See if any non-hidden shares are associated with the collection.
    # A "hidden" share is one that was not requested by the DetailView,
    # This is to support shares that don't participate in the whole
    # invitation process (such as transient import/export shares, or shares
    # for publishing an .ics file to a webdav server).

    for share in collection.shares:
        if share.hidden == False:
            return True
    return False


def getShare(collection):
    """ Return the Share item (if any) associated with an ItemCollection.

    @param collection: an ItemCollection
    @type collection: ItemCollection
    @return: A Share item, or None
    """

    # Return the first "non-hidden" share for this collection -- see isShared()
    # method for further details.

    for share in collection.shares:
        if share.hidden == False:
            return share
    return None


def isIMAPSetUp(view):
    """ See if the IMAP account has at least the minimum setup needed for
        sharing (IMAP needs email address).

    @param view: The repository view object
    @type view: L{repository.persistence.RepositoryView}
    @return: True if the account is set up; False otherwise.
    """

    # Find imap account, and make sure email address is valid
    imap = Mail.MailParcel.getIMAPAccount(view)
    if not imap.emailAddress:
        return False
    return True


def isSMTPSetUp(view):
    """ See if SMTP account has at least the minimum setup needed for
        sharing (SMTP needs host).

    @param view: The repository view object
    @type view: L{repository.persistence.RepositoryView}
    @return: True if the account is set up; False otherwise.
    """

    # Find smtp account, and make sure server field is set
    imap = Mail.MailParcel.getIMAPAccount(view)
    smtp = imap.defaultSMTPAccount
    if not smtp.host:
        return False
    return True


def isMailSetUp(view):
    """ See if the email accounts have at least the minimum setup needed for
        sharing.

    @param view: The repository view object
    @type view: L{repository.persistence.RepositoryView}
    @return: True if the accounts are set up; False otherwise.
    """
    if isIMAPSetUp(view) and isSMTPSetUp(view):
        return True
    return False


def isWebDAVSetUp(view):
    """ See if WebDAV is set up.

    @param view: The repository view object
    @type view: L{repository.persistence.RepositoryView}
    @return: True if accounts are set up; False otherwise.
    """

    account = getWebDAVAccount(view)
    return account is not None

def ensureAccountSetUp(view):
    """ A helper method to make sure the user gets the account info filled out.

    This method will examine all the account info and if anything is missing,
    a dialog will explain to the user what is missing; if they want to proceed
    to enter that information, the accounts dialog will pop up.  If at any
    point they hit Cancel, this method will return False.  Only when all
    account info is filled in will this method return True.

    @param view: The repository view object
    @type view: L{repository.persistence.RepositoryView}
    @return: True if accounts are set up; False otherwise.
    """

    while True:

        DAVReady = isWebDAVSetUp(view)
        IMAPReady = isIMAPSetUp(view)
        SMTPReady = isSMTPSetUp(view)
        if DAVReady and IMAPReady and SMTPReady:
            return True

        msg = "The following account(s) need to be set up before you can share a collection:\n\n"
        if not DAVReady:
            msg += " - WebDAV (collection publishing)\n"
        if not IMAPReady:
            msg += " - IMAP (inbound email)\n"
        if not SMTPReady:
            msg += " - SMTP (outound email)\n"
        msg += "\nWould you like to enter account information now?"

        response = application.dialogs.Util.yesNo(wx.GetApp().mainFrame,
                                                  "Account set up",
                                                  msg)
        if response == False:
            return False

        if not IMAPReady:
            account = Mail.MailParcel.getIMAPAccount(view)
        elif not SMTPReady:
            account = Mail.MailParcel.getIMAPAccount(view).defaultSMTPAccount

        response = \
          application.dialogs.AccountPreferences.ShowAccountPreferencesDialog(
          wx.GetApp().mainFrame, account=account, view=view)

        if response == False:
            return False


def syncShare(share):

    try:
        share.sync()
    except SharingError, err:
        msg = "Error syncing the '%s' collection\n" % share.contents.getItemDisplayName()
        msg += "using the '%s' account:\n\n" % share.conduit.account.getItemDisplayName()
        msg += err.message
        application.dialogs.Util.ok(wx.GetApp().mainFrame,
                                    "Synchronization Error", msg)


def syncAll(view):
    """ Synchronize all active shares.

    @param view: The repository view object
    @type view: L{repository.persistence.RepositoryView}
    """

    shareKind = view.findPath("//parcels/osaf/framework/sharing/Share")
    for share in KindQuery().run([shareKind]):
        if share.active:
            syncShare(share)


def checkForActiveShares(view):
    """ See if there are any non-hidden, active shares.

    @param view: The repository view object
    @type view: L{repository.persistence.RepositoryView}
    @return: True if there are non-hidden, active shares; False otherwise
    """

    shareKind = view.findPath("//parcels/osaf/framework/sharing/Share")
    for share in KindQuery().run([shareKind]):
        if share.active and not share.hidden:
            return True
    return False

def manualSubscribeToCollection(view):
    url = application.dialogs.Util.promptUser(wx.GetApp().mainFrame,
                                              "Subscribe to share",
                                              "Enter the share's URL", "")
    if not url:
        return

    share = newInboundShare(view, url)
    share.get()
    collection = share.contents
    mainView = Globals.views[0]
    mainView.postEventByName ("AddToSidebarWithoutCopying", {'items':[collection]})
    view.commit()
    mainView.postEventByName('RequestSelectSidebarItem', {'item':collection})
    mainView.postEventByName ('SelectItemBroadcastInsideActiveView', {'item':collection})

def manualPublishCollection(view, collection):
    share = getShare(collection)
    if share is not None:
        msg = "This collection is already shared at:\n%s" % share.conduit.getLocation()
        application.dialogs.Util.ok(wx.GetApp().mainFrame,
                                    "Already shared", msg)
        return

    shareName = application.dialogs.Util.promptUser(wx.GetApp().mainFrame,
                                              "Publish share",
                                              "Enter a name",
                                              collection.getItemDisplayName())

    if shareName is None:
        return

    share = newOutboundShare(view, collection, shareName=shareName)
    if share.exists():
        msg = "There is already a share at:\n%s" % share.conduit.getLocation()
        application.dialogs.Util.ok(wx.GetApp().mainFrame,
                                    "Share exists", msg)
        return

    share.create()
    share.put()
