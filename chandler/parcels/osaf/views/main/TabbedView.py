__version__ = "$Revision$"
__date__ = "$Date$"
__copyright__ = "Copyright (c) 2003 Open Source Applications Foundation"
__license__ = "http://osafoundation.org/Chandler_0.1_license_terms.htm"

import application.Globals as Globals
import OSAF.framework.blocks.ControlBlocks as ControlBlocks
from OSAF.framework.blocks.Node import Node as Node
from OSAF.framework.blocks.Block import Block as Block
from repository.util.UUID import UUID

class TabbedView(ControlBlocks.TabbedContainer):
    def renderOneBlock (self, parent, parentWindow):
        try:
            self.tabTitles
        except AttributeError:
            self.tabTitles = self.tabNames
        self.activeTab = -1
        return ControlBlocks.TabbedContainer.renderOneBlock(self, parent, parentWindow)

    def OnSelectionChangedEvent(self, notification):
        node = notification.data['item']
        if node and isinstance(node, Node):
            newChild = node.item
            if isinstance(newChild, Block):
                try:
                    tabbedContainer = Globals.association [self.itsUUID]
                except KeyError:
                    return  # tabbed container hasn't been rendered yet
                self.activeTab = tabbedContainer.GetSelection()
                self.tabTitles[self.activeTab] = self.getUniqueName(node.getItemDisplayName())
                page = tabbedContainer.GetPage(self.activeTab)
                tabbedContainer.RemovePage(self.activeTab)
                self.UnregisterEvents(page)
                item = Globals.repository.find(page.counterpartUUID)
                item.parentBlock = None
                page.Destroy()

                newChild.parentBlock = self
                newChild.render(tabbedContainer, tabbedContainer)
                
                wxNewChild = Globals.association [newChild.itsUUID]
                wxNewChild.SetSize (tabbedContainer.GetClientSize())
                
                self.RegisterEvents(newChild)
                Globals.mainView.onSetActiveView(newChild)

    def addToContainer(self, parent, child, weight, flag, border, append=True):
        if self.activeTab == -1:
            parent.AddPage(child, self.tabTitles[self.tabIndex])
            self.tabIndex += 1
        else:
            parent.InsertPage(self.activeTab, child, self.tabTitles[self.activeTab], True)

    def OnNewTabEvent (self, notification):
        tabbedContainer = Globals.association[self.itsUUID]
        kind = Globals.repository.find("parcels/OSAF/framework/blocks/HTML")
        self.activeTab = tabbedContainer.GetPageCount()
        self.tabTitles.append(self.getUniqueName("untitled"))
        
        item = kind.newItem(self.tabTitles[self.activeTab], self)
        item.url = ""
        item.parentBlock = self
        (page, parent, parentWindow) = item.render(tabbedContainer, tabbedContainer)

    def OnCloseTabEvent (self, notification):
        tabbedContainer = Globals.association[self.itsUUID]
        selection = tabbedContainer.GetSelection()
        self.tabTitles.remove(self.tabTitles[selection])
        page = tabbedContainer.GetPage(selection)
        tabbedContainer.RemovePage(selection)
        self.UnregisterEvents(page)
        item = Globals.repository.find(page.counterpartUUID)
        item.parentBlock = None
        page.Destroy()
                    
#    def OnSelectionChanging(self, event):
#        tabbedContainer = Globals.association [self.itsUUID]
#        page = tabbedContainer.GetPage(tabbedContainer.GetSelection())
#        self.UnregisterEvents(page)
#        event.Skip()
        
#    def OnSelectionChanged(self, event):
#        tabbedContainer = Globals.association [self.itsUUID]
#        page = tabbedContainer.GetPage(tabbedContainer.GetSelection())
#        self.RegisterEvents(page)
#        Globals.mainView.onSetActiveView(page)
#        event.Skip()
            
    def RegisterEvents(self, block):
        try:
            events = block.blockEvents
        except AttributeError:
            return
        self.currentId = UUID()
        Globals.notificationManager.Subscribe(events, 
                                              self.currentId, 
                                              Globals.mainView.dispatchEvent)
 
    def UnregisterEvents(self, oldBlock):
        try:
            events = oldBlock.blockEvents
        except AttributeError:
            return
        try:
            id = self.currentId
        except AttributeError:
            return # If we haven't registered yet
        Globals.notificationManager.Unsubscribe(id)
        
    def getUniqueName (self, name):
        if not self.hasChild(name):
            return name
        number = 1
        while self.hasChild(name + str(number)):
            number += 1
        return name + str(number)

        