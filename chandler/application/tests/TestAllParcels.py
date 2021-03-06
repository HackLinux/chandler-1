"""
Loads all parcels
"""
__revision__  = "$Revision$"
__date__      = "$Date$"
__copyright__ = "Copyright (c) 2003-2004 Open Source Applications Foundation"
__license__   = "http://osafoundation.org/Chandler_0.1_license_terms.htm"

import ParcelLoaderTestCase, os, sys, unittest

import application
import util.timing

class AllParcelsTestCase(ParcelLoaderTestCase.ParcelLoaderTestCase):

    def testAllParcels(self):

        """
        Test to ensure all parcels load
        """
        util.timing.begin("application.TestAllParcels")

        self.loadParcels()
        
        util.timing.end("application.TestAllParcels")
        util.timing.results(verbose=False)

        self.assert_( self.rep.check(), "Repository check failed -- see chandler.log" )

if __name__ == "__main__":
    unittest.main()
