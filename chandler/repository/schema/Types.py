
__revision__  = "$Revision$"
__date__      = "$Date$"
__copyright__ = "Copyright (c) 2003-2004 Open Source Applications Foundation"
__license__   = "http://osafoundation.org/Chandler_0.1_license_terms.htm"

import mx.DateTime

import chandlerdb.util.UUID
import repository.util.Path
import repository.util.SingleRef
import repository.util.URL

from new import classobj

from repository.item.Item import Item
from repository.schema.TypeHandler import TypeHandler
from repository.item.ItemHandler import ValueHandler
from repository.item.PersistentCollections import PersistentList
from repository.item.PersistentCollections import PersistentDict
from repository.item.Query import KindQuery
from repository.schema.Kind import Kind
from repository.util.ClassLoader import ClassLoader


class TypeKind(Kind):

    def _fillItem(self, name, parent, kind, **kwds):

        super(TypeKind, self)._fillItem(name, parent, kind, **kwds)

        typeHandlers = TypeHandler.typeHandlers[self.itsView]
        typeHandlers[None] = self

    def findTypes(self, value):
        """Return a list of types recognizing value.

        The list is sorted by order of 'relevance', a very subjective concept
        that is specific to the category of matching types.
        For example, Integer < Long < Float or String < Symbol."""

        matches = [i for i in KindQuery().run([self]) if i.recognizes(value)]
        if matches:
            matches.sort(lambda x, y: x._compareTypes(y))

        return matches


class Type(Item):

    def __init__(self, name, parent, kind):

        super(Type, self).__init__(name, parent, kind)
        self._status |= Item.SCHEMA | Item.PINNED
        
    def _fillItem(self, name, parent, kind, **kwds):

        super(Type, self)._fillItem(name, parent, kind, **kwds)
        self._status |= Item.SCHEMA | Item.PINNED

    def _registerTypeHandler(self, implementationType):

        if implementationType is not None:
            try:
                typeHandlers = TypeHandler.typeHandlers[self.itsView]
            except KeyError:
                typeHandlers = TypeHandler.typeHandlers[self.itsView] = {}

            if implementationType in typeHandlers:
                typeHandlers[implementationType].append(self)
            else:
                typeHandlers[implementationType] = [ self ]

    def onItemLoad(self, view):
        self._registerTypeHandler(self.getImplementationType())

    def getImplementationType(self):
        return self.implementationTypes['python']

    def handlerName(self):
        return None

    def makeValue(self, data):
        raise NotImplementedError, "%s.makeValue()" %(type(self))

    def makeString(self, value):
        return str(value)

    def recognizes(self, value):
        return type(value) is self.getImplementationType()

    def eval(self, value):
        return value

    # override this to compare types of the same category, like
    # Integer, Long and Float or String and Symbol
    # in order of 'relevance' for findTypes
    def _compareTypes(self, other):
        return 0

    def isAlias(self):
        return False

    def typeXML(self, value, generator, withSchema):
        generator.characters(self.makeString(value))

    def startValue(self, itemHandler):
        pass

    def isValueReady(self, itemHandler):
        return True

    def getParsedValue(self, itemHandler, data):
        return self.makeValue(data)

    def writeValue(self, itemWriter, buffer, item, value, withSchema):
        raise NotImplementedError, "%s._writeValue" %(type(self))

    def readValue(self, itemReader, offset, data, withSchema, view, name):
        raise NotImplementedError, "%s._readValue" %(type(self))

    NoneString = "__NONE__"


class String(Type):

    def _fillItem(self, name, parent, kind, **kwds):

        super(String, self)._fillItem(name, parent, kind, **kwds)
        self._registerTypeHandler(str)

    def getImplementationType(self):

        return unicode

    def handlerName(self):

        return 'unicode'

    def makeValue(self, data):

        if isinstance(data, unicode):
            return data

        return unicode(data, 'utf-8')

    def makeString(self, value):

        return value

    def recognizes(self, value):

        return type(value) in (unicode, str)

    def typeXML(self, value, generator, withSchema):

        generator.cdataSection(value)

    def _compareTypes(self, other):

        return -1

    def writeValue(self, itemWriter, buffer, item, value, withSchema):

        itemWriter.writeString(buffer, value)

    def readValue(self, itemReader, offset, data, withSchema, view, name):
        
        return itemReader.readString(offset, data)


class Symbol(Type):

    def getImplementationType(self):

        return str

    def handlerName(self):

        return 'str'

    def makeValue(self, data):

        return str(data)

    def _compareTypes(self, other):

        return 1

    def recognizes(self, value):

        if type(value) not in (str, unicode):
            return False
        
        for char in value:
            if not (char == '_' or
                    char >= '0' and char <= '9' or
                    char >= 'A' and char <= 'Z' or
                    char >= 'a' and char <= 'z'):
                return False

        return True

    def writeValue(self, itemWriter, buffer, item, value, withSchema):

        itemWriter.writeSymbol(buffer, value)

    def readValue(self, itemReader, offset, data, withSchema, view, name):
        
        return itemReader.readSymbol(offset, data)


class Integer(Type):

    def getImplementationType(self):
        return int
    
    def handlerName(self):
        return 'int'

    def makeValue(self, data):
        return int(data)

    def _compareTypes(self, other):
        return -1

    def writeValue(self, itemWriter, buffer, item, value, withSchema):
        itemWriter.writeInteger(buffer, value)

    def readValue(self, itemReader, offset, data, withSchema, view, name):
        return itemReader.readInteger(offset, data)


class Long(Type):

    def getImplementationType(self):
        return long
    
    def handlerName(self):
        return 'long'

    def makeValue(self, data):
        return long(data)

    def recognizes(self, value):
        return type(value) in (long, int)

    def _compareTypes(self, other):
        if other._name == 'Integer':
            return 1
        if other._name == 'Float':
            return -1
        return 0

    def writeValue(self, itemWriter, buffer, item, value, withSchema):
        itemWriter.writeLong(buffer, value)

    def readValue(self, itemReader, offset, data, withSchema, view, name):
        return itemReader.readLong(offset, data)


class Float(Type):

    def getImplementationType(self):
        return float
    
    def handlerName(self):
        return 'float'
    
    def makeValue(self, data):
        return float(data)

    def recognizes(self, value):
        return type(value) in (float, long, int)

    def _compareTypes(self, other):
        return 1

    def writeValue(self, itemWriter, buffer, item, value, withSchema):
        itemWriter.writeFloat(buffer, value)

    def readValue(self, itemReader, offset, data, withSchema, view, name):
        return itemReader.readFloat(offset, data)

    
class Complex(Type):

    def getImplementationType(self):
        return complex
    
    def handlerName(self):
        return 'complex'

    def makeValue(self, data):
        return complex(data[1:-1])

    def writeValue(self, itemWriter, buffer, item, value, withSchema):

        itemWriter.writeFloat(buffer, value.real)
        itemWriter.writeFloat(buffer, value.imag)

    def readValue(self, itemReader, offset, data, withSchema, view, name):

        offset, real = itemReader.readFloat(offset, data)
        offset, imag = itemReader.readFloat(offset, data)

        return offset, complex(real, imag)
        

class Boolean(Type):

    def getImplementationType(self):
        return bool
    
    def handlerName(self):
        return 'bool'
    
    def makeValue(self, data):

        if data in ('True', 'true'):
            return True
        elif data in ('False', 'false'):
            return False
        else:
            raise ValueError, "'%s' is not 'T|true' or 'F|false'" %(data)

    def writeValue(self, itemWriter, buffer, item, value, withSchema):

        itemWriter.writeBoolean(buffer, value)

    def readValue(self, itemReader, offset, data, withSchema, view, name):

        return itemReader.readBoolean(offset, data)


class UUID(Type):

    def handlerName(self):

        return 'uuid'

    def makeValue(self, data):

        if data == Type.NoneString:
            return None

        return chandlerdb.util.UUID.UUID(data)

    def makeString(self, value):

        if value is None:
            return Type.NoneString
        
        return value.str64()
    
    def recognizes(self, value):

        return value is None or type(value) is chandlerdb.util.UUID.UUID

    def eval(self, value):

        return self.itsView[value]

    def _compareTypes(self, other):

        if other._name == 'None':
            return 1
        elif self._name < other._name:
            return -1
        elif self._name > other._name:
            return 1

        return 0

    def writeValue(self, itemWriter, buffer, item, value, withSchema):

        if value is None:
            buffer.write('\0')
        else:
            buffer.write('\1')
            buffer.write(value._uuid)

    def readValue(self, itemReader, offset, data, withSchema, view, name):

        if data[offset] == '\0':
            return offset+1, None
        
        return offset+17, chandlerdb.util.UUID.UUID(data[offset+1:offset+17])


class SingleRef(Type):

    def handlerName(self):

        return 'ref'
    
    def makeValue(self, data):

        if data == Type.NoneString:
            return None
        
        uuid = chandlerdb.util.UUID.UUID(data)
        return repository.util.SingleRef.SingleRef(uuid)

    def makeString(self, value):

        if value is None:
            return Type.NoneString
        
        return str(value)
    
    def recognizes(self, value):

        return (value is None or
                type(value) is repository.util.SingleRef.SingleRef or
                isinstance(value, Item))

    def eval(self, value):

        return self.itsView[value.itsUUID]

    def _compareTypes(self, other):

        if other._name == 'None':
            return 1
        elif self._name < other._name:
            return -1
        elif self._name > other._name:
            return 1

        return 0

    def writeValue(self, itemWriter, buffer, item, value, withSchema):

        if value is None:
            buffer.write('\0')
        else:
            buffer.write('\1')
            buffer.write(value._uuid._uuid)

    def readValue(self, itemReader, offset, data, withSchema, view, name):

        if data[offset] == '\0':
            return offset+1, None
        
        uuid = chandlerdb.util.UUID.UUID(data[offset+1:offset+17])
        return offset+17, repository.util.SingleRef.SingleRef(uuid)


class Path(Type):

    def handlerName(self):

        return 'path'

    def makeValue(self, data):

        if data == Type.NoneString:
            return None

        return repository.util.Path.Path(data)

    def makeString(self, value):

        if value is None:
            return Type.NoneString
        
        return str(value)
    
    def recognizes(self, value):

        return value is None or type(value) is repository.util.Path.Path

    def eval(self, value):

        item = self.findPath(value)
        if item is None:
            raise ValueError, 'Path %s evaluated to None' %(value)

        return item

    def _compareTypes(self, other):

        if other._name == 'None':
            return 1
        elif self._name < other._name:
            return -1
        elif self._name > other._name:
            return 1

        return 0

    def writeValue(self, itemWriter, buffer, item, value, withSchema):

        if value is None:
            buffer.write('\0')
        else:
            buffer.write('\1')
            itemWriter.writeString(buffer, str(value))

    def readValue(self, itemReader, offset, data, withSchema, view, name):

        if data[offset] == '\0':
            return offset+1, None
        
        offset, string = itemReader.readString(offset, data)
        return offset, repository.util.Path.Path(string)


class URL(Type):

    def handlerName(self):

        return 'url'

    def makeValue(self, data):

        if data == Type.NoneString:
            return None

        return repository.util.URL.URL(data)

    def makeString(self, value):

        if value is None:
            return Type.NoneString
        
        return str(value)
    
    def recognizes(self, value):

        return value is None or type(value) is repository.util.URL.URL

    def _compareTypes(self, other):

        return -1

    def writeValue(self, itemWriter, buffer, item, value, withSchema):

        if value is None:
            buffer.write('\0')
        else:
            buffer.write('\1')
            itemWriter.writeString(buffer, str(value))

    def readValue(self, itemReader, offset, data, withSchema, view, name):

        if data[offset] == '\0':
            return offset+1, None
        
        offset, string = itemReader.readString(offset, data)
        return offset, repository.util.URL.URL(string)


class NoneType(Type):

    def getImplementationType(self):
        return type(None)

    def handlerName(self):
        return 'none'
    
    def makeValue(self, data):
        return None

    def makeString(self, value):
        return Type.NoneString

    def recognizes(self, value):
        return value is None

    def _compareTypes(self, other):
        return -1

    def writeValue(self, itemWriter, buffer, item, value, withSchema):
        buffer.write('\0')

    def readValue(self, itemReader, offset, data, withSchema, view, name):
        if data[offset] != '\0':
            raise AssertionError, 'invalid byte for None'
        return offset+1, None


class Class(Type):

    def getImplementationType(self):
        return type

    def recognizes(self, value):
        return type(value) in (type, classobj)

    def handlerName(self):
        return 'class'
    
    def makeValue(self, data):
        return ClassLoader.loadClass(data)

    def makeString(self, value):
        return "%s.%s" %(value.__module__, value.__name__)

    def writeValue(self, itemWriter, buffer, item, value, withSchema):
        itemWriter.writeString(buffer, self.makeString(value))

    def readValue(self, itemReader, offset, data, withSchema, view, name):
        offset, string = itemReader.readString(offset, data)
        return offset, ClassLoader.loadClass(string)
        

class Enumeration(Type):

    def getImplementationType(self):
        return type(self)

    def handlerName(self):
        return 'str'
    
    def makeValue(self, data):
        return data

    def makeString(self, value):
        return value

    def recognizes(self, value):

        try:
            return self.values.index(value) >= 0
        except ValueError:
            return False

    def writeValue(self, itemWriter, buffer, item, value, withSchema):

        if withSchema:
            itemWriter.writeString(buffer, value)
        else:
            itemWriter.writeInteger(buffer, self.values.index(value))

    def readValue(self, itemReader, offset, data, withSchema, view, name):
        
        if withSchema:
            return itemReader.readString(offset, data)
        else:
            offset, integer = itemReader.readInteger(offset, data)
            return offset, self.values[integer]


class Struct(Type):

    def getDefaultValue(self, fieldName):
        return Item.Nil

    def getFieldValue(self, value, fieldName, default):
        return getattr(value, fieldName, default)

    def startValue(self, itemHandler):
        itemHandler.tagCounts.append(0)

    def isValueReady(self, itemHandler):
        return itemHandler.tagCounts[-1] == 0

    def typeXML(self, value, generator, withSchema):

        fields = self.getAttributeValue('fields', _attrDict=self._values,
                                        default={})

        if fields:
            repository = self.itsView
            generator.startElement('fields', {})
            for fieldName, field in fields.iteritems():
                self._fieldXML(repository, value, fieldName, field, generator)
            generator.endElement('fields')
        else:
            raise TypeError, 'Struct %s has no fields' %(self.itsPath)
    
    def _fieldXML(self, repository, value, fieldName, field, generator):

        fieldValue = getattr(value, fieldName, Item.Nil)

        if fieldValue is not Item.Nil:
            typeHandler = field.get('type', None)

            if typeHandler is None:
                typeHandler = TypeHandler.typeHandler(repository, fieldValue)

            attrs = { 'name': fieldName, 'typeid': typeHandler._uuid.str64() }
            generator.startElement('field', attrs)
            generator.characters(typeHandler.makeString(fieldValue))
            generator.endElement('field')

    def fieldsStart(self, itemHandler, attrs):

        itemHandler.tagCounts[-1] += 1
        itemHandler.fields = {}

    def fieldsEnd(self, itemHandler, attrs):

        itemHandler.tagCounts[-1] -= 1

    def fieldEnd(self, itemHandler, attrs):

        name = attrs['name']

        if attrs.has_key('typeid'):
            typeHandler = itemHandler.repository[chandlerdb.util.UUID.UUID(attrs['typeid'])]
            value = typeHandler.makeValue(itemHandler.data)
        elif attrs.has_key('type'):
            value = itemHandler.makeValue(attrs['type'], itemHandler.data)
        else:
            value = itemHandler.data
            field = self.fields[name]
            typeHandler = field.get('type', None)
            if typeHandler is not None:
                value = typeHandler.makeValue(value)

        itemHandler.fields[name] = value

    def recognizes(self, value):

        if super(Struct, self).recognizes(value):
            for fieldName, field in self.fields.iteritems():
                typeHandler = field.get('type', None)
                if typeHandler is not None:
                    fieldValue = getattr(value, fieldName, Item.Nil)
                    if not (fieldValue is Item.Nil or
                            typeHandler.recognizes(fieldValue)):
                        return False
            return True

        return False

    def getParsedValue(self, itemHandler, data):

        fields = itemHandler.fields
        
        if fields is None:
            return self.makeValue(data)

        else:
            result = self.getImplementationType()()
            for fieldName, value in fields.iteritems():
                setattr(result, fieldName, value)

            return result

    def makeValue(self, data):

        result = self.getImplementationType()()
        if data:
            for pair in data.split(','):
                fieldName, value = pair.split(':')
                typeHandler = self.fields[fieldName].get('type', None)
                if typeHandler is not None:
                    value = typeHandler.makeValue(value)
                setattr(result, fieldName, value)

        return result

    def makeString(self, value):

        strings = []
        for fieldName, field in self.fields.iteritems():
            fieldValue = getattr(value, fieldName, Item.Nil)
            if fieldValue is not Item.Nil:
                strings.append("%s:%s" %(fieldName, fieldValue))

        return ",".join(strings)

    def writeValue(self, itemWriter, buffer, item, value, withSchema):

        fields = self.getAttributeValue('fields',
                                        _attrDict=self._values,
                                        default={})

        for fieldName, field in fields.iteritems():
            default = self.getDefaultValue(fieldName) 
            fieldValue = self.getFieldValue(value, fieldName, default)
            if fieldValue == default:
                continue
            
            fieldType = field.get('type', None)
            itemWriter.writeSymbol(buffer, fieldName)
            itemWriter.writeValue(buffer, item, fieldValue,
                                  withSchema, fieldType)

        itemWriter.writeSymbol(buffer, '')

    def readValue(self, itemReader, offset, data, withSchema, view, name):

        fields = self.getAttributeValue('fields', _attrDict=self._values,
                                        default=None)

        value = self.getImplementationType()()
        while True:
            offset, fieldName = itemReader.readSymbol(offset, data)
            if fieldName != '':
                fieldType = fields[fieldName].get('type', None)
                offset, fieldValue = itemReader.readValue(offset, data,
                                                          withSchema, fieldType,
                                                          view, name)
                setattr(value, fieldName, fieldValue)
            else:
                return offset, value


class MXType(Struct):

    def recognizes(self, value):
        return type(value) is self.getImplementationType()

    def getParsedValue(self, itemHandler, data):

        flds = itemHandler.fields
        if flds is None:
            return self.makeValue(data)
        else:
            itemHandler.fields = None
        
        return self._valueFromFields(flds)

    def readValue(self, itemReader, offset, data, withSchema, view, name):

        fields = self.getAttributeValue('fields', _attrDict=self._values,
                                        default=None)

        flds = {}
        while True:
            offset, fieldName = itemReader.readSymbol(offset, data)
            if fieldName != '':
                fieldType = fields[fieldName].get('type', None)
                offset, fieldValue = itemReader.readValue(offset, data,
                                                          withSchema, fieldType,
                                                          view, name)
                flds[fieldName] = fieldValue
            else:
                break

        return offset, self._valueFromFields(flds)
    

class DateTime(MXType):

    def getImplementationType(self):
        return DateTime.implementationType

    def makeValue(self, data):
        return mx.DateTime.ISO.ParseDateTime(data)
        
    def makeString(self, value):
        return mx.DateTime.ISO.str(value)

    def _valueFromFields(self, flds):
        return mx.DateTime.DateTime(flds['year'],
                                    flds['month'],
                                    flds['day'],
                                    flds['hour'],
                                    flds['minute'],
                                    flds['second'])        

    implementationType = type(mx.DateTime.now())


class DateTimeDelta(MXType):

    defaults = { 'day': 0.0, 'hour': 0.0, 'minute': 0.0, 'second': 0.0 }

    def getDefaultValue(self, fieldName):
        return DateTimeDelta.defaults[fieldName]

    def getImplementationType(self):
        return DateTimeDelta.implementationType

    def makeValue(self, data):
        return mx.DateTime.DateTimeDeltaFrom(str(data))
        
    def makeString(self, value):
        return str(value)

    def _fieldXML(self, repository, value, fieldName, field, generator):

        default = self.getDefaultValue(fieldName)
        fieldValue = self.getFieldValue(value, fieldName, default)
        if default != fieldValue:
            super(DateTimeDelta, self)._fieldXML(repository, value,
                                                 fieldName, field, generator)

    def _valueFromFields(self, flds):

        return mx.DateTime.DateTimeDeltaFrom(days=flds.get('day', 0.0),
                                             hours=flds.get('hour', 0.0),
                                             minutes=flds.get('minute', 0.0),
                                             seconds=flds.get('second', 0.0))
          
    implementationType = type(mx.DateTime.DateTimeDelta(0))
    

class RelativeDateTime(MXType):

    defaults = { 'years': 0, 'months': 0, 'days': 0,
                 'year': None, 'month': None, 'day': None,
                 'hours': 0, 'minutes': 0, 'seconds': 0,
                 'hour': None, 'minute': None, 'second': None,
                 'weekday': None, 'weeks': 0 }

    def getDefaultValue(self, fieldName):
        return RelativeDateTime.defaults[fieldName]

    def getImplementationType(self):
        return RelativeDateTime.implementationType

    def makeValue(self, data):
        return mx.DateTime.RelativeDateTimeFrom(str(data))

    def makeString(self, value):
        return str(value)

    def _fieldXML(self, repository, value, fieldName, field, generator):

        default = self.getDefaultValue(fieldName)
        fieldValue = self.getFieldValue(value, fieldName, default)
        if default != fieldValue:
            super(RelativeDateTime, self)._fieldXML(repository, value,
                                                    fieldName, field,
                                                    generator)

    def _valueFromFields(self, flds):

        return mx.DateTime.RelativeDateTime(years=flds.get('years', 0),
                                            months=flds.get('months', 0),
                                            days=flds.get('days', 0),
                                            year=flds.get('year', None),
                                            month=flds.get('month', None),
                                            day=flds.get('day', None),
                                            hours=flds.get('hours', 0),
                                            minutes=flds.get('minutes', 0),
                                            seconds=flds.get('seconds', 0),
                                            hour=flds.get('hour', None),
                                            minute=flds.get('minute', None),
                                            second=flds.get('second', None),
                                            weekday=flds.get('weekday', None),
                                            weeks=flds.get('weeks', 0))
          
    implementationType = type(mx.DateTime.RelativeDateTime())


class Collection(Type):

    def getParsedValue(self, itemHandler, data):

        itemHandler.tagCounts.pop()
        itemHandler.attributes.pop()
        return itemHandler.collections.pop()

    def startValue(self, itemHandler):

        itemHandler.tagCounts.append(0)
        itemHandler.attributes.append(None)
        itemHandler.collections.append(self._empty())

    def isValueReady(self, itemHandler):

        return itemHandler.tagCounts[-1] == 0

    def valuesStart(self, itemHandler, attrs):

        itemHandler.tagCounts[-1] += 1

    def valuesEnd(self, itemHandler, attrs):

        itemHandler.tagCounts[-1] -= 1

    def valueStart(self, itemHandler, attrs):

        itemHandler.tagCounts[-1] += 1
        itemHandler.valueStart(itemHandler, attrs)

    def valueEnd(self, itemHandler, attrs, **kwds):

        itemHandler.tagCounts[-1] -= 1
        itemHandler.valueEnd(itemHandler, attrs, **kwds)


class Dictionary(Collection):

    def handlerName(self):

        return 'dict'

    def recognizes(self, value):

        return isinstance(value, dict)

    def typeXML(self, value, generator, withSchema):

        repository = self.itsView

        generator.startElement('values', {})
        for key, val in value._iteritems():
            ValueHandler.xmlValue(repository,
                                  key, val, 'value', None, 'single', None, {},
                                  generator, withSchema)
        generator.endElement('values')

    def makeValue(self, data):
        """
        Make a dict of string key/value pairs from comma separated pairs.

        The implementation is very cheap, using split, so spaces are part of
        the dict's elements and the strings cannot contain spaces or colons.
        """

        result = {}
        if data:
            for pair in data.split(','):
                key, value = pair.split(':')
                result[key] = value

        return result

    def makeString(self, value):

        return ",".join(["%s:%s" %(k, v) for k, v in value.iteritems()])

    def _empty(self):

        return PersistentDict(None, None, None)

    def writeValue(self, itemWriter, buffer, item, value, withSchema):

        itemWriter.writeDict(buffer, item, value, withSchema, None)

    def readValue(self, itemReader, offset, data, withSchema, view, name):

        return itemReader.readDict(offset, data, withSchema, None, view, name)
    

class List(Collection):

    def handlerName(self):

        return 'list'

    def recognizes(self, value):

        return isinstance(value, list)

    def typeXML(self, value, generator, withSchema):

        repository = self.itsView

        generator.startElement('values', {})
        for val in value._itervalues():
            ValueHandler.xmlValue(repository,
                                  None, val, 'value', None, 'single', None, {},
                                  generator, withSchema)
        generator.endElement('values')

    def makeValue(self, data):
        """
        Make a list of strings from comma separated strings.

        The implementation is very cheap, using split, so spaces are part of
        the list's elements and the strings cannot contain spaces.
        """

        if data:
            return data.split(',')
        else:
            return []

    def makeString(self, value):

        return ",".join([str(v) for v in value])

    def _empty(self):

        return PersistentList(None, None, None)

    def writeValue(self, itemWriter, buffer, item, value, withSchema):

        itemWriter.writeList(buffer, item, value, withSchema, None)

    def readValue(self, itemReader, offset, data, withSchema, view, name):

        return itemReader.readList(offset, data, withSchema, None, view, name)


class Tuple(Collection):

    def getImplementationType(self):

        return tuple

    def handlerName(self):

        return 'tuple'

    def recognizes(self, value):

        return isinstance(value, tuple)

    def typeXML(self, value, generator, withSchema):

        repository = self.itsView

        generator.startElement('values', {})
        for val in value:
            ValueHandler.xmlValue(repository,
                                  None, val, 'value', None, 'single', None, {},
                                  generator, withSchema)
        generator.endElement('values')

    def makeValue(self, data):
        """
        Make a tuple of strings from comma separated strings.

        The implementation is very cheap, using split, so spaces are part of
        the tuple's elements and the strings cannot contain spaces.
        """

        if data:
            return tuple(data.split(','))
        else:
            return ()

    def makeString(self, value):

        return ",".join([str(v) for v in value])

    def _empty(self):

        class _tuple(list):
            def append(self, value, setDirty=True):
                super(_tuple, self).append(value)

        return _tuple()

    def getParsedValue(self, itemHandler, data):

        return tuple(super(Tuple, self).getParsedValue(itemHandler, data))

    def writeValue(self, itemWriter, buffer, item, value, withSchema):

        itemWriter.writeList(buffer, item, value, withSchema, None)

    def readValue(self, itemReader, offset, data, withSchema, view, name):

        offset, value = itemReader.readList(offset, data, withSchema,
                                            None, view, name)
        return offset, tuple(value)


class Lob(Type):

    def getImplementationType(self):

        return self.itsView._getLobType()

    def getParsedValue(self, itemHandler, data):

        value = itemHandler.value
        itemHandler.value = None
        itemHandler.tagCounts.pop()

        return value

    def makeValue(self, data,
                  encoding=None, mimetype='text/plain', compression='bz2',
                  encryption=None, key=None, indexed=False):

        if data and not encoding and type(data) is unicode:
            encoding = 'utf-8'

        lob = self.getImplementationType()(self.itsView,
                                           encoding, mimetype, indexed)

        if data:
            if encoding:
                out = lob.getWriter(compression, encryption, key)
            else:
                out = lob.getOutputStream(compression, encryption, key)
            out.write(data)
            out.close()

        return lob
    
    def startValue(self, itemHandler):

        itemHandler.tagCounts.append(0)
        itemHandler.value = self.getImplementationType()(self.itsView)

    def isValueReady(self, itemHandler):

        return itemHandler.tagCounts[-1] == 0

    def typeXML(self, value, generator, withSchema):

        value._xmlValue(generator)

    def writeValue(self, itemWriter, buffer, item, value, withSchema):

        value._writeValue(itemWriter, buffer, withSchema)

    def readValue(self, itemReader, offset, data, withSchema, view, name):

        value = self.getImplementationType()(self.itsView)
        return value._readValue(itemReader, offset, data, withSchema)

    def lobStart(self, itemHandler, attrs):

        itemHandler.tagCounts[-1] += 1

    def lobEnd(self, itemHandler, attrs):

        itemHandler.value.load(itemHandler.data, attrs)
        itemHandler.tagCounts[-1] -= 1

    def handlerName(self):

        return 'lob'
