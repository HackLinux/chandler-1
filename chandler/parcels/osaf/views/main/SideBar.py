__version__ = "$Revision$"
__date__ = "$Date$"
__copyright__ = "Copyright (c) 2003-2004 Open Source Applications Foundation"
__license__ = "http://osafoundation.org/Chandler_0.1_license_terms.htm"

import osaf.framework.blocks.ControlBlocks as ControlBlocks
import osaf.framework.blocks.Block as Block
import osaf.framework.blocks.Trunk as Trunk
import osaf.contentmodel.ItemCollection as ItemCollection
import wx
import osaf.framework.blocks.DrawingUtilities as DrawingUtilities
import os


def GetRenderEditorTextRect (rect):
    image = wx.GetApp().GetImage ("SidebarAll.png")
    width = image.GetWidth() + 2
    return wx.Rect (rect.GetLeft() + width,
                    rect.GetTop(),
                    rect.GetWidth() - (2 * width),
                    rect.GetHeight())


class SidebarElementDelegate (ControlBlocks.ListDelegate):
    def ReadOnly (self, row, column):
        """
          Second argument should be True if all cells have the first value
        """
        (item, attribute) = self.GetElementValue (row, column)
        try:
            readOnly = not item.renameable
        except AttributeError:
            readOnly = False
        return readOnly, False

    def GetElementType (self, row, column):
        return "Item"

    def GetElementValue (self, row, column):
        return self.blockItem.contents [row], self.blockItem.columnData [column]


class wxSidebar(ControlBlocks.wxTable):

    def OnRequestDrop(self, x, y):
        self.dropRow = self.YToRow(y)
        if self.dropRow == wx.NOT_FOUND:
            return False
        return True
        
    def AddItem(self, itemUUID):
        item = self.blockItem.findUUID(itemUUID)
        self.blockItem.contents[self.dropRow].add(item)
        self.SetRowHighlight(self.dropRow, False)
    
    def OnItemDrag(self, event):
        # @@@ You currently can't drag out of the sidebar
        pass

    def OnHover(self, x, y):
        hoverRow = self.YToRow(y)
        try:
            self.hoverRow
        except AttributeError:
            # If it's our first time hovering then set previous state to be NOT_FOUND
            self.hoverRow = wx.NOT_FOUND
        else:
            # Clear the selection colour if necessary
            if self.hoverRow != wx.NOT_FOUND and self.hoverRow != hoverRow:
                self.SetRowHighlight(self.hoverRow, False)
                
            # Colour the item if it exists and isn't already coloured
            if hoverRow != wx.NOT_FOUND and hoverRow != self.hoverRow:
                self.SetRowHighlight(hoverRow, True)
            
            # Store current state
            self.hoverRow = hoverRow
            
    def SetRowHighlight(self, row, highlightOn):
        if highlightOn:
            self.SetCellBackgroundColour(row, 0, wx.LIGHT_GREY)
        else:
            self.SetCellBackgroundColour(row, 0, wx.WHITE)
        # Just invalidate the changed rect
        rect = self.CellToRect(row, 0)
        rect.OffsetXY (self.GetRowLabelSize(), self.GetColLabelSize())
        self.RefreshRect(rect)
        self.Update()

class SSSidebarRenderer (wx.grid.PyGridCellRenderer):
    """
      Super specialized Sidebar Renderer, is so specialized that it works in
    only one context -- Mimi's Sidebar.
    """
    def Draw (self, grid, attr, dc, rect, row, col, isSelected):
        DrawingUtilities.SetTextColorsAndFont (grid, attr, dc, isSelected)

        dc.SetBackgroundMode (wx.SOLID)
        dc.SetPen (wx.TRANSPARENT_PEN)

        dc.DrawRectangleRect(rect)

        dc.SetBackgroundMode (wx.TRANSPARENT)
        item, attribute = grid.GetTable().GetValue (row, col)
        name = getattr (item, attribute)

        if isinstance (item, ItemCollection.ItemCollection):
            if len (item) == 0:
                dc.SetTextForeground (wx.SystemSettings.GetColour (wx.SYS_COLOUR_GRAYTEXT))

            numberOfShares = len (item.shares)
            if numberOfShares > 0:
                sharer = item.shares.first().sharer
                if numberOfShares == 1 and str(sharer.itsPath) == "//userdata/me":
                    imageName = "SidebarOut.png"
                else:
                    imageName = "SidebarIn.png"
                image = wx.GetApp().GetImage (imageName)
                x = rect.GetRight() -image.GetWidth() - 1
                y = rect.GetTop() + (rect.GetHeight() - image.GetHeight()) / 2
                dc.DrawBitmap (image, x, y, True)

            if not getattr (item, "renameable", True):
                key = name
                sidebar = grid.blockItem
                if sidebar.filterKind is not None:
                    key += os.path.basename (unicode (sidebar.filterKind.itsPath))
                try:
                    name = sidebar.nameAlternatives [key]
                except KeyError:
                    imageSuffix = name
                else:
                    imageSuffix = key
                image = wx.GetApp().GetImage ("Sidebar" + imageSuffix + ".png")
        
                if image is not None:
                    x = rect.GetLeft() + 1
                    y = rect.GetTop() + (rect.GetHeight() - image.GetHeight()) / 2
                    dc.DrawBitmap (image, x, y, True)

        textRect = GetRenderEditorTextRect (rect)
        textRect.Inflate (-1, -1)
        dc.SetClippingRect (textRect)
        DrawingUtilities.DrawWrappedText (dc, name, textRect)
        dc.DestroyClippingRegion()


class SSSidebarEditor (ControlBlocks.GridCellAttributeEditor):
    """
      Super specialized Sidebar Editor, is so specialized that it works in
    only one context -- Mimi's Sidebar.
    """

    def SetSize(self, rect):
        textRect = GetRenderEditorTextRect (rect)
        self.control.SetRect (textRect);


class Sidebar (ControlBlocks.Table):
    def instantiateWidget (self):
        widget = wxSidebar (self.parentBlock.widget, Block.Block.getWidgetID(self))    
        widget.RegisterDataType ("Item", SSSidebarRenderer(), SSSidebarEditor("Item"))
        return widget

    def onKindParameterizedEvent (self, event):                
        self.filterKind = event.kindParameter
        self.widget.Refresh()
        self.postEventByName("SelectItemBroadcast", {'item':self.selectedItemToView})

    def onRequestSelectSidebarItemEvent (self, event):
        # Request the sidebar to change selection
        # Item specified is usually by name
        try:
            item = event.arguments['item']
        except KeyError:
            # find the item by name
            itemName = event.arguments['itemName']
            for item in self.contents:
                if item.displayName == itemName:
                    break
            else:
                return

        self.postEventByName("SelectItemBroadcast", {'item':item})


class SidebarTrunkDelegate(Trunk.TrunkDelegate):
    def _mapItemToCacheKeyItem(self, item):
        key = item
        if isinstance (item, ItemCollection.ItemCollection):
            filterKind = Block.Block.findBlockByName ("Sidebar").filterKind
            if not filterKind is None:
                tupleKey = (item.itsUUID, filterKind.itsUUID)
                try:
                    key = self.itemTupleKeyToCacheKey [tupleKey]
                except KeyError:
                    """
                      We need to make a new filtered item collection that depends
                      upon the unfiltered collection. Unfortunately, making a new
                      ItemCollection with a rule whose results include all items
                      in the original ItemCollection has a problem: when the results
                      in the unfiltered ItemCollection change we don't get notified.

                      Alternatively we make a copy of the ItemCollection (and it's
                      rule) which has another problem: When the rule in the original
                      ItemCollection change we don't update our copied rule.                      
                    """
                    key = ItemCollection.ItemCollection (view=self.itsView)
                    key.source = item
                    key.displayName = item.displayName + u" filtered by " + filterKind.displayName
                    key.addFilterKind (filterKind)
                    self.itemTupleKeyToCacheKey [tupleKey] = key
        return key

    def _makeTrunkForCacheKey(self, keyItem):
        if isinstance (keyItem, ItemCollection.ItemCollection):
            sidebar = Block.Block.findBlockByName ("Sidebar")
            filterKind = sidebar.filterKind
            if (filterKind is not None and
                unicode (filterKind.itsPath) == "//parcels/osaf/contentmodel/calendar/CalendarEventMixin" and
                keyItem.displayName not in sidebar.dontShowCalendarForItemsWithName):
                    trunk = self.findPath (self.calendarTemplatePath)
                    keyUUID = trunk.itsUUID
                    try:
                        trunk = self.keyUUIDToTrunk[keyUUID]
                    except KeyError:
                        trunk = self._copyItem(trunk, onlyIfReadOnly=True)
                        self.keyUUIDToTrunk[keyUUID] = trunk
            else:
                trunk = self.findPath (self.tableTemplatePath)
        else:
            trunk = keyItem
        
        assert isinstance (trunk, Block.Block)
        return self._copyItem(trunk, onlyIfReadOnly=True)

    def _setContentsOnTrunk(self, trunk, item, keyItem):
        trunk.postEventByName("SetContents", {'item':keyItem})


class CPIATestSidebarTrunkDelegate(Trunk.TrunkDelegate):
    def _makeTrunkForCacheKey(self, keyItem):
        if isinstance (keyItem, ItemCollection.ItemCollection):
            trunk = self.findPath (self.templatePath)
        else:
            trunk = keyItem
        
        assert isinstance (trunk, Block.Block)
        return self._copyItem(trunk, onlyIfReadOnly=True)
