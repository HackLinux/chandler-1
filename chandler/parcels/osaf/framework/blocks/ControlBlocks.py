__version__ = "$Revision$"
__date__ = "$Date$"
__copyright__ = "Copyright (c) 2003-2005 Open Source Applications Foundation"
__license__ = "http://osafoundation.org/Chandler_0.1_license_terms.htm"

import os, sys
from application.Application import mixinAClass
from Block import *
from ContainerBlocks import *
from DragAndDrop import DraggableWidget as DraggableWidget
from Styles import Font
from repository.item.ItemError import NoSuchAttributeError
import wx
import wx.html
import wx.gizmos
import wx.grid
import webbrowser # for opening external links
from osaf.framework.attributeEditors.AttributeEditors import IAttributeEditor
from repository.schema.Types import DateTime
from repository.schema.Types import RelativeDateTime
import mx.DateTime

class Button(RectangularChild):
    def instantiateWidget(self):
        id = self.getWidgetID(self)
        parentWidget = self.parentBlock.widget
        if self.buttonKind == "Text":
            button = wx.Button (parentWidget,
                                id,
                                self.title,
                                wx.DefaultPosition,
                                (self.minimumSize.width, self.minimumSize.height))
        elif self.buttonKind == "Image":
            image = wx.Image(self.icon, 
                             wx.BITMAP_TYPE_PNG)
            bitmap = image.ConvertToBitmap()
            button = wx.BitmapButton (parentWidget,
                                      id,
                                      bitmap,
                                      wx.DefaultPosition,
                                      (self.minimumSize.width, self.minimumSize.height))
        elif self.buttonKind == "Toggle":
                button = wx.ToggleButton (parentWidget, 
                                          id, 
                                          self.title,
                                          wx.DefaultPosition,
                                          (self.minimumSize.width, self.minimumSize.height))
        elif __debug__:
            assert False, "unknown buttonKind"

        parentWidget.Bind(wx.EVT_BUTTON, self.buttonPressed, id=id)
        return button

    def buttonPressed(self, event):
        try:
            event = self.event
        except AttributeError:
            pass
        else:
            self.post(event, {'item':self})

                              
class wxCheckBox(ShownSynchronizer, wx.CheckBox):
    pass

class CheckBox(RectangularChild):
    def instantiateWidget(self):
        try:
            id = Block.getWidgetID(self)
        except AttributeError:
            id = 0

        parentWidget = self.parentBlock.widget
        checkbox = wxCheckBox (parentWidget,
                          id, 
                          self.title,
                          wx.DefaultPosition,
                          (self.minimumSize.width, self.minimumSize.height))
        checkbox.Bind(wx.EVT_CHECKBOX, wx.GetApp().OnCommand, id=id)
        return checkbox
    
class wxChoice(ShownSynchronizer, wx.Choice):
    pass

class Choice(RectangularChild):
    def instantiateWidget(self):
        try:
            id = Block.getWidgetID(self)
        except AttributeError:
            id = 0

        parentWidget = self.parentBlock.widget
        choice = wxChoice (parentWidget,
                         id, 
                         wx.DefaultPosition,
                         (self.minimumSize.width, self.minimumSize.height),
                         self.choices)
        choice.Bind(wx.EVT_CHOICE, wx.GetApp().OnCommand, id=id)
        return choice

class ComboBox(RectangularChild):
    def instantiateWidget(self):
        return wx.ComboBox (self.parentBlock.widget,
                            -1,
                            self.selection, 
                            wx.DefaultPosition,
                            (self.minimumSize.width, self.minimumSize.height),
                            self.choices)

    
class ContextMenu(RectangularChild):
    def displayContextMenu(self, parentWindow, position, data):
        menu = wx.Menu()
        for child in self.childrenBlocks:
            child.addItem(menu, data)
        parentWindow.PopupMenu(menu, position)
        menu.Destroy()
        

class ContextMenuItem(RectangularChild):
    def addItem(self, wxContextMenu, data):
        id = Block.getWidgetID(self)
        self.data = data
        wxContextMenu.Append(id, self.title)
        wxContextMenu.Bind(wx.EVT_MENU, wx.GetApp().OnCommand, id=id)

    
class wxEditText(ShownSynchronizer, wx.TextCtrl):
    def __init__(self, *arguments, **keywords):
        super (wxEditText, self).__init__ (*arguments, **keywords)
        self.Bind(wx.EVT_TEXT_ENTER, self.OnEnterPressed, id=self.GetId())
        minW, minH = arguments[-1] # assumes minimum size passed as last arg
        self.SetSizeHints(minW=minW, minH=minH)

    def OnEnterPressed(self, event):
        self.blockItem.postEventByName ('EnterPressed', {'text':self.GetValue()})
        event.Skip()

class EditText(RectangularChild):
    def instantiateWidget(self):
        style = 0
        if self.textAlignmentEnum == "Left":
            style |= wx.TE_LEFT
        elif self.textAlignmentEnum == "Center":
            style |= wx.TE_CENTRE
        elif self.textAlignmentEnum == "Right":
            style |= wx.TE_RIGHT

        if self.lineStyleEnum == "MultiLine":
            style |= wx.TE_MULTILINE
        else:
            style |= wx.TE_PROCESS_ENTER

        if self.textStyleEnum == "RichText":
            style |= wx.TE_RICH2

        if self.readOnly:
            style |= wx.TE_READONLY

        editText = wxEditText (self.parentBlock.widget,
                               -1,
                               "",
                               wx.DefaultPosition,
                               (self.minimumSize.width, self.minimumSize.height),
                               style=style, name=self.itsUUID.str64())

        editText.SetFont(Font (self.characterStyle))
        return editText
    
    """
    Edit Menu enabling and handling
    """
    def onUndoEventUpdateUI (self, event):
        canUndo = self.widget.CanUndo()
        event.arguments ['Enable'] = canUndo
        if canUndo:
            event.arguments ['Text'] = 'Undo Command\tCtrl+Z'
        else:
            event.arguments ['Text'] = "Can't Undo\tCtrl+Z"            

    def onUndoEvent (self, event):
        self.widget.Undo()
        self.OnDataChanged()

    def onRedoEventUpdateUI (self, event):
        event.arguments ['Enable'] = self.widget.CanRedo()

    def onRedoEvent (self, event):
        self.widget.Redo()
        self.OnDataChanged()

    def onCutEventUpdateUI (self, event):
        event.arguments ['Enable'] = self.widget.CanCut()

    def onCutEvent (self, event):
        self.widget.Cut()
        self.OnDataChanged()

    def onCopyEventUpdateUI (self, event):
        event.arguments ['Enable'] = self.widget.CanCopy()

    def onCopyEvent (self, event):
        self.widget.Copy()

    def onPasteEventUpdateUI (self, event):
        event.arguments ['Enable'] = self.widget.CanPaste()

    def onPasteEvent (self, event):
        self.widget.Paste()
        self.OnDataChanged()
    
    def OnDataChanged (self):
        # override in subclass for event when edit operations have taken place
        pass

class wxHTML(wx.html.HtmlWindow):
    def OnLinkClicked(self, link):
        webbrowser.open(link.GetHref())


class HTML(RectangularChild):
    def instantiateWidget (self):
        htmlWindow = wxHTML (self.parentBlock.widget,
                             Block.getWidgetID(self),
                             wx.DefaultPosition,
                             (self.minimumSize.width, self.minimumSize.height))
        if self.url:
            htmlWindow.LoadPage(self.url)
        return htmlWindow

 
class ListDelegate (object):
    """
      Default delegate for Lists that use the block's contents. Override
    to customize your behavior. You must implement GetElementValue.
    """
    def GetColumnCount (self):
        return len (self.blockItem.columnHeadings)

    def GetElementCount (self):
        return len (self.blockItem.contents)

    def GetElementType (self, row, column):
        return "String"

    def GetColumnHeading (self, column, item):
        return self.blockItem.columnHeadings [column]


class AttributeDelegate (ListDelegate):
    def GetElementType (self, row, column):
        """
          An apparent bug in wxWidgets occurs when there are no items in a table,
        the Table asks for the type of cell 0,0
        """
        typeName = "_default"
        try:
            item = self.blockItem.contents [row]
        except IndexError:
            pass
        else:
            attributeName = self.blockItem.columnData [column]
            if item.itsKind.hasAttribute (attributeName):
                try:
                    typeName = item.getAttributeAspect (attributeName, 'type').itsName
                except NoSuchAttributeError:
                    # We special-case the non-Chandler attributes we want to use (_after_ trying the
                    # Chandler attribute, to avoid a hit on Chandler-attribute performance). If we
                    # want to add other itsKind-like non-Chandler attributes, we'd add more tests here.
                    raise
            elif attributeName == 'itsKind':
                typeName = 'Kind'
            else:
                try:
                    # to support properties, we get the value, and use its type's name.
                    value = getattr (item, attributeName)
                except AttributeError:
                    pass
                else:
                    typeName = type (value).__name__
        return typeName

    def GetElementValue (self, row, column):
        return self.blockItem.contents [row], self.blockItem.columnData [column]
    
    def SetElementValue (self, row, column, value):
        item = self.blockItem.contents [row]
        attributeName = self.blockItem.columnData [column]
        assert item.itsKind.hasAttribute (attributeName), "You cannot set a non-Chandler attribute value of an item (like itsKind)"
        item.setAttributeValue (attributeName, value)

    def GetColumnHeading (self, column, item):
        attributeName = self.blockItem.columnData [column]
        if item is not None:
            try:
                attribute = item.itsKind.getAttribute (attributeName)
            except NoSuchAttributeError:
                # We don't need to redirect non-Chandler attributes (eg, itsKind).
                heading = self.blockItem.columnHeadings[column]
            else:
                heading = attribute.getItemDisplayName()
                redirect = item.getAttributeAspect(attributeName, 'redirectTo')
                if redirect is not None:
                    names = redirect.split('.')
                    for name in names [:-1]:
                        item = item.getAttributeValue (name)
                    actual = item.itsKind.getAttribute (names[-1]).getItemDisplayName()
                    heading = "%s (%s)" % (heading, actual)
                self.blockItem.columnHeadings [column] = heading
        else:
            heading = self.blockItem.columnHeadings [column]
        return heading
    

class wxList (DraggableWidget, wx.ListCtrl):
    def __init__(self, *arguments, **keywords):
        super (wxList, self).__init__ (*arguments, **keywords)
        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnWXSelectItem, id=self.GetId())
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_LIST_BEGIN_DRAG, self.OnItemDrag)

    def OnInit (self):
        elementDelegate = self.blockItem.elementDelegate
        if not elementDelegate:
            elementDelegate = 'osaf.framework.blocks.ControlBlocks.ListDelegate'
        mixinAClass (self, elementDelegate)
        
    def OnSize(self, event):
        if not wx.GetApp().ignoreSynchronizeWidget:
            size = self.GetClientSize()
            widthMinusLastColumn = 0
            assert self.GetColumnCount() > 0, "We're assuming that there is at least one column"
            for column in xrange (self.GetColumnCount() - 1):
                widthMinusLastColumn += self.GetColumnWidth (column)
            lastColumnWidth = size.width - widthMinusLastColumn
            if lastColumnWidth > 0:
                self.SetColumnWidth (self.GetColumnCount() - 1, lastColumnWidth)
        event.Skip()

    def OnWXSelectItem(self, event):
        if not wx.GetApp().ignoreSynchronizeWidget:
            item = self.blockItem.contents [event.GetIndex()]
            if self.blockItem.selection != item:
                self.blockItem.selection = item
            self.blockItem.postEventByName("SelectItemBroadcast", {'item':item})
        event.Skip()

    def OnItemDrag(self, event):
        self.SetDragData (self.blockItem.contents [event.GetIndex()].itsUUID)
                            
    def wxSynchronizeWidget(self):
        self.Freeze()
        self.ClearAll()
        self.SetItemCount (self.GetElementCount())
        for columnIndex in xrange (self.GetColumnCount()):
            self.InsertColumn (columnIndex,
                               self.GetColumnHeading (columnIndex, self.blockItem.selection),
                               width = self.blockItem.columnWidths [columnIndex])

        self.Thaw()

        if self.blockItem.selection:
            self.GoToItem (self.blockItem.selection)

    def OnGetItemText (self, row, column):
        """
          OnGetItemText won't be called if it's in the delegate -- WxPython won't
        call it if it's in a base class
        """
        return self.GetElementValue (row, column)

    def OnGetItemImage (self, item):
        return -1
    
    def GoToItem(self, item):
        self.Select (self.blockItem.contents.index (item))


class List(RectangularChild):
    def __init__(self, *arguments, **keywords):
        super (List, self).__init__ (*arguments, **keywords)
        self.selection = None

    def instantiateWidget (self):
        return wxList (self.parentBlock.widget,
                       Block.getWidgetID(self),
                       style=wx.LC_REPORT|wx.LC_VIRTUAL|wx.SUNKEN_BORDER|wx.LC_EDIT_LABELS)

    def onSelectItemEvent (self, event):
        """
          Display the item in the widget.
        """
        self.selection = event.arguments['item']
        self.widget.GoToItem (self.selection)


class wxTableData(wx.grid.PyGridTableBase):
    def __init__(self, *arguments, **keywords):
        super (wxTableData, self).__init__ (*arguments, **keywords)
        self.defaultRWAttribute = wx.grid.GridCellAttr()
        self.defaultROAttribute = wx.grid.GridCellAttr()
        self.defaultROAttribute.SetReadOnly (True)

    def __del__ (self):
        self.defaultRWAttribute.DecRef()
        self.defaultROAttribute.DecRef()
        
    def GetNumberRows (self):
        """
          We've got the usual chicken & egg problems: wxWidgets calls GetNumberRows &
        GetNumberCols before wiring up the view instance variable
        """
        view = self.GetView()
        if view:
            return view.GetElementCount()
        return 1

    def GetNumberCols (self):
        view = self.GetView()
        if view:
            return view.GetColumnCount()
        return 1

    def GetColLabelValue (self, column):
        grid = self.GetView()
        if grid.GetElementCount():
            item = grid.blockItem.contents [grid.GetGridCursorRow()]
        else:
            item = None
        return grid.GetColumnHeading (column, item)

    def IsEmptyCell (self, row, column): 
        return False 

    def GetValue (self, row, column): 
        return self.GetView().GetElementValue (row, column)

    def SetValue (self, row, column, value):
        self.GetView().SetElementValue (row, column, value) 

    def GetTypeName (self, row, column):
        return self.GetView().GetElementType (row, column)

    def GetAttr (self, row, column, kind):
        attribute = self.base_GetAttr (row, column, kind)
        if not attribute:
            type = self.GetTypeName (row, column)
            delegate = IAttributeEditor.GetAttributeEditorSingleton (type)
            attribute = self.defaultROAttribute
            """
              An apparent bug in table asks for an attribute even when
            there are no entries in the table
            """
            view = self.GetView()
            if (view.GetElementCount() != 0 and
                not delegate.ReadOnly (view.GetElementValue (row, column))):
                attribute = self.defaultRWAttribute
            attribute.IncRef()
        return attribute
        

class wxTable(DraggableWidget, DropReceiveWidget, wx.grid.Grid):
    def __init__(self, *arguments, **keywords):
        """
          Giant hack. Calling event.GetEventObject in OnShow of application, while the
        object is being created cause the object to get the wrong type because of a
        "feature" of SWIG. So we need to avoid OnShows in this case.
        """
        oldIgnoreSynchronizeWidget = wx.GetApp().ignoreSynchronizeWidget
        wx.GetApp().ignoreSynchronizeWidget = True
        try:
            super (wxTable, self).__init__ (*arguments, **keywords)
        finally:
            wx.GetApp().ignoreSynchronizeWidget = oldIgnoreSynchronizeWidget

        self.SetColLabelAlignment(wx.ALIGN_LEFT, wx.ALIGN_CENTRE)
        self.SetRowLabelSize(0)
        self.AutoSizeRows()
        self.EnableGridLines(False)
        self.EnableDragCell(True)
        self.DisableDragRowSize()
        self.SetDefaultCellBackgroundColour(wx.WHITE)
        """
          Big fat hack. Since the grid is a scrolled window we set a border equal to the size
        of the scrollbar so the scroll bars won't show. Instead we should consider modifying
        grid adding a new style for not showing scrollbars.  Bug #2375
        """
        self.SetMargins(0-wx.SystemSettings_GetMetric(wx.SYS_VSCROLL_X),
                        0-wx.SystemSettings_GetMetric(wx.SYS_HSCROLL_Y))
        """
          Don't draw cursor outline on selected cells
        """
        self.SetCellHighlightPenWidth (0)
        self.SetCellHighlightROPenWidth (0)

        defaultName = "_default"
        self.SetDefaultRenderer (GridCellAttributeRenderer (defaultName))
        map = wx.GetApp().UIRepositoryView.findPath('//parcels/osaf/framework/attributeEditors/AttributeEditors')
        for key in map.editorString.keys():
            if key != defaultName:
                self.RegisterDataType (key,
                                       GridCellAttributeRenderer (key),
                                       GridCellAttributeEditor (key))

        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.grid.EVT_GRID_COL_SIZE, self.OnColumnDrag)
        self.Bind(wx.grid.EVT_GRID_RANGE_SELECT, self.OnRangeSelect)
        self.Bind(wx.grid.EVT_GRID_CELL_RIGHT_CLICK, self.OnRightClick)
        self.Bind(wx.grid.EVT_GRID_CELL_BEGIN_DRAG, self.OnItemDrag)

    def OnInit (self):
        elementDelegate = self.blockItem.elementDelegate
        if not elementDelegate:
            elementDelegate = 'osaf.framework.blocks.ControlBlocks.AttributeDelegate'
        mixinAClass (self, elementDelegate)
        """
          wxTableData handles the callbacks to display the elements of the
        table. Setting the second argument to True cause the table to be deleted
        when the grid is deleted.

          We've also got the usual chicken and egg problem: SetTable uses the
        table before initializing it's view so GetView() returns none.
        """
        gridTable = wxTableData()

        self.currentRows = gridTable.GetNumberRows()
        self.currentColumns = gridTable.GetNumberCols()

        self.SetTable (gridTable, True, selmode=wx.grid.Grid.SelectRows)

        
    def OnRangeSelect(self, event):
        if not wx.GetApp().ignoreSynchronizeWidget:
            topRow = event.GetTopRow()
            bottomRow = event.GetBottomRow()
            selecting = event.Selecting()
            if topRow == 0 and bottomRow == (self.GetElementCount() -1):
                self.blockItem.selection = []
                if not selecting:
                    return
            self.blockItem.selection.append ([topRow, bottomRow, selecting])

            topLeftList = self.GetSelectionBlockTopLeft()
            topLeftList.sort()
            try:
                (row, column) = topLeftList [0]
            except IndexError:
                item = None
            else:
                item = self.blockItem.contents [row]

            if item != self.blockItem.selectedItemToView:
                self.blockItem.selectedItemToView = item
                if item is not None:
                    gridTable = self.GetTable()
                    for columnIndex in xrange (gridTable.GetNumberCols()):
                        self.SetColLabelValue (columnIndex, gridTable.GetColLabelValue (columnIndex))
                self.blockItem.postEventByName("SelectItemBroadcast", {'item':item})
        event.Skip()

    def OnSize(self, event):
        if not wx.GetApp().ignoreSynchronizeWidget:
            size = event.GetSize()
            widthMinusLastColumn = 0

            assert self.GetNumberCols() > 0, "We're assuming that there is at least one column"
            lastColumnIndex = self.GetNumberCols() - 1
            for column in xrange (lastColumnIndex):
                widthMinusLastColumn += self.GetColSize (column)
            lastColumnWidth = size.width - widthMinusLastColumn
            """
              Big fat hack. Since the grid is a scrolled window we set a border equal to the size
            of the scrollbar so the scroll bars won't show. Instead we should consider modifying
            grid adding a new style for not showing scrollbars.  Bug #2375
            """
            lastColumnWidth = lastColumnWidth - wx.SystemSettings_GetMetric(wx.SYS_VSCROLL_X)
            # @@@ This does not work properly and needs to be looked at
            # Removing it for the single column case because it causes the
            # sidebar to grow indefinitely
            if lastColumnWidth > 0:
                self.SetColSize (lastColumnIndex, lastColumnWidth)
                self.ForceRefresh()
        event.Skip()

    def OnColumnDrag(self, event):
        if not wx.GetApp().ignoreSynchronizeWidget:
            columnIndex = event.GetRowOrCol()
            self.blockItem.columnWidths [columnIndex] = self.GetColSize (columnIndex)

    def OnItemDrag(self, event):
        self.SetDragData (self.blockItem.contents [event.GetRow()].itsUUID)

    def AddItem(self, itemUUID):
        item = self.findUUID(itemUUID)
        self.blockItem.contents.add (item)

    def OnRightClick(self, event):
        self.blockItem.DisplayContextMenu(event.GetPosition(),
                                          self.blockItem.contents [event.GetRow()])

    def wxSynchronizeWidget(self):
        """
          A Grid can't easily redisplay its contents, so we write the following
        helper function to readjust everything after the contents change
        """
        #Trim/extend the control's rows and update all values

        if self.blockItem.hideColumnHeadings:
            self.SetColLabelSize (0)
        else:
            """
              Should be using wx.grid.GRID_DEFAULT_COL_LABEL_HEIGHT, but
            it hasn't been wrapped yet -- DJA
            """
            self.SetColLabelSize (20)

        gridTable = self.GetTable()
        newRows = gridTable.GetNumberRows()
        newColumns = gridTable.GetNumberCols()

        self.BeginBatch()
        for current, new, deleteMessage, addMessage in [
            (self.currentRows, newRows, wx.grid.GRIDTABLE_NOTIFY_ROWS_DELETED, wx.grid.GRIDTABLE_NOTIFY_ROWS_APPENDED), 
            (self.currentColumns, newColumns, wx.grid.GRIDTABLE_NOTIFY_COLS_DELETED, wx.grid.GRIDTABLE_NOTIFY_COLS_APPENDED)]: 
                if new < current: 
                    message = wx.grid.GridTableMessage (gridTable, deleteMessage, new, current-new) 
                    self.ProcessTableMessage (message) 
                elif new > current: 
                    message = wx.grid.GridTableMessage (gridTable, addMessage, new-current) 
                    self.ProcessTableMessage (message) 
        self.currentRows = newRows
        self.currentColumns = newColumns
        # update all column widths but the last one
        widthMinusLastColumn = 0
        for columnIndex in xrange (newColumns - 1):
            widthMinusLastColumn += self.blockItem.columnWidths[columnIndex]
            self.SetColSize (columnIndex, self.blockItem.columnWidths [columnIndex])

        # update the last column to fill the rest of the widget
        remaining = self.GetSize().width - widthMinusLastColumn
        """
          Big fat hack. Since the grid is a scrolled window we set a border equal to the size
        of the scrollbar so the scroll bars won't show. Instead we should consider modifying
        grid adding a new style for not showing scrollbars.  Bug #2375
        """
        remaining = remaining - wx.SystemSettings_GetMetric(wx.SYS_VSCROLL_X)
        if remaining > 0:
            self.SetColSize(newColumns - 1, remaining)
        
        self.ClearSelection()
        for range in self.blockItem.selection:
            if range [2]:
                self.SelectBlock (range[0], 0, range[1], newColumns, True)
            else:
                for row in xrange (range[0], range[1] + 1):
                    self.DeselectRow (row)
        self.EndBatch() 

        #Update all displayed values
        message = wx.grid.GridTableMessage (gridTable, wx.grid.GRIDTABLE_REQUEST_VIEW_GET_VALUES) 
        self.ProcessTableMessage (message) 
        self.ForceRefresh () 
        try:
            row = self.blockItem.contents.index (self.blockItem.selectedItemToView)
        except ValueError:
            pass
        else:
            self.MakeCellVisible (row, 0)

    def GoToItem(self, item):
        if item != None:
            try:
                row = self.blockItem.contents.index (item)
            except ValueError:
                item = None
        if item is not None:
            self.blockItem.selection.append ([row, row, True])
            self.blockItem.selectedItemToView = item
            self.SelectBlock (row, 0, row, self.GetColumnCount() - 1)
            self.MakeCellVisible (row, 0)
        else:
            self.blockItem.selection = []
            self.blockItem.selectedItemToView = None
            self.ClearSelection()
        self.blockItem.postEventByName("SelectItemBroadcast", {'item':item})

    def DeleteSelection (self):
        self.blockItem.contents.beginUpdate()
        topLeftList = self.GetSelectionBlockTopLeft()
        bottomRightList = self.GetSelectionBlockBottomRight()
        """
          Clear the selection before removing the elements from the collection
        otherwise our delegate will get called asking for deleted items
        """
        self.ClearSelection()
        selectionRanges = []
        for topLeft in topLeftList:
            bottomRight = bottomRightList.pop (0)
            selectionRanges.append ([topLeft[0], bottomRight[0]])
        selectionRanges.sort()
        selectionRanges.reverse()
        contents = self.blockItem.contents
        for range in selectionRanges:
            for row in xrange (range[1], range [0] - 1, -1):
                contents.remove (contents [row])
        self.blockItem.selection = []
        self.blockItem.selectedItemToView = None
        self.blockItem.itsView.commit()
        self.blockItem.contents.endUpdate()
        self.blockItem.postEventByName("SelectItemBroadcast", {'item':None})


class GridCellAttributeRenderer (wx.grid.PyGridCellRenderer):
    def __init__(self, type):
        super (GridCellAttributeRenderer, self).__init__ ()
        self.delegate = IAttributeEditor.GetAttributeEditorSingleton (type)

    def SetTextColorsAndFont (self, grid, attr, dc, isSelected):
        """
          Set the text foreground, text background, brush and font into the dc
        """
        if grid.IsEnabled():
            if isSelected:
                background = grid.GetSelectionBackground()
                foreground = grid.GetSelectionForeground()
            else:
                background = attr.GetBackgroundColour()
                foreground = attr.GetTextColour()
        else:
            background = wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNFACE)
            foreground = wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT)
        dc.SetTextBackground (background)
        dc.SetTextForeground (foreground)
        dc.SetBrush (wx.Brush (background, wx.SOLID))

        dc.SetFont (attr.GetFont())

    def Draw (self, grid, attr, dc, rect, row, column, isSelected):
        """
          Currently only handles left justified multiline text
        """
        self.SetTextColorsAndFont (grid, attr, dc, isSelected)
        item, attributeName = grid.GetElementValue (row, column)
        self.delegate.Draw (dc, rect, item, attributeName, isSelected)


class GridCellAttributeEditor (wx.grid.PyGridCellEditor):
    def __init__(self, type):
        super (GridCellAttributeEditor, self).__init__ ()
        self.delegate = IAttributeEditor.GetAttributeEditorSingleton (type)

    def Create (self, parent, id, evtHandler):
        """
          Create an edit control to edit the text
        """
        self.control = self.delegate.Create (parent, id) # create Attribute Editor control
        self.SetControl (self.control)
        if evtHandler:
            self.control.PushEventHandler (evtHandler)

    def PaintBackground (self, *arguments, **keywords):
        """
          background drawing is done by the edit control
        """
        pass

    def BeginEdit (self, row,  column, grid):
        item, attributeName = grid.GetElementValue (row, column)
        self.initialValue = self.delegate.GetAttributeValue (item, attributeName)
        self.delegate.BeginControlEdit (self.control, self.initialValue)

    def EndEdit (self, row, column, grid):
        value = self.delegate.GetControlValue (self.control)
        item, attributeName = grid.GetElementValue (row, column)
        if value == self.initialValue:
            changed = False
        # @@@ For now we do not want to allow users to blank out fields.  This should eventually be
        #  replaced by proper editor validation.
        elif value.strip() == '':
            changed = False
        else:
            changed = True
            # set the value using the delegate's setter, if it has one.
            try:
                attributeSetter = self.delegate.SetAttributeValue
            except AttributeError:
                grid.SetElementValue (row, column, value)
            else:
                attributeSetter (item, attributeName, value)
        self.delegate.EndControlEdit (item, attributeName, self.control)
        return changed

    def Reset (self):
        self.delegate.SetControlValue (self.control, self.initialValue)

    def GetValue (self):
        return self.delegate.GetControlValue (self.control)


class ImageRenderer (wx.grid.PyGridCellRenderer):
    def Draw (self, grid, attr, dc, rect, row, col, isSelected):
        imageName = grid.GetTable().GetValue (row, col)
        image = wx.GetApp().GetImage (imageName)

        if image:
            offscreenBuffer = wx.MemoryDC()
    
            offscreenBuffer.SelectObject (image)
    
            dc.SetBackgroundMode (wx.SOLID)
    
            if isSelected:
                dc.SetBrush (wx.Brush (grid.GetSelectionBackground(), wx.SOLID))
                dc.SetPen (wx.Pen (grid.GetSelectionBackground(), 1, wx.SOLID))
            else:
                dc.SetBrush (wx.Brush (attr.GetBackgroundColour(), wx.SOLID))
                dc.SetPen (wx.Pen (attr.GetBackgroundColour(), 1, wx.SOLID))
     
            dc.DrawRectangleRect(rect)
    
            width, height = image.GetWidth(), image.GetHeight()
    
            if width > rect.width - 2:
                width = rect.width - 2
    
            if height > rect.height - 2:
                height = rect.height - 2
    
            dc.Blit ((rect.x + 1, rect.y + 1),
                     (width, height),
                     offscreenBuffer,
                     (0, 0),
                     wx.COPY,
                     True)

class Table (RectangularChild):
    def __init__(self, *arguments, **keywords):
        super (Table, self).__init__ (*arguments, **keywords)

    def instantiateWidget (self):
        return wxTable (self.parentBlock.widget, Block.getWidgetID(self))

    def onSetContentsEvent (self, event):
        item = event.arguments ['item']
        if isinstance (item, ItemCollection):
            self.contents = item

    def onSelectItemEvent (self, event):
        item = event.arguments ['item']
        if item != self.selectedItemToView:
            self.selectedItemToView = item
            row = -1
            if item is not None:
                try:
                    row = self.contents.index (item)
                except ValueError:
                    pass
            if row < 0:
                self.widget.ClearSelection()
            else:
                self.widget.SelectBlock (row, 0, row, self.widget.GetColumnCount() - 1)
                self.widget.MakeCellVisible (row, 0)
            self.postEventByName("SelectItemBroadcast", {'item':item})

    def onDeleteEvent (self, event):
        self.widget.DeleteSelection()
        
    def onDeleteEventUpdateUI (self, event):
        event.arguments ['Enable'] = len (self.selection) != 0

class RadioBox(RectangularChild):
    def instantiateWidget(self):
        if self.radioAlignEnum == "Across":
            dimension = wx.RA_SPECIFY_COLS
        elif self.radioAlignEnum == "Down":
            dimension = wx.RA_SPECIFY_ROWS
        elif __debug__:
            assert False, "unknown radioAlignEnum"
                                    
        return wx.RadioBox (self.parentBlock.widget,
                            -1,
                            self.title,
                            wx.DefaultPosition, 
                            (self.minimumSize.width, self.minimumSize.height),
                            self.choices, self.itemsPerLine, dimension)

class wxStaticText(ShownSynchronizer, wx.StaticText):
    pass

class StaticText(RectangularChild):
    def instantiateWidget (self):
        if self.textAlignmentEnum == "Left":
            style = wx.ALIGN_LEFT
        elif self.textAlignmentEnum == "Center":
            style = wx.ALIGN_CENTRE
        elif self.textAlignmentEnum == "Right":
            style = wx.ALIGN_RIGHT

        staticText = wxStaticText (self.parentBlock.widget,
                                   -1,
                                   self.title,
                                   wx.DefaultPosition,
                                   (self.minimumSize.width, self.minimumSize.height),
                                   style)

        staticText.SetFont(Font (self.characterStyle))
        return staticText

    
class wxStatusBar (ShownSynchronizer, wx.StatusBar):
    def __init__(self, *arguments, **keyWords):
        super (wxStatusBar, self).__init__ (*arguments, **keyWords)
        self.gauge = wx.Gauge(self, -1, 100, size=(125, 30), style=wx.GA_HORIZONTAL|wx.GA_SMOOTH)
        self.gauge.Show(False)

    def Destroy(self):
        self.blockItem.getFrame().SetStatusBar(None)
        super (wxStatusBar, self).Destroy()
        
    def wxSynchronizeWidget(self):
        super (wxStatusBar, self).wxSynchronizeWidget()
        self.blockItem.getFrame().Layout()


class StatusBar(Block):
    def instantiateWidget (self):
        frame = self.getFrame()
        widget = wxStatusBar (frame, Block.getWidgetID(self))
        frame.SetStatusBar (widget)
        return widget

    def setStatusMessage(self, statusMessage, progressPercentage=-1):
        """
          Allows you to set the message contained in the status bar.  You can also specify 
        values for the progress bar contained on the right side of the status bar.  If you
        specify a progressPercentage (as a float 0 to 1) the progress bar will appear.  If 
        no percentage is specified the progress bar will disappear.
        """
        if progressPercentage == -1:
            if self.widget.GetFieldsCount() != 1:
                self.widget.SetFieldsCount(1)
            self.widget.SetStatusText(statusMessage)
            self.widget.gauge.Show(False)
        else:
            if self.widget.GetFieldsCount() != 2:
                self.widget.SetFieldsCount(2)
                self.widget.SetStatusWidths([-1, 150])
            if statusMessage is not None:
                self.widget.SetStatusText(statusMessage)
            self.widget.gauge.Show(True)
            self.widget.gauge.SetValue((int)(progressPercentage*100))
            # By default widgets are added to the left side...we must reposition them
            rect = self.widget.GetFieldRect(1)
            self.widget.gauge.SetPosition((rect.x+2, rect.y+2))
                            
    def onShowHideEvent(self, event):
        self.isShown = not self.isShown
        self.synchronizeWidget()


"""
  To use the TreeAndList you must provide a delegate to perform access
to the data that is displayed. 
  You might be able to subclass ListDelegate and implement the following methods:

class TreeAndListDelegate (ListDelegate):

    def GetElementParent(self, element):

    def GetElementChildren(self, element):

    def GetElementValues(self, element):

    def ElementHasChildren(self, element):
        
    Optionally override GetColumnCount and GetColumnHeading
"""


class wxTreeAndList(DraggableWidget):
    def __init__(self, *arguments, **keywords):
        super (wxTreeAndList, self).__init__ (*arguments, **keywords)
        self.Bind(wx.EVT_TREE_ITEM_EXPANDING, self.OnExpanding, id=self.GetId())
        self.Bind(wx.EVT_TREE_ITEM_COLLAPSING, self.OnCollapsing, id=self.GetId())
        self.Bind(wx.EVT_LIST_COL_END_DRAG, self.OnColumnDrag, id=self.GetId())
        self.Bind(wx.EVT_TREE_SEL_CHANGED, self.OnWXSelectItem, id=self.GetId())
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_TREE_BEGIN_DRAG, self.OnItemDrag)

    def OnInit (self):
        mixinAClass (self, self.blockItem.elementDelegate)
        
    def OnSize(self, event):
        if not wx.GetApp().ignoreSynchronizeWidget:
            if isinstance (self, wx.gizmos.TreeListCtrl):
                size = self.GetClientSize()
                widthMinusLastColumn = 0
                assert self.GetColumnCount() > 0, "We're assuming that there is at least one column"
                for column in xrange (self.GetColumnCount() - 1):
                    widthMinusLastColumn += self.GetColumnWidth (column)
                lastColumnWidth = size.width - widthMinusLastColumn
                if lastColumnWidth > 0:
                    self.SetColumnWidth (self.GetColumnCount() - 1, lastColumnWidth)
            else:
                assert isinstance (self, wx.TreeCtrl), "We're assuming the only other choice is a wx.Tree"
        event.Skip()

    def OnExpanding(self, event):
        if not wx.GetApp().ignoreSynchronizeWidget:
            self.LoadChildren(event.GetItem())

    def LoadChildren(self, parentId):
        """
          Load the items in the tree only when they are visible.
        """
        child, cookie = self.GetFirstChild (parentId)
        if not child.IsOk():

            parentUUID = self.GetItemData(parentId).GetData()
            for child in self.GetElementChildren (wx.GetApp().UIRepositoryView [parentUUID]):
                cellValues = self.GetElementValues (child)
                childNodeId = self.AppendItem (parentId,
                                               cellValues.pop(0),
                                               -1,
                                               -1,
                                               wx.TreeItemData (child.itsUUID))
                index = 1
                for value in cellValues:
                    self.SetItemText (childNodeId, value, index)
                    index += 1
                self.SetItemHasChildren (childNodeId, self.ElementHasChildren (child))
 
            self.blockItem.openedContainers [parentUUID] = True

    def OnCollapsing(self, event):
        id = event.GetItem()
        """
          if the data passed in has a UUID we'll keep track of the
        state of the opened tree
        """
        del self.blockItem.openedContainers [self.GetItemData(id).GetData()]
        self.DeleteChildren (id)

    def OnColumnDrag(self, event):
        if not wx.GetApp().ignoreSynchronizeWidget:
            columnIndex = event.GetColumn()
            try:
                self.blockItem.columnWidths [columnIndex] = self.GetColumnWidth (columnIndex)
            except AttributeError:
                pass

    def OnWXSelectItem(self, event):
        if not wx.GetApp().ignoreSynchronizeWidget:
    
            itemUUID = self.GetItemData(self.GetSelection()).GetData()
            selection = self.blockItem.find (itemUUID)
            if self.blockItem.selection != selection:
                self.blockItem.selection = selection
        
                self.blockItem.postEventByName("SelectItemBroadcast", {'item':selection})
        event.Skip()

    def OnItemDrag(self, event):
        self.SetDragData (self.GetItemData(event.GetItem()).GetData())
        
    def wxSynchronizeWidget(self):
        def ExpandContainer (self, openedContainers, id):
            try:
                expand = openedContainers [self.GetItemData(id).GetData()]
            except KeyError:
                pass
            else:
                self.LoadChildren(id)

                self.Expand(id)

                child, cookie = self.GetFirstChild (id)
                while child.IsOk():
                    ExpandContainer (self, openedContainers, child)
                    child = self.GetNextSibling (child)

        try:
            self.blockItem.columnWidths
        except AttributeError:
            pass # A wx.TreeCtrl won't use columnWidths
        else:
            for index in xrange(wx.gizmos.TreeListCtrl.GetColumnCount(self)):
                self.RemoveColumn (0)
    
            for index in xrange (self.GetColumnCount()):
                info = wx.gizmos.TreeListColumnInfo()
                info.SetText (self.GetColumnHeading (index, None))
                info.SetWidth (self.blockItem.columnWidths [index])
                self.AddColumnInfo (info)

        self.DeleteAllItems()

        root = self.blockItem.rootPath
        if not root:
            root = self.GetElementChildren (None)
        cellValues = self.GetElementValues (root)
        rootNodeId = self.AddRoot (cellValues.pop(0),
                                   -1,
                                   -1,
                                   wx.TreeItemData (root.itsUUID))        
        index = 1
        for value in cellValues:
            self.SetItemText (rootNodeId, value, index)
            index += 1
        self.SetItemHasChildren (rootNodeId, self.ElementHasChildren (root))
        self.LoadChildren (rootNodeId)
        ExpandContainer (self, self.blockItem.openedContainers, rootNodeId)

        selection = self.blockItem.selection
        if not selection:
            selection = root
        self.GoToItem (selection)
        
    def GoToItem(self, item):
        def ExpandTreeToItem (self, item):
            parent = self.GetElementParent (item)
            if parent:
                id = ExpandTreeToItem (self, parent)
                self.LoadChildren(id)
                if self.IsVisible(id):
                    self.Expand (id)
                itemUUID = item.itsUUID
                child, cookie = self.GetFirstChild (id)
                while child.IsOk():
                    if self.GetItemData(child).GetData() == itemUUID:
                        return child
                    child = self.GetNextSibling (child)
                assert False, "Didn't find the item in the tree"
                return None
            else:
                return self.GetRootItem()

        id = ExpandTreeToItem (self, item)
        self.SelectItem (id)
        self.ScrollTo (id)

    def CalculateWXStyle(theClass, block):
        style = wx.TR_DEFAULT_STYLE|wx.NO_BORDER
        if block.hideRoot:
            style |= wx.TR_HIDE_ROOT
        if block.noLines:
            style |= wx.TR_NO_LINES
        if block.useButtons:
            style |= wx.TR_HAS_BUTTONS
        else:
            style |= wx.TR_NO_BUTTONS
        return style
    CalculateWXStyle = classmethod(CalculateWXStyle)
        
 
class wxTree(wxTreeAndList, wx.TreeCtrl):
    pass
    

class wxTreeList(wxTreeAndList, wx.gizmos.TreeListCtrl):
    pass


class Tree(RectangularChild):
    def instantiateWidget(self):
        try:
            self.columnWidths
        except AttributeError:
            tree = wxTree (self.parentBlock.widget, Block.getWidgetID(self), 
                           style=wxTreeAndList.CalculateWXStyle(self))
        else:
            tree = wxTreeList (self.parentBlock.widget, Block.getWidgetID(self), 
                               style=wxTreeAndList.CalculateWXStyle(self))
        return tree

    def onSelectItemEvent (self, event):
        self.widget.GoToItem (event.arguments['item'])
                            

class wxItemDetail(wx.html.HtmlWindow):
    def OnLinkClicked(self, wx_linkinfo):
        """
          Clicking on an item changes the selection (post event).
          Clicking on a URL loads the page in a separate browser.
        """
        itemURL = wx_linkinfo.GetHref()
        item = self.blockItem.findPath(itemURL)
        if not item:
            webbrowser.open(itemURL)
        else:
            self.blockItem.postEventByName("SelectItemBroadcast", {'item':item})

    def wxSynchronizeWidget(self):
        if self.blockItem.selection is not None:
            self.SetPage (self.blockItem.getHTMLText (self.blockItem.selection))
        else:
            self.SetPage('<html><body></body></html>')


class ItemDetail(RectangularChild):
    def __init__(self, *arguments, **keywords):
        super (ItemDetail, self).__init__ (*arguments, **keywords)
        self.selection = None

    def instantiateWidget (self):
        return wxItemDetail (self.parentBlock.widget,
                             Block.getWidgetID(self),
                             wx.DefaultPosition,
                             (self.minimumSize.width,
                              self.minimumSize.height))

    def getHTMLText(self, item):
        return '<body><html><h1>%s</h1></body></html>' % item.getDisplayName()

    def onSelectItemEvent (self, event):
        """
          Display the item in the wxWidget.
        """
        self.selection = event.arguments['item']
        self.synchronizeWidget ()

    
class ContentItemDetail(BoxContainer):
    """
    ContentItemDetail
    Any container block in the Content Item's Detail View hierarchy.
    Not to be confused with ItemDetail (above) which uses an HTML-based widget.
    Keeps track of the current selected item
    Supports Color Style
    """
    
    def synchronizeWidget (self):
        super(ContentItemDetail, self).synchronizeWidget()
        if not wx.GetApp().ignoreSynchronizeWidget:
            self.synchronizeColor()
        
    def synchronizeColor (self):
        # if there's a color style defined, syncronize the color
        if self.hasAttributeValue("colorStyle"):
            self.colorStyle.synchronizeColor(self)
           
class wxPyTimer(wx.PyTimer):
    """ 
    A wx.PyTimer that has an IsShown() method, like all the other widgets
    that blocks deal with; it also generates its own event from Notify
    """              
    def IsShown(self):
        return True
    
    def Notify(self):
        event = wx.PyEvent()
        event.SetEventType(wx.wxEVT_TIMER)
        event.SetId(Block.getWidgetID(self.blockItem))
        wx.GetApp().OnCommand(event)

    def __del__(self):
       Block.wxOnDestroyWidget (self)

class Timer(Block):
    """
    A Timer block. Fires (sending a BlockEvent) at a particular time.
    A passed time will fire "shortly".
    """
    def instantiateWidget (self):
        timer = wxPyTimer(self.parentBlock.widget)
        return timer

    def setFiringTime(self, when):
        # First turn off the old timer
        timer = self.widget
        timer.Stop()

        # Set the new time, if we have one. If it's in the past, fire "really soon". If it's way in the future,
        # don't bother firing.
        if when is not None:
            millisecondsUntilFiring = (when - mx.DateTime.now()).seconds * 1000                
            if millisecondsUntilFiring < 100:
                millisecondsUntilFiring = 100
            elif millisecondsUntilFiring > sys.maxint:
                millisecondsUntilFiring = sys.maxint

            # print "*** setFiringTime: will fire at %s in %s minutes" % (when, millisecondsUntilFiring / 60000)
            timer.Start(millisecondsUntilFiring, True)
        else:
            # print "*** setFiringTime: No new time."
            pass

"""
Attribute Editor Block

This Block uses the type of the attribute to determine how to display itself. 

Issues
------
* Item Location.  I'm trying to use the "contents" attribute on Block to find 
    the Item, but "contents" isn't set up yet by the Detail View.  I'm currently 
    using a Hack that knows about how the Detail View finds the selected item.

* Attribute Location.  Currently using  "viewAttribute" attribute.

* Finalization.  We're relying on EVT_KILL_FOCUS to know when to end editing.  We 
    know the Detail View doesn't always operate in ways that cause this to be reliable,
    but I think these problems can be fixed there.

"""

class wxAEBlock(wxRectangularChild):
    """
      Widget that invokes an Attribute Editor for a Block.
    """
    def __init__(self, *arguments, **keywords):
        super (wxAEBlock, self).__init__ (*arguments, **keywords)

        # set minimum size hints
        minW, minH = arguments[-1] # assumes minimum size passed as last arg
        self.SetSizeHints(minW=minW, minH=minH)

        # install event handlers
        self.Bind(wx.EVT_LEFT_DOWN, self.onClick)
        self.Bind(wx.EVT_PAINT, self.OnPaint)

        # init python attributes
        self.editor = None  # remembers the current attribute editor
        self.control = None  # remembers the instantiated edit control widget

    def wxSynchronizeWidget(self):
        """
           Synchronize the current value from the widget with the data model.
        """
        # superclass sync will handle shown-ness
        super(wxAEBlock, self).wxSynchronizeWidget()

        block = self.blockItem
        if not block.isShown:
            self.destroyControl()
            return

        # lookup the appropriate editor
        # could do the lookup at init time, but then value-based lookups won't be right.
        editor = self.blockItem.lookupEditor()
        if editor is not self.editor:
            self.destroyControl()
        self.editor = editor

        # redraw
        self.redrawAEBlock()

    def onClick(self, event):
        """
          A click has occured.  Prepare to edit the value, if editable.
        """
        # if already created a control, then return
        if self.control is not None:
            return

        # consume the event
        event.Skip()

        # return if editing is not allowed
        block = self.blockItem
        if block.readOnly:  # the block could be readOnly
            return
        editor = self.editor
        item = block.getItem()
        attribute = block.getAttributeName()
        if editor.ReadOnly ((item, attribute)):  # The editor might not allow editing
            return

        # create the control to use for editing
        self.createControl()

        # begin editing
        curValue = editor.GetAttributeValue(item, attribute)
        editor.BeginControlEdit(self.control, curValue)

        # redraw
        self.redrawAEBlock()

    def OnPaint(self, paintEvent):
        """
          Need to update a portion of ourself.  Ask the control to draw in the update region.
        """
        paintDC = wx.PaintDC(self)
        paintDC.SetBrush (wx.TRANSPARENT_BRUSH)
        self.drawAEBlock(paintDC)

    def redrawAEBlock(self):
        """
          Redraw the control.  

        If editable, a control exists, and it will redraw itself.  
        Otherwise we call the Attribute Editor to do the drawing.
        """
        clientDC = wx.ClientDC(self)
        clientDC.SetBrush (wx.TRANSPARENT_BRUSH)
        self.drawAEBlock(clientDC)

    def drawAEBlock(self, dc):
        block = self.blockItem
        if block.isShown: 
            item = block.getItem ()
            if item is not None:
                blockRect = self.GetRect() # use the rect of the AE Block
                rect = wx.Rect(0, 0, blockRect.width, blockRect.height)
                attributeName = block.getAttributeName()
                isSelected = self.control is not None
                self.ensureEditor()
                font = self.GetFont()
                dc.SetFont(font)
                self.editor.Draw(dc, rect, item, attributeName, isSelected)

    def ensureEditor(self):
        if self.editor is None:
            self.editor = self.blockItem.lookupEditor()

    def createControl(self):
        # create the control to use for editing
        control = self.editor.Create(self.blockItem.widget, -1)
        control.Bind(wx.EVT_KILL_FOCUS, self.onLoseFocusFromControl)
        self.control = control # remember the widget created (aka the control)

    def destroyControl(self):
        if self.control is None:
            return
        wx.CallAfter(self.control.Destroy) # destroy this control next idle.
        self.control = None

    def onLoseFocusFromControl(self, event):
        """
          The control lost focus - we're finishing editing in the control.
        """
        # return if there's no control
        if self.control is None:
            return

        item = self.blockItem.getItem()
        attributeName = self.blockItem.getAttributeName()
        self.editor.EndControlEdit(item, attributeName, self.control)
        self.destroyControl()

        self.wxSynchronizeWidget() #resync, so we'll draw without the control.
        event.Skip()

class AEBlock(RectangularChild):
    """
      Attribute Editor Block
    
      Instantiates an Attribute Editor that's appropriate for the
    attribute specified in this block.
    """

    def instantiateWidget(self):
        """
          Create the Attribute Editor shell widget, that defines the
        drawing world that the actual Attribute Editor will live within.
        """
        widget = wxAEBlock (self.parentBlock.widget,
                            -1,
                            wx.DefaultPosition,
                            (self.minimumSize.width, self.minimumSize.height))
        widget.SetFont(Font (self.characterStyle))
        return widget

    def lookupEditor(self):
        # get the Attribute Editor for this Type
        typeName = self.getItemAttributeTypeName()
        item = self.getItem()
        attributeName = self.getAttributeName()
        try:
            presentationStyle = self.presentationStyle
        except AttributeError:
            presentationStyle = None
        selectedEditor = IAttributeEditor.GetAttributeEditorInstance (typeName, 
                                        item, attributeName, presentationStyle)
        return selectedEditor

    def getItem(self):
        # Get the Item connected to this block
        try:
            item = self.contents
        except AttributeError:
            try:
                item = self.detailRoot().selectedItem() # @@@DLD fix Detail-View specific code
            except AttributeError:
                item = None
        return item

    def getAttributeName(self):
        attributeName = self.viewAttribute
        return attributeName

    def getItemAttributeTypeName(self):
        # Get the type of the current attribute
        item = self.getItem()
        if item is None:
            return None

        # if the attribute has a value, use it's type's name
        attributeName = self.getAttributeName()
        try:
            attrValue = getattr(item, attributeName)
            typeName = type(attrValue).__name__
        except:

            # if the attribute has no value, we must use the schema to determine type
            try:
                theType = item.getAttributeAspect(attributeName, "type")
            except:
                typeName = "_default"
            else:
                typeName = theType.itsName
        return typeName

