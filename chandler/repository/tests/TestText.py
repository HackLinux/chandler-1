"""
Text storage unit tests
"""

__revision__  = "$Revision$"
__date__      = "$Date$"
__copyright__ = "Copyright (c) 2003-2004 Open Source Applications Foundation"
__license__   = "http://osafoundation.org/Chandler_0.1_license_terms.htm"

import unittest, os

from repository.tests.RepositoryTestCase import RepositoryTestCase
from chandlerdb.util.UUID import UUID

class TestText(RepositoryTestCase):
    """ Test Text storage """

    def setUp(self):

        super(TestText, self).setUp()

        cineguidePack = os.path.join(self.testdir, 'data', 'packs',
                                     'cineguide.pack')
        self.rep.loadPack(cineguidePack)
        self.rep.commit()

    def compressed(self, compression, encryption, key):
        khepburn = self.rep.findPath('//CineGuide/KHepburn')
        movie = khepburn.movies.first()
        self.assert_(movie is not None)

        largeText = os.path.join(self.testdir, 'data', 'world192.txt')

        input = file(largeText, 'r')
        movie.synopsis.mimetype = 'text/plain'
        writer = movie.synopsis.getWriter(compression=compression,
                                          encryption=encryption,
                                          key=key)

        count = 0
        while True:
            data = input.read(1048576)
            if len(data) > 0:
                writer.write(data)
                count += len(data)
            else:
                break

        input.close()
        writer.close()
        
        self.rep.logger.info("%s compressed %d bytes to %d",
                             compression, count, len(movie.synopsis._data))

        self._reopenRepository()

        khepburn = self.rep.findPath('//CineGuide/KHepburn')
        movie = khepburn.movies.first()
        self.assert_(movie is not None)

        input = file(largeText, 'r')
        reader = movie.synopsis.getReader(key)
        data = input.read()
        string = reader.read()
        input.close()
        reader.close()

        self.assert_(data == string)

    def testBZ2Compressed(self):

        self.compressed('bz2', None, None)
       
    def testBZ2Encrypted(self):

        self.compressed('bz2', 'rijndael', UUID()._uuid)
       
    def testZlibCompressed(self):

        self.compressed('zlib', None, None)
        
    def testZlibEncrypted(self):

        self.compressed('zlib', 'rijndael', UUID()._uuid)
        
    def testUncompressed(self):

        self.compressed(None, None, None)

    def testEncrypted(self):

        self.compressed(None, 'rijndael', UUID()._uuid)

    def appended(self, compression, encryption, key):

        khepburn = self.rep.findPath('//CineGuide/KHepburn')
        movie = khepburn.movies.first()
        self.assert_(movie is not None)

        largeText = os.path.join(self.testdir, 'data', 'world192.txt')

        input = file(largeText, 'r')
        movie.synopsis.mimetype = 'text/plain'
        writer = movie.synopsis.getWriter(compression=compression,
                                          encryption=encryption,
                                          key=key)

        while True:
            data = input.read(548576)
            if len(data) > 0:
                writer.write(data)
                writer.close()
                self.rep.commit()
                writer = movie.synopsis.getWriter(compression=compression,
                                                  encryption=encryption,
                                                  key=key, append=True)
            else:
                break

        input.close()
        writer.close()

        self._reopenRepository()

        khepburn = self.rep.findPath('//CineGuide/KHepburn')
        movie = khepburn.movies.first()
        self.assert_(movie is not None)

        input = file(largeText, 'r')
        reader = movie.synopsis.getReader(key)
        data = input.read()
        string = reader.read()
        input.close()
        reader.close()

        self.assert_(data == string)
        
    def testAppendBZ2(self):

        self.appended('bz2', None, None)

    def testAppendBZ2Encrypted(self):

        self.appended('bz2', 'rijndael', UUID()._uuid)

    def testAppendZlib(self):

        self.appended('zlib', None, None)

    def testAppendZlibEncrypted(self):

        self.appended('zlib', 'rijndael', UUID()._uuid)

    def testAppend(self):

        self.appended(None, None, None)

    def testAppendEncrypted(self):

        self.appended(None, 'rijndael', UUID()._uuid)


if __name__ == "__main__":
#    import hotshot
#    profiler = hotshot.Profile('/tmp/TestItems.hotshot')
#    profiler.run('unittest.main()')
#    profiler.close()
    unittest.main()
