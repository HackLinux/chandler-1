__version__ = "$Revision$"
__date__ = "$Date$"
__copyright__ = "Copyright (c) 2003-2005 Open Source Applications Foundation"
__license__ = "http://osafoundation.org/Chandler_0.1_license_terms.htm"

from Block import Block, RectangularChild, wxRectangularChild
from DragAndDrop import DropReceiveWidget as DropReceiveWidget
from DynamicContainerBlocks import Toolbar as Toolbar
from Styles import Font
from chandlerdb.util.UUID import UUID
from repository.item.Item import Item
from osaf.contentmodel.ItemCollection import ItemCollection
import wx
import time


class wxBoxContainer (wxRectangularChild):
    def wxSynchronizeWidget(self, *arguments, **keywords):
        super (wxBoxContainer, self).wxSynchronizeWidget (*arguments, **keywords)
        
        if self.blockItem.isShown:
            sizer = self.GetSizer()
            if not sizer:
                sizer = wx.BoxSizer ({'Horizontal': wx.HORIZONTAL,
                                    'Vertical': wx.VERTICAL} [self.blockItem.orientationEnum])
            self.SetSizer (sizer)
            sizer.Clear()
            for childBlock in self.blockItem.childrenBlocks:
                if childBlock.isShown and isinstance (childBlock, RectangularChild):
                    sizer.Add (childBlock.widget,
                               childBlock.stretchFactor, 
                               wxRectangularChild.CalculateWXFlag(childBlock), 
                               wxRectangularChild.CalculateWXBorder(childBlock))
            self.Layout()

class BoxContainer (RectangularChild):
    def instantiateWidget (self): 
        return wxBoxContainer (self.parentBlock.widget, Block.getWidgetID(self))
    
class wxLayoutChooser(wxBoxContainer):
    def __init__(self, *arguments, **keywords):
        super (wxLayoutChooser, self).__init__ (*arguments, **keywords)
            
    def wxSynchronizeWidget(self, *arguments, **keywords):
        selectedChoice = self._getSelectedChoice()
        if selectedChoice != self.blockItem.selection:
            for childBlock in self.blockItem.childrenBlocks:
                if not isinstance(childBlock, Toolbar):
                    childBlock.parentBlock = None
                    if hasattr(childBlock, 'widget'):
                        childBlock.widget.Destroy()
            super(wxLayoutChooser, self).wxSynchronizeWidget(*arguments, **keywords)

            try: # @@@ Until all the views have the necessary choices
                choice = self.blockItem.choices[selectedChoice]
            except IndexError:
                choice = self.blockItem.choices[0]
            self.blockItem.selection = selectedChoice
            sizer = self.GetSizer()
            choice.parentBlock = self.blockItem
            choice.render()
            sizer.Add(choice.widget,
                      choice.stretchFactor,
                      wxRectangularChild.CalculateWXFlag(choice),
                      wxRectangularChild.CalculateWXBorder(choice))
            self.Layout()    

    def setSelectedChoice(self, selectedIndex):
        index = 0
        for childBlock in self.blockItem.childrenBlocks:
            if isinstance(childBlock, Toolbar):
                for toolbarItem in childBlock.widget.toolItemList:
                    toolbarItemId = toolbarItem.widget.GetId()
                    if index == selectedIndex:
                        if not childBlock.widget.GetToolState(toolbarItemId):                                
                            childBlock.widget.ToggleTool(toolbarItemId, True)                            
                    else:
                        if childBlock.widget.GetToolState(toolbarItemId):
                            childBlock.widget.ToggleTool(toolbarItemId, False)
                    index += 1
                                        
    def _getSelectedChoice(self):
        index = 0
        for childBlock in self.blockItem.childrenBlocks:
            if isinstance(childBlock, Toolbar):
                for toolbarItem in childBlock.widget.toolItemList:
                    if childBlock.widget.GetToolState(toolbarItem.widget.GetId()):
                        return index
                    index += 1
        # @@@ On the Mac, the radio buttons are not given a default selection.
        # This is a bug in wxWidgets that should be fixed.
        return 0
            
    def getIdPos(self, id):
        index = 0
        for childBlock in self.blockItem.childrenBlocks:
            if isinstance(childBlock, Toolbar):
                for toolbarItem in childBlock.widget.toolItemList:
                    if id == toolbarItem.widget.GetId():
                        return index
                    index += 1
        return LayoutChooser.NONE_SELECTED
    

class LayoutChooser(BoxContainer):
    NONE_SELECTED = -1
    
    def instantiateWidget (self):
        self.selection = LayoutChooser.NONE_SELECTED

        parentWidget = self.parentBlock.widget 
        return wxLayoutChooser(parentWidget, Block.getWidgetID(self))

    def changeSelection(self, selectionIndex):
        self.widget.setSelectedChoice(selectionIndex)
        self.synchronizeWidget()

    def onChangeLayoutEvent(self, event):
        # @@@ On the Mac, radio buttons do not work as radio
        # buttons, but rather they behave as individual toggle
        # buttons.  As a workaround, we deselect the other 
        # radio buttons.
        if '__WXMAC__' in wx.PlatformInfo:
            itemId = event.arguments['sender'].widget.GetId()
            pos = self.widget.getIdPos(itemId)
            self.widget.setSelectedChoice(pos)
        self.synchronizeWidget()

        
class wxScrolledContainer (wx.ScrolledWindow):
    def wxSynchronizeWidget(self, *arguments, **keywords):
        if self.blockItem.isShown:
            sizer = self.GetSizer()
            sizer.Clear()
            for childBlock in self.blockItem.childrenBlocks:
                if childBlock.isShown and isinstance (childBlock, RectangularChild):
                    sizer.Add (childBlock.widget,
                               childBlock.stretchFactor, 
                               wxRectangularChild.CalculateWXFlag(childBlock), 
                               wxRectangularChild.CalculateWXBorder(childBlock))
            self.Layout()
            self.SetScrollRate(0,1)

        
class ScrolledContainer(BoxContainer):
    def instantiateWidget (self):
        return wxScrolledContainer (self.parentBlock.widget, Block.getWidgetID(self))    


class SelectionContainer(BoxContainer):
    """
    SelectionContainer
    Keeps track of the current selected item
    """
    def __init__(self, *arguments, **keywords):
        super (SelectionContainer, self).__init__ (*arguments, **keywords)
        self.selection = None

    def onSelectItemEvent (self, event):
        """
          just remember the new selected ContentItem.
        """
        item = event.arguments['item']
        self.selection = item

    def selectedItem(self):
        # return the item being viewed
        return self.selection    

        
class wxSplitterWindow(wx.SplitterWindow):

    def __init__(self, *arguments, **keywords):
        super (wxSplitterWindow, self).__init__ (*arguments, **keywords)
        self.Bind(wx.EVT_SPLITTER_SASH_POS_CHANGED,
                  self.OnSplitChanged,
                  id=self.GetId())
        self.Bind(wx.EVT_SPLITTER_SASH_POS_CHANGING,
                  self.OnSplitChanging,
                  id=self.GetId())
        self.Bind(wx.EVT_SIZE, self.OnSize)
        """
          Setting minimum pane size prevents unsplitting a window by double-clicking
        """
        self.SetMinimumPaneSize(20)
 
    def OnSize(self, event):
        if not wx.GetApp().ignoreSynchronizeWidget:
            newSize = self.GetSize()
            self.blockItem.size.width = newSize.width
            self.blockItem.size.height = newSize.height
            self.blockItem.setDirty(self.blockItem.VDIRTY, 'size', self.blockItem._values)   # Temporary repository hack -- DJA
            
            if self.blockItem.orientationEnum == "Horizontal":
                distance = self.blockItem.size.height
            else:
                distance = self.blockItem.size.width
            self.SetSashPosition (int (distance * self.blockItem.splitPercentage + 0.5))
        event.Skip()

    def OnSplitChanging(self, event):
        if not self.blockItem.allowResize:
            event.SetSashPosition(-1)
        event.Skip()

    def OnSplitChanged(self, event):
        if not wx.GetApp().ignoreSynchronizeWidget:
            width, height = self.GetSizeTuple()
            position = float (event.GetSashPosition())
            splitMode = self.GetSplitMode()
            if splitMode == wx.SPLIT_HORIZONTAL:
                self.blockItem.splitPercentage = position / height
            else:
                self.blockItem.splitPercentage = position / width

    def wxSynchronizeWidget(self):
        self.SetSize ((self.blockItem.size.width, self.blockItem.size.height))

        assert (len (self.blockItem.childrenBlocks) >= 1 and
                len (self.blockItem.childrenBlocks) <= 2), "We don't currently allow splitter windows with no contents"

        # Collect information about the splitter
        oldWindow1 = self.GetWindow1()
        oldWindow2 = self.GetWindow2()
 
        children = iter (self.blockItem.childrenBlocks)

        window1 = None
        child1 = children.next()
        if child1.isShown:
            window1 = child1.widget
        child1.widget.Show (child1.isShown)

        window2 = None
        if len (self.blockItem.childrenBlocks) >= 2:
            child2 = children.next()
            if child2.isShown:
                window2 = child2.widget
            child2.widget.Show (child2.isShown)

        shouldSplit = bool (window1) and bool (window2)
        
        # Update any differences between the block and widget
        self.Freeze()
        if not self.IsSplit() and shouldSplit:
            """
              First time SplitterWindow creation with two windows or going between
            a split with one window to a split with two windows
            """            
            if self.blockItem.orientationEnum == "Horizontal":
                position = self.blockItem.size.height * self.blockItem.splitPercentage
                success = self.SplitHorizontally (window1, window2, position)
            else:
                position = self.blockItem.size.width * self.blockItem.splitPercentage
                success = self.SplitVertically (window1, window2, position)
            assert success
        elif not oldWindow1 and not oldWindow2 and not shouldSplit:
            """
              First time splitterWindow creation with one window.
            """
            if window1:
                self.Initialize (window1)
            else:
                self.Initialize (window2)
        else:
            if self.IsSplit() and not shouldSplit:
                """
                  Going from two windows in a split to one window in a split.
                """
                show = oldWindow2.IsShown()
                success = self.Unsplit()
                oldWindow2.Show (show)
                assert success
            """
              Swap window1 and window2 so we can simplify the we can finish
            our work with only two comparisons.
            """            
            if bool (oldWindow1) ^ bool (window1):
                window1, window2 = window2, window1
            if window1:
                success = self.ReplaceWindow (oldWindow1, window1)
                assert success
            if window2:
                success = self.ReplaceWindow (oldWindow2, window2)
                assert success
        parent = self.GetParent()
        if parent:
            parent.Layout()
        self.Thaw()

    def CalculateWXStyle(theClass, block):
        style = wx.SP_LIVE_UPDATE
        if isinstance (block.parentBlock, SplitterWindow):
            style |= wx.SP_3DSASH
        else:
            style |= wx.SP_3D
        return style
    CalculateWXStyle = classmethod(CalculateWXStyle)
 
class SplitterWindow(RectangularChild):
    def instantiateWidget (self):
        return wxSplitterWindow (self.parentBlock.widget,
                                 Block.getWidgetID(self), 
                                 wx.DefaultPosition,
                                 (self.size.width, self.size.height),
                                 style=wxSplitterWindow.CalculateWXStyle(self))
                

class wxTabbedViewContainer(DropReceiveWidget, wx.Notebook):
    def wxSynchronizeWidget(self):
        pass

    def CalculateWXStyle(theClass, block):
        return {
            'Top': 0,
            'Bottom': wx.NB_BOTTOM, 
            'Left': wx.NB_LEFT,
            'Right': wx.NB_RIGHT,
        } [block.tabPositionEnumEnum]
    CalculateWXStyle = classmethod(CalculateWXStyle)
    
class wxViewContainer (wxBoxContainer):
    pass


class ViewContainer(BoxContainer):
    def instantiateWidget (self):
        """
        There is a repository bug where copying trees of blocks won't copy parentBlock
        when it's initialValue is None -- DJA
        """
        try:
            parentBlock = self.parentBlock
        except AttributeError:
            self.parentBlock = None
        """
          Somewhat of a hack: When the ViewContainer is the root of all the blocks
        it doesn't have a parent block widget, so in that case we use the mainFrame.
        """
        if self.parentBlock:
            parentWidget = self.parentBlock.widget
        else:
            parentWidget = self.getFrame()

        if self.hasTabs:
            return wxTabbedViewContainer (parentWidget, 
                                          Block.getWidgetID(self),
                                          wx.DefaultPosition,
                                          (self.size.width, self.size.height),
                                          style=wxTabbedViewContainer.CalculateWXStyle(self))
        else:
            return wxViewContainer (parentWidget)
    
    def onChoiceEvent (self, event):
        choice = event.choice
        for view in self.views:
            if view.getItemDisplayName() == choice:
                self.postEventByName('SelectItemBroadcast', {'item':view})
                break

class wxTabbedContainer(DropReceiveWidget, wx.Notebook):
    def __init__(self, *arguments, **keywords):
        super (wxTabbedContainer, self).__init__ (*arguments, **keywords)
        self.selectedTab = 0
        
        self.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.OnWXSelectItem,
                  id=self.GetId())

    def CalculateWXStyle(self, block):
        if block.tabPosEnum == "Top":
            style = 0
        elif block.tabPosEnum == "Bottom":
            style = wx.NB_BOTTOM
        elif block.tabPosEnum == "Left":
            style = wx.NB_LEFT
        elif block.tabPosEnum == "Right":
            style = wx.NB_RIGHT
        elif __debug__:
            assert False
        return style
    CalculateWXStyle = classmethod(CalculateWXStyle)

    def OnWXSelectItem (self, event):
        if not wx.GetApp().ignoreSynchronizeWidget:
            selection = event.GetSelection()
            if self.selectedTab != selection:
                self.selectedTab = selection
                page = self.GetPage(self.selectedTab)
                self.blockItem.postEventByName("SelectItemBroadcast", {'item':page.blockItem})
        event.Skip()
        
    def OnRequestDrop(self, x, y):
        tab = self.HitTest((x, y))[0]
        if tab > -1:
            self.SetSelection(tab)
            return True
        return False

    def AddItem(self, itemUUID):
        node = self.blockItem.findUUID(itemUUID)
        try:
            newItem = node.item
        except AttributeError:
            pass
        else:
            if isinstance(newItem, Block):
                self.blockItem.ChangeCurrentTab(node)

    def OnHover(self, x, y):
        currentTab = self.HitTest((x, y))[0]
        if currentTab < 0:
            return
        currentTime = time.time()
        if not hasattr(self, "hoverTab") or self.hoverTab != currentTab:
            self.hoverTab = currentTab            
            self.dropTarget.enterTime = currentTime
        elif (currentTime - self.dropTarget.enterTime) > 1:
            self.SetSelection(currentTab)
            
    def wxSynchronizeWidget(self):
        assert(len(self.blockItem.childrenBlocks) >= 1), "Tabbed containers cannot be empty"
        self.Freeze()
        for pageNum in range (self.GetPageCount()):
            page = self.GetPage(0)
            if not page.blockItem.parentBlock:
                self.DeletePage(0)
            else:
                self.RemovePage(0)
        index = 0
        for child in self.blockItem.childrenBlocks:
            self.AddPage (child.widget, self.blockItem._getBlockName(child))
            index += 1
        self.SetSelection(self.selectedTab)
        page = self.GetPage(self.selectedTab)
        self.Thaw()
                

class TabbedContainer(RectangularChild):
    def instantiateWidget (self):
        return wxTabbedContainer (self.parentBlock.widget, 
                                  Block.getWidgetID(self),
                                  wx.DefaultPosition,
                                  (self.size.width, self.size.height),
                                  style=wxTabbedContainer.CalculateWXStyle(self))

    
    def onChoiceEvent (self, event):
        choice = event.choice
        for index in xrange (self.widget.GetPageCount()):
            if self.widget.GetPageText(index) == choice:
                self.widget.SetSelection (index)
                break

    def _getBlockName(self, block):
        try:
            item = block.contents
        except AttributeError:
            item = block
            
        try:
            return item.displayName
        except AttributeError:
            return ""


class TabbedView(TabbedContainer):
    def ChangeCurrentTab(self, item):
        if hasattr (self, 'widget'):
            # tabbed container hasn't been rendered yet
            activeTab = self.widget.GetSelection()
            itemName = self._getBlockName(item)
            found = False
            for tabIndex in range(self.widget.GetPageCount()):
                tabName = self.widget.GetPageText(tabIndex)
                if tabName == itemName:
                    found = True
                    self.widget.SetSelection(tabIndex)
            self.parentBlock.widget.Freeze()
            if not found:
                page = self.widget.GetPage(activeTab)
                previousChild = self.childrenBlocks.previous(page.blockItem)
                page.blockItem.parentBlock = None
    
                item.parentBlock = self 
                self.childrenBlocks.placeItem(item, previousChild)
                item.render()                
                item.widget.SetSize (self.widget.GetClientSize())                
            self.synchronizeWidget()
            self.parentBlock.widget.Thaw()

    def onNewEvent (self, event):
        "Create a new tab"
        originalItem = self.findPath('parcels/osaf/views/content/UntitledView')
        userdata = self.findPath('//userdata')
        newItem = originalItem.copy(parent=userdata, cloudAlias='default')
        newItem.contents.displayName = self._getUniqueName("Untitled")
        
        self.widget.selectedTab = self.widget.GetPageCount()
        newItem.parentBlock = self
        self.parentBlock.widget.Freeze()
        newItem.render()
        self.synchronizeWidget()
        self.parentBlock.widget.Thaw()
        self.postEventByName ('SelectItemBroadcast', {'item':newItem})

    def onCloseEvent (self, event):
        """
          Will either close the current tab (if not data is present
        in the sender) or will close the tab specified by data.
        """
        try:
            item = event.arguments['sender'].data
        except AttributeError:
            pageIndex = self.widget.GetSelection()
        else:
            for tabIndex in range (self.widget.GetPageCount()):
                tabName = self.widget.GetPageText(tabIndex)
                if tabName == self._getBlockName(item):
                    found = True
                    pageIndex = tabIndex
            if not found:
                # Tab isn't actually open
                return
        if pageIndex == self.widget.GetSelection():
            if pageIndex == (self.widget.GetPageCount() - 1):
                self.widget.selectedTab = pageIndex - 1
            else:
                self.widget.selectedTab = pageIndex
        elif pageIndex < self.widget.GetSelection():
            self.widget.selectedTab = self.widget.GetSelection() - 1
        page = self.widget.GetPage(pageIndex)
        page.blockItem.parentBlock = None
        self.parentBlock.widget.Freeze()        
        self.synchronizeWidget()
        self.parentBlock.widget.Thaw()
        self.postEventByName ('SelectItemBroadcast',
                              {'item':self.widget.GetPage(self.widget.selectedTab).blockItem})

    def onOpenEvent (self, event):
        "Opens the chosen item in a new tab"
        item = event.arguments['sender'].arguments
        found = False
        for tabIndex in range (self.widget.GetPageCount()):
            tabName = self.widget.GetPageText (tabIndex)
            if tabName == self._getBlockName(item):
                found = True
                self.widget.SetSelection(tabIndex)
        if not found:
            self.widget.selectedTab = self.widget.GetPageCount()
            item.parentBlock = self
            self.parentBlock.widget.Freeze()
            item.render()
            item.widget.SetSize (self.widget.GetClientSize())
            self.synchronizeWidget()
            self.parentBlock.widget.Thaw()
            self.postEventByName ('SelectItemBroadcast', {'item':item})
        
    def onCloseEventUpdateUI(self, event):
        event.arguments['Enable'] = (self.widget.GetPageCount() > 1)
        
    def _getUniqueName (self, name):
        if not self.hasChild(name):
            return name
        number = 1
        uniqueName = name + "-" + str(number)
        while self.hasChild(uniqueName):
            number += 1
            uniqueName = name + "-" + str(number)
        return uniqueName

        
class wxDetailPanel (wxBoxContainer):
    def wxSynchronizeWidget(self, *arguments, **keywords):
        if self.blockItem.isShown:
            self.blockItem.InstallTreeOfBlocks()
        super (wxDetailPanel, self).wxSynchronizeWidget (*arguments, **keywords)

class DetailBlock(BoxContainer):
    def instantiateWidget (self):
        return wxDetailPanel (self.parentBlock.widget)

    def onSelectItemEvent (self, event):
        self.detailItem = event.arguments['item']
        self.widget.wxSynchronizeWidget()

    def InstallTreeOfBlocks (self):
        # $$$ Repository bug doesn't let us have an initial value for detailItem
        # fix later. DJA
        try:
            detailItem = self.detailItem
        except AttributeError:
            newView = None
        else:
            newView = self.viewCache.GetViewForItem (detailItem)

        oldView = self.childrenBlocks.first()

        if not newView is oldView:
            if not oldView is None:
                oldView.unRender()

            self.childrenBlocks = []

            if not newView is None:
                self.childrenBlocks.append (newView)
                """
                  Seems like we should always mark new views with an event boundary
                """
                assert newView.eventBoundary
                newView.postEventByName("SetContents", {'item':detailItem})

                newView.render()

# @@@BJS: "reload parcels" needs to blow away this cache!

class DetailViewCache (Item):
    def GetViewForItem (self, item):
        view = None
        if not item is None:
            kindUUID = item.itsUUID
            try:
                viewUUID = self.kindUUIDToViewUUID [kindUUID]
            except KeyError:
                kindString = str (item.itsKind.itsName)
                try:
                    name = {"MailMessage":"EmailRootTemplate",
                            "CalendarEvent":"CalendarRootTemplate"} [kindString]
                except KeyError:
                    pass
                else:
                    # @@@BJS: work in progress...
                    # NOT: For now, just use the old detail view
                    # was: template = self.findPath ("//parcels/osaf/framework/blocks/detail/DetailRootTemplate")
                    template = self.findPath ("//parcels/osaf/framework/blocks/detail/" + name)
                    view = template.copy (parent = self.findPath ("//userdata"),
                                          cloudAlias="default")
                    self.kindUUIDToViewUUID [kindUUID] = view.itsUUID
            else:
                view = self.findUUID (viewUUID)
        return view


class SidebarDetailViewCache (Item):
    def GetViewForItem (self, item):
        view = None
        try:
            viewUUID = self.itemCollectionUUIDToViewUUID [item.itsUUID]
        except KeyError:
            if isinstance (item, ItemCollection):
                template = self.findPath (self.treeTemplatePath)
                view = template.copy (parent = self.findPath ("//userdata"),
                                      cloudAlias="default")
                self.itemCollectionUUIDToViewUUID [item.itsUUID] = view.itsUUID
            elif isinstance (item, Block):
                """
                  We don't copy the view because it's already copied to the soup
                """
                view = item
        else:
            view = self.find (viewUUID)
        return view
