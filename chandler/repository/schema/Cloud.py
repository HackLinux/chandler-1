
__revision__  = "$Revision$"
__date__      = "$Date$"
__copyright__ = "Copyright (c) 2004 Open Source Applications Foundation"
__license__   = "http://osafoundation.org/Chandler_0.1_license_terms.htm"

import re

from repository.item.Item import Item
from repository.item.RefCollections import RefList
from repository.item.PersistentCollections import PersistentCollection
from repository.remote.CloudFilter import CloudFilter, EndpointFilter
from repository.remote.CloudFilter import RefHandler
from repository.persistence.RepositoryError import NoSuchItemError


class Cloud(Item):

    def getItems(self, item, cloudAlias, items=None, references=None):
        """
        Gather all items in the cloud from a given item entrypoint.

        Items are found at each endpoint of this cloud and are included into
        the returned result set and the optional C{items} and C{references}
        dictionaries according to the following endpoint policies:

            - C{byValue}: the item is added to the result set and is added
              to the C{items} dictionary.

            - C{byRef}: the item is not added to the result set but is added
              to the C{references} dictionary.

            - C{byCloud}: the item is added to the result set and is used
              as an entrypoint for a cloud gathering operation. The cloud
              used is determined in this order:

                  - the cloud specified on the endpoint

                  - the cloud obtained by the optional C{cloudAlias}

                  - the first cloud specified for the item's kind

              The results of the cloud gathering operation are merged with
              the current one.

            - C{byMethod}: the method named in the endpoint's C{method}
              attribute is invoked on the item with the current C{items}, 
              C{references} and C{cloudAlias} arguments. The method is
              supposed to return a list of items to include into the cloud
              and is supposed to fill the C{items} and C{references}
              dictionaries as this method does.

        @param item: the entrypoint of the cloud.
        @type item: an C{Item} instance
        @param items: an optional dictionary keyed on the item UUIDs that
        also receives all items in the cloud.
        @type items: dict
        @param references: an optional dictionary keyed on the item UUIDs
        that receives all items referenced from an endpoint with a C{byRef}
        include policy.
        @type references: dict
        @param cloudAlias: the optional alias name to use for C{byCloud}
        policy endpoints where the cloud is unspecified.
        @type cloudAlias: a string
        @return: the list of all items considered part of the cloud.
        """

        if not item.isItemOf(self.kind):
            raise TypeError, '%s (Kind: %s) is not of a kind this cloud (%s) understands' %(item.itsPath, item._kind.itsPath, self.itsPath)

        if items is None:
            items = {}
        if references is None:
            references = {}

        if not item._uuid in items:
            items[item._uuid] = item
            results = [item]
        else:
            results = []

        for alias, endpoint, inCloud in self.iterEndpoints(cloudAlias):
            for other in endpoint.iterValues(item):
                if other is not None and other._uuid not in items:
                    results.extend(endpoint.getItems(other, cloudAlias,
                                                     items, references))

        return results

    def copyItems(self, item, name=None, parent=None,
                  copies=None, cloudAlias=None):
        """
        Copy all items in the cloud.

        Items are first gathered as documented in L{getItems}. They are then
        copied as follows:

            - items in the result set returned by L{getItems} are copied and
              added to the result set copy in the order they occur in the
              original result set.

            - references to items in the original result set are copied as
              references to their corresponding copies and are set on the
              item copies everywhere they occur.

            - references to items in the C{references} dictionary upon
              returning from L{getItems}, that is, references to items that
              are not considered part of the cloud but are nonetheless
              referenced by items in it are set unchanged on the item copies
              everywhere they occur.

            - any other item references are not set on the item copies.

        The copy of the cloud entrypoint, C{item}, is first in the results
        list.
        
        @param item: the entry point of the cloud.
        @type item: an C{Item<repository.item.Item.Item>} instance
        @param parent: the optional parent of the copies; by default, each
        copy gets the same parent as the original
        @type parent: an C{Item<repository.item.Item.Item>} instance 
        @param copies: an optional dictionary keyed on the original item
        UUIDs that also received all items copies.
        @type items: dict
        @param cloudAlias: the optional alias name to use for C{byCloud}
        policy endpoints where the cloud is unspecified.
        @type cloudAlias: a string
        @return: the list of all item copies considered part of the cloud.
        """

        items = {}
        references = {}
        copying = self.getItems(item, cloudAlias, items, references)
        
        if copies is None:
            copies = {}

        results = []
        def copyOther(copy, other, policy):
            uuid = other._uuid
            if uuid in items:
                if uuid in copies:
                    return copies[uuid]
                else:
                    other = other.copy(None, parent, copies, 'remove',
                                       None, copyOther)
                    results.append(other)
                    return other
            elif uuid in references:
                return other
            else:
                return None

        copy = item.copy(name, parent, copies, 'remove', None, copyOther)
        results.insert(0, copy)

        for item in copying:
            if item._uuid not in copies:
                results.append(item.copy(None, parent, copies, 'remove',
                                         None, copyOther))
                
        return results

    def getAttributeEndpoints(self, attrName, index=0, cloudAlias=None):

        endpoints = []
        for alias, endpoint, inCloud in self.iterEndpoints(cloudAlias):
            names = endpoint.attribute
            if index < len(names) and names[index] == attrName:
                endpoints.append(endpoint)

        return endpoints

    def writeItems(self, uuid, version, cloudAlias,
                   generator, xml=None, uuids=None):

        if uuids is None:
            uuids = {}
            
        if not uuid in uuids:
            store = self.itsView.store

            uuids[uuid] = uuid
            if xml is None:
                doc = store.loadItem(version, uuid)
                if doc is None:
                    raise NoSuchItemError, (uuid, version)
                
                xml = doc.getContent()

            filter = CloudFilter(self, cloudAlias, store, uuid, version,
                                 generator)
            filter.parse(xml, uuids)

    def iterEndpoints(self, cloudAlias=None):
        """
        Iterate over the endpoints of this cloud.

        If C{cloudAlias} is not C{None}, endpoints are inherited vertically
        by going up the cloud kind's superKind chain and horizontally by
        iterating over the cloud kind's superKinds.

        The iterator yields C{(alias, endpoint, inCloud)} tuples, where:

            - C{alias} is the alias of the endpoint in {cloud}'s
              C{endpoints} ref collection.

            - C{endpoint} is an C{Endpoint<repository.schema.Cloud.Endpoint>}
              instance.

            - C{inCloud} is the cloud C{endpoint} is defined on.

        If an endpoint is aliased in a cloud's endpoints collection,
        endpoints by the same alias are not inherited.
        """

        endpoints = self.getAttributeValue('endpoints', default=None)
        if endpoints is not None:
            for endpoint in endpoints:
                yield (endpoints.getAlias(endpoint), endpoint, self)

        if cloudAlias is not None:
            for superKind in self.kind.superKinds:
                for cloud in superKind.getClouds(cloudAlias):
                    for (alias, endpoint,
                         inCloud) in cloud.iterEndpoints(cloudAlias):
                        if (alias is None or
                            endpoints is None or
                            endpoints.resolveAlias(alias) is None):
                            yield (alias, endpoint, inCloud)

    def getEndpoints(self, alias, cloudAlias=None):
        """
        Get the endpoints for a given alias for this cloud.

        If C{cloudAlias} is not C{None} and this cloud does not define an
        endpoint by this alias, matching endpoints are inherited
        from the cloud kind's superKinds.

        @param alias: the alias of the endpoint(s) sought
        @type alias: a string
        @param cloudAlias: the optional cloud alias to inherit endpoints with
        @type cloudAlias: a string
        """

        if 'endpoints' in self._references:
            endpoint = self.endpoints.getByAlias(alias)
            if endpoint is not None:
                return [endpoint]

        if cloudAlias is not None:
            results = []
            for superKind in self.kind.superKinds:
                for cloud in superKind.getClouds(cloudAlias):
                    results.extend(cloud.getEndpoints(cloudAlias, alias))
            return results

        return []

    def iterEndpointValues(self, item, alias, cloudAlias=None):
        """
        Iterate over the items at the endpoints for the given alias.

        If C{cloudAlias} is not None and this cloud does not define an
        endpoint by this alias, matching endpoints are inherited
        from the cloud kind's superKinds.

        @param alias: the alias of the endpoint(s) sought
        @type alias: a string
        @param cloudAlias: the optional cloud alias to inherit endpoints with
        @type cloudAlias: a string
        """


        if not item.isItemOf(self.kind):
            raise TypeError, '%s (Kind: %s) is not of a kind this cloud (%s) understands' %(item.itsPath, item._kind.itsPath, self.itsPath)

        for endpoint in self.getEndpoints(alias, cloudAlias):
            for other in endpoint.iterValues(item):
                yield other


class Endpoint(Item):

    def getItems(self, item, cloudAlias, items, references):

        policy = self.includePolicy
        results = []

        if policy == 'byValue':
            if not item._uuid in items:
                items[item._uuid] = item
                results.append(item)

        elif policy == 'byRef':
            references[item._uuid] = item

        elif policy == 'byCloud':

            def getItems(cloud):
                results.extend(cloud.getItems(item, cloudAlias,
                                              items, references))

            cloud = self.getAttributeValue('cloud', default=None,
                                           _attrDict=self._references)
            if cloud is not None:
                getItems(cloud)
            else:
                kind = item._kind
                if cloudAlias is None:
                    cloudAlias = self.getAttributeValue('cloudAlias',
                                                        default=None,
                                                        _attrDict=self._values)
                clouds = kind.getClouds(cloudAlias)
                for cloud in clouds:
                    getItems(cloud)

        elif policy == 'byMethod':
            method = self.getAttributeValue('method', default=None,
                                            _attrDict=self._values)
            if method is not None:
                results.extend(getattr(item, method)(items, references,
                                                     cloudAlias))

        else:
            raise NotImplementedError, policy

        return results

    def writeItems(self, index, uuid, version, cloudAlias,
                   generator, xml, uuids):

        names = self.attribute

        if index == len(names):
            if not uuid in uuids:
                policy = self.includePolicy

                if policy == 'byValue':
                    filter = EndpointFilter(self, self.itsView.store,
                                            uuid, version, generator)
                    filter.parse(xml)
                    uuids[uuid] = uuid

                elif policy == 'byCloud':
                    cloud = self.getAttributeValue('cloud', default=None,
                                                   _attrDict=self._references)
                    if cloud is None:
                        match = self.kindExp.match(xml, xml.index("<kind "))
                        kind = self.itsView[UUID(match.group(1))]
                        cloud = kind.getClouds(cloudAlias)
                        if not cloud:
                            raise TypeError, 'No cloud for %s' %(kind.itsPath)
                        cloud = cloud[0]

                    cloud.writeItems(uuid, version, cloudAlias,
                                     generator, xml, uuids)

                else:
                    raise NotImplementedError, policy

        else:
            handler = RefHandler(self, names[index], uuid, version)
            handler.parse(xml)

            if handler.values is not None:
                store = self.itsView.store
                for uuid in handler.values:
                    doc = store.loadItem(version, uuid)
                    if doc is None:
                        raise NoSuchItemError, (uuid, version)
                    xml = doc.getContent()
                    self.writeItems(index + 1, uuid, version, cloudAlias,
                                    generator, xml, uuids)

    def iterValues(self, item):

        def append(values, value):
            if value is not None:
                if isinstance(value, Item) or isinstance(value, RefList):
                    values.append(value)
                elif isinstance(value, PersistentCollection):
                    values.append(value._getItems())
                else:
                    raise TypeError, type(value)

        value = item
        for name in self.attribute:
            if isinstance(value, PersistentCollection):
                values = []
                for v in value._getItems():
                    append(values, v.getAttributeValue(name, default=None))
                value = values
            elif isinstance(value, RefList):
                values = []
                for v in value:
                    append(values, v.getAttributeValue(name, default=None))
                value = values
            elif isinstance(value, list):
                values = []
                for v in value:
                    if isinstance(v, Item):
                        append(values, v.getAttributeValue(name, default=None))
                    else:
                        for i in v:
                            append(values, i.getAttributeValue(name, default=None))
                value = values
            else:
                value = value.getAttributeValue(name, default=None)
                if value is None:
                    break
                if not (isinstance(value, Item) or
                        isinstance(value, RefList) or
                        isinstance(value, PersistentCollection)):
                    raise TypeError, type(value)

        if value is None:
            return []

        if isinstance(value, Item):
            return [value]

        return value


    kindExp = re.compile('<kind type="uuid">(.*)</kind>')
