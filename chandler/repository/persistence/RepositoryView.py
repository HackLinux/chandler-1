
__revision__  = "$Revision$"
__date__      = "$Date$"
__copyright__ = "Copyright (c) 2004 Open Source Applications Foundation"
__license__   = "http://osafoundation.org/Chandler_0.1_license_terms.htm"

import logging, heapq, sys, gc

from threading import currentThread, Thread

from chandlerdb.util.UUID import UUID
from repository.util.Path import Path
from repository.util.ThreadSemaphore import ThreadSemaphore
from repository.persistence.RepositoryError import RepositoryError, VersionConflictError, ViewError
from repository.item.Item import Item
from repository.item.ItemHandler import ItemHandler
from repository.persistence.PackHandler import PackHandler

timing = True
if timing: import tools.timing

class RepositoryView(object):
    """
    This class implements the cache for loaded items. Changes to items in a
    view are not written into persistent storage until the view is
    committed. A view will not see changes in the repository made by other
    views until the view is refreshed during a L{commit}.
    """
    
    def __init__(self, repository, name):
        """
        Initializes a repository view.

        This contructor should not be invoked directly but the
        L{createView<repository.persistence.Repository.Repository.createView>}
        method should be used instead so that the appropriate view
        implementation for the repository be used.
        """

        super(RepositoryView, self).__init__()

        if not repository.isOpen():
            raise RepositoryError, "Repository is not open"

        self.repository = repository
        self.name = name or currentThread().getName()

        self.openView()
        
    def __repr__(self):

        return "<%s: %s>" %(type(self).__name__, self.name)

    def setCurrentView(self):
        """
        Make this view the current view for the current thread.

        The repository gets the current view from the current thread. This
        method should be used to select this view as the current one for the
        current thread.

        @return: the view that was current for the thread before this call.
        """

        return self.repository.setCurrentView(self)

    def _isRepository(self):

        return False

    def _isItem(self):

        return False

    def _createRefList(self, item, name, otherName,
                       persist, readOnly, new, uuid):

        raise NotImplementedError, "%s._createRefList" %(type(self))
    
    def _createChildren(self, parent, new):

        raise NotImplementedError, "%s._createChildren" %(type(self))
    
    def _getLobType(self):

        raise NotImplementedError, "%s._getLobType" %(type(self))

    def openView(self):
        """
        Open this repository view.

        A view is created open, calling this method is only necessary when
        re-opening a closed view.
        """

        self._roots = self._createChildren(self, False)
        self._registry = {}
        self._deletedRegistry = {}
        self._instanceRegistry = {}
        self._status = RepositoryView.OPEN

        if self.repository.isRefCounted():
            self._status |= RepositoryView.REFCOUNTED
        
        self.repository.store.attachView(self)

    def _setChildren(self, children):

        self._roots = children

    def setDirty(self, dirty):

        if dirty:
            if not self._status & RepositoryView.LOADING:
                self._status |= Item.CDIRTY
        else:
            self._status &= ~Item.CDIRTY

    def isDirty(self):

        return self._status & Item.CDIRTY != 0

    def closeView(self):
        """
        Close this repository view.

        All items in the view are marked stale. The item cache is flushed.
        A closed view cannot be used until is re-opened with L{openView}.
        """

        if not self._status & RepositoryView.OPEN:
            raise RepositoryError, "RepositoryView is not open"

        if self.repository._threaded.view is self:
            del self.repository._threaded.view
        
        for item in self._registry.itervalues():
            item._setStale()

        self._registry.clear()
        self._roots = None
        self._deletedRegistry.clear()
        self._instanceRegistry.clear()
        self._status &= ~(RepositoryView.OPEN | Item.CDIRTY)

        self.repository.store.detachView(self)

    def prune(self, size):
        """
        Remove least-used items from the view's item cache.

        If there are C{size + 10%} items in the view's cache, the least-used
        items are removed from cache such that the cache size decreases to
        C{size - 10%} items.

        Pinned items and schema items are never removed from cache.
        
        @param size: the threshhold value
        @type size: integer
        """

        pass

    def isOpen(self):
        """
        Tell whether this view is open.

        If the repository owning this view is closed, this view is also
        considered closed.

        @return: boolean
        """

        return ((self._status & RepositoryView.OPEN) != 0 and
                self.repository.isOpen())

    def isNew(self):

        return False

    def isStale(self):

        return False

    def isRefCounted(self):

        return (self._status & RepositoryView.REFCOUNTED) != 0
        
    def isLoading(self):
        """
        Tell whether this view is in the process of loading items.

        @return: boolean
        """

        return (self._status & RepositoryView.LOADING) != 0

    def _setLoading(self, loading, runHooks=False):

        if self.repository.view is not self:
            raise ViewError, (self, self.repository.view)

        status = (self._status & RepositoryView.LOADING != 0)

        if loading:
            self._status |= RepositoryView.LOADING
        else:
            self._status &= ~RepositoryView.LOADING

        return status

    def walk(self, path, callable, _index=0, **kwds):
        """
        Walk a path and invoke a callable along the way.

        The callable's arguments need to be defined as C{parent},
        C{childName}, C{child} and C{**kwds}.
        The callable is passed C{None} for the C{child} argument if C{path}
        doesn't correspond to an existing item.
        The callable's return value is used to recursively continue walking
        when it is not C{None}.

        For example: L{find} calls this method when passed a path with the
        callable being the simple lambda body:

            - C{lambda parent, name, child, **kwds: child}

        A C{load} keyword can be used to prevent loading of items by setting
        it to C{False}. Items are loaded as needed by default.

        @param path: an item path
        @type path: a L{Path<repository.util.Path.Path>} instance
        @param callable: a function, method, or lambda body
        @type callable: a python callable
        @param kwds: optional keywords passed to the callable
        @return: the item the walk finished on or C{None}
        """

        l = len(path)
        if l == 0:
            return None

        if path[_index] == '//':
            _index += 1

        if _index >= l:
            return None

        name = path[_index]
        if isinstance(name, UUID):
            root = self.findUUID(name, kwds.get('load', True))
            if root is not None and root.itsParent is not self:
                root = None
        else:
            root = self.getRoot(name, kwds.get('load', True))
            
        root = callable(self, path[_index], root, **kwds)
        if root is not None:
            if _index == l - 1:
                return root
            return root.walk(path, callable, _index + 1, **kwds)

        return None

    def find(self, spec, load=True):
        """
        Find an item.

        An item can be found by a path determined by its name and container
        or by a uuid generated for it at creation time. If C{spec} is a
        relative path, it is evaluated relative to C{self}.

        This method returns C{None} if the item is not found or if it is
        found but not yet loaded and C{load} was set to C{False}.

        See the L{findPath} and L{findUUID} methods for versions of this
        method that can also be called with a string.

        @param spec: a path or UUID
        @type spec: L{Path<repository.util.Path.Path>} or
                    L{UUID<chandlerdb.util.UUID.UUID>} 
        @param load: load the item if it not yet loaded, C{True} by default
        @type load: boolean
        @return: an item or C{None} if not found
        """
        
        if isinstance(spec, UUID):
            if spec == self.itsUUID:
                return self
            else:
                try:
                    return self._registry[spec]
                except KeyError:
                    if load is True:
                        return self._loadItem(spec)
                    elif load and not spec in self._deletedRegistry:
                        # in this case, load is an itemReader (queryItems)
                        return self._readItem(load)
                    else:
                        return None

        if isinstance(spec, Path):
            return self.walk(spec, lambda parent, name, child, **kwds: child,
                             load=load)

        raise TypeError, '%s is not Path or UUID' %(type(spec))

    def findPath(self, path, load=True):
        """
        Find an item by path.

        See L{find} for more information.

        @param path: a path
        @type path: L{Path<repository.util.Path.Path>} or a path string
        @param load: load the item if it not yet loaded, C{True} by default
        @type load: boolean
        @return: an item or C{None} if not found
        """

        if isinstance(path, str) or isinstance(path, unicode):
            path = Path(path)
        elif not isinstance(path, Path):
            raise TypeError, '%s is not Path or string' %(type(path))

        return self.walk(path, lambda parent, name, child, **kwds: child,
                         load=load)

    def findUUID(self, uuid, load=True):
        """
        Find an item by UUID.

        See L{find} for more information.

        @param uuid: a UUID
        @type uuid: L{UUID<chandlerdb.util.UUID.UUID>} or a uuid string
        @param load: load the item if it not yet loaded, C{True} by default
        @type load: boolean
        @return: an item or C{None} if not found
        """

        if isinstance(uuid, str) or isinstance(uuid, unicode):
            uuid = UUID(uuid)
        elif not isinstance(uuid, UUID):
            raise TypeError, '%s is not UUID or string' %(type(uuid))

        return self.find(uuid, load)

    def _findKind(self, spec, withSchema):

        return self.find(spec)

    def getACL(self, uuid, name):
        """
        Get an Access Control List.

        ACLs are stored by C{(uuid, name)} tuples. C{name} can be C{None}.
        Therefore, each item in the repository may have an ACL, and each
        attribute value for each item in the repository may also have an
        ACL.

        By convention, the ACL for an item is stored with C{(item.itsUUID,
        None)} and the ACL for an attribute value on an item is stored with
        C{(item.itsUUID, attributeName)}.

        @param uuid: a L{UUID<chandlerdb.util.UUID.UUID>} instance
        @param name: a string or C{None}
        @return: an L{ACL<repository.item.Access.ACL>} instance or C{None}
        """

        return self.repository.store.loadACL(self._version, uuid, name)

    def loadPack(self, path, parent=None):
        """
        Load items from the pack definition file at path.

        This is mostly a bootstrap feature.

        @param path: the path to the packfile to load
        @type path: a string
        @param parent: the item to load the items in the pack under
        @type parent: an item
        """

        if timing: tools.timing.begin("Load pack")

        packs = self.getRoot('Packs')
        if not packs:
            packs = Item('Packs', self, None)

        PackHandler(path, parent, self).parseFile(path)

        if timing: tools.timing.end("Load pack")

    def dir(self, item=None, path=None):
        """
        Print out a listing of each item in the repository or under item.

        This is a debugging feature.

        @param item: the item to list children of, or C{None}
        @type item: an item
        @param path: the path to the item to list children of, or C{None}
        @type path: a L{Path<repository.util.Path.Path>} instance
        """
        
        if item is None:
            path = Path('//')
            for root in self.iterRoots():
                self.dir(root, path)
        else:
            if path is None:
                path = item.itsPath
            else:
                path.append(item._name or item._uuid)
            print path
            for child in item:
                self.dir(child, path)
            path.pop()

    def check(self):
        """
        Runs repository consistency checks on this view.

        All items of the repository are loaded into this view and checked
        for consistency with their schema definition. See
        L{Item.check<repository.item.Item.Item.check>} for more details.
        """

        result = True
        for root in self.iterRoots():
            check = root.check(True)
            result = result and check

        return result

    def hasRoot(self, name, load=True):
        """
        Tell whether the repository has a root by a given name.

        This view is searched for a root.

        @param name: the name of the root to be looked for
        @type name: a string
        @param load: controls whether to check only loaded roots if
        C{False} or all roots if C{True}, the default.
        @return: C{True} or C{False}
        """

        return (name is not None and
                self._roots.resolveAlias(name, load) is not None)

    def getRoot(self, name, load=True):
        """
        Get a root by a given name.

        This view is searched for a root.

        @param name: the name of the root to be looked for
        @type name: a string
        @param load: controls whether to check only loaded roots if
        C{False} or all roots if C{True}, the default.
        @return: a root item or C{None} if not found.
        """

        return self._roots.getByAlias(name, None, load)

    def __getitem__(self, key):

        if isinstance(key, UUID):
            if key == self.itsUUID:
                return self
            else:
                try:
                    return self._registry[key]
                except KeyError:
                    item = self._loadItem(key)
                    if item is not None:
                        return item
                    raise

        if isinstance(key, str) or isinstance(key, unicode):
            root = self.getRoot(key)
            if root is not None:
                return root
            raise KeyError, key

        raise TypeError, key

    def __iter__(self):
        """
        (deprecated) Use L{iterRoots} instead.
        """

        raise DeprecationWarning, 'Use RepositoryView.iterRoots() instead'
    
    def iterChildren(self):
        """
        See L{iterRoots}
        """

        return self.iterRoots()
    
    def iterRoots(self, load=True):
        """
        Iterate over the roots of this repository in this view.
        """

        if not load:
            for child in self._roots._itervalues():
                yield child._value

        else:
            for child in self._roots:
                yield child

    def _getPath(self, path=None):

        if path is None:
            path = Path()
        path.set('//')

        return path

    def _getStore(self):

        return self.repository.store

    def _logItem(self, item):

        if not self.repository.isOpen():
            raise RepositoryError, 'Repository is not open'

        if item.itsView is not self:
            raise RepositoryError, 'Repository view is not owning item: %s' %(item.itsPath)

        return not self.isLoading()

    def _addItem(self, item, previous=None, next=None):

        name = item.itsName

        if (name is not None and
            self._roots.resolveAlias(name, not self.isLoading()) is not None):
            raise ValueError, "A root named '%s' exists already" %(name)

        self._roots.__setitem__(item._uuid, item, alias=name)

        return item

    def _removeItem(self, item):

        del self._roots[item.itsUUID]

    def _unloadChild(self, child):

        self._roots._unloadChild(child)

    def _registerItem(self, item):

        uuid = item.itsUUID

        old = self._registry.get(uuid)
        if old is not None and old is not item:
            raise ValueError, '%s: re-registering %s with different object' %(self, item)
        
        self._registry[uuid] = item

    def _unregisterItem(self, item, reloadable):

        uuid = item.itsUUID
        del self._registry[uuid]

        if item.isDeleting():
            self._deletedRegistry[uuid] = uuid
        elif reloadable:
            self._instanceRegistry[uuid] = item

    def _reuseItemInstance(self, uuid):

        try:
            instance = self._instanceRegistry[uuid]
            del self._instanceRegistry[uuid]
        except KeyError:
            instance = None

        return instance

    def refresh(self, mergeFn=None):
        """
        Refresh this view to the changes made in other views.

        Refreshing a view causes the following to happen, in this order:
        
            1. Version conflicts are detected. If an item in this view was
               changed in another view and it committed its changes first,
               there is a chance that these changes would conflict with the
               ones about to be committed by this view. A
               C{VersionConflictError} is raised in that situation.
            2. The view is refreshed to the latest version in persistent
               store. Pointers to items that changed in other views that are
               also in this view are marked C{STALE} unless they're pinned
               in memory in which case they're refreshed in place.
            3. Change and history notifications from changes in other views
               are dispatched after the merges succeeded.
            4. If the view's cache has reached a threshhold item count - at
               the moment 10,000 - the least-used items are removed from
               cache and pointers to them are marked C{STALE} such that the
               size of the cache drops below 90% of this threshhold.
        """
        
        raise NotImplementedError, "%s.commit" %(type(self))

    def commit(self, mergeFn=None):
        """
        Commit all the changes made to items in this view.

        Committing a view causes the following to happen, in this order:
        
            1. L{refresh} is called.
            2. All changes made to items in the view are saved to
               persistent storage.
            3. Change and history notifications from the items committed
               are dispatched after the transactions commits.
        """
        
        raise NotImplementedError, "%s.commit" %(type(self))

    def cancel(self):
        """
        Cancel all the changes made to items in this view.

        Cancelling a view causes the following to happen, in this order:
        
            1. All new items are unloaded.
            2. All deleted and changed items are refreshed to their original
               state and marked unchanged.
            3. If the view's cache has reached a threshhold item count - at
               the moment 10,000 - the least-used items are removed from
               cache and pointers to them are marked C{STALE} such that the
               size of the cache drops below 90% of this threshhold.
        """
        
        raise NotImplementedError, "%s.cancel" %(type(self))

    def queryItems(self, kind=None, attribute=None, load=True):
        """
        Query this view for items.

        @param kind: a kind item for a kind query
        @type kind: an item
        @param attribute: an attribute UUID for a value query
        @type attribute: a UUID
        @param load: if C{False} only return loaded items
        @type load: boolean
        """
        
        raise NotImplementedError, "%s.queryItems" %(type(self))

    def searchItems(self, query, load=True):
        """
        Search this view for items using an Lucene full text query.

        @param query: an lucene query
        @type query: a string
        @param load: if C{False} only return loaded items
        @type load: boolean
        """

        raise NotImplementedError, "%s.searchItems" %(type(self))

    def _loadItem(self, uuid):
        raise NotImplementedError, "%s._loadItem" %(type(self))

    def _loadRoot(self, name):
        raise NotImplementedError, "%s._loadRoot" %(type(self))

    def _newItems(self):
        raise NotImplementedError, "%s._newItems" %(type(self))

    def __getUUID(self):

        return self.repository.itsUUID

    def __getName(self):

        return self.name

    def getLogger(self):

        return self.repository.logger

    def isDebug(self):

        return self.repository.logger.getEffectiveLevel() <= logging.DEBUG

    def getRepositoryView(self):

        return self

    def mapChanges(self, callable):
        """
        Invoke a callable for every item changed in this view.

        For each item that was changed in this view since it last committed
        a callable is invoked with the following arguments:

            - the item

            - the item's current version

            - the item's current status bits

            - a list of changed literal attribute names

            - a list of changed references attribute names
        """

        raise NotImplementedError, "%s.mapChanges" %(type(self))
    
    def mapHistory(self, callable, fromVersion=0, toVersion=0):
        """
        Invoke a callable for every committed item change in other views.

        For each item in this view that was changed and committed in another
        view a callable is invoked with the following arguments:

            - the item as it is in this view

            - the item's committed version for the change

            - the item's committed status bits for the change

            - a list of changed literal attribute names

            - a list of changed references attribute names

        @param fromVersion: the version to start iterating changes from, the
        current version by default.
        @type fromVersion: integer
        @param fromVersion: the version to continue iterating changes to, the
        latest committed version by default.
        @type fromVersion: integer
        """

        raise NotImplementedError, "%s.mapHistory" %(type(self))
        
    def _commitMerge(self):

        if self._status & Item.CMERGED:
            self._roots._commitMerge()

    def _revertMerge(self):

        if self._status & Item.CMERGED:
            self._roots._revertMerge()

        self._status &= ~Item.MERGED

    def getItemVersion(self, version, item):

        return self.repository.store.getItemVersion(version, item._uuid)

    itsUUID = property(__getUUID)
    itsName = property(__getName)
    itsPath = property(_getPath)
    itsParent = None
    
    logger = property(getLogger)
    debug = property(isDebug)
    store = property(_getStore)

    OPEN       = 0x0001
    REFCOUNTED = 0x0002
    LOADING    = 0x0004
    COMMITTING = 0x0008
    
    # flags from Item
    # CDIRTY   = 0x0200
    # merge flags


class OnDemandRepositoryView(RepositoryView):

    def __init__(self, repository, name):

        self._version = repository.store.getVersion()
        self._exclusive = ThreadSemaphore()
        self._hooks = []
        
        super(OnDemandRepositoryView, self).__init__(repository, name)

    def isNew(self):

        return self._version == 0

    def _setLoading(self, loading, runHooks=False):

        if not loading and self.isLoading() and runHooks:
            try:
                for hook in self._hooks:
                    hook(self)
            finally:
                self._hooks = []

        return super(OnDemandRepositoryView, self)._setLoading(loading,
                                                               runHooks)

    def _readItem(self, itemReader):

        try:
            release = False
            loading = self.isLoading()
            debug = self.isDebug()
            if not loading:
                release = self._exclusive.acquire()
                self._setLoading(True)
                self._hooks = []

            exception = None

            if debug:
                self.logger.debug('loading item %s', itemReader.getUUID())

            item = itemReader.readItem(self, self._hooks)

            if debug:
                self.logger.debug("loaded version %d of %s",
                                  item._version, item.itsPath)

        except:
            if not loading:
                self._setLoading(False, False)
                self._hooks = []
            if release:
                self._exclusive.release()
            raise
        
        else:
            if not loading:
                self._setLoading(False, True)
            if release:
                self._exclusive.release()

        return item

    def _loadItem(self, uuid):

        if not uuid in self._deletedRegistry:
            itemReader = self.repository.store.loadItem(self._version, uuid)

            if itemReader is not None:
                self.logger.debug("loading item %s", uuid)
                return self._readItem(itemReader)

        return None

    def _findSchema(self, spec, withSchema):

        if withSchema:
            return self.find(spec, load=False)

        # when crossing the schema boundary, reset loading status so that
        # hooks get called before resuming regular loading

        try:
            hooks = self._hooks
            loading = self._setLoading(False)
            
            return self.find(spec)
        finally:
            self._hooks = hooks
            self._setLoading(loading)

    def _addItem(self, item, previous=None, next=None):

        super(OnDemandRepositoryView, self)._addItem(item, previous, next)

        item.setPinned(True)

        return item

    def _removeItem(self, item):

        super(OnDemandRepositoryView, self)._removeItem(item)

        item.setPinned(False)
        
    def prune(self, size):

        registry = self._registry
        
        if len(registry) > size * 1.1:
            gc.collect()
            heap = [(item._lastAccess, item._uuid)
                    for item in registry.itervalues()
                    if not item._status & (item.PINNED | item.DIRTY)]

            heapq.heapify(heap)
            count = len(heap) - int(size * 0.9)
            self.logger.info('pruning %d items', count)

            if self.isRefCounted():
                for i in xrange(count):
                    item = registry[heapq.heappop(heap)[1]]
                    itemRefs = item._refCount()
                    pythonRefs = sys.getrefcount(item)
                    if pythonRefs - itemRefs <= 3:
                        item._unloadItem(False)
                    else:
                        self.logger.warn('not pruning %s (refCount %d)',
                                         Item.__repr__(item),
                                         pythonRefs - itemRefs)
            else:
                for i in xrange(count):
                    registry[heapq.heappop(heap)[1]]._unloadItem(False)


class AbstractRepositoryViewManager(object):

    def __init__(self, repository, viewName = None):
        """
        Base Class for View Context Management.

        @param repository: a Repository instance
        @type repository: C{Repository}
        @param viewName: The name to assign as the key for the view
        @type name: a string
        @return: C{None}
        """

        if repository is None:
            raise RepositoryError, "Repository Instance is None"

        self.repository = repository
        self.view = self.repository.createView(viewName)
        self.prevView = None
        self.callChain = False
        self.log = self._getLog()

    def _getLog(self):
        """
        This method is called by the __init__ method to retrieve a C{logging.Logger} for
        logging.

        This method can be sub-classed to return a custom logger by the child.

        @return: C{logging.Logger}
        """

        log = logging.getLogger("AbstractRepositoryViewManager")
        log.setLevel(logging.DEBUG)
        return log

    def setViewCurrent(self):
        """
        This method changes the current C{RepositoryView} to be the C{RepositoryView} associated with the 
        C{AbstractRepositoryViewManger} instance.

        It saves the previous C{RepositoryView}. Calling C{AbstractRepositoryViewManager.restorePreviousView} will
        set the previous C{RepositoryView} as the current C{RepositoryView}.

        @return: C{None}
        """

        assert self.callChain is False, "setViewCurrent called again before a restorePreviousView"

        assert self.prevView is None, "Nested prevView investigate"
        self.prevView = self.getCurrentView()
        self.repository.setCurrentView(self.view)

        self.callChain = True


    def restorePreviousView(self):
        """
        This method will restore the C{RepositoryView} that was current before 
        C{AbstractRepositoryViewManager.setViewCurrent} when called.

        The C{AbstractRepositoryViewManager.setViewCurrent} method must be called before this method.

        @return: C{None}
        """

        if self.callChain is not True:
            raise RepositoryError, "restorePreviousView called before setViewCurrent"

        if self.prevView is not None:
             self.repository.setCurrentView(self.prevView)
             self.prevView = None

        self.callChain = False


    def execInView(self, method, *args, **kw):
        """
        This utility method will call C{AbstractRepositoryViewManager.setCurrentView}.
        Execute the method passed in as an argument and call
        C{AbstractRepositoryViewManager.restorePreviousView} when the method is finished executing.

        It abstracts the C{RepositoryView} switching logic for the caller and is the recommended means of
        executing code that utilizes a C{RepositoryView}.

        @param method: The method to execute
        @type method: a string
        @param args: Arguments to pass to the method
        @type args: list reference
        @param kw: Keyword dict to pass to the method
        @type args: dict reference
        @return: The value returned by the method call or None
        """

        result = None

        self.setViewCurrent()

        try:
            result = method(*args, **kw)

        finally:
            self.restorePreviousView()

        return result


    def execInViewThenCommit(self, method, *args, **kw):
        """
        This utility method will call C{AbstractRepositoryViewManager.setCurrentView},
        execute the method passed in as an argument and perform a Repository commit in
        the current Thread then call C{AbstractRepositoryViewManager.restorePreviousView}.

        It abstracts the C{RepositoryView} switching and commit logic for the caller and
        is the recommended means of executing a method and inline commit in a C{RepositoryView}.

        @param method: The method to execute
        @type method: a string
        @param args: Arguments to pass to the method
        @type args: list reference
        @param kw: Keyword dict to pass to the method
        @type args: dict reference
        @return: The value returned by the method call or None
        """
        result = None

        self.setViewCurrent()

        try:
            result = method(*args, **kw)
            self.__commit()
        finally:
            self.restorePreviousView()

        return result

    def execInViewThenCommitInThread(self, method, *args, **kw):
        """
        This utility method will call C{AbstractRepositoryViewManager.setCurrentView},
        execute the method passed in as an argument, spawn a Thread to perform a Repository commit,
        then call C{AbstractRepositoryViewManager.restorePreviousView}. Spawning a thread prevents the
        current Thread from blocking which the C{RepositoryView} is commiting. This is especially useful
        when a Asynchronous model is employed.

        The method abstracts the C{RepositoryView} switching and commit logic for the caller and
        is the recommended means of executing a method and non-blocking commit in a C{RepositoryView}.

        @param method: The method to execute
        @type method: a string
        @param args: Arguments to pass to the method
        @type args: list reference
        @param kw: Keyword dict to pass to the method
        @type args: dict reference
        @return: The value returned by the method call or None
        """

        result = self.execInView(method, *args, **kw)
        self.commitInView(True)
        return result

    def getCurrentView(self):
        """
        Gets the current C{RepositoryView} the C{Repository} is working with
        @return: C{RepositoryView}
        """

        return self.repository.getCurrentView(False)

    def printCurrentView(self, printString = None):
        """
        Writes the current C{RepositoryView} as well as optional printString to the C{logging.Logger}
        instance. This method is useful for C{RepositoryView} debugging.

        @param printString: An optional string to display with the message (i.e. the name of the calling method)
        @type printString: string
        @return: C{None}
        """

        str = None

        if printString is None:
             self.log.info("Current View is: %s" % self.getCurrentView())
        else:
             self.log.info("[%s] Current View is: %s" % (printString, self.getCurrentView()))


    def commitInView(self, useThread=False):
        """
        Runs a C{RepositoryView} commit. If the commit is successful calls the
        C{AbstractRepositoryViewManager._viewCommitSuccess} method otherwise calls
        the C{AbstractRepositoryViewManager._viewCommitFailed} method. Both methods
        can be subclassed to add additional functionality. An optional useThread
        argument can be passed which indicates to run the commit in a dedicated
        thread to prevent blocking the current thread.

        @param useThread: Flag to indicate whether to run the view commit in the current
                          thread or a dedicated thread to prevent blocking
        @type: boolean
        @return: C{None}
        """

        if useThread:
            thread = Thread(target=self.__commitInView)
            thread.start()

        else:
            self.__commitInView

    def _viewCommitSuccess(self):
         """
         Called by C{AbstractRepositoryViewManager.commitView} when a
         C{RepositoryView} is commited.

         Overide this method to handle any additional functionality needed
         when a C{RepositoryView} is committed.
         @return: C{None}
         """

         pass

    def _viewCommitFailed(self, err):
         """
         Called by C{AbstractRepositoryViewManager.commitView} when a
         C{RepositoryView} raises an error on commited.

         Overide this method to handle any additional functionality needed
         when a C{RepositoryView} fails on commit.

         @param err: A Python Exception instance to use for debugging and error message display
         @type Exception

         @return: C{None}
         """
         str = "View Commit Failed: %s" % err
         self.log.error(str)

    def __commitInView(self):
        """
        Sets the current view then Attempts to commit the view.
        Calls viewCommitSuccess or viewCommitFailed. Then restore the 
        previous view. Need to sync with Andi on
        what happens in the case of a conflict or
        failed commit. This is still being resolved
        by the repository team
        """

        self.setViewCurrent()

        try:
            self.__commit()

        finally:
            self.restorePreviousView()

    def __commit(self):
        """
        Attempts to commit in the view. Calls viewCommitSuccess or
        viewCommitFailed.  This method does not set or unset the current 
        view.  Need to sync with Andi on
        what happens in the case of a conflict or
        failed commit. This is still being resolved
        by the repository team
        """

        try:
           self.view.commit()

        except RepositoryError, e:
           """This condition needs to be flushed out more"""
           self._viewCommitFailed(e)

        except VersionConflictError, e1:
           """This condition needs to be flushed out more"""
           self._viewCommitFailed(e1)

        except Exception, e2:
           """Catch any unknown exceptions raised by the Repository"""
           self._viewCommitFailed(e2)

        else:
           self._viewCommitSuccess()
