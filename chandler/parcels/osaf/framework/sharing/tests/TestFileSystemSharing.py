"""
A helper class which sets up and tears down dual RamDB repositories
"""
__revision__  = "$Revision$"
__date__      = "$Date$"
__copyright__ = "Copyright (c) 2003-2004 Open Source Applications Foundation"
__license__   = "http://osafoundation.org/Chandler_0.1_license_terms.htm"

import unittest, os, sys, logging
import repository.persistence.DBRepository as DBRepository
import repository.item.Item as Item
import application.Parcel as Parcel
import application.Globals as Globals
import osaf.framework.sharing.Sharing as Sharing
import osaf.contentmodel.ItemCollection as ItemCollection
import osaf.contentmodel.ContentModel as ContentModel
import osaf.contentmodel.calendar.Calendar as Calendar
import osaf.contentmodel.contacts.Contacts as Contacts

import time # @@@ temporary

class SharingTestCase(unittest.TestCase):

    def runTest(self):
        self._setup()
        self.RoundTrip()
        time.sleep(1)  # @@@ if all happens within the same second, changes
                       # aren't detected.  perhaps checksum checking is needed
        self.Modify()
        self.Remove()
        self._teardown()

    def _setup(self):

        rootdir = os.environ['CHANDLERHOME']
        packs = (
         os.path.join(rootdir, 'repository', 'packs', 'schema.pack'),
         os.path.join(rootdir, 'repository', 'packs', 'chandler.pack'),
        )
        parcelpath = [os.path.join(rootdir, 'parcels')]

        handler = logging.FileHandler(os.path.join(rootdir,'chandler.log'))
        formatter = logging.Formatter('%(asctime)s %(name)s %(levelname)s %(message)s')
        handler.setFormatter(formatter)
        root = logging.getLogger()
        root.setLevel(logging.INFO)
        root.addHandler(handler)

        namespaces = [
         'http://osafoundation.org/parcels/osaf/framework/sharing',
         'http://osafoundation.org/parcels/osaf/contentmodel/calendar',
        ]

        self.repos = []
        self.mgrs = []
        for i in xrange(2):
            self.repos.append(self._initRamDB(packs))
            Globals.repository = self.repos[i] # argh!
            self.mgrs.append(Parcel.Manager.getManager(
             repository=self.repos[i], path=parcelpath))
            self.mgrs[i].loadParcels(namespaces)
            # create a sandbox root
            Item.Item("sandbox", self.repos[i], None)
            self.repos[i].commit()

        self._createCollection(self.repos[0])
        self._populateCollection(self.repos[0])

    def _teardown(self):
        self.share1.destroy()

    def _initRamDB(self, packs):
        repo = DBRepository.DBRepository(None)
        repo.create(ramdb=True, stderr=False, refcounted=True)
        for pack in packs:
            repo.loadPack(pack)
        repo.commit()
        return repo

    def _createCollection(self, repo):
        Globals.repository = repo # argh!
        sandbox = repo.findPath("//sandbox")

        coll = ItemCollection.ItemCollection(name="testcollection",
         parent=sandbox)


    def _populateCollection(self, repo):
        Globals.repository = repo # argh!
        sandbox = repo.findPath("//sandbox")

        coll = sandbox.findPath("testcollection")

        names = [
            ("Morgen", "Sagen", "morgen@example.com"),
            ("Ted", "Leung", "ted@example.com"),
            ("Andi", "Vajda", "andi@example.com"),
        ]

        contacts = []

        for name in names:
            c = Contacts.Contact(parent=sandbox)
            c.contactName = Contacts.ContactName(parent=sandbox)
            c.contactName.firstName = name[0]
            c.contactName.lastName = name[1]
            c.emailAddress = name[2]
            c.displayName = "%s %s" % (name[0], name[1])
            contacts.append(c)

        coll.displayName = "test collection"

        events = [
            "breakfast",
            "lunch",
            "dinner",
            "meeting",
            "movie",
            "game",
        ]
        for i in xrange(6):
            c = Calendar.CalendarEvent(parent=sandbox)
            c.displayName = events[i % 6]
            c.organizer = contacts[0]
            c.participants = [contacts[1], contacts[2]]
            c.issues = ["123", "abc", "xyz"]
            coll.add(c)


    def dumpSandbox(self, repo):
        Globals.repository = repo # argh!
        Parcel.PrintItem("//sandbox", repo, recursive=True)


    def RoundTrip(self):

        # Export
        repo = self.repos[0]
        Globals.repository = repo # argh!
        sandbox = repo.findPath("//sandbox")
        coll = sandbox.findPath("testcollection")

        conduit = Sharing.FileSystemConduit(name="conduit", parent=sandbox,
         sharePath=".", shareName="exportedcollection")
        format = Sharing.CloudXMLFormat(name="format", parent=sandbox)
        self.share1 = Sharing.Share(name="share", parent=sandbox,
         contents=coll, conduit=conduit, format=format)
        if self.share1.exists():
            self.share1.destroy()
        self.share1.create()
        self.share1.put()

        # Import
        repo = self.repos[1]
        Globals.repository = repo # argh!
        sandbox = repo.findPath("//sandbox")
        coll = sandbox.findPath("testcollection")

        conduit = Sharing.FileSystemConduit(name="conduit", parent=sandbox,
         sharePath=".", shareName="exportedcollection")
        format = Sharing.CloudXMLFormat(name="format", parent=sandbox)
        self.share2 = Sharing.Share(name="share", parent=sandbox,
         conduit=conduit, format=format)
        self.share2.get()

        # Make sure that the items we imported have the same displayNames
        # as the ones we exported (and no fewer, no more)
        names = {}
        for item in self.share1.contents:
            names[item.displayName] = 1
        for item in self.share2.contents:
            self.assert_(item.displayName in names, "Imported item that wasn't"
             "exported")
            del names[item.displayName]
        self.assert_(len(names) == 0, "Import is missing some items that were"
         "exported")

    def Modify(self):

        # change one of the items in share2
        for item in self.share2.contents:
            if item.displayName == "meeting":
                item.displayName = "meeting rescheduled"

        # find the corresponding item in share1 and we'll see if it changes
        changedItem = None
        for item in self.share1.contents:
            if item.displayName == "meeting":
                changedItem = item

        Globals.repository = self.repos[1] # just in case (not needed?)
        self.share2.put()

        Globals.repository = self.repos[0] # just in case (not needed?)
        self.share1.get()

        self.assert_(changedItem.displayName == "meeting rescheduled",
         "displayName is %s" % (changedItem.displayName))

    def Remove(self):

        Globals.repository = self.repos[0] # just in case (not needed?)

        # Remove an item from share1...
        for item in self.share1.contents:
            if item.displayName == "lunch":
                toRemove = item
        self.share1.contents.remove(toRemove)
        # ...publish...
        self.share1.put()

        Globals.repository = self.repos[1] # just in case (not needed?)
        # ...get...
        self.share2.get()
        # ...and make sure it's gone from share2
        for item in self.share2.contents:
            self.assert_(item.displayName != "lunch")

if __name__ == "__main__":
    unittest.main()
