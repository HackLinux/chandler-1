"""
Test moving of items
"""

__revision__  = "$Revision$"
__date__      = "$Date$"
__copyright__ = "Copyright (c) 2003-2004 Open Source Applications Foundation"
__license__   = "http://osafoundation.org/Chandler_0.1_license_terms.htm"

import unittest, os

from repository.tests.RepositoryTestCase import RepositoryTestCase


class TestMove(RepositoryTestCase):
    """ Test item moving """

    def setUp(self):

        super(TestMove, self).setUp()

        cineguidePack = os.path.join(self.testdir, 'data', 'packs',
                                     'cineguide.pack')
        self.rep.loadPack(cineguidePack)
        
    def move(self, withCommit):

        if withCommit:
            self.rep.commit()
            
        c = self.rep['CineGuide']
        k = c['KHepburn']
        m = k.movies.first()

        m.move(self.rep)
        self.assert_(m._parent is self.rep.view)
        self.assert_(m._root is m)
        self.assert_(c.hasChild(m._name) is False)

        if withCommit:
            self.rep.commit()
        
        m.move(c)
        self.assert_(m._parent is c)
        self.assert_(m._root is c)
        self.assert_(self.rep.hasRoot(m._name) is False)

        if withCommit:
            self.rep.commit()
        
    def testMoveCommit(self):
        self.move(True)

    def testMove(self):
        self.move(False)

    def testReopenCommit(self):
        self._reopenRepository()
        self.move(True)

    def testReopen(self):
        self._reopenRepository()
        self.move(False)


if __name__ == "__main__":
#    import hotshot
#    profiler = hotshot.Profile('/tmp/TestItems.hotshot')
#    profiler.run('unittest.main()')
#    profiler.close()
    unittest.main()
