import application.Globals as Globals
from Block import Block
from wxPython.wx import *

class MenuEntry(Block):
    pass

    def rebuildMenus (self, startingAtBlock):
        """
          Rebuild the menus, starting with the any menus that
        are children of startingAtBlock, and proceeding up
        all the parents.
        """
        
        from OSAF.framework.blocks.MenuBlocks import Menu, MenuEntry

        def buildMenuList (block, data):
            """
               buildMenuList collects all the data about the menus by
            scanning all the blocks and their parents looking for menu
            blocks, keeping track of the things in the dictionary named
            "data".
            
              Menu's are identified by their itemName rather than
            their UUIDs. This requires itemNames to be unique across all
            items and that nesting blocks be aware of the names of
            the menus in their parent blocks.
            """
            parent = block.parentBlock
            if (parent):
                buildMenuList (parent, data)

            """
              Initialize data if it's empty
            """
            if len (data) == 0:
                data['mainMenu'] = []
                data['nameToItemIndex'] = {}
                data['nameToMenuList'] = {}

            nameToItemIndex = data['nameToItemIndex']
            nameToMenuList = data['nameToMenuList']
            for child in block.childrenBlocks:
                if isinstance (child, MenuEntry):
                    """
                      Use menuLocation to look up the menu that
                    contains the item or menu
                    """
                    if child.menuLocation:
                        """
                          If you get an exception here, it's probably because
                        the name of menuLocation isn't the name of an existing
                        menu.
                        """
                        menu = nameToMenuList [child.menuLocation]
                    else:
                        menu = data['mainMenu']
                    
                    name = child.getItemName()
                    if child.operation == 'InsertBefore':
                        try:
                            index = menu.index (name)
                        except ValueError:
                            index = len (menu)
                        menu.insert (index, name)
                    elif child.operation == 'Replace':
                        menu[menu.index (name)] = name
                    elif child.operation == 'Delete':
                        menu.remove (name)
                    else:
                       assert (False)
                    
                    if child.operation != 'Delete':
                        # Shouldn't have items with the same name
                        assert not nameToItemIndex.has_key (name)  
                        nameToItemIndex[name] = child
                        if isinstance (child, Menu):
                            nameToMenuList[name] = []
            
        data = {}
        buildMenuList (startingAtBlock, data)
        
        frame = Globals.wxApplication.mainFrame
        if frame:
            menuBar = frame.GetMenuBar()
            if not menuBar:
                menuBar = wxMenuBar()
                frame.SetMenuBar(menuBar)
            """
              The actual work of setting the menus is done by installMenu
            """
            self.installMenu (data['mainMenu'], menuBar, data)
    rebuildMenus = classmethod (rebuildMenus)


    def installMenu (cls, menuList, wxMenuObject, data):
        nameToItemIndex = data['nameToItemIndex']
        oldMenuList = cls.getMenuItems (wxMenuObject)
        for index in xrange (len (menuList)):
            menuItemName = menuList [index]
            menuItem = nameToItemIndex [menuItemName]
            try:
                oldItem = oldMenuList.pop(0)
            except IndexError:
                oldItem = None
            wxMenuItem = menuItem.renderMenuEntry (wxMenuObject, index, oldItem)
            if wxMenuItem:
                nameToMenuList = data['nameToMenuList']
                cls.installMenu (nameToMenuList[menuItemName], wxMenuItem, data)
 
        for oldItem in oldMenuList:
            cls.deleteItem (wxMenuObject, index, oldItem)
    installMenu = classmethod (installMenu)

    
    """
      wxWindows doesn't implement convenient menthods for dealing
    with menus, so we'll write our own: getMenuItems, deleteItem
    getItemTitle, and setMenuItem
    """
    def getMenuItems (cls, wxMenuObject):
        """
          Returns a list of wxMenuItems in wxMenuObject, which can
        be either a menu or menubar
        """
        if isinstance (wxMenuObject, wxMenuPtr):
            menuList = wxMenuObject.GetMenuItems()
        else:
            assert isinstance (wxMenuObject, wxMenuBarPtr)
            menuList = []
            for index in xrange (wxMenuObject.GetMenuCount()):
                menuList.append (wxMenuObject.GetMenu (index))
        return menuList
    getMenuItems = classmethod (getMenuItems)


    def deleteItem (cls, wxMenuObject, index, oldItem):
        """
          Deletes an item from a wxMenuObject, where wxMenuObject can
        be either a menu or menubar. Unfortunately, wxWindows requires
        that you pass the oldItem whenever wxMenuObject is a wxMenu.
        """
        if isinstance (wxMenuObject, wxMenuPtr):
            wxMenuObject.DestroyItem (oldItem)
            pass
        else:
            assert isinstance (wxMenuObject, wxMenuBarPtr)
            oldMenu = wxMenuObject.Remove (index)
            assert oldMenu == oldItem
            oldMenu.Destroy()
    deleteItem = classmethod (deleteItem)

 
    def getItemTitle (cls, wxMenuObject, index, item):
        """
          Gets the title of the item at index in wxMenuObject, where
        wxMenuObject can be either a menu or menubar. Unfortunately,
        wxWindows requires that you pass the oldItem whenever
        wxMenuObject is a wxMenu.
        """
        title = None
        if item:
            if isinstance (wxMenuObject, wxMenuPtr):
                id = item.GetId()
                title = wxMenuObject.GetLabel (id)
            else:
                assert isinstance (wxMenuObject, wxMenuBarPtr)
                title = wxMenuObject.GetLabelTop (index)
            return title
    getItemTitle = classmethod (getItemTitle)

 
    def setMenuItem (self, wxMenuObject, newItem, oldItem, index):
        """
          Sets an item in wxMenuObject, which can be either a menu or
        menubar with a new item. Unfortunately, wxWindows requires that
        you pass the oldItem whenever wxMenuObject is a wxMenu and
        you're replacing the item.
        """
        if isinstance (wxMenuObject, wxMenuPtr):
            itemsInMenu = wxMenuObject.GetMenuItemCount()
            assert (index <= itemsInMenu)
            if index < itemsInMenu:
                wxMenuObject.DestroyItem (oldItem)
                pass
            success = wxMenuObject.InsertItem (index, newItem)
            assert success
        else:
            assert isinstance (wxMenuObject, wxMenuBarPtr)
            itemsInMenu = wxMenuObject.GetMenuCount()
            assert (index <= itemsInMenu)
            if index < itemsInMenu:
                oldMenu = wxMenuObject.Replace (index, newItem, self.title)
                assert oldMenu == oldItem
                oldMenu.Destroy()
            else:
                success = wxMenuObject.Append (newItem, self.title)
                assert success


class MenuItem(MenuEntry):
    def renderMenuEntry(self, wxMenuObject, index, oldItem):
        """
          You can't put a MenuItem into anything besides a wxMenu,
        e.g. a MenuBar.
        """
        assert isinstance (wxMenuObject, wxMenu)

        if self.menuItemKind == "Separator":
            id = wxID_SEPARATOR
            kind = wxITEM_SEPARATOR
        else:
            """
              Menu items must have an event, otherwise they can't cause any action,
            nor can we use wxWindows api's to distinguish them from each other.
            """
            assert self.hasAttributeValue('event')
            id = self.event.getwxID()
            if self.menuItemKind == "Normal":
                kind = wxITEM_NORMAL
            elif self.menuItemKind == "Check":
                kind = wxITEM_CHECK
            elif self.menuItemKind == "Radio":
                kind = wxITEM_RADIO
            else:
                assert (False)        
        if oldItem == None or oldItem.GetId() != id or oldItem.GetKind() != kind:
            title = self.title
            if len(self.accel) > 0:
                title = title + "\tCtrl+" + self.accel

            newItem = wxMenuItem (wxMenuObject, id, title, self.helpString, kind)
            self.setMenuItem (wxMenuObject, newItem, oldItem, index)
        return None


class Menu(MenuEntry):
    def renderMenuEntry(self, wxMenuObject, index, oldItem):
        title = self.getItemTitle (wxMenuObject, index, oldItem)
        if title != self.title:
            newItem = wxMenu()
            self.setMenuItem (wxMenuObject, newItem, oldItem, index)
            return newItem
        else:
            return oldItem

        
