"""
A base class for repository testing
"""
__revision__  = "$Revision$"
__date__      = "$Date$"
__copyright__ = "Copyright (c) 2003-2004 Open Source Applications Foundation"
__license__   = "http://osafoundation.org/Chandler_0.1_license_terms.htm"

from unittest import TestCase
import logging, os, sys, gettext

from repository.persistence.DBRepository import DBRepository
from repository.util.Path import Path
from application.Parcel import Manager as ParcelManager

class RepositoryTestCase(TestCase):

    def _setup(self, ramdb=True):
        self.rootdir = os.environ['CHANDLERHOME']
        self.schemaPack = os.path.join(self.rootdir, 'repository',
                                  'packs', 'schema.pack')
        self.chandlerPack = os.path.join(self.rootdir, 'repository',
                                         'packs', 'chandler.pack')

        handler = logging.FileHandler(os.path.join(self.rootdir,'chandler.log'))
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        handler.setFormatter(formatter)
        root = logging.getLogger()
        root.addHandler(handler)

        self.ramdb = ramdb

        # set up the gettext locale, so we have a definition of _()
        os.environ['LANGUAGE'] = 'en'
        gettext.install('chandler', 'locale')

    def _openRepository(self, ramdb=True):
        preloadedRepositoryPath = os.path.join(self.testdir, '__preloaded_repository__')
        self.rep = DBRepository(os.path.join(self.testdir, '__repository__'))

        if os.path.exists(preloadedRepositoryPath):
            self.ramdb = False
            self.rep.open(ramdb=False,
                          fromPath=preloadedRepositoryPath,
                          stderr=True,
                          refcounted=True)
            self.rep.logger.info('Using preloaded repository')
        else:
            self.rep.create(ramdb=self.ramdb,
                            stderr=True,
                            refcounted=True)

            self.rep.loadPack(self.schemaPack)
            self.rep.loadPack(self.chandlerPack)
            self.rep.commit()

        self.manager = \
         ParcelManager.getManager(repository=self.rep, \
         path=[os.path.join(self.rootdir, 'parcels')])

    def setUp(self, ramdb=True):
        self._setup(ramdb)
        
        self.testdir = os.path.join(self.rootdir, 'repository',
                                    'tests')
        self._openRepository(ramdb)

    def tearDown(self):
        self.rep.close()
        self.rep.logger.debug('RAMDB = %s', self.ramdb)
        if not self.ramdb:
            self.rep.delete()

    def _reopenRepository(self):
        self.rep.commit()

        if self.ramdb:
            self.rep.closeView()
            self.rep.openView()
        else:
            self.rep.close()
            self.rep = DBRepository(os.path.join(self.testdir,
                                                 '__repository__'))
            self.rep.open()

    def _find(self, path):
        return self.rep.findPath(path)

    def loadParcel(self, namespace):
        self.loadParcels([namespace])

    def loadParcels(self, namespaces=None):
        import application
        import application.Globals as Globals
        import osaf.contentmodel.tests.GenerateItems as GenerateItems
        Globals.repository = self.rep

        self.manager.loadParcels(namespaces)
        if namespaces:
            for namespace in namespaces:
                parcelItem = self.manager.lookup(namespace)
                self.assert_(parcelItem)
                # print "Loaded namespace %s as item %s" % \
                # (namespace, parcelItem.itsPath)

    _KIND_KIND = Path("//Schema/Core/Kind")
    _ITEM_KIND = Path("//Schema/Core/Item")

    # Repository specific assertions
    def assertIsRoot(self, item):
        self.assert_(item in list(self.rep.iterRoots()))

    def assertItemPathEqual(self, item, string):
        self.assertEqual(str(item.itsPath), string)
