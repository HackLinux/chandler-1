
__revision__  = "$Revision$"
__date__      = "$Date$"
__copyright__ = "Copyright (c) 2003-2004 Open Source Applications Foundation"
__license__   = "http://osafoundation.org/Chandler_0.1_license_terms.htm"

from repository.item.PersistentCollections import PersistentCollection
from repository.item.PersistentCollections import PersistentList
from repository.item.PersistentCollections import PersistentDict
from repository.item.Values import Values, References, ItemValue

from repository.util.SingleRef import SingleRef
from chandlerdb.util.UUID import UUID
from repository.util.Path import Path
from repository.util.ClassLoader import ClassLoader
from repository.util.SAX import ContentHandler


class RefArgs(object):

    def __init__(self, name, item, otherName, ref, **kwds):

        self.name = name
        self.item = item
        self.otherName = otherName
        self.ref = ref
        self.other = None
        self.kwds = kwds

    def _setItem(self, item):

        self.item = item
        other = item.find(self.ref, load=False)
        if other is not None:
            self.other = other

        return other

    def _setValue(self):

        item = self.item
        other = self.other

        if other is None:
            other = item.find(self.ref, load=False)
            if other is None:
                raise ValueError, 'item not found: %s' %(self.ref)

        item._references._setValue(self.name, other, self.otherName,
                                   **self.kwds)

    def _setRef(self):

        if self.other is None:
            other = self.ref
        else:
            other = self.other
            
        self.item._references._setRef(self.name, other, self.otherName,
                                      **self.kwds)
        

class ItemHandler(ContentHandler):
    'A SAX ContentHandler implementation responsible for loading items.'
    
    typeHandlers = {}
    
    def __init__(self, repository, parent, afterLoadHooks):

        ContentHandler.__init__(self)

        self.repository = repository
        self.loading = repository.isLoading()
        self.parent = parent
        self.afterLoadHooks = afterLoadHooks
        self.item = None
        self.handlerClass = ItemHandler
        
        if repository not in ItemHandler.typeHandlers:
            ItemHandler.typeHandlers[repository] = {}
        
    def startDocument(self):

        self.tagAttrs = []
        self.tags = []
        self.delegates = []
        self.fields = None
        self.tagCounts = []

    def startElement(self, tag, attrs):

        if not self.errorOccurred():
            try:
                self.data = ''
                if attrs is None:
                    attrs = {}
            
                if self.delegates:
                    delegate = self.delegates[-1]
                    delegateClass = type(delegate)
                else:
                    delegate = self
                    delegateClass = self.handlerClass
            
                method = getattr(delegateClass, tag + 'Start', None)
                if method is not None:
                    method(delegate, self, attrs)

                self.tags.append(tag)
                self.tagAttrs.append(attrs)
            except:
                self.saveException()

    def endElement(self, tag):

        if not self.errorOccurred():
            try:
                withValue = False

                if self.delegates:
                    delegate = self.delegates[-1]
                    if delegate.isValueReady(self):
                        self.delegates.pop()
                        value = delegate.getParsedValue(self, self.data)
                        withValue = True

                if self.delegates:
                    delegate = self.delegates[-1]
                    delegateClass = type(delegate)
                else:
                    delegate = self
                    delegateClass = self.handlerClass
            
                attrs = self.tagAttrs.pop()
                method = getattr(delegateClass, self.tags.pop() + 'End', None)
                if method is not None:
                    if withValue:
                        method(delegate, self, attrs, value=value)
                    else:
                        method(delegate, self, attrs)
            except:
                self.saveException()

    def characters(self, data):

        self.data += data

    def refStart(self, itemHandler, attrs):

        if self.tags[-1] == 'item':
            name = attrs['name']
            attribute = self.getAttribute(name)
            self.attributes.append(attribute)

            flags = attrs.get('flags', None)
            if flags is not None:
                flags = int(flags)
                self.references._setFlags(name, flags)
                readOnly = flags & Values.READONLY
            else:
                readOnly = False

            cardinality = self.getCardinality(attribute, attrs)
            if cardinality != 'single':
                if cardinality == 'dict':
                    self.repository.logger.warning("Warning, 'dict' cardinality for reference attribute %s on %s is deprecated, use 'list' instead", name, self.name or self.uuid)
                self._setupRefList(name, attribute, readOnly, attrs)

    def _setupRefList(self, name, attribute, readOnly, attrs):

        refList = None
        otherName = self.getOtherName(name, attribute, attrs)

        if 'uuid' in attrs:
            uuid = UUID(attrs['uuid'])
        else:
            uuid = None

        if self.update and attrs.get('operation') == 'append':
            refList = self.item._references.get(name)

        if refList is None:
            refList = self.repository._createRefList(None, name, otherName,
                                                     True, readOnly, uuid)
                
        self.collections.append(refList)

    def itemStart(self, itemHandler, attrs):

        self.values = Values(None)
        self.references = References(None)
        self.collections = []
        self.attributes = []
        self.refs = []
        self.name = None
        self.kind = None
        self.cls = None
        self.kindRef = None
        self.parentRef = None
        self.isContainer = False
        self.withSchema = attrs.get('withSchema', 'False') == 'True'
        self.uuid = UUID(attrs.get('uuid'))
        self.version = long(attrs.get('version', '0L'))
        self.update = update = attrs.get('update')

        if update is not None:
            typeAttr = attrs.get('type', 'path')
            if typeAttr == 'path':
                item = self.parent.find(Path(update))
            elif typeAttr == 'uuid':
                item = self.parent.find(UUID(update))
            else:
                raise TypeError, typeAttr

            if item is None:
                raise NoSuchItemError, (update, self.version)

            self.item = item
            self.cls = type(item)
            self.version = item._version
            self.name = item.itsName
            self.kind = item.itsKind
            self.uuid = item.itsUUID
            self.parent = item.itsParent
        
    def itemEnd(self, itemHandler, attrs):

        from repository.item.Item import Item
        
        if self.withSchema:
            status = Item.CORESCHEMA
        else:
            status = 0

        cls = self.cls
        if cls is None:
            if self.kind is None:
                cls = Item
            else:
                cls = self.kind.getItemClass()

        instance = self.repository._reuseItemInstance(self.uuid)
        if instance is not None:
            if cls is not type(instance):
                raise TypeError, 'Class for item has changed from %s to %s' %(type(instance), cls)
            item = self.item = instance
            status |= item._status & item.PINNED
            instance = None

        elif self.update:
            item = self.item
            values = item._values
            references = item._references

            for name, value in self.values.iteritems():
                values[name] = value
                item.setDirty(Item.VDIRTY, name, values, noMonitors=True)
            self.values = values

            for name, value in self.references.iteritems():
                if not isinstance(value, dict):
                    dirty = Item.VDIRTY
                    item.setAttributeValue(name, value, _attrDict=references,
                                           setDirty=False)
                else:
                    dirty = Item.RDIRTY
                    references[name] = value
                item.setDirty(dirty, name, references, noMonitors=True)
            self.references = references

            status = item._status | Item.NDIRTY

        else:
            item = self.item = cls.__new__(cls)

        item._fillItem(self.name, self.parent, self.kind, uuid = self.uuid,
                       values = self.values, references = self.references,
                       afterLoadHooks = self.afterLoadHooks,
                       version = self.version, status = status,
                       update = self.update)

        if self.isContainer and item._children is None:
            item._children = self.repository._createChildren(item)

        if not self.update:
            self.repository._registerItem(item)
            self.values._setItem(item)
            self.references._setItem(item)

        for attribute, value in self.values.iteritems():
            if isinstance(value, PersistentCollection):
                if self.withSchema:
                    # mixed collections not supported in core schema
                    companion = None
                else:
                    companion = item.getAttributeAspect(attribute, 'companion',
                                                        default=None)
                value._setItem(item, attribute, companion)
            elif isinstance(value, ItemValue):
                value._setItem(item, attribute)

        for refArgs in self.refs:
            other = refArgs._setItem(item)
            if self.loading:
                refArgs._setRef()
            elif other is None:
                self.afterLoadHooks.append(refArgs._setValue)
            else:
                refArgs._setValue()

        if hasattr(cls, 'onItemLoad'):
            self.afterLoadHooks.append(item.onItemLoad)

    def kindEnd(self, itemHandler, attrs):

        assert not self.item

        if attrs['type'] == 'uuid':
            self.kindRef = UUID(self.data)
        else:
            self.kindRef = Path(self.data)

        self.kind = self.repository._findSchema(self.kindRef, self.withSchema)
        if self.kind is None:
            if self.withSchema:
                self.afterLoadHooks.append(self._setKind)
            else:
                raise ValueError, "While loading %s, kind %s not found" %(self.name or self.uuid, self.kindRef)

    def _setKind(self):

        if self.item._kind is None:
            self.kind = self.repository.find(self.kindRef)
            if self.kind is None:
                raise ValueError, 'Kind %s not found' %(self.kindRef)
            else:
                self.item._kind = self.kind

    def parentEnd(self, itemHandler, attrs):

        if attrs['type'] == 'uuid':
            self.parentRef = UUID(self.data)
        else:
            self.parentRef = Path(self.data)

        self.isContainer = attrs.get('container', 'False') == 'True'
        self.parent = self.repository.find(self.parentRef)

        if self.parent is None:
            self.afterLoadHooks.append(self._move)

    def _move(self):

        if self.item._parent is None:
            self.parent = self.repository.find(self.parentRef)
            if self.parent is None:
                raise ValueError, 'Parent %s not found' %(self.parentRef)
            else:
                self.item.move(self.parent)

    def classEnd(self, itemHandler, attrs):

        self.cls = ClassLoader.loadClass(self.data, attrs['module'])

    def nameEnd(self, itemHandler, attrs):

        self.name = self.data

    def refEnd(self, itemHandler, attrs):

        if self.tags[-1] == 'item':
            attribute = self.attributes.pop()
            cardinality = self.getCardinality(attribute, attrs)
            otherCard = attrs.get('otherCard', None)
            
        else:
            cardinality = 'single'
            otherCard = self.tagAttrs[-1].get('otherCard', None)

        if cardinality == 'single':     # cardinality of tag
            typeName = attrs.get('type', 'path')

            if typeName == 'path':
                ref = Path(self.data)
            elif typeName == 'none':
                self.references[attrs['name']] = None
                return
            else:
                ref = UUID(self.data)

            if self.collections:
                refList = self.collections[-1]
                self.refs.append(RefArgs(refList._name, None,
                                         refList._otherName, ref,
                                         otherCard=otherCard,
                                         otherAlias=attrs.get('otherAlias'),
                                         previous=self.refName(attrs, 'previous'),
                                         next=self.refName(attrs, 'next'),
                                         alias=attrs.get('alias')))
            else:
                name = attrs['name']
                otherName = self.getOtherName(name, self.getAttribute(name),
                                              attrs)
                self.refs.append(RefArgs(name, None, otherName, ref,
                                         otherCard=otherCard,
                                         otherAlias=attrs.get('otherAlias')))
        else:
            value = self.collections.pop()
            self.references[attrs['name']] = value
            if value._indexes:
                self.afterLoadHooks.append(value._restoreIndexes)

    def indexEnd(self, itemHandler, attrs):

        if not self.collections:
            raise ValueError, self.tagAttrs[-1]['name']

        refList = self.collections[-1]
        kwds = attrs.copy()
        del kwds['type']
        del kwds['name']
        refList.addIndex(attrs['name'], attrs['type'], **kwds)

    def attributeStart(self, itemHandler, attrs):

        attribute = self.getAttribute(attrs['name'])
        self.attributes.append(attribute)

        cardinality = self.getCardinality(attribute, attrs)
        typeName = self.getTypeName(attribute, attrs, 'str')
        
        if cardinality == 'list':
            self.collections.append(PersistentList(None, None, None))
        elif cardinality == 'dict':
            self.collections.append(PersistentDict(None, None, None))
        else:
            self.valueStart(itemHandler, attrs)

    def valueStart(self, itemHandler, attrs):

        if self.setupTypeDelegate(attrs):
            return

        if (self.tags[-1] == 'attribute' and
            self.setupTypeDelegate(self.tagAttrs[-1])):
            return

        typeName = None

        if attrs.has_key('type'):
            typeName = attrs['type']
        elif (self.tags[-1] == 'attribute' and
              self.tagAttrs[-1].has_key('type')):
            typeName = self.tagAttrs[-1]['type']

        if typeName == 'dict':
            self.collections.append(PersistentDict(None, None, None))
        elif typeName == 'list':
            self.collections.append(PersistentList(None, None, None))

    # valueEnd is called when parsing 'dict' or 'list' cardinality values of
    # one type (type specified with cardinality) or of unspecified type
    # (type specified with value) or 'dict' or 'list' type values of 'single'
    # or unspecified cardinality or values of type 'Dictionary' or 'List' of
    # any cardinality. A mess of overloading.
    
    def attributeEnd(self, itemHandler, attrs, **kwds):

        if kwds.has_key('value'):
            value = kwds['value']
        else:
            attribute = self.attributes.pop()
            cardinality = self.getCardinality(attribute, attrs)

            if cardinality == 'dict' or cardinality == 'list':
                value = self.collections.pop()
            else:
                typeName = self.getTypeName(attribute, attrs, 'str')
                if typeName == 'dict' or typeName == 'list':
                    value = self.collections.pop()
                else:
                    value = self.makeValue(typeName, self.data)
                    if attrs.has_key('eval'):
                        typeHandler = self.typeHandler(self.repository, value)
                        value = typeHandler.eval(value)
            
        if self.delegates:
            raise ValueError, "while loading '%s.%s' type delegates didn't pop: %s" %(self.name or self.uuid, attrs['name'], self.delegates)

        self.values[attrs['name']] = value

        flags = attrs.get('flags', None)
        if flags is not None:
            flags = int(flags)
            self.values._setFlags(attrs['name'], flags)
            if flags & Values.READONLY:
                if isinstance(value, PersistentCollection):
                    value.setReadOnly()
                elif isinstance(value, ItemValue):
                    value._setReadOnly()

    def valueEnd(self, itemHandler, attrs, **kwds):

        if kwds.has_key('value'):
            value = kwds['value']
        else:
            typeName = self.getTypeName(self.attributes[-1], attrs, None)
            if typeName is None:
                if self.tags[-1] == 'attribute':
                    typeName = self.getTypeName(self.attributes[-1],
                                                self.tagAttrs[-1], 'str')
                else:
                    typeName = 'str'
                
            if typeName == 'dict' or typeName == 'list':
                value = self.collections.pop()
            else:
                value = self.makeValue(typeName, self.data)
                if attrs.has_key('eval'):
                    typeHandler = self.typeHandler(self.repository, value)
                    value = typeHandler.eval(value)

        name = attrs.get('name')

        if name is None:
            self.collections[-1].append(value, False)
        else:
            name = self.makeValue(attrs.get('nameType', 'str'), name)
            self.collections[-1].__setitem__(name, value, False)

    def getCardinality(self, attribute, attrs):

        cardinality = attrs.get('cardinality')

        if cardinality is None:
            if attribute is None:
                cardinality = 'single'
            else:
                cardinality = attribute.getAspect('cardinality',
                                                  default='single')

        return cardinality

    def getTypeName(self, attribute, attrs, default):

        if attrs.has_key('typeid'):
            try:
                return self.repository[UUID(attrs['typeid'])].handlerName()
            except KeyError:
                raise TypeError, "Type %s not found" %(attrs['typeid'])

        if attrs.has_key('typepath'):
            typeItem = self.repository.find(Path(attrs['typepath']))
            if typeItem is None:
                raise TypeError, "Type %s not found" %(attrs['typepath'])
            return typeItem.handlerName()

        if attrs.has_key('type'):
            return attrs['type']

        if attribute is not None:
            attrType = attribute.getAspect('type', default=None)
            if attrType is not None:
                return attrType.handlerName()

        return default

    def refName(self, attrs, attr):

        try:
            return self.makeValue(attrs.get(attr + 'Type', 'str'), attrs[attr])
        except KeyError:
            return None

    def getOtherName(self, name, attribute, attrs):

        otherName = attrs.get('otherName')

        if otherName is None and attribute is not None:
            otherName = self.kind.getOtherName(name, default=None)

        if otherName is None:
            raise TypeError, 'Undefined other endpoint for %s.%s of kind %s' %(self.name or self.uuid, name, self.kind.itsPath)

        return otherName

    def getAttribute(self, name):

        if self.withSchema is False and self.kind is not None:
            return self.kind.getAttribute(name)
        else:
            return None

    def setupTypeDelegate(self, attrs):

        if attrs.has_key('typeid'):
            try:
                attrType = self.repository[UUID(attrs['typeid'])]
            except KeyError:
                raise TypeError, "Type %s not found" %(attrs['typeid'])

            self.delegates.append(attrType)
            attrType.startValue(self)

            return True
        
        elif self.attributes[-1]:
            attrType = self.attributes[-1].getAspect('type')
            if attrType is not None and not attrType.isAlias():
                self.delegates.append(attrType)
                attrType.startValue(self)

                return True

        return False
    
    def makeValue(cls, typeName, data):

        try:
            return cls.typeDispatch[typeName](data)
        except KeyError:
            raise ValueError, "Unknown type %s for data: %s" %(typeName, data)

    def typeHandler(cls, repository, value):

        try:
            for uuid in ItemHandler.typeHandlers[repository][type(value)]:
                t = repository[uuid]
                if t.recognizes(value):
                    return t
        except KeyError:
            pass

        typeKind = repository[ItemHandler.typeHandlers[repository][None]]
        types = typeKind.findTypes(value)
        if types:
            return types[0]
            
        raise TypeError, 'No handler for values of type %s' %(type(value))

    def typeName(cls, repository, value):

        return cls.typeHandler(repository, value).handlerName()

    def makeString(cls, repository, value):

        return cls.typeHandler(repository, value).makeString(value)
    
    def xmlValue(cls, repository, name, value, tag, attrType, attrCard, attrId,
                 attrs, generator, withSchema):

        if name is not None:
            if not isinstance(name, str) and not isinstance(name, unicode):
                attrs['nameType'] = cls.typeName(repository, name)
                attrs['name'] = cls.makeString(repository, name)
            else:
                attrs['name'] = name

        if attrId is not None:
            attrs['id'] = attrId.str64()

        if attrCard == 'single':
            if attrType is not None and attrType.isAlias():
                aliasType = attrType.type(value)
                if aliasType is None:
                    raise TypeError, "%s does not alias type of value '%s' of type %s" %(attrType.itsPath, value, type(value))
                attrType = aliasType
                attrs['typeid'] = attrType._uuid.str64()

            elif withSchema or attrType is None:
                attrType = cls.typeHandler(repository, value)
                attrs['typeid'] = attrType._uuid.str64()

        else:
            attrs['cardinality'] = attrCard

        generator.startElement(tag, attrs)

        if attrCard == 'single':

            from repository.item.Item import Item
            
            if isinstance(value, Item):
                raise TypeError, "item %s cannot be stored as a literal value" %(value.itsPath)

            if value is Item.Nil:
                raise ValueError, 'Cannot persist Item.Nil'

            if attrType is not None:
                if not attrType.recognizes(value):
                    raise TypeError, "value '%s' of type %s is not recognized by type %s" %(value, type(value), attrType.itsPath)
                else:
                    attrType.typeXML(value, generator, withSchema)
            else:
                generator.characters(cls.makeString(repository, value))
            
        elif attrCard == 'list':
            for val in value._itervalues():
                cls.xmlValue(repository,
                             None, val, 'value', attrType, 'single',
                             None, {}, generator, withSchema)

        elif attrCard == 'dict':
            for key, val in value._iteritems():
                cls.xmlValue(repository,
                             key, val, 'value', attrType, 'single',
                             None, {}, generator, withSchema)
        else:
            raise ValueError, attrCard

        generator.endElement(tag)

    typeName = classmethod(typeName)
    typeHandler = classmethod(typeHandler)
    makeString = classmethod(makeString)
    makeValue = classmethod(makeValue)
    xmlValue = classmethod(xmlValue)

    typeDispatch = {
        'str': str,
        'unicode': unicode,
        'uuid': UUID,
        'path': Path,
        'ref': lambda(data): SingleRef(UUID(data)),
        'bool': lambda(data): data != 'False',
        'int': int,
        'long': long,
        'float': float,
        'complex': complex,
        'class': lambda(data): ClassLoader.loadClass(data),
        'none': lambda(data): None,
    }


class ItemsHandler(ContentHandler):

    def __init__(self, repository, parent, afterLoadHooks):

        ContentHandler.__init__(self)

        self.repository = repository
        self.parent = parent
        self.afterLoadHooks = afterLoadHooks

    def startDocument(self):

        self.itemHandler = None
        self.items = []
        
    def startElement(self, tag, attrs):

        if self.exception is None:
            if tag == 'item':
                self.itemHandler = ItemHandler(self.repository, self.parent,
                                               self.afterLoadHooks)
                self.itemHandler.startDocument()

            if self.itemHandler is not None:
                try:
                    self.itemHandler.startElement(tag, attrs)
                except Exception:
                    self.saveException()
                    return

    def characters(self, data):

        if self.exception is None and self.itemHandler is not None:
            self.itemHandler.characters(data)

    def endElement(self, tag):

        if self.exception is None:
            if self.itemHandler is not None:
                try:
                    self.itemHandler.endElement(tag)
                except Exception:
                    self.saveException()
                    return
            
            if tag == 'item':
                item = self.itemHandler.item
                self.items.append(self.itemHandler.item)
                self.itemHandler.endDocument()
                self.itemHandler = None


class MergeHandler(ItemHandler):

    def __init__(self, repository, origItem):

        ItemHandler.__init__(self, repository, None, None)
        self.origItem = origItem
        self.handlerClass = MergeHandler

    def itemEnd(self, itemHandler, attrs):

        item = self.origItem
        values = self.values
        references = self.references

        values._original = item._values
        references._original = item._references

        values._mergeChanges(item._values)
        references._mergeChanges(item._references)

        for key, value in item._references.iteritems():
            if value is not None and value._isRefList():
                references[key] = value

        item._values = values
        item._references = references

        values._item = item
        references._item = item

    def refEnd(self, itemHandler, attrs):

        if self.tags[-1] == 'item':
            attribute = self.attributes.pop()
            cardinality = self.getCardinality(attribute, attrs)
        else:
            return

        if cardinality == 'single':     # cardinality of tag

            if 'uuid' in attrs:         # ref collection
                return
            
            typeName = attrs.get('type')

            if typeName == 'none':
                self.references[attrs['name']] = None
                return

            if typeName == 'uuid':
                uuid = UUID(self.data)
            else:
                raise TypeError, (self.data, typeName)

            name = attrs['name']
            otherName = self.getOtherName(name, self.getAttribute(name), attrs)

            origItem = self.origItem
            origRef = origItem._references.get(name, None)

            if origRef is None:
                itemRef = None
            elif origRef._isItem() and origRef._uuid == uuid:
                itemRef = origRef
            else:
                itemRef = uuid

            self.references[name] = itemRef

    def kindEnd(self, itemHandler, attrs):

        ItemHandler.kindEnd(self, itemHandler, attrs)
        if self.kind is None:
            raise AssertionError, 'no kind'

    def parentEnd(self, itemHandler, attrs):
        pass

    def classEnd(self, itemHandler, attrs):
        pass

    def indexEnd(self, itemHandler, attrs):
        pass

    def _setupRefList(self, name, attribute, readOnly, attrs):
        pass
