__date__ = "$Date$"
__copyright__ = "Copyright (c) 2003-2004 Open Source Applications Foundation"
__license__ = "http://osafoundation.org/Chandler_0.1_license_terms.htm"

import application.Globals as Globals
import osaf.contentmodel.ContentModel as ContentModel
import repository.query.Query as Query
from chandlerdb.item.ItemError import NoSuchIndexError

class ItemCollection(ContentModel.ContentItem, Query.Query):
    myKindID = None
    myKindPath = "//parcels/osaf/contentmodel/ItemCollection"

    def add (self, item):
        """
          Add an item to the inclusions. Optimize changes to inclusions and
        exclusions.
        """
        if item not in self.inclusions:
            self.inclusions.append (item)
            if item in self.exclusions:
                self.exclusions.remove (item)
            if item not in self._resultSet:
                self._resultSet.append (item)
            self.ruleIsStale = True

    def remove (self, item):
        """
          Remove an item from the exclusions. Optimize changes to inclusions and
        exclusions.
        """
        if item not in self.exclusions:
            if self._rule:
                self.exclusions.append (item)
            if item in self.inclusions:
                self.inclusions.remove (item)
            if item in self._resultSet:
                self._resultSet.remove (item)
            self.ruleIsStale = True

    def addFilterKind (self, item):
        """
          Add an kind to the list of kinds to filter
        """
        kindPath = str (item.itsPath)
        if kindPath not in self.kindFilter:
            self.kindFilter.append (kindPath)
            self.ruleIsStale = True

    def removeFilterKind (self, item):
        """
          Remove a kind from the list of kinds to filter. If item is not None remove all filters
        """
        if item is not None:
            self.kindFilter.remove (str (item.itsPath))
        else:
            del self.kindFilter[:]
        self.ruleIsStale = True

    def getRule (self):
        return self._rule

    def setRule (self, value):
        self._rule = value
        self.ruleIsStale = True

    rule = property (getRule, setRule)

    def _ensureQueryIsCurrent (self):
        """
           Make sure that we update the queryString if the rule is stale,
        then let our superclass handle its part.
        """
        if self.ruleIsStale:
            args = {}
            newQueryString = self._rule
            if self.source:
                if newQueryString:
                    newQueryString = "union (" + newQueryString + ", for i in $0 where True)"
                else:
                    newQueryString = "for i in $0 where True"
                args ["$0"] = (self.source.itsUUID, "_resultSet")
            if len (self.inclusions):
                if newQueryString:
                    newQueryString = "union (" + newQueryString + ", for i in $1 where True)"
                else:
                    newQueryString = "for i in $1 where True"
                args ["$1"] = (self.itsUUID, "inclusions")
            if newQueryString:
                if len (self.exclusions):
                    newQueryString = "difference (" + newQueryString + ", for i in $2 where True)"
                    args ["$2"] = (self.itsUUID, "exclusions")
                if len (self.kindFilter) != 0:
                    for kindPath in self.kindFilter:
                        newQueryString = "intersect (" + newQueryString + ", for i inevery '" + kindPath + "' where True)"
            self.queryString = newQueryString
            self.args = args
            self.ruleIsStale = False
        return super (ItemCollection, self)._ensureQueryIsCurrent ()

    def shareSend (self):
        """
          Share this Item, or Send it (if it's an Email)
        """
        # message the mainView to do the bulk of the work, showing progress
        Globals.views[0].postEventByName ('ShareItem', {'item': self})

    def __getitem__ (self, index):
        try:
            return self.resultSet.getByIndex (self.indexName, index)
        except NoSuchIndexError:
            self.createIndex()
            return self.resultSet.getByIndex (self.indexName, index)

    def __delitem__(self, index):
        self.remove (self.resultSet [index])

    def createIndex (self):
        if self.indexName == "__adhoc__":
            self.resultSet.addIndex (self.indexName, 'numeric')
        else:
            self.resultSet.addIndex (self.indexName, 'attribute', attribute=self.indexName)

    def index (self, item):
        try:
            return self.resultSet.getIndexPosition (self.indexName, item)
        except NoSuchIndexError:
            self.createIndex()
            return self.resultSet.getIndexPosition (self.indexName, item)

    def subscribe(self, *arguments, **keywords):
        if self.source:
            self.source.subscribe (self, "")
        super (ItemCollection, self).subscribe (*arguments, **keywords)

    def unsubscribe(self, *arguments, **keywords):
        super (ItemCollection, self).unsubscribe (*arguments, **keywords)
        if self.source:
            self.source.unsubscribe (self)
