__version__ = "$Revision$"
__date__ = "$Date$"
__copyright__ = "Copyright (c) 2004-2005 Open Source Applications Foundation"
__license__ = "http://osafoundation.org/Chandler_0.1_license_terms.htm"

import sys
import application
import osaf.framework.blocks.Block as Block
import osaf.framework.blocks.DynamicContainerBlocks as DynamicContainerBlocks
import osaf.framework.blocks.ControlBlocks as ControlBlocks
import osaf.framework.sharing.Sharing as Sharing
import osaf.framework.blocks.Trunk as Trunk
import osaf.contentmodel.mail.Mail as Mail
import osaf.contentmodel.ContentModel as ContentModel
import osaf.contentmodel.ItemCollection as ItemCollection
import osaf.contentmodel.tasks.Task as Task
import osaf.contentmodel.calendar.Calendar as Calendar
import osaf.contentmodel.contacts.Contacts as Contacts
import osaf.contentmodel.Notes as Notes
import application.dialogs.Util as Util
import application.dialogs.AccountPreferences as AccountPreferences
import osaf.mail.constants as MailConstants
import osaf.mail.sharing as MailSharing
import osaf.mail.message as MailMessage
from repository.item.Item import Item
from repository.item.Query import KindQuery
import repository.item.Query as Query
import mx.DateTime as DateTime
import wx
import sets

"""
Detail.py
Classes for the ContentItem Detail View
"""

class DetailRoot (ControlBlocks.ContentItemDetail):
    """
      Root of the Detail View.
    """
    def onSetContentsEvent (self, event):
        self.selection = event.arguments['item']

    def onSelectItemEvent (self, event):
        """
          A DetailTrunk is an event boundary; this keeps all the events 
        sent between blocks of the Detail View to ourselves.
        """
        # Finish changes to previous selected item 
        self.finishSelectionChanges () 
        """
          Remember the new selected ContentItem.
        """
        self.selection = event.arguments['item']

        # Synchronize to this item; this'll swap in an appropriate detail trunk.
        self.synchronizeWidget()
        if __debug__:
            dumpSelectItem = False
            if dumpSelectItem:
                self.dumpShownHierarchy ('onSelectItemEvent')

    def selectedItem(self):
        # return the item being viewed
        return self.selection    

    def detailRoot (self):
        # we are the detail root object
        return self

    def synchronizeDetailView(self, item):
        """
          We have an event boundary inside us, which keeps all
        the events sent between blocks of the Detail View to
        ourselves.
          When we get a SelectItem event, we jump across
        the event boundary and call synchronizeItemDetail on each
        block to give it a chance to update the widget with data
        from the Item.
          Notify container blocks before their children.
          
          @@@DLD - find a better way to broadcast inside my boundary.
        """
        def reNotifyInside(block, item):
            notifySelf = len(block.childrenBlocks) == 0 # True if no children
            try:
                # process from the children up
                for child in block.childrenBlocks:
                    notifySelf = reNotifyInside (child, item) or notifySelf
            except AttributeError:
                pass
            try:
                syncMethod = type(block).synchronizeItemDetail
            except AttributeError:
                if notifySelf:
                    block.synchronizeWidget()
            else:
                notifySelf = syncMethod(block, item) or notifySelf
            return notifySelf

        children = self.childrenBlocks
        for child in children:
            child.isShown = item is not None
            reNotifyInside(child, item)
        wx.GetApp().needsUpdateUI = True

    if __debug__:
        def dumpShownHierarchy (self, methodName=''):
            """ Like synchronizeDetailView, but just dumps info about which
            blocks are currently shown.
            """
            def reNotifyInside(block, item, indent):
                if not isinstance(block, DynamicContainerBlocks.ToolbarItem):
                    if block.isShown:
                        print indent + '+' + block.blockName
                    else:
                        print indent + '-' + block.blockName
                try:
                    # process from the children up
                    for child in block.childrenBlocks:
                        reNotifyInside (child, item, indent + '  ')
                except AttributeError:
                    pass
            item= self.selectedItem()
            try:
                itemDescription = item.itsKind.itsName + ' '
            except AttributeError:
                itemDescription = ''
            try:
                itemDescription += str (item)
            except:
                itemDescription += str (item.itsName)
            print methodName + " " + itemDescription
            print "-------------------------------"
            reNotifyInside(self, item, '')
            print

    def synchronizeWidget (self):
        item= self.selectedItem()
        super(DetailRoot, self).synchronizeWidget ()
        self.synchronizeDetailView(item)
        if __debug__:
            dumpSynchronizeWidget = False
            if dumpSynchronizeWidget:
                self.dumpShownHierarchy ('synchronizeWidget')
        
    def onDestroyWidget (self):
        # Hack - @@@DLD - remove when wxWidgets issue is resolved.
        # set ourself to be shown, to work around Windows DetailView garbage problem.
        def showReentrant (block):
            block.isShown = True
            for child in block.childrenBlocks:
                showReentrant (child)
        super(DetailRoot, self).onDestroyWidget ()
        showReentrant (self)

    def onSendShareItemEventUpdateUI(self, event):    
        item = self.selectedItem()
        enabled = False
        label = _("Send")
        if item is not None:            
            if isinstance(item, ItemCollection.ItemCollection):
                # It's a collection: label should read "Send", or "Send to new" if it's already shared.
                enabled = len(item.invitees) > 0
                try:
                    renotify = Sharing.isShared (item)
                except AttributeError:
                    pass
                else:
                    if renotify:
                        label = _("Send to new")
            elif isinstance(item, Mail.MailMessageMixin) and item.isOutbound:
                # It's mail. Has it been sent already?
                sent = False
                try:
                    sent = item.deliveryExtension.state == "SENT"
                except AttributeError:
                    pass
                if sent:
                    label = _("Sent")
                else:
                    # Not sent yet - enable it if it's outbound and we have valid addressees?
                    enabled = len(item.toAddress) > 0
        
        event.arguments['Enable'] = enabled    
        event.arguments ['Text'] = label
            
    def onSendShareItemEvent (self, event):
        """
          Send or Share the current item.
        """
        self.finishSelectionChanges () # finish changes to previous selected item 
        item = self.selectedItem()

        # Make sure we have all the accounts; returns False if the user cancels
        # out and we don't.
        if not Sharing.ensureAccountSetUp(self.itsView):
            return

        # preflight the send/share request
        # mail items and collections need their sender and recievers set up
        message = None
        if isinstance (item, ItemCollection.ItemCollection):
            try:
                whoTo = item.invitees
            except AttributeError:
                whoTo = []
            if len (whoTo) == 0:
                message = _('Please specify who to share this collection with in the "to" field.')
        elif isinstance (item, Mail.MailMessageMixin):
            if item.ItemWhoFromString() == '':
                item.whoFrom = item.getCurrentMeEmailAddress()
            try:
                whoTo = item.toAddress
            except AttributeError:
                whoTo = []
            if len (whoTo) == 0:
                message = _('Please specify who to send this message to in the "to" field.')
                
        if message:
            Util.ok(wx.GetApp().mainFrame,
             _("No Receivers"), message)
        else:
            item.shareSend() # tell the ContentItem to share/send itself.

    def resynchronizeDetailView (self):
        # Called to resynchronize the whole Detail View
        # Called when an itemCollection gets new sharees,
        #  because the Notify button should then be enabled.
        # Also called after stamping.
        
        # @@@BJS: stripped-down for trees of blocks; used to be:
        ## @@@DLD - devise a block-dependency-event scheme.        
        #item= self.selectedItem()
        #self.synchronizeDetailView(item)
        #
        # After moving DetailRoot into the event boundary in the
        # trees of blocks, we need to call synchronizeWidget on
        # the TrunkParentBlock since stamping may change the tree
        # of blocks displayed in the detail view event boundary -- DJA
        self.parentBlock.synchronizeWidget()

    def finishSelectionChanges (self):
        """ 
          Need to finish any changes to the selected item
        that are in progress.
        @@@DLD - find a better way to commit widget changes
        Maybe trigger an EVT_KILL_FOCUS event?
        """
        focusBlock = self.getFocusBlock()
        try:
            focusBlock.saveTextValue (validate=True)
        except AttributeError:
            pass


class DetailTrunkDelegate (Trunk.TrunkDelegate):
    """ 
    Delegate for the trunk builder on DetailRoot; the cache key is the given item's Kind
    """    
    def _mapItemToCacheKeyItem(self, item):
        """ 
        Overrides to use the item's kind as our cache key
        """
        if item is None:
            return None
        else:
            return item.itsKind
    
    def _makeTrunkForCacheKey(self, keyItem):
        """ 
        Handle a cache miss; build and return the detail tree-of-blocks for this keyItem, a Kind. 
        """
        # Walk through the keys we have subtrees for, and collect subtrees to use;
        # we decide to use a subtree if _includeSubtree returns True for it.
        # Each subtree we find has children that are the blocks that are to be 
        # collected and sorted (by their 'position' attribute, then their paths
        # to be deterministic in the event of a tie) into the tree we'll use.
        # Blocks without 'position' attributes will naturally be sorted to the end.
        # If we were given a reference to a 'stub' block, we'll copy that and use
        # it as the root of the tree; otherwise, it's assumed that we'll only find
        # one subtree for our key, and use it directly.
        
        # (Yes, I wrote this as a double nested list comprehension with filtering, 
        # but I couldn't decide how to work in a lambda function, so I backed off and
        # opted for clarity.)
        decoratedSubtreeList = [] # each entry will be (position, path, subtreechild)
        for subtree in self._getSubtrees():
            if keyItem.isKindOf(subtree.key) and subtree.hasLocalAttributeValue('rootBlocks'):
                for block in subtree.rootBlocks:
                    entryTobeSorted = (block.getAttributeValue('position', default=sys.maxint), 
                                       block.itsPath,
                                       self._copyItem(block))
                    decoratedSubtreeList.append(entryTobeSorted) 
                
        if len(decoratedSubtreeList) == 0:
            assert False, "Don't know how to build a trunk for this kind!"
            # (We can continue here - we'll end up just caching an empty view.)

        decoratedSubtreeList.sort()
        
        # Copy our stub block and move the new kids on(to) the block.
        trunk = self._copyItem(self.trunkStub)
        trunk.childrenBlocks.extend([ block for position, path, block in decoratedSubtreeList ])
            
        return trunk    
    
    def _getSubtrees(self):
        """
        Get a list of mappings from kind to subtree; by default, we generate it once at startup
        """
        try:
            subtrees = self.subtreeList
        except AttributeError:
            trunkSubtreeKind = self.findPath("//parcels/osaf/framework/blocks/detail/DetailTrunkSubtree")
            subtrees = list(KindQuery().run([trunkSubtreeKind]))
            self.subtreeList = subtrees
        return subtrees
        
class DetailSynchronizer(Item):
    """
      Mixin class that handles synchronizeWidget and
    the SelectItem event by calling synchronizeItemDetail.
    Most client classes will only have to implement
    synchronizeItemDetail.
    """
    def detailRoot (self):
        # Cruise up the parents looking for someone who can return the detailRoot
        block = self
        while True:
            try:
                return block.parentBlock.detailRoot()
            except AttributeError:
                block = block.parentBlock
        else:
            assert False, "Detail Synchronizer can't find the DetailRoot!"
        

    def selectedItem (self):
        # return the selected item
        rootBlock = self.detailRoot()
        return rootBlock.selectedItem()

    def resynchronizeDetailView (self):
        # resynchronize the whole detail view.
        self.detailRoot().resynchronizeDetailView ()

    def finishSelectionChanges (self):
        # finish any changes in progress in editable text fields.
        self.detailRoot().finishSelectionChanges ()

    def synchronizeItemDetail (self, item):
        # if there is an item, we should show ourself, else hide
        if item is None:
            shouldShow = False
        else:
            shouldShow = self.shouldShow (item)
        return self.show(shouldShow)
    
    def shouldShow (self, item):
        return item is not None

    def show (self, shouldShow):
        # if the show status has changed, tell our widget, and return True
        try:
            widget = self.widget
        except AttributeError:
            return False
        if shouldShow != widget.IsShown():
            # we have a widget
            # make sure widget shown state is what we want
            widget.Show (shouldShow)
            self.isShown = shouldShow
            return True
        return False

    def whichAttribute(self):
        # define the attribute to be used
        return self.parentBlock.selectedItemsAttribute

    def parseEmailAddresses(self, item, addressesString):
        """
          Parse the email addresses in addressesString and return
        a tuple with: (the processed string, a list of EmailAddress
        items created/found for those addresses).
        @@@DLD - seems like the wrong place to parse Email Address list strings
        """

        # get the user's address strings into a list
        addresses = []
        tmp = addressesString.split(',')
   
        for val in tmp:
            #Many people are use to entering ';' in an email client
            #so if one or more ';' are found treat as an email address
            #divider
            if val.find(';') != -1:
                addresses.extend(val.split(';'))
            else:
                addresses.append(val)


        # build a list of all processed addresses, and all valid addresses
        validAddresses = []
        processedAddresses = []

        # convert the text addresses into EmailAddresses
        for address in addresses:
            whoAddress = item.getEmailAddress (address)
            if whoAddress is None:
                processedAddresses.append (address + '?')
            else:
                processedAddresses.append (str (whoAddress))
                validAddresses.append (whoAddress)

        # prepare the processed addresses return value
        processedResultString = ', '.join (processedAddresses)

        return (processedResultString, validAddresses)

class StaticTextLabel (DetailSynchronizer, ControlBlocks.StaticText):
    def staticTextLabelValue (self, item):
        theLabel = self.title
        return theLabel

    def synchronizeLabel (self, value):
        label = self.widget.GetLabel ()
        relayout = label != value
        if relayout:
            self.widget.SetLabel (value)
        return relayout

    def synchronizeItemDetail (self, item):
        hasChanged = super(StaticTextLabel, self).synchronizeItemDetail(item)
        if self.isShown:
            labelChanged = self.synchronizeLabel(self.staticTextLabelValue(item))
            hasChanged = hasChanged or labelChanged
        return hasChanged

# gets redirectTo for an attribute name, or just returns the attribute
# name if a there is no redirectTo
def GetRedirectAttribute(item, defaultAttr):
    attributeName = item.getAttributeAspect(defaultAttr, 'redirectTo');
    if attributeName is None:
        attributeName = defaultAttr
    return attributeName

        
class StaticRedirectAttribute (StaticTextLabel):
    """
      Static text label that displays the attribute value
    """
    def staticTextLabelValue (self, item):
        try:
            value = item.getAttributeValue(GetRedirectAttribute(item, self.whichAttribute()))
            theLabel = str(value)
        except AttributeError:
            theLabel = ""
        return theLabel
        
class StaticRedirectAttributeLabel (StaticTextLabel):
    """
      Static Text that displays the name of the selected item's Attribute
    """
    def shouldShow (self, item):
        return not (item is None or
                    item.isItemOf (Contacts.Contact.getKind (self.itsView)))

    def staticTextLabelValue (self, item):
        redirectAttr = GetRedirectAttribute(item, self.whichAttribute ())
        # lookup better names for display of some attributes
        if item.hasAttributeAspect (redirectAttr, 'displayName'):
            redirectAttr = item.getAttributeAspect (redirectAttr, 'displayName')
        return redirectAttr

class LabeledTextAttributeBlock (ControlBlocks.ContentItemDetail):
    """
      basic class for a block in the detail view typically containing:
        * a label (e.g. a StaticText with "Title:")
        * an attribute value (e.g. in an EditText with the value of item.title)
      it also handles visibility of the block, depending on if the attribute
      exists on the item or not (with a special case for contacts, which is 
      always hidden)
    """ 
    def synchronizeItemDetail(self, item):
        whichAttr = self.selectedItemsAttribute
        contactKind = Contacts.Contact.getKind (self.itsView)
        if item is None or item.isItemOf (contactKind):
            self.isShown = False
        else:
            self.isShown = item.itsKind.hasAttribute(whichAttr)
        self.synchronizeWidget()

    def shouldShow (self, item):
        return not (item is None or
                    item.isItemOf (Contacts.Contact.getKind (self.itsView)))

class DetailSynchronizedLabeledTextAttributeBlock (DetailSynchronizer, LabeledTextAttributeBlock):
    pass

class DetailSynchronizedAttributeEditorBlock (DetailSynchronizer, ControlBlocks.AEBlock):
    
    # temporary fix until AEBlocks update themselves automatically
    def synchronizeItemDetail(self, item):
        super(DetailSynchronizedAttributeEditorBlock, self).synchronizeItemDetail(item)
        
        # tell the AE block to update itself
        if self.isShown:
            self.synchronizeWidget()

def ItemCollectionOrMailMessageMixin (item):
    # if the item is a MailMessageMixin, or an ItemCollection,
    # then return True
    mailKind = Mail.MailMessageMixin.getKind (item.itsView)
    isCollection = isinstance (item, ItemCollection.ItemCollection)
    isOneOrOther = isCollection or item.isItemOf (mailKind)
    return isOneOrOther

class MarkupBar (DetailSynchronizer, DynamicContainerBlocks.Toolbar):
    """
      Markup Toolbar, for quick control over Items.
    Doesn't need to synchronizeItemDetail, because
    the individual ToolbarItems synchronizeItemDetail.
    """
    def shouldShow (self, item):
        # if the item is a collection, we should not show ourself
        shouldShow = not isinstance (item, ItemCollection.ItemCollection)
        return shouldShow

    def onButtonPressedEvent (self, event):
        # Rekind the item by adding or removing the associated Mixin Kind
        self.finishSelectionChanges () # finish changes to editable fields 
        tool = event.arguments['sender']
        item = self.selectedItem()
        
        if not item or not self._isStampable(item):
            return
            
        mixinKind = tool.stampMixinKind()
        if self.widget.GetToolState(tool.toolID):
            operation = 'add'
        else:
            operation = 'remove'
        item.StampKind(operation, mixinKind)
        # notify the world that the item has a new kind.
        self.resynchronizeDetailView ()

    def onButtonPressedEventUpdateUI(self, event):
        item = self.selectedItem()
        enable = item and self._isStampable(item)
        event.arguments ['Enable'] = enable

    def onTogglePrivateEvent(self, event):
        item = self.selectedItem()
        if item is not None:
            tool = event.arguments['sender']
            item.isPrivate = self.widget.GetToolState(tool.toolID)
            
    def _isStampable(self, item):
        # for now, any ContentItem is stampable. This may change if Mixin rules/policy change
        return item.isItemOf(ContentModel.ContentItem.getKind(self.itsView))

class DetailStampButton (DetailSynchronizer, DynamicContainerBlocks.ToolbarItem):
    """
      Common base class for the stamping buttons in the Markup Bar
    """
    def stampMixinClass(self):
        # return the class of this stamp's Mixin Kind (bag of kind-specific attributes)
        raise NotImplementedError, "%s.stampMixinClass()" % (type(self))
    
    def stampMixinKind(self):
        # return the Mixin Kind of this stamp
        raise NotImplementedError, "%s.stampMixinKind()" % (type(self))
    
    def synchronizeItemDetail (self, item):
        # toggle this button to reflect the kind of the selected item
        shouldToggleBasedOnClass = isinstance(item, self.stampMixinClass())
        shouldToggleBasedOnKind = item.isItemOf(self.stampMixinKind())
        assert shouldToggleBasedOnClass == shouldToggleBasedOnKind, \
               "Class/Kind mismatch for class %s, kind %s" % (item.__class__, item.itsKind)
        # @@@DLD remove workaround for bug 1712 - ToogleTool doesn't work on mac when bar hidden
        if shouldToggleBasedOnKind:
            self.dynamicParent.show (True) # if we're toggling a button down, the bar must be shown
            
        self.dynamicParent.widget.ToggleTool(self.toolID, shouldToggleBasedOnKind)
        return False

class MailMessageButton (DetailStampButton):
    """
      Mail Message Stamping button in the Markup Bar
    """
    def stampMixinClass(self):
        return Mail.MailMessageMixin
    
    def stampMixinKind(self):
        return Mail.MailMessageMixin.getKind(self.itsView)
    
class CalendarStamp (DetailStampButton):
    """
      Calendar button in the Markup Bar
    """
    def stampMixinClass(self):
        return Calendar.CalendarEventMixin

    def stampMixinKind(self):
        return Calendar.CalendarEventMixin.getKind(self.itsView)

class TaskStamp (DetailStampButton):
    """
      Task button in the Markup Bar
    """
    def stampMixinClass(self):
        return Task.TaskMixin

    def stampMixinKind(self):
        return Task.TaskMixin.getKind(self.itsView)


class PrivateSwitchButton(DetailSynchronizer, DynamicContainerBlocks.ToolbarItem):
    """
      "Never share" button in the Markup Bar
    """
    def synchronizeItemDetail (self, item):
        # toggle this button to reflect the privateness of the selected item        
        # @@@DLD remove workaround for bug 1712 - ToogleTool doesn't work on mac when bar hidden
        if item.isPrivate:
            self.dynamicParent.show (True) # if we're toggling a button down, the bar must be shown
        self.dynamicParent.widget.ToggleTool(self.toolID, item.isPrivate)
        return False
        
class EditTextAttribute (DetailSynchronizer, ControlBlocks.EditText):
    """
    EditText field connected to some attribute of a ContentItem
    Override LoadAttributeIntoWidget, SaveAttributeFromWidget in subclasses
    """
    def instantiateWidget (self):
        widget = super (EditTextAttribute, self).instantiateWidget()
        # We need to save off the changed widget's data into the block periodically
        # Hopefully OnLoseFocus is getting called every time we lose focus.
        widget.Bind(wx.EVT_KILL_FOCUS, self.onLoseFocus)
        widget.Bind(wx.EVT_KEY_UP, self.onKeyPressed)
        return widget

    def saveTextValue (self, validate=False):
        # save the user's edits into item's attibute
        item = self.selectedItem()
        try:
            widget = self.widget
        except AttributeError:
            widget = None
        if item is not None and widget is not None:
            self.saveAttributeFromWidget(item, widget, validate=validate)
        
    def loadTextValue (self, item):
        # load the edit text from our attribute into the field
        if item is None:
            item = self.selectedItem()
        if item is not None:
            widget = self.widget
            self.loadAttributeIntoWidget(item, widget)
    
    def onLoseFocus (self, event):
        # called when we get an event; to saves away the data and skips the event
        self.saveTextValue (validate=True)
        event.Skip()
        
    def onKeyPressed (self, event):
        # called when we get an event; to saves away the data and skips the event
        self.saveTextValue()
        event.Skip()
        
    def OnDataChanged (self):
        # event that an edit operation has taken place
        self.saveTextValue()

    def synchronizeItemDetail (self, item):
        self.loadTextValue(item)
        return super(EditTextAttribute, self).synchronizeItemDetail(item)
            
    def saveAttributeFromWidget (self, item, widget, validate):  
       # subclasses need to override this method
       raise NotImplementedError, "%s.SaveAttributeFromWidget()" % (type(self))

    def loadAttributeIntoWidget (self, item, widget):  
       # subclasses need to override this method
       raise NotImplementedError, "%s.LoadAttributeIntoWidget()" % (type(self))

class NoteBody (EditTextAttribute):
    """
    Body attribute of a ContentItem, e.g. a Note
    """
    def shouldShow (self, item):
        # need to show even if there is no value, so we test
        # the kind to see if it knows about the attribute.
        knowsBody = item.itsKind.hasAttribute("body")
        return knowsBody
        
    def saveAttributeFromWidget (self, item, widget, validate):
        attributeName = GetRedirectAttribute(item, 'body');
        textType = item.getAttributeAspect(attributeName, 'type')
        widgetText = widget.GetValue()
        if widgetText:
            item.body = textType.makeValue(widgetText, encoding='ascii',
             indexed=True)
        
    def loadAttributeIntoWidget (self, item, widget):  
        attributeName = GetRedirectAttribute(item, 'body');
        if item.hasLocalAttributeValue(attributeName):
            # get the character string out of the Text LOB
            noteBody = item.ItemBodyString ()
            widget.SetValue(noteBody)
        else:
            widget.Clear()

class EditToAddressTextAttribute (EditTextAttribute):
    """
    An editable address attribute that resyncs the DV when changed
    """
    def saveAttributeFromWidget(self, item, widget, validate):
        if validate:
            toFieldString = widget.GetValue().strip('?')

    
            # parse the addresses and get/create/validate
            processedAddresses, validAddresses = self.parseEmailAddresses (item, toFieldString)
    
            # reassign the list to the attribute
            try:
                item.setAttributeValue (self.whichAttribute (), validAddresses)
            except:
                pass
    
            # redisplay the processed addresses in the widget
            widget.SetValue (processedAddresses)

    def loadAttributeIntoWidget (self, item, widget):
        if self.shouldShow (item):
            try:
                whoContacts = item.getAttributeValue (self.whichAttribute ())
            except AttributeError:
                whoContacts = ''
            try:
                numContacts = len(whoContacts)
            except TypeError:
                numContacts = -1
            if numContacts == 0:
                whoString = ''
            elif numContacts > 0:
                whoNames = []
                for whom in whoContacts.values():
                    whoNames.append (str (whom))
                whoString = ', '.join(whoNames)
            else:
                whoString = str (whoContacts)
                if isinstance(whoContacts, Contacts.ContactName):
                    names = []
                    if len (whoContacts.firstName):
                        names.append (whoContacts.firstName)
                    if len (whoContacts.lastName):
                        names.append (whoContacts.lastName)
                    whoString = ' '.join(names)
            widget.SetValue (whoString)

class ToMailEditField (EditToAddressTextAttribute):
    """
    'To' attribute of a Mail ContentItem, e.g. who it's sent to
    """
    def whichAttribute(self):
        # define the attribute to be used
        return 'toAddress'

class SharingArea (DetailSynchronizedLabeledTextAttributeBlock):
    """ an area visible only when the item (a collection) is shared """
    def shouldShow (self, item):
        return item is not None and Sharing.isShared(item)
                
class ParticipantsTextField (EditTextAttribute):
    """
    'participants' attribute of an ItemCollection, e.g. who it's already been shared with.
    Read only, at least for now.
    """
    def loadAttributeIntoWidget (self, item, widget):
        share = Sharing.getShare(item)
        if share is not None:
            sharees = sets.Set(share.sharees)
            sharees.add(share.sharer)
            value = ", ".join([ str(sharee) for sharee in list(sharees) ])
            widget.SetValue(value)

    def saveAttributeFromWidget (self, item, widget, validate):  
        # It's read-only, but we have to override this method.
        pass
    
class InviteEditField (EditToAddressTextAttribute):
    """
    'invitees' attribute of an ItemCollection, e.g. who we're inviting to share it.
    """
    def whichAttribute(self):
        # define the attribute to be used
        return 'invitees'

class EditSharingActive (DetailSynchronizer, ControlBlocks.CheckBox):
    """
      "Sharing Active" checkbox on item collections
    """
    def synchronizeItemDetail (self, item):
        hasChanged = super(EditSharingActive, self).synchronizeItemDetail(item)
        if item is not None and self.isShown:
            share = Sharing.getShare(item)
            if share is not None:
                self.widget.SetValue(share.active)
        return hasChanged
    
    def onToggleSharingActiveEvent (self, event):
        item = self.selectedItem()
        if item is not None:
            share = Sharing.getShare(item)
            if share is not None:
                share.active = self.widget.GetValue() == wx.CHK_CHECKED

class FromEditField (EditTextAttribute):
    """Edit field containing the sender's contact"""
    def saveAttributeFromWidget(self, item, widget, validate):  
        pass

    def loadAttributeIntoWidget(self, item, widget):
        """
          Load the widget based on the attribute associated with whoFrom.
        """
        try:
            whoFrom = item.whoFrom
        except AttributeError:
            whoFrom = None

        if whoFrom is None:
            # Hack to set up whoFrom for Items with no value... like ItemCollections
            # Can't set the whoFrom at creation time, because many start life at
            # system startup before the user account is setup.
            if item.itsKind.hasAttribute ('whoFrom'):
                try:
                    # Determine which kind of item to assign based on the
                    # types of the redirected-to attributes:
                    type = item.getAttributeAspect('whoFrom', 'type')
                    contactKind = \
                     item.findPath("//parcels/osaf/contentmodel/contacts/Contact")
                    if type is contactKind:
                        item.whoFrom = item.getCurrentMeContact(item.itsView)
                    else:
                        emailAddressKind = \
                         item.findPath("//parcels/osaf/contentmodel/mail/EmailAddress")
                        if type is emailAddressKind:
                            item.whoFrom = item.getCurrentMeEmailAddress()
                except AttributeError:
                    pass

        try:
            whoString = item.ItemWhoFromString ()
        except AttributeError:
            whoString = ''
        widget.SetValue (whoString)

class EditRedirectAttribute (EditTextAttribute):
    """
    An attribute-based edit field
    Our parent block knows which attribute we edit.
    """
    def saveAttributeFromWidget(self, item, widget, validate):
        item.setAttributeValue(self.whichAttribute(), widget.GetValue())

    def loadAttributeIntoWidget(self, item, widget):
        try:
            value = item.getAttributeValue(self.whichAttribute())
        except AttributeError:
            value = _('untitled')
        widget.SetValue(value)

class EditHeadlineRedirectAttribute (EditRedirectAttribute):
    """
    An attribute-based edit field
    Doesn't show for contacts.
    """
    def shouldShow (self, item):
        # don't show if the item is a Contact
        contactKind = Contacts.Contact.getKind (self.itsView)
        shouldShow = not item.isItemOf (contactKind)
        return shouldShow

"""
Classes to support Contact details
"""

class ContactFullNameEditField (EditRedirectAttribute):
    """
    An attribute-based edit field for contactName:fullName
    The actual value is stored in an contactName object.
    """
    def saveAttributeFromWidget(self, item, widget, validate):
        contactName = item.getAttributeValue (self.whichAttribute())
        widgetString = widget.GetValue()
        contactName.setAttributeValue('fullName', widgetString)
        if validate:
            names = widgetString.split (' ')
            if len (names) > 0:
                contactName.firstName = names[0]
            if len (names) > 1:
                contactName.lastName = names[-1]
            # put the fullName into any emailAddress objects connected to this item.
            try:
                item.homeSection.fullName = widgetString
                item.homeSection.emailAddress.fullName = widgetString
            except AttributeError:
                pass
            try:
                item.workSection.fullName = widgetString
                item.workSection.emailAddress.fullName = widgetString
            except AttributeError:
                pass


    def loadAttributeIntoWidget(self, item, widget):
        value = ''
        try:
            contactName = item.getAttributeValue (self.whichAttribute())
            value = contactName.getAttributeValue ('emailAddress')
        except AttributeError:
            pass
        if value == '':
            value = item.ItemWhoString ()
        widget.SetValue(value)

class StaticEmailAddressAttribute (StaticRedirectAttributeLabel):
    """
      Static Text that displays the name of the selected item's Attribute.
    Customized for EmailAddresses
    """
    def staticTextLabelValue (self, item):
        label = self.title
        return label

class EditEmailAddressAttribute (EditRedirectAttribute):
    """
    An attribute-based edit field for email addresses
    The actual value is stored in an emailaddress 'section' object
    for home or work.
    """
    def saveAttributeFromWidget(self, item, widget, validate):
        if validate:
            section = item.getAttributeValue (self.whichAttribute())
            widgetString = widget.GetValue()
            processedAddresses, validAddresses = self.parseEmailAddresses (item, widgetString)
            section.setAttributeValue('emailAddresses', validAddresses)
            for address in validAddresses:
                try:
                    address.fullName = section.fullName
                except AttributeError:
                    pass
            widget.SetValue (processedAddresses)

    def loadAttributeIntoWidget(self, item, widget):
        value = ''
        try:
            section = item.getAttributeValue (self.whichAttribute())
            value = section.getAttributeValue ('emailAddresses')
        except AttributeError:
            value = {}
        # convert the email address list to a nice string.
        whoNames = []
        for whom in value.values():
            whoNames.append (str (whom))
        whoString = ', '.join(whoNames)
        widget.SetValue(whoString)


class AttachmentArea (DetailSynchronizedLabeledTextAttributeBlock):
    """ an area visible only when the item (a mail message) has attachments """
    def shouldShow (self, item):
        return item is not None and item.hasAttachments()
    
class AttachmentTextField (EditTextAttribute):
    """
    A read-only list of email attachments, for now.
    """
    def loadAttributeIntoWidget (self, item, widget):
        # For now, just list the attachments' filenames
        if item is None or not item.hasAttachments():
            value = ""
        else:
            value = ", ".join([ attachment.filename for attachment in item.getAttachments() if hasattr(attachment, 'filename') ])
        widget.SetValue(value)
    
    def saveAttributeFromWidget (self, item, widget, validate):  
        # It's read-only, but we have to override this method.
        pass
    
    
class AcceptShareButton (DetailSynchronizer, ControlBlocks.Button):
    def shouldShow (self, item):
        showIt = False
        if item is not None and item.isInbound:
            try:
                MailSharing.getSharingHeaderInfo(item)
            except:       
                pass
            else:
                showIt = True
        # print "AcceptShareButton.shouldShow = %s" % showIt
        return showIt
    
    def onAcceptShareEvent(self, event):
        url, collectionName = MailSharing.getSharingHeaderInfo(self.selectedItem())
        wx.Yield()
        share = Sharing.newInboundShare(self.itsView, url)
        share.get()
    
        # @@@ Remove this when the sidebar autodetects new collections
        collection = share.contents
        mainView = application.Globals.views[0]
        mainView.postEventByName ("AddToSidebarWithoutCopyingAndSelectFirst", {'items':[collection]})

    def onAcceptShareEventUpdateUI(self, event):
        # If we're already sharing it, we should disable the button and change the text.
        enabled = True
        item = self.selectedItem()
        try:
            url, collectionName = MailSharing.getSharingHeaderInfo(item)
            existingSharedCollection = Sharing.findMatchingShare(self.itsView, url)
        except:
            enabled = True
        else:
            if existingSharedCollection is not None:
                self.widget.SetLabel(_("(Already sharing this collection)"))
                enabled = False
        event.arguments['Enable'] = enabled

"""
Classes to support CalendarEvent details
"""
class CalendarEventBlock (DetailSynchronizer, LabeledTextAttributeBlock):
    def synchronizeItemDetail (self, item):
        # @@@DLD - remove special case for AEBlock child (duration).
        # Need to really resynchronize, because sizer needs to be redone
        # for AEBlock showing duration attribute inside this block.
        relayoutParent = super(CalendarEventBlock, self).synchronizeItemDetail(item)
        self.synchronizeWidget()
        return relayoutParent

class EditTimeAttribute (EditRedirectAttribute):
    """
    An attribute-based edit field for Time Values
    Our parent block knows which attribute we edit.
    """
    # (@@@BJS ... though we also modify allDay and anyTime ourselves)

    dateTimeFormat = '%Y-%m-%d %I:%M %p'
    dateFormat = '%Y-%m-%d'
    dateTimeFormatHint = 'yyyy-mm-dd HH:MM'
    dateFormatHint = 'yyyy-mm-dd'
    
    def parseDateTime (self, dateString):
        theDate = None
        dateOnly = False

        # work around a problem when using hour of 12
        # @@@DLD Check if this date parsing bug is fixed yet - due in version 2.1
        if DateTime.__version__ < '2.1':
            try:
                twelveLocation = dateString.upper().index('12:')
            except ValueError:
                pass
            else:
                dateString = dateString[:twelveLocation]\
                             + '00:' + dateString[twelveLocation+3:]
        try:
            # convert to Date/Time. This quietly accepts input with and without times.
            theDate = DateTime.Parser.DateTimeFromString (dateString)
        except ValueError: 
            pass
        except DateTime.RangeError:
            pass
        else:
            # Try to discern whether the user specified a time
            # @@@ BJS: For now, we have a time if the returned value's time isn't midnight,
            # _and_ there's a colon in the string.
            dateOnly = (theDate == (theDate + DateTime.RelativeDateTime(hour=0, minute=0, second=0))) \
                     and (dateString.find(':') == -1)

        return (theDate, dateOnly)

    def saveAttributeFromWidget(self, item, widget, validate):
        """"
          Update the attribute from the user edited string in the widget.
        """
        if validate:
            dateString = widget.GetValue().strip('?')
            (theDate, dateOnly) = self.parseDateTime (dateString)
            
            if theDate is not None:
                # save the new Date/Time into the startTime attribute
                item.ChangeStart (theDate)
                item.anyTime = dateOnly and not item.allDay
                
                # and reformat it to put back in the box.
                format = (item.allDay or item.anyTime) and self.dateFormat or self.dateTimeFormat
                dateString = theDate.strftime (format)
            else:
                # @@@DLD figure out reasonable exceptions to catch during conversion
                dateString = dateString + '?'
                
            # redisplay the processed Date/Time in the widget
            widget.SetValue(dateString)


    def loadAttributeIntoWidget(self, item, widget):
        """"
          Update the widget display based on the value in the attribute.
        """
        try:
            dateTime = item.getAttributeValue(self.whichAttribute())
        except AttributeError:
            value = item.allDay and self.dateFormatHint or self.dateTimeFormatHint
        else:
            format = (item.allDay or item.anyTime) and self.dateFormat or self.dateTimeFormat
            value = dateTime.strftime (format)
        widget.SetValue (value)

class EditDurationAttribute (DetailSynchronizedAttributeEditorBlock):
    def shouldShow (self, item):
        return not item.allDay

class AllDayCheckBox (DetailSynchronizer, ControlBlocks.CheckBox):
    """
      "All Day" checkbox
    """
    def synchronizeItemDetail (self, item):
        hasChanged = super(AllDayCheckBox, self).synchronizeItemDetail(item)
        if item is not None and self.isShown:
            self.widget.SetValue(item.allDay)
        return hasChanged
    
    def onToggleAllDayEvent (self, event):
        item = self.selectedItem()
        if item is not None:
            item.allDay = self.widget.GetValue() == wx.CHK_CHECKED
            self.resynchronizeDetailView()

class EditReminder (DetailSynchronizer, ControlBlocks.Choice):
    """
    A choice popup for Reminder Values
    """
    def synchronizeItemDetail (self, item):
        hasChanged = super(EditReminder, self).synchronizeItemDetail(item)
        if item is not None and self.isShown:
            try:
                reminderDelta = item.reminderDelta
            except AttributeError:
                reminderDelta = None
            if reminderDelta is None:
                reminderChoice = _("None")
            else:
                reminderChoice = (reminderDelta.minutes == 1) and _("1 minute") or (_("%i minutes") % reminderDelta.minutes)
            choiceIndex = self.widget.FindString(reminderChoice)
            # If we can't find the choice, just show "None" - this'll happen if this event's reminder has been "snoozed"
            if choiceIndex == -1:
                choiceIndex = self.widget.FindString(_("None"))
            self.widget.Select(choiceIndex)
        return hasChanged

    def onReminderChangedEvent (self, event):
        item = self.selectedItem()
        if item is not None:
            reminderChoice = self.widget.GetStringSelection()
            if reminderChoice == _('None'):
                item.reminderDelta = None
            else:
                # @@@BJS Assumes the menu item is of the form "nn Minutes"
                item.reminderDelta = DateTime.DateTimeDeltaFrom(minutes=int(reminderChoice.split(' ', 2)[0]))

class EditTransparency (DetailSynchronizer, ControlBlocks.Choice):
    """
    A choice popup for Transparency Values (free, busy, etc.)
    """
    def synchronizeItemDetail (self, item):
        hasChanged = super(EditTransparency, self).synchronizeItemDetail(item)
        if item is not None and self.isShown:
            try:
                choiceIndex = item.getAttributeAspect('transparency', 'type').values.index(item.transparency)
            except AttributeError:
                choiceIndex = 0
            self.widget.Select(choiceIndex)
        return hasChanged

    def onTransparencyChangedEvent (self, event):
        item = self.selectedItem()
        if item is not None:
            choiceIndex = self.widget.GetSelection()
            item.transparency = item.getAttributeAspect('transparency', 'type').values[choiceIndex]



class HTMLDetailArea(DetailSynchronizer, ControlBlocks.ItemDetail):
    def synchronizeItemDetail(self, item):
        self.selection = item
        # this ensures that getHTMLText() gets called appropriately on the derived class
        self.synchronizeWidget()
        
    def getHTMLText(self, item):
        return "<html><body>" + str(item) + "</body></html>"
