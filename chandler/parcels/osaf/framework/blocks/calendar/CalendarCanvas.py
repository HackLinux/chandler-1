""" Canvas for calendaring blocks
"""

__version__ = "$Revision$"
__date__ = "$Date$"
__copyright__ = "Copyright (c) 2004 Open Source Applications Foundation"
__license__ = "http://osafoundation.org/Chandler_0.1_license_terms.htm"

import wx
import wx.colheader
import wx.lib.colourselect as colourselect
import mx.DateTime as DateTime

import osaf.contentmodel.calendar.Calendar as Calendar
import osaf.contentmodel.ContentModel as ContentModel

import osaf.framework.blocks.DragAndDrop as DragAndDrop
import osaf.framework.blocks.Block as Block
import osaf.framework.blocks.Styles as Styles
import osaf.framework.blocks.calendar.CollectionCanvas as CollectionCanvas

from colorsys import *
import copy

# 'color' is 0..255 based
# 'rgb' is 0..1.0 based
def color2rgb(r,g,b):
    return (r*1.0)/255, (g*1.0)/255, (b*1.0)/255
    
def rgb2color(r,g,b):
    return r*255,g*255,b*255
    
# from ASPN/Python Cookbook
class CachedAttribute(object):
    def __init__(self, method):
        self.method = method
        self.name = method.__name__
        
    def __get__(self, inst, cls):
        if inst is None:
            return self
        result = self.method(inst)
        setattr(inst, self.name, result)
        return result

class CalendarData(ContentModel.ContentItem):
    myKindPath = "//parcels/osaf/framework/blocks/calendar/CalendarData"
    myKindID = None
    def __init__(self, *args, **keywords):
        super(CalendarData, self).__init__(*args, **keywords)

    # need to convert hues from 0..360 to 0..1.0 range
    hueList = [k/360.0 for k in [210, 120, 60, 0, 240, 90, 330, 30, 180, 270]]
    
    @classmethod
    def getNextHue(cls, oldhue):
        """
        returns the next hue following the one passed in
        For example,
        f.hue = nextHue(f.hue)
        """
        found = False
        for hue in cls.hueList:
            if found: return hue
            if hue == oldhue:
                found = True
        return cls.hueList[0]
    
    def _setEventColor(self, color):
        self.calendarColor.backgroundColor = color

        # clear cached values
        try:
            del self.eventHue
        except AttributeError:
            pass
        
    def _getEventColor(self):
        return self.calendarColor.backgroundColor
        
    # this is the actual RGB value for eventColor
    eventColor = property(_getEventColor, _setEventColor)
    
    @CachedAttribute
    def eventHue(self):
        c = self.eventColor
        rgbvalues = (c.red, c.green, c.blue)
        hsv = rgb_to_hsv(*color2rgb(*rgbvalues))
        return hsv[0]
    
    # to be used like a property, i.e. prop = tintedColor(0.5, 1.0)
    # takes HSV 'S' and 'V' and returns an color based tuple property
    def tintedColor(saturation, value = 1.0):
        def getSaturatedColor(self):
            hsv = (self.eventHue, saturation, value)
            return rgb2color(*hsv_to_rgb(*hsv))
        return property(getSaturatedColor)
            
    # these are all for when this calendar is the 'current' one
    gradientLeft = tintedColor(0.4)
    gradientRight = tintedColor(0.2)
    outlineColor = tintedColor(0.5)
    textColor = tintedColor(0.67, 0.6)
    
    # when a user selects a calendar event, use these
    selectedGradientLeft = tintedColor(0.15)
    selectedGradientRight = tintedColor(0.05)
    selectedOutlineColor = tintedColor(0.5)
    selectedTextColor = tintedColor(0.67, 0.6)
    
    # 'visible' means that its not the 'current' calendar, but is still visible
    visibleGradientLeft = tintedColor(0.4)
    visibleGradientRight = tintedColor(0.4)
    visibleOutlineColor = tintedColor(0.3)
    visibleTextColor = tintedColor(0.5)
        
class CalendarCanvasItem(CollectionCanvas.CanvasItem):
    """
    Base class for calendar items. Covers:
    - editor position & size
    - text wrapping
    - conflict management
    """
    
    def __init__(self, *args, **keywords):
        super(CalendarCanvasItem, self).__init__(*args, **keywords)
        self._parentConflicts = []
        self._childConflicts = []
        # the rating of conflicts - i.e. how far to indent this
        self._conflictDepth = 0
                
        # the total depth of all conflicts - i.e. the maximum simultaneous 
        # conflicts with this item, including this one
        self._totalConflictDepth = 1
        
    def GetEditorPosition(self):
        """
        This returns a location to show the editor. By default it is the same
        as the default bounding box
        """
        return self._bounds.GetPosition()
        
    def GetDragOrigin(self):
        """
        This is just a stable coordinate that we can use so that when dragging
        items around, for example you can use this to know consistently where 
        the mouse started relative to this origin
        """
        return self._bounds.GetPosition()
        
    def GetMaxEditorSize(self):
        return self._bounds.GetSize()
    
    def GetStatusPen(self, styles):
        # probably should use styles to determine a good pen color
        item = self.GetItem()
        eventColors = styles.blockItem.getEventColors(item)
        color = eventColors.outlineColor
        if (item.transparency == "confirmed"):
            pen = wx.Pen(color, 4)
        elif (item.transparency == "fyi"):
            pen = wx.Pen(color, 1)
        elif (item.transparency == "tentative"):
            pen = wx.Pen(color, 4, wx.DOT)
        return pen
        
    # Drawing utility -- scaffolding, we'll try using editor/renderers
    @staticmethod
    def DrawWrappedText(dc, text, rect):
        # Simple wordwrap, next step is to not overdraw the rect
        
        result = []
        
        lines = text.splitlines()
        y = rect.y
        for line in lines:
            x = rect.x
            wrap = 0
            for word in line.split():
                width, height = dc.GetTextExtent(word)

                # first see if we want to jump to the next line
                # (careful not to jump if we're already at the beginning of the line)
                if (x != rect.x and x + width > rect.x + rect.width):
                    y += height
                    x = rect.x
                
                # if we're out of vertical space, just return
                if (y + height > rect.y + rect.height):
                    return y
                   
                # if we wrapped but we still can't fit the word,
                # just truncate it    
                if (x == rect.x and width > rect.width):
                    CalendarCanvasItem.DrawClippedText(dc, word, x, y, rect.width)
                    y += height
                    continue
                
                dc.DrawText(word, x, y)
                x += width
                width, height = dc.GetTextExtent(' ')
                dc.DrawText(' ', x, y)
                x += width
            y += height
        return y

    @staticmethod
    def DrawClippedText(dc, word, x, y, maxWidth):
        # keep shortening the word until it fits
        for i in xrange(len(word), 0, -1):
            smallWord = word[0:i] # + "..."
            width, height = dc.GetTextExtent(smallWord)
            if width <= maxWidth:
                dc.DrawText(smallWord, x, y)
                return
                
    def AddConflict(self, child):
        # we might want to keep track of the inverse conflict as well,
        # for conflict bars
        child._parentConflicts.append(self)
        self._childConflicts.append(child)
        
    @staticmethod
    def FindFirstGapInSequence(seq):
        """
        Look for the first gap in a sequence - for instance
         0,2,3: choose 1
         1,2,3: choose 0
         0,1,2: choose 3        
        """
        for index, value in enumerate(seq):
            if index != value:
                return index
                
        # didn't find any gaps, so just put it one higher
        return index+1
        
    def CalculateConflictDepth(self):
        if not self._parentConflicts:
            return 0
        
        # We'll find out the depth of all our parents, and then
        # see if there's an empty gap we can fill
        # this relies on parentDepths being sorted, which 
        # is true because the conflicts are added in 
        # the same order as the they appear in the calendar
        parentDepths = [parent._conflictDepth for parent in self._parentConflicts]
        self._conflictDepth = self.FindFirstGapInSequence(parentDepths)
        return self._conflictDepth
        
    def GetIndentLevel(self):
        # this isn't right. but its a start
        # it should be some wierd combination of 
        # maximum indent level of all children + 1
        return self._conflictDepth
        
    def GetMaxDepth(self):
        maxparents = maxchildren = 0
        if self._childConflicts:
            maxchildren = max([child.GetIndentLevel() for child in self._childConflicts])
        if self._parentConflicts:
            maxparents = max([parent.GetIndentLevel() for parent in self._parentConflicts])
        return max(self.GetIndentLevel(), maxchildren, maxparents)
        

class ColumnarCanvasItem(CalendarCanvasItem):
    resizeBufferSize = 5
    textMargin = 3
    RESIZE_MODE_START = 1
    RESIZE_MODE_END = 2
    def __init__(self, item, calendarCanvas, *arguments, **keywords):
        super(ColumnarCanvasItem, self).__init__(None, item)
        
        # this is really annoying that we need to keep a reference back to 
        # the calendar canvas in every single ColumnarCanvasItem, but we
        # need it for drawing hints.. is there a better way?
        self._calendarCanvas = calendarCanvas

    def UpdateDrawingRects(self):
        item = self.GetItem()
        indent = self.GetIndentLevel() * 5
        width = self.GetMaxDepth() * 5
        self._boundsRects = list(self.GenerateBoundsRects(self._calendarCanvas,
                                                          item.startTime,
                                                          item.endTime, indent, width))
        self._bounds = self._boundsRects[0]

        r = self._boundsRects[-1]
        self._resizeLowBounds = wx.Rect(r.x, r.y + r.height - self.resizeBufferSize,
                                        r.width, self.resizeBufferSize)
        
        r = self._boundsRects[0]
        self._resizeTopBounds = wx.Rect(r.x, r.y,
                                        r.width, self.resizeBufferSize)
        

    def isHitResize(self, point):
        """ Hit testing of a resize region.
        
        @param point: point in unscrolled coordinates
        @type point: wx.Point
        @return: True if the point hit the resize region
        @rtype: Boolean
        """
        return (self._resizeTopBounds.Inside(point) or
                self._resizeLowBounds.Inside(point))

    def isHit(self, point):
        """
        User may have clicked in any of the possible bounds
        """
        for rect in self._boundsRects:
            if rect.Inside(point):
                return True
        return False

    def getResizeMode(self, point):
        """ Returns the mode of the resize, either RESIZE_MODE_START or
        RESIZE_MODE_END.

        The resize mode is RESIZE_MODE_START if dragging from the top of the event,
        and RESIZE_MODE_END if dragging from the bottom of the event. None indicates
        that we are not resizing at all.

        @param point: drag start position in uscrolled coordinates
        @type point: wx.Point
        @return: resize mode, RESIZE_MODE_START, RESIZE_MODE_END or None
        @rtype: string or None
        """
        
        if hasattr(self, '_forceResizeMode'):
            return self._forceResizeMode
            
        if self._resizeTopBounds.Inside(point):
            return self.RESIZE_MODE_START
        if self._resizeLowBounds.Inside(point):
            return self.RESIZE_MODE_END
        return None
        
    def SetResizeMode(self, mode):
        self._forceResizeMode = mode
        
    def ResetResizeMode(self):
        if hasattr(self, '_forceResizeMode'):
            del self._forceResizeMode
    
    @staticmethod
    def GenerateBoundsRects(calendarCanvas, startTime, endTime, indent=0, width=0):
        """
        Generate a bounds rectangle for each day period. For example, an event
        that goes from noon monday to noon wednesday would have three bounds rectangles:
            one from noon monday to midnight
            one for all day tuesday
            one from midnight wednesday morning to noon wednesday
        """
        # calculate how many unique days this appears on 
        days = int(endTime.absdays) - int(startTime.absdays) + 1
        
        for i in xrange(days):
            
            # first calculate the midnight time for the beginning and end
            # of the current day
            absDay = int(startTime.absdays) + i
            absDayStart = DateTime.DateTimeFromAbsDays(absDay)
            absDayEnd = DateTime.DateTimeFromAbsDays(absDay + 1)
            
            boundsStartTime = max(startTime, absDayStart)
            boundsEndTime = min(endTime, absDayEnd)
            
            try:
                rect = ColumnarCanvasItem.MakeRectForRange(calendarCanvas, boundsStartTime, boundsEndTime)
                rect.x += indent
                rect.width -= width
                yield rect
            except ValueError:
                pass
        
    @staticmethod
    def MakeRectForRange(calendarCanvas, startTime, endTime):
        """
        Turn a datetime range into a rectangle that can be drawn on the screen
        This is a static method, and can be used outside this class
        """
        startPosition = calendarCanvas.getPositionFromDateTime(startTime)
        
        # ultimately, I'm not sure that we should be asking the calendarCanvas
        # directly for dayWidth and hourHeight, we probably need some system 
        # instead similar to getPositionFromDateTime where we pass in a duration
        duration = (endTime - startTime).hours
        (cellWidth, cellHeight) = (calendarCanvas.dayWidth, int(duration * calendarCanvas.hourHeight))
        
        return wx.Rect(startPosition.x, startPosition.y, cellWidth, cellHeight)

    def Draw(self, dc, boundingRect, styles, bitmapBrush):
        item = self._item

        time = item.startTime

        # Draw one event - an event consists of one or more bounds
        lastRect = self._boundsRects[-1]
            
        clipRect = None   
        (cx,cy,cwidth,cheight) = dc.GetClippingBox()
        if not cwidth == cheight == 0:
            clipRect = wx.Rect(x,y,width,height)

        # save the current pen, we'll need it
        drawingPen = dc.GetPen()
        origin = dc.GetDeviceOrigin()
        newOrigin = copy.copy(origin)
        
        for rectIndex, itemRect in enumerate(self._boundsRects):        
            
            newOrigin.x += itemRect.x
            dc.SetDeviceOriginPoint(newOrigin)
            itemRect = copy.copy(itemRect)
            itemRect.x = 0
            brush = wx.Brush(wx.WHITE,wx.STIPPLE)
            brush.SetStipple(bitmapBrush)
            dc.SetBrush(brush)
            dc.SetPen(drawingPen)

            # properly round the corners - first and last
            # boundsRect gets some rounding, and they
            # may actually be the same boundsRect
            hasTopRightRounded = hasBottomRightRounded = False
            drawTime = False
            if rectIndex == 0:
                hasTopRightRounded = True
                drawTime = True
            if rectIndex == len(self._boundsRects)-1:
                hasBottomRightRounded = True

            self.DrawDRectangle(dc, itemRect, hasTopRightRounded, hasBottomRightRounded)

            pen = self.GetStatusPen(styles)
    
            cornerRadius = 0
            pen.SetCap(wx.CAP_BUTT)
            dc.SetPen(pen)
            dc.DrawLine(itemRect.x+1, itemRect.y + (cornerRadius*3/4),
                        itemRect.x+1, itemRect.y + itemRect.height - (cornerRadius*3/4))
    
            # Shift text
            x = itemRect.x + self.textMargin + 3
            y = itemRect.y + self.textMargin
            width = itemRect.width - (self.textMargin + 10)
            height = 15
            timeRect = wx.Rect(x, y, width, height)
            
            # only draw date/time on first item
            if drawTime:
                # amazingly, there is no hour-without-the-zero in mx.DateTime!
                # (If anyone knows a better way to do this, please fix..)
                hour = str(int(time.Format('%I')))
                timeString = hour + time.Format(':%M %p').lower()
                te = dc.GetFullTextExtent(timeString, styles.eventTimeFont)
                timeHeight = te[1]
                
                # draw the time if there is room
                if (timeHeight < itemRect.height/2):
                    dc.SetFont(styles.eventTimeFont)
                    y = self.DrawWrappedText(dc, timeString, timeRect)
                
                textRect = wx.Rect(x, y, width, itemRect.height - (y - itemRect.y))
                
                dc.SetFont(styles.eventLabelFont)
                self.DrawWrappedText(dc, item.displayName, textRect)
        
        dc.DestroyClippingRegion()
        if clipRect:
            dc.SetClippingRect(clipRect)
        dc.SetDeviceOriginPoint(origin)

    def DrawDRectangle(self, dc, rect, hasTopRightRounded=True, hasBottomRightRounded=True):
        """
        Make a D-shaped rectangle, optionally specifying if the top and bottom
        right side of the rectangle should have rounded corners. Uses
        clip rect tricks to make sure it is drawn correctly
        
        Side effect: Destroys the clipping region.
        """

        radius = 10
        diameter = radius * 2

        dc.DestroyClippingRegion()
        dc.SetClippingRect(rect)
        
        roundRect = wx.Rect(rect.x, rect.y, rect.width, rect.height)
        
        # first widen the whole thing left, this makes sure the 
        # left rounded corners aren't drawn
        roundRect.x -= radius
        roundRect.width += radius
        
        # now optionally push the other rounded corners off the top or bottom
        if not hasBottomRightRounded:
            roundRect.height += radius
            
        if not hasTopRightRounded:
            roundRect.y -= radius
            roundRect.height += radius
        
        # finally draw the clipped rounded rect
        dc.DrawRoundedRectangleRect(roundRect, radius)
        
        # draw the lefthand side border, to stay consistent all
        # the way around the rectangle
        dc.DrawLine(rect.x, rect.y, rect.x, rect.y + rect.height)

class HeaderCanvasItem(CalendarCanvasItem):
    def Draw(self, dc, styles):
        item = self._item
        itemRect = self._bounds
        
        dc.DrawRectangleRect(itemRect)
                
        # draw little rectangle to the left of the item
        pen = self.GetStatusPen(styles)
        
        pen.SetCap(wx.CAP_BUTT)
        dc.SetPen(pen)
        dc.DrawLine(itemRect.x + 2, itemRect.y + 3,
                    itemRect.x + 2, itemRect.y + itemRect.height - 3)
        
        # Shift text
        textRect = copy.copy(itemRect)
        textRect.x += 5
        textRect.width -= 7
        self.DrawWrappedText(dc, item.displayName, textRect)

class CalendarEventHandler(object):

    """ Mixin to a widget class """

    def OnPrev(self, event):
        self.blockItem.decrementRange()
        self.blockItem.postDateChanged()
        self.wxSynchronizeWidget()

    def OnNext(self, event):
        self.blockItem.incrementRange()
        self.blockItem.postDateChanged()
        self.wxSynchronizeWidget()

    def OnToday(self, event):
        today = DateTime.today()
        self.blockItem.setRange(today)
        self.blockItem.postDateChanged()
        self.wxSynchronizeWidget()

class ClosureTimer(wx.Timer):
    """
    Helper class because targets may need to recieve multiple different timers
    """
    def __init__(self, callback, *args, **kwargs):
        super(ClosureTimer, self).__init__(*args, **kwargs)
        self._callback = callback
        
    def Notify(self):
        self._callback()

class CalendarBlock(CollectionCanvas.CollectionBlock):
    """ Abstract block used as base Kind for Calendar related blocks.

    This base class can be used for any block that displays a collection of
    items based on a date range.

    @ivar rangeStart: beginning of the currently displayed range (persistent)
    @type rangeStart: mx.DateTime.DateTime
    @ivar rangeIncrement: increment used to find the next or prev block of time
    @type rangeIncrement: mx.DateTime.RelativeDateTime
    """
    
    def __init__(self, *arguments, **keywords):
        super(CalendarBlock, self).__init__(*arguments, **keywords)

    # Event handling
    
    def onSelectedDateChangedEvent(self, event):
        """
        Sets the selected date range and synchronizes the widget.

        @param event: event sent on selected date changed event
        @type event: osaf.framework.blocks.Block.BlockEvent
        @param event['start']: start of the newly selected date range
        @type event['start']: mx.DateTime.DateTime
        """
        self.setRange(event.arguments['start'])
        self.widget.wxSynchronizeWidget()

    def postDateChanged(self):
        """
        Convenience method for changing the selected date.
        """
        self.postEventByName ('SelectedDateChanged',{'start':self.selectedDate})

    # Managing the date range

    def setRange(self, date):
        """ Sets the range to include the given date.

        @param date: date to include
        @type date: mx.DateTime.DateTime
        """
        self.rangeStart = date
        self.selectedDate = self.rangeStart

    def incrementRange(self):
        """ Increments the calendar's current range """
        self.rangeStart += self.rangeIncrement
        if self.selectedDate:
            self.selectedDate += self.rangeIncrement

    def decrementRange(self):
        """ Decrements the calendar's current range """
        self.rangeStart -= self.rangeIncrement
        if self.selectedDate:
            self.selectedDate -= self.rangeIncrement

    # Get items from the collection

    def getDayItemsByDate(self, date):
        nextDate = date + DateTime.RelativeDateTime(days=1)
        for item in self.contents:
            try:
                anyTime = item.anyTime
            except AttributeError:
                anyTime = False
            try:
                allDay = item.allDay
            except AttributeError:
                allDay = False
            if (item.hasLocalAttributeValue('startTime') and
                (allDay or anyTime) and
                (item.startTime >= date) and
                (item.startTime < nextDate)):
                yield item

    def itemIsInRange(self, item, start, end):
        """
        Helpful utility to determine if an item is within a given range
        Assumes the item has a startTime and endTime attribute
        """
        # three possible cases where we're "in range"
        # 1) start time is within range
        # 2) end time is within range
        # 3) start time before range, end time after
        return (((item.startTime >= start) and
                 (item.startTime < end)) or 
                ((item.endTime >= start) and
                 (item.endTime < end)) or 
                ((item.startTime <= start) and
                 (item.endTime >= end)))

    def getItemsInRange(self, date, nextDate):
        """
        Convenience method to look for the items in the block's contents
        that appear on the given date. We might be able to push this
        to Queries, but itemIsInRange is actually fairly complex.
        
        @type date: mx.DateTime.DateTime
        @type nextDate: mx.DateTime.DateTime
        @return: the items in this collection that appear within the given range
        @rtype: list of Items
        """
        for item in self.contents:
            try:
                anyTime = item.anyTime
            except AttributeError:
                anyTime = False
            try:
                allDay = item.allDay
            except AttributeError:
                allDay = False
            if (item.hasLocalAttributeValue('startTime') and
                item.hasLocalAttributeValue('endTime') and
                (not allDay and not anyTime) and
                self.itemIsInRange(item, date, nextDate)):
                yield item

    def GetCurrentDateRange(self):
        if self.dayMode:
            startDay = self.selectedDate
            endDay = startDay + DateTime.RelativeDateTime(days = 1)
        else:
            startDay = self.rangeStart
            endDay = startDay + self.rangeIncrement
        return (startDay, endDay)

    #
    # Color stuff
    #
    def getCalendarData(self):
        """
        Lazily stamp the data
        """
        caldata = self.contents.source
        if not isinstance(caldata, CalendarData):
            caldata.StampKind('add', CalendarData.getKind(view=caldata.itsView))
            
            # XXX really, the object should be lazily creating this.
            
            colorstyle = Styles.ColorStyle(view=self.itsView)
            # make copies, because initialValue ends up being shared, because
            # it is isn't immutable
            colorstyle.foregroundColor = copy.copy(colorstyle.foregroundColor)
            colorstyle.backgroundColor = copy.copy(colorstyle.backgroundColor)
            
            caldata.calendarColor = colorstyle

            self.setupNextHue()
            
        return caldata
                            
    calendarData = property(getCalendarData)

    def setupNextHue(self):
        c = self.contents.source.calendarColor.backgroundColor
        self.lastHue = CalendarData.getNextHue(self.lastHue)
        (c.red, c.green, c.blue) = rgb2color(*hsv_to_rgb(self.lastHue, 1.0, 1.0))
        
    def getEventColors(self, event):
        """
        Get the eventColors object which contains all the right color tints
        for the given event. If the given event doesn't have color data,
        then we return the default one associated with the view
        """
        containingCollections = event.itemCollectionInclusions
        calDataKind = CalendarData.getKind(view=self.itsView)
        for coll in containingCollections:

            # hack alert! The out-of-the-box collections aren't renameable, so
            # we'll rely on that to make sure we don't get 'All's color
            if (not hasattr(coll, 'renameable') or coll.renameable) and \
                coll.isItemOf(calDataKind):
                return coll
        return self.calendarData

    def setCalendarColor(self, color):
        """
        Set the base color from which all tints are determined. Note that
        this will lazily stamp the selected collection
        """
        ec = copy.copy(self.calendarData.eventColor)
        (ec.red, ec.green, ec.blue) = color
        self.calendarData.eventColor = ec
                        
class wxCalendarCanvas(CollectionCanvas.wxCollectionCanvas):
    """
    Base class for all calendar canvases - handles basic item selection, 
    date ranges, and so forth
    """
    def __init__(self, *arguments, **keywords):
        super (wxCalendarCanvas, self).__init__ (*arguments, **keywords)


        self.Bind(wx.EVT_SCROLLWIN, self.OnScroll)
        
    def OnInit(self):
        self.editor = wxInPlaceEditor(self, -1) 
        
    def OnScroll(self, event):
        self.Refresh()
        event.Skip()

    def OnSelectItem(self, item):
        self.parent.blockItem.selection = item
        self.parent.blockItem.postSelectItemBroadcast()
        #self.parent.wxSynchronizeWidget()
    
    def GrabFocusHack(self):
        self.editor.SaveItem()
        self.editor.Hide()
        
    def GetCurrentDateRange(self):
        return self.parent.blockItem.GetCurrentDateRange()


class wxWeekPanel(wx.Panel, CalendarEventHandler):
    def __init__(self, *arguments, **keywords):
        super (wxWeekPanel, self).__init__ (*arguments, **keywords)

        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)

        self.scrollbarWidth = wx.SystemSettings_GetMetric(wx.SYS_VSCROLL_X)
        
        self.headerWidgets = wxWeekHeaderWidgets(self, -1)
        self.headerCanvas = wxWeekHeaderCanvas(self, -1)
        self.columnCanvas = wxWeekColumnCanvas(self, -1)
        self.headerWidgets.parent = self
        self.headerCanvas.parent = self
        self.columnCanvas.parent = self

        box = wx.BoxSizer(wx.VERTICAL)
        box.Add(self.headerWidgets, 0, wx.EXPAND)
        box.Add(self.headerCanvas, 0, wx.EXPAND)
        box.Add(self.columnCanvas, 1, wx.EXPAND)
        self.SetSizer(box)
        
        # This is where all the styles come from - eventually should probably
        # be moved up to the block
        if '__WXMAC__' in wx.PlatformInfo:
            
            bigFont = wx.Font(13, wx.NORMAL, wx.NORMAL, wx.NORMAL)
            bigBoldFont = wx.Font(13, wx.NORMAL, wx.NORMAL, wx.BOLD)
            smallFont = wx.Font(10, wx.SWISS, wx.NORMAL, wx.NORMAL,
                                face="Verdana")
            smallBoldFont = wx.Font(10, wx.SWISS, wx.NORMAL, wx.BOLD,
                                    face="Verdana")
        else:
            bigFont = wx.Font(11, wx.NORMAL, wx.NORMAL, wx.NORMAL)
            bigBoldFont = wx.Font(11, wx.NORMAL, wx.NORMAL, wx.BOLD)
            smallFont = wx.Font(8, wx.SWISS, wx.NORMAL, wx.NORMAL,
                                face="Verdana")
            smallBoldFont = wx.Font(8, wx.SWISS, wx.NORMAL, wx.BOLD,
                                         face="Verdana")

        self.monthLabelFont = bigBoldFont
        self.monthLabelColor = wx.Colour(64, 64, 64)
        
        self.eventLabelFont = smallFont
        self.eventLabelColor = wx.BLACK
        
        self.eventTimeFont = smallBoldFont
        
        self.legendFont = bigBoldFont
        self.legendColor = wx.Colour(153, 153, 153)

        self.bgColor = wx.WHITE

        self.majorLinePen = wx.Pen(wx.Colour(204, 204, 204))
        self.minorLinePen = wx.Pen(wx.Colour(229, 229, 229))
        self.selectionBrush = wx.Brush(wx.Colour(217, 217, 217)) # or 229?
        self.selectionPen = wx.Pen(wx.Colour(102,102,102))

        self.Bind(wx.EVT_SIZE, self.OnSize)
        
        # gradient cache
        self._gradientCache = {}
        
    def _doDrawingCalculations(self):
        self.size = self.GetSize()
        
        self.xOffset = (self.size.width - self.scrollbarWidth) / 8
        
        try:
            oldDayWidth = self.dayWidth
        except AttributeError:
            oldDayWidth = -1
            
        self.dayWidth = (self.size.width - self.scrollbarWidth - self.xOffset) / self.blockItem.daysPerView

        # the gradient brushes are based on dayWidth, so blow it away
        # when dayWidth changes
        if oldDayWidth != self.dayWidth:
            self._gradientCache = {}
        
        if self.blockItem.dayMode:
            self.columns = 1
        else:
            self.columns = self.blockItem.daysPerView        

    def OnEraseBackground(self, event):
        pass

    def OnInit(self):
        self._doDrawingCalculations()
        self.headerWidgets.OnInit()
        self.headerCanvas.OnInit()
        self.columnCanvas.OnInit()
        
    def OnSize(self, event):
        self._doDrawingCalculations()
        event.Skip()

    def wxSynchronizeWidget(self):
        
        self._doDrawingCalculations()
        #self.Layout()
        self.headerWidgets.wxSynchronizeWidget()
        self.headerCanvas.wxSynchronizeWidget()
        self.columnCanvas.wxSynchronizeWidget()
        
    def PrintCanvas(self, dc):
        self.columnCanvas.PrintCanvas(dc)

    def OnDaySelect(self, day):
            
        startDate = self.blockItem.rangeStart
        selectedDate = startDate + DateTime.RelativeDateTime(days=day)
        
        # @@@ add method on block item for setting selected date
        self.blockItem.selectedDate = selectedDate
        self.blockItem.dayMode = True
        self.blockItem.postDateChanged()
        self.wxSynchronizeWidget()

    def OnWeekSelect(self):
        self.blockItem.dayMode = False
        self.blockItem.selectedDate = self.blockItem.rangeStart
        self.blockItem.postDateChanged()
        self.wxSynchronizeWidget()

    def OnExpand(self):
        self.headerCanvas.toggleSize()
        self.Layout()
        
    def OnSelectColor(self, event):
        c = event.GetValue().Get()
        self.blockItem.setCalendarColor(c)
        
        # just cause a repaint - hopefully this cascades to child windows?
        self.Refresh()
        
    def MakeGradientBitmap(self, width, leftColor, rightColor):
        """
        Creates a gradient brush from leftColor to rightColor, specified
        as color tuples (r,g,b)
        The brush is a bitmap, width of self.dayWidth, height 1. The color 
        gradient is made by varying the color saturation from leftColor to 
        rightColor. This means that the Hue and Value should be the same, 
        or the resulting color on the right won't match rightColor
        """
        
        # There is probably a nicer way to do this, without:
        # - going through wxImage
        # - individually setting each RGB pixel
        image = wx.EmptyImage(width, 1)
        leftHSV = rgb_to_hsv(*color2rgb(*leftColor))
        rightHSV = rgb_to_hsv(*color2rgb(*rightColor))
        
        # make sure they are the same hue
        # this doesn't quite work, because sometimes division issues
        # cause numbers to be very close, but not quite the same
        #assert leftHSV[0] == rightHSV[0]
        #assert leftHSV[2] == rightHSV[2]
        
        hue = leftHSV[0]
        value = leftHSV[2]
        satStart = leftHSV[1]
        satDelta = rightHSV[1] - leftHSV[1]
        satStep = satDelta / width
        
        # assign a sliding scale of floating point values from left to right
        # in the bitmap
        for x in xrange(width):
            sat = satStart + satStep*x
            newColor = rgb2color(*hsv_to_rgb(hue, sat, value))
            image.SetRGB(x,0,*newColor)
        
        # and now we have to go from Image -> Bitmap. Yuck.
        return wx.BitmapFromImage(image)
        
    def GetGradientBitmap(self, width, leftColor, rightColor):
        """
        Gets an appropriately sized gradient brush from the cache, 
        or creates one if necessary
        """
        key = (width, leftColor, rightColor)
        bitmap = self._gradientCache.get(key, None)
        if not bitmap:
            bitmap = self.MakeGradientBitmap(*key)
            self._gradientCache[key] = bitmap
        return bitmap
        

class wxWeekHeaderWidgets(wx.Panel):

    currentSelectedDate = None
    currentStartDate = None
    
    def OnInit(self):
        self.SetBackgroundColour(self.parent.bgColor)

        # Set up sizers
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        navigationRow = wx.BoxSizer(wx.HORIZONTAL)
        
        sizer.Add((3,3), 0, wx.EXPAND)
        sizer.Add(navigationRow, 0, wx.EXPAND)
        sizer.Add((3,3), 0, wx.EXPAND)

        # beginnings of  in the calendar
        self.colorSelect = colourselect.ColourSelect(self, -1)
        self.Bind(colourselect.EVT_COLOURSELECT, self.parent.OnSelectColor)
        navigationRow.Add(self.colorSelect, 0, wx.EXPAND)

        today = DateTime.today()
        styles = self.parent
        self.monthButton = CollectionCanvas.CanvasTextButton(self, today.Format("%B %Y"),
                                                             styles.monthLabelFont, 
                                                             styles.monthLabelColor,
                                                             styles.bgColor)
        navigationRow.Add((0,0), 1)
        navigationRow.Add(self.monthButton, 0, wx.ALIGN_CENTER)
        navigationRow.Add((0,0), 1)
        
        # 
        # top row - left/right buttons, anchored to the right
        self.prevButton = CollectionCanvas.CanvasBitmapButton(self, "backarrow.png")
        self.nextButton = CollectionCanvas.CanvasBitmapButton(self, "forwardarrow.png")
        self.Bind(wx.EVT_BUTTON, self.parent.OnPrev, self.prevButton)
        self.Bind(wx.EVT_BUTTON, self.parent.OnNext, self.nextButton)

        #navigationRow.Add((0,0), 1, wx.EXPAND)
        navigationRow.Add(self.prevButton, 0, wx.EXPAND)
        navigationRow.Add((5,5), 0)
        navigationRow.Add(self.nextButton, 0, wx.EXPAND)
        navigationRow.Add((5,5), 0)
        
        #
        # finally the last row, with the header
        self.weekHeader = wx.colheader.ColumnHeader(self)
        
        # turn this off for now, because our sizing needs to be exact
        self.weekHeader.SetAttribute(wx.colheader.CH_ATTR_ProportionalResizing,False)
        headerLabels = ["Week", "S", "M", "T", "W", "T", "F", "S", "+"]
        for header in headerLabels:
            self.weekHeader.AppendItem(header, wx.colheader.CH_JUST_Center, 5, bSortEnabled=False)
        self.Bind(wx.colheader.EVT_COLUMNHEADER_SELCHANGED, self.OnDayColumnSelect, self.weekHeader)

        # set up initial selection
        self.weekHeader.SetAttribute(wx.colheader.CH_ATTR_VisibleSelection,True)
        self.UpdateHeader()
        sizer.Add(self.weekHeader, 0, wx.EXPAND)
        
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.SetSizer(sizer)
        sizer.SetSizeHints(self)
        self.Layout()

    def UpdateHeader(self):
        if self.parent.blockItem.dayMode:
            # ugly back-calculation of the previously selected day
            reldate = self.parent.blockItem.selectedDate - \
                      self.parent.blockItem.rangeStart
            self.weekHeader.SetSelectedItem(reldate.day+1)
        else:
            self.weekHeader.SetSelectedItem(0)

    def ResizeHeader(self):
        # column layout rules are funky:
        # - the "Week" column and the first 6 days are more or less fixed at self.dayWidth
        # - the last column (expando-button) is fixed
        # - the 7th day is flexy

        size = self.GetSize()
        columnCount = self.weekHeader.GetItemCount()
        drawInfo = self.parent
        for day in range(columnCount - 2):
            self.weekHeader.SetUIExtent(day, (0, drawInfo.dayWidth))

        lastWidth = size.width - (drawInfo.dayWidth * (columnCount-2)) - drawInfo.scrollbarWidth
        self.weekHeader.SetUIExtent(columnCount-2, (0, lastWidth))
        self.weekHeader.SetUIExtent(columnCount-1, (0, drawInfo.scrollbarWidth))

    def OnSize(self, event):
        self.ResizeHeader()
        event.Skip()
        
    def wxSynchronizeWidget(self):
        selectedDate = self.parent.blockItem.selectedDate
        startDate = self.parent.blockItem.rangeStart

        if (selectedDate == self.currentSelectedDate and
            startDate == self.currentStartDate):
            return

        # update the calendar with the calender's color
        self.colorSelect.SetColour(self.parent.blockItem.calendarData.eventColor.wxColor())

        # Update the month button given the selected date
        lastDate = startDate + DateTime.RelativeDateTime(days=6)
        if (startDate.month == lastDate.month):
            monthText = selectedDate.Format("%B %Y")
        else:
            monthText = "%s - %s" % (startDate.Format("%B"),
                                     lastDate.Format("%B %Y"))
     
        self.monthButton.SetLabel(monthText)

        today = DateTime.today()
        for day in range(7):
            currentDate = startDate + DateTime.RelativeDateTime(days=day)
            if currentDate == today:
                dayName = "Today"
            else:
                dayName = currentDate.Format('%a ') + str(currentDate.day)
            self.weekHeader.SetLabelText(day+1, dayName)
            
            
        self.currentSelectedDate = selectedDate
        self.currentStartDate = startDate
        
        self.Layout()
        
    def OnDayColumnSelect(self, event):
        """
        dispatches to appropriate events in self.parent, 
        based on the column selected
        """
        
        colIndex = self.weekHeader.GetSelectedItem()
        
        # column 0, week button
        if (colIndex == 0):
            return self.parent.OnWeekSelect()
            
        # last column, the "+" expand button
        # (this may change...)
        if (colIndex == 8):
            # re-fix selection so that the expand button doesn't stay selected
            self.UpdateHeader()
            return self.parent.OnExpand()
        
        # all other cases mean a day was selected
        # OnDaySelect takes a zero-based day, and our first day is in column 1
        return self.parent.OnDaySelect(colIndex-1)



class wxWeekHeaderCanvas(wxCalendarCanvas):
    def __init__(self, *arguments, **keywords):
        super (wxWeekHeaderCanvas, self).__init__ (*arguments, **keywords)

        self.fixed = True

        # @@@ constants
        
        self.hourHeight = 40
        self.dayHeight = self.hourHeight * 24

    def OnInit(self):
        super (wxWeekHeaderCanvas, self).OnInit()
        
        self.SetMinSize((-1,20))
        self.size = self.GetSize()
        # Event handlers
        self.Bind(wx.EVT_SIZE, self.OnSize)
                    
    
    def OnSize(self, event):
        self.size = self.GetSize()
        self.RebuildCanvasItems()
        
        self.Refresh()
        event.Skip()
        
    def wxSynchronizeWidget(self):
        self.RebuildCanvasItems()
        self.Refresh()

    def toggleSize(self):
        # Toggles size between fixed and large enough to show all tasks
        if self.fixed:
            self.oldFixedSize = self.GetMinSize()
            if self.fullHeight > self.oldFixedSize.height:
                self.SetMinSize((-1, self.fullHeight + 9))
            else:
                self.SetMinSize(self.oldFixedSize)
        else:
            self.SetMinSize(self.oldFixedSize)
        self.fixed = not self.fixed

    # Drawing code
    def DrawBackground(self, dc):
        styles = self.parent
        
        # Use the transparent pen for painting the background
        dc.SetPen(wx.TRANSPARENT_PEN)
        
        # Paint the entire background
        dc.SetBrush(wx.WHITE_BRUSH)
        dc.DrawRectangle(0, 0, self.size.width, self.size.height)

        dc.SetPen(styles.majorLinePen)

        drawInfo = self.parent
        # Draw lines between days
        for day in range(drawInfo.columns):
            dc.DrawLine(drawInfo.xOffset + (drawInfo.dayWidth * day), 0,
                        drawInfo.xOffset + (drawInfo.dayWidth * day),
                        self.size.height)

        # Draw one extra line to parallel the scrollbar below
        dc.DrawLine(self.size.width - drawInfo.scrollbarWidth, 0,
                    self.size.width - drawInfo.scrollbarWidth,
                    self.size.height)

        
    def DrawCells(self, dc):
        
        styles = self.parent

        #dc.SetTextForeground(styles.eventLabelColor)
        dc.SetFont(styles.eventLabelFont)
        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.SetBrush(wx.WHITE_BRUSH)
        
        selectedBox = None

        for canvasItem in self.canvasItemList:
            dc.SetPen(wx.TRANSPARENT_PEN)
            # save the selected box to be drawn last
            item = canvasItem.GetItem()
            if self.parent.blockItem.selection is item:
                selectedBox = canvasItem
            else:
                eventColors = styles.blockItem.getEventColors(item)
                #dc.SetPen(wx.Pen(eventColors.outlineColor))
                #dc.SetBrush(wx.Brush(eventColors.gradientLeft))
                dc.SetTextForeground(eventColors.textColor)
                canvasItem.Draw(dc, styles)
        
        if selectedBox:
            eventColors = styles.blockItem.getEventColors(selectedBox.GetItem())
            dc.SetPen(wx.Pen(eventColors.selectedOutlineColor))
            bitmap = styles.GetGradientBitmap(self.parent.dayWidth,
                                              eventColors.selectedGradientLeft,
                                              eventColors.selectedGradientRight)
            brush = wx.Brush(wx.WHITE,wx.STIPPLE)
            brush.SetStipple(bitmap)
            dc.SetBrush(brush)
            dc.SetTextForeground(eventColors.selectedTextColor)

            selectedBox.Draw(dc, styles)

        # Draw a line across the bottom of the header
        dc.SetPen(styles.majorLinePen)
        dc.DrawLine(0, self.size.height - 1,
                    self.size.width, self.size.height - 1)
        dc.DrawLine(0, self.size.height - 4,
                    self.size.width, self.size.height - 4)
        dc.SetPen(styles.minorLinePen)
        dc.DrawLine(0, self.size.height - 2,
                    self.size.width, self.size.height - 2)
        dc.DrawLine(0, self.size.height - 3,
                    self.size.width, self.size.height - 3)

            
    def RebuildCanvasItems(self):
        self.canvasItemList = []

        if self.parent.blockItem.dayMode:
            startDay = self.parent.blockItem.selectedDate
            width = self.size.width
        else:
            startDay = self.parent.blockItem.rangeStart
            width = self.parent.dayWidth

        self.fullHeight = 0
        size = self.GetSize()
        for day in range(self.parent.columns):
            currentDate = startDay + DateTime.RelativeDateTime(days=day)
            rect = wx.Rect((self.parent.dayWidth * day) + self.parent.xOffset, 0,
                           width, size.height)
            self.RebuildCanvasItemsByDay(currentDate, rect)



    def RebuildCanvasItemsByDay(self, date, rect):
        x = rect.x
        y = rect.y
        w = rect.width
        h = 15

        for item in self.parent.blockItem.getDayItemsByDate(date):
            itemRect = wx.Rect(x, y, w, h)
            
            canvasItem = HeaderCanvasItem(itemRect, item)
            self.canvasItemList.append(canvasItem)
            
            # keep track of the current drag/resize box
            if self._currentDragBox and self._currentDragBox.GetItem() == item:
                self._currentDragBox = canvasItem

            y += itemRect.height
            
        if (y > self.fullHeight):
            self.fullHeight = y
                    
    def OnCreateItem(self, unscrolledPosition):
        view = self.parent.blockItem.itsView
        newTime = self.getDateTimeFromPosition(unscrolledPosition)
        event = Calendar.CalendarEvent(view=view)
        event.InitOutgoingAttributes()
        event.ChangeStart(DateTime.DateTime(newTime.year, newTime.month,
                                            newTime.day,
                                            event.startTime.hour,
                                            event.startTime.minute))
        event.allDay = True

        self.parent.blockItem.contents.source.add(event)
        self.OnSelectItem(event)
        view.commit()
        return event

    def OnDraggingItem(self, unscrolledPosition):
        if self.parent.blockItem.dayMode:
            return
        
        newTime = self.getDateTimeFromPosition(unscrolledPosition)
        item = self._currentDragBox.GetItem()
        if (newTime.absdate != item.startTime.absdate):
            item.ChangeStart(DateTime.DateTime(newTime.year, newTime.month,
                                               newTime.day,
                                               item.startTime.hour,
                                               item.startTime.minute))
            self.Refresh()

    def OnEditItem(self, box):
        position = box.GetEditorPosition()
        size = box.GetMaxEditorSize()

        self.editor.SetItem(box.GetItem(), position, size, size.height)


    def getDateTimeFromPosition(self, position):
        # bound the position by the available space that the user 
        # can see/scroll to
        yPosition = max(position.y, 0)
        xPosition = max(position.x, self.parent.xOffset)
        
        if (self.fixed):
            height = self.GetMinSize().GetWidth()
        else:
            height = self.fullHeight
            
        yPosition = min(yPosition, height)
        xPosition = min(xPosition, self.parent.xOffset + self.parent.dayWidth * self.parent.columns - 1)

        if self.parent.blockItem.dayMode:
            newDay = self.parent.blockItem.selectedDate
        elif self.parent.dayWidth > 0:
            deltaDays = (xPosition - self.parent.xOffset) / self.parent.dayWidth
            startDay = self.parent.blockItem.rangeStart
            newDay = startDay + DateTime.RelativeDateTime(days=deltaDays)
        else:
            newDay = self.parent.blockItem.rangeStart
        return newDay

class wxWeekColumnCanvas(wxCalendarCanvas):

    def wxSynchronizeWidget(self):
        self._doDrawingCalculations()
        self.RebuildCanvasItems()
        self.Refresh()
        
    def OnSize(self, event):
        self._doDrawingCalculations()
        self.RebuildCanvasItems()
        #self.Refresh()
        #event.Skip()

    def OnInit(self):
        super (wxWeekColumnCanvas, self).OnInit()
        
        # @@@ rationalize drawing calculations...
        self.hourHeight = 40
        
        self._scrollYRate = 10
        
        self._bgSelectionStartTime = None
        self._bgSelectionEndTime = None
        
        # determines if we're dragging the start or the end of an event, usually
        # the end
        self._bgSelectionDragEnd = True
        
        self.SetVirtualSize((self.GetVirtualSize().width, self.hourHeight*24))
        self.SetScrollRate(0, self._scrollYRate)
        self.Scroll(0, (self.hourHeight*7)/self._scrollYRate)
        
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyPressed)

    def ScaledScroll(self, dx, dy):
        (scrollX, scrollY) = self.CalcUnscrolledPosition(0,0)
        scrollX += dx
        scrollY += dy
        
        # rounding ensures we scroll at least one unit
        if dy < 0:
            rounding = -self._scrollYRate
        else:
            rounding = self._scrollYRate

        scaledY = (scrollY // self._scrollYRate) + rounding
        self.Scroll(scrollX, scaledY)
        
    def _doDrawingCalculations(self):
        # @@@ magic numbers
        self.size = self.GetVirtualSize()
        self.xOffset = self.size.width / 8
        if self.parent.blockItem.dayMode:
            self.parent.columns = 1
        else:
            self.parent.columns = self.parent.blockItem.daysPerView

        self.dayWidth = (self.size.width - self.xOffset) / self.parent.columns
            
        self.dayHeight = self.hourHeight * 24

    def DrawBackground(self, dc):
        styles = self.parent
        self._doDrawingCalculations()

        # Use the transparent pen for painting the background
        dc.SetPen(wx.TRANSPARENT_PEN)
        
        # Paint the entire background
        dc.SetBrush(wx.WHITE_BRUSH)
        dc.DrawRectangle(0, 0, self.size.width, self.size.height + 10)

        # Set text properties for legend
        dc.SetTextForeground(styles.legendColor)
        dc.SetFont(styles.legendFont)

        # Use topTime to draw am/pm on the topmost hour
        topCoordinate = self.CalcUnscrolledPosition((0,0))
        topTime = self.getDateTimeFromPosition(wx.Point(topCoordinate[0],
                                                        topCoordinate[1]))
        
        #bottomCoordinate = self.CalcUnscrolledPosition((
        #bottomTime = self.getDateTimeFromPosition(wx.Point(bottomCoordinate[0],
        #                                                   bottomCoordinate[1]))

        # Draw the lines separating hours
        halfHourHeight = self.hourHeight/2
        for hour in range(24):
            
            # Draw the hour legend
            if (hour > 0):
                if (hour == 1):
                    hourString = "am 1"
                elif (hour == 12): 
                    hourString = "pm 12"
                elif (hour > 12):
                    if (hour == (topTime.hour + 1)): # topmost hour
                        hourString = "pm %s" % str(hour - 12)
                    else:
                        hourString = str(hour - 12)
                else:
                    if (hour == (topTime.hour + 1)): # topmost hour
                        hourString = "am %s" % str(hour)
                    else:
                        hourString = str(hour)
                wText, hText = dc.GetTextExtent(hourString)
                dc.DrawText(hourString,
                            self.xOffset - wText - 5,
                             hour * self.hourHeight - (hText/2))
            
            # Draw the line between hours
            dc.SetPen(styles.majorLinePen)
            dc.DrawLine(self.xOffset,
                         hour * self.hourHeight,
                        self.size.width,
                         hour * self.hourHeight)

            # Draw the line between half hours
            dc.SetPen(styles.minorLinePen)
            dc.DrawLine(self.xOffset,
                         hour * self.hourHeight + halfHourHeight,
                        self.size.width,
                         hour * self.hourHeight + halfHourHeight)

        # Draw lines between days
        for day in range(self.parent.columns):
            if day == 0:
                dc.SetPen(styles.majorLinePen)
            else:
                dc.SetPen(styles.minorLinePen)
            dc.DrawLine(self.xOffset + (self.dayWidth * day), 0,
                        self.xOffset + (self.dayWidth * day), self.size.height)

        (startDay, endDay) = self.GetCurrentDateRange()
        # draw selection stuff
        if (self._bgSelectionStartTime and self._bgSelectionEndTime):
            dc.SetPen(styles.majorLinePen)
            dc.SetBrush(styles.selectionBrush)
            
            rects = \
                ColumnarCanvasItem.GenerateBoundsRects(self,
                                                       self._bgSelectionStartTime,
                                                       self._bgSelectionEndTime)
            for rect in rects:
                dc.DrawRectangleRect(rect)

    @staticmethod
    def sortByStartTime(item1, item2):
        """
        Comparison function for sorting, mostly by start time
        """
        dateResult = DateTime.cmp(item1.startTime, item2.startTime)
        
        # when two items start at the same time, we actually want to show the
        # SHORTER event last, so that painting draws it on top
        if dateResult == 0:
            dateResult = DateTime.cmp(item2.endTime, item1.endTime)
        return dateResult

    def RebuildCanvasItems(self):
        
        self.canvasItemList = []

        (startDay, endDay) = self.GetCurrentDateRange()
        
        # we sort the items so that when drawn, the later events are drawn last
        # so that we get proper stacking
        visibleItems = list(self.parent.blockItem.getItemsInRange(startDay, endDay))
        visibleItems.sort(self.sortByStartTime)
                
        
        # First generate a sorted list of ColumnarCanvasItems
        for item in visibleItems:
                                               
            canvasItem = ColumnarCanvasItem(item, self)
            self.canvasItemList.append(canvasItem)

            if self._currentDragBox and self._currentDragBox.GetItem() == item:
                self._currentDragBox = canvasItem                

        # now generate conflict info
        self.CheckConflicts()
        
        for canvasItem in self.canvasItemList:
            # drawing rects should be updated to reflect conflicts
            canvasItem.UpdateDrawingRects()
            
        # canvasItemList has to be sorted by depth
        # should be relatively quick because the canvasItemList is already
        # sorted by startTime. If no conflicts, this is an O(n) operation
        # (note that as of Python 2.4, sorts are stable, so this remains safe)
        self.canvasItemList.sort(key=ColumnarCanvasItem.GetIndentLevel)
        
        
    def DrawCells(self, dc):
        styles = self.parent
        
        # Set up fonts and brushes for drawing the events
        dc.SetTextForeground(wx.BLACK)
        dc.SetBrush(wx.WHITE_BRUSH)

        selectedBox = None        
        # finally, draw the items
        boundingRect = wx.Rect(self.xOffset, 0, self.size.width, self.size.height)
        for canvasItem in self.canvasItemList:

            item = canvasItem.GetItem()
            
            # save the selected box to be drawn last
            if self.parent.blockItem.selection is item:
                selectedBox = canvasItem
            else:
                eventColors = styles.blockItem.getEventColors(item)
                dc.SetPen(wx.Pen(eventColors.outlineColor))
                bitmap = styles.GetGradientBitmap(self.dayWidth, eventColors.gradientLeft, 
                                                  eventColors.gradientRight)
                dc.SetTextForeground(eventColors.textColor)
                
                canvasItem.Draw(dc, boundingRect, styles, bitmap)
            
        # now draw the current item on top of everything else
        if selectedBox:
            item = selectedBox.GetItem()
            eventColors = styles.blockItem.getEventColors(item)
            dc.SetPen(wx.Pen(eventColors.selectedOutlineColor))
            bitmap = styles.GetGradientBitmap(self.dayWidth, eventColors.selectedGradientLeft,
                                              eventColors.selectedGradientRight)
            dc.SetTextForeground(eventColors.selectedTextColor)
            selectedBox.Draw(dc, boundingRect, styles, bitmap)
        
    def CheckConflicts(self):
        for itemIndex, canvasItem in enumerate(self.canvasItemList):
            # since these are sorted, we only have to check the items 
            # that come after the current one
            for innerItem in self.canvasItemList[itemIndex+1:]:
                # we know we're done when we stop hitting conflicts
                # 
                # have a guarantee that innerItem.startTime >= item.endTime
                # Since item.endTime < item.startTime, we know we're
                # done
                if innerItem.GetItem().startTime >= canvasItem.GetItem().endTime: break
                
                # item and innerItem MUST conflict now
                canvasItem.AddConflict(innerItem)
            
            # we've now found all conflicts for item, do we need to calculate
            # depth or anything?
            # first theory: leaf children have a maximum conflict depth?
            canvasItem.CalculateConflictDepth()


    def OnKeyPressed(self, event):
        # create an event here - unfortunately the panel can't get focus, so it
        # can't recieve keystrokes yet...
        pass
            
    # handle mouse related actions: move, resize, create, select
    
    def OnSelectItem(self, item):
        if item:
            # clear background selection when an existing item is selected
            self._bgSelectionStartTime = self._bgSelectionEndTime = None
        
        super(wxWeekColumnCanvas, self).OnSelectItem(item)
        
    def OnSelectNone(self, unscrolledPosition):
        selectedTime = self.getDateTimeFromPosition(unscrolledPosition)
        
        # only select something new if there's no existing selection, or if 
        # we're outside of an existing selection
        if (not self._bgSelectionStartTime or
            selectedTime < self._bgSelectionStartTime or
            selectedTime > self._bgSelectionEndTime):
            self._bgSelectionStartTime = self.getDateTimeFromPosition(unscrolledPosition)
            self._bgSelectionDragEnd = True
            self._bgSelectionEndTime = self._bgSelectionStartTime + \
                DateTime.RelativeDateTime(minutes=30)
            
        # set focus on the calendar so that we can receive key events
        # (as of this writing, wxPanel can't recieve focus, so this is a no-op)
        self.SetFocus()
        super(wxWeekColumnCanvas, self).OnSelectNone(unscrolledPosition)
        
    def OnEditItem(self, box):
        styles = self.parent
        position = self.CalcScrolledPosition(box.GetEditorPosition())
        size = box.GetMaxEditorSize()

        textPos = wx.Point(position.x + 8, position.y + 15)
        textSize = wx.Size(size.width - 13, size.height - 20)

        self.editor.SetItem(box.GetItem(), textPos, textSize, styles.eventLabelFont.GetPointSize()) 

    def OnCreateItem(self, unscrolledPosition):
        # @@@ this code might want to live somewhere else, refactored
        view = self.parent.blockItem.itsView
        event = Calendar.CalendarEvent(view=view)
        
        # if a region is selected, then use that for the event span
        if (self._bgSelectionStartTime):
            newTime = self._bgSelectionStartTime
            duration = self._bgSelectionEndTime - self._bgSelectionStartTime
        else:
            newTime = self.getDateTimeFromPosition(unscrolledPosition)
            duration = None
            
        event.InitOutgoingAttributes()
        event.ChangeStart(newTime)
        
        # only set the duration if its something larger than the default
        if duration and duration.hours >= 1:
            event.duration = duration

        # ugh, this is a hack to work around the whole ItemCollection stuff
        # see bug 2749 for some background
        self.parent.blockItem.contents.source.add(event)
        
        self.OnSelectItem(event)

        # @@@ Bug#1854 currently this is too slow,
        # and the event causes flicker
        #view.commit()
        canvasItem = ColumnarCanvasItem(event, self)
        
        # only problem here is that we haven't checked for conflicts
        canvasItem.UpdateDrawingRects()
        canvasItem.SetResizeMode(canvasItem.RESIZE_MODE_END)
        return canvasItem
        
    
    def OnBeginResizeItem(self):
        self._lastUnscrolledPosition = self._dragStartUnscrolled
        self.StartDragTimer()
        pass
        
    def OnEndResizeItem(self):
        self.StopDragTimer()
        self._originalDragBox.ResetResizeMode()
        pass
        
    def OnResizingItem(self, unscrolledPosition):
        newTime = self.getDateTimeFromPosition(unscrolledPosition)
        item = self._currentDragBox.GetItem()
        resizeMode = self.GetResizeMode()
        delta = DateTime.DateTimeDelta(0, 0, 15)
        
        # make sure we're changing by at least delta 
        if (resizeMode == ColumnarCanvasItem.RESIZE_MODE_END and 
            newTime > (item.startTime + delta)):
            item.endTime = newTime
        elif (resizeMode == ColumnarCanvasItem.RESIZE_MODE_START and 
              newTime < (item.endTime - delta)):
            item.startTime = newTime
        self.Refresh()
    
    def OnDragTimer(self):
        """
        This timer goes off while we're dragging/resizing
        """
        scrolledPosition = self.CalcScrolledPosition(self._dragCurrentUnscrolled)
        self.ScrollIntoView(scrolledPosition)
    
    def StartDragTimer(self):
        self.scrollTimer = ClosureTimer(self.OnDragTimer)
        self.scrollTimer.Start(100, wx.TIMER_CONTINUOUS)
    
    def StopDragTimer(self):
        self.scrollTimer.Stop()
        self.scrollTimer = None
        
    def OnBeginDragItem(self):
        self.StartDragTimer()
        pass
        
    def OnEndDragItem(self):
        self.StopDragTimer()
        pass
        
    def OnDraggingNone(self, unscrolledPosition):
        dragDateTime = self.getDateTimeFromPosition(unscrolledPosition)
        if self._bgSelectionDragEnd:
            self._bgSelectionEndTime = dragDateTime
        else:
            self._bgSelectionStartTime = dragDateTime
            
        if (self._bgSelectionEndTime < self._bgSelectionStartTime):
            # swap values, drag the other end
            self._bgSelectionDragEnd = not self._bgSelectionDragEnd
            (self._bgSelectionStartTime, self._bgSelectionEndTime) = \
                (self._bgSelectionEndTime, self._bgSelectionStartTime)
        self.Refresh()
            
        
    def OnDraggingItem(self, unscrolledPosition):
        # at the start of the drag, the mouse was somewhere inside the
        # dragbox, but not necessarily exactly at x,y
        #
        # so account for the original offset within the ORIGINAL dragbox so the 
        # mouse cursor stays in the same place relative to the original box
        
        # We need to figure out where the original drag started,
        # so the mouse stays in the same position relative to
        # the origin of the item
        (boxX,boxY) = self._originalDragBox.GetDragOrigin()
        dy = self._dragStartUnscrolled.y - boxY
        
        # dx is tricky: we want the user to be able to drag left/right within
        # the confines of the current day, but if they cross a day threshold,
        # then we want to shift the whole event over one day
        # to do this, we need to round dx to the nearest dayWidth
        dx = self._dragStartUnscrolled.x - boxX
        dx = int(dx/self.dayWidth) * self.dayWidth
        position = wx.Point(unscrolledPosition.x - dx, unscrolledPosition.y - dy)
        
        newTime = self.getDateTimeFromPosition(position)
        item = self._currentDragBox.GetItem()
        if ((newTime.absdate != item.startTime.absdate) or
            (newTime.hour != item.startTime.hour) or
            (newTime.minute != item.startTime.minute)):
            item.ChangeStart(newTime)
            self.RebuildCanvasItems()
            
            # this extra paint is actually unnecessary because ContainerBlock is
            # giving us too many paints on a drag anyway. Why? hmm.
            #self.Refresh()

    def GetResizeMode(self):
        """
        Helper method for drags
        """
        return self._originalDragBox.getResizeMode(self._dragStartUnscrolled)
        
    def getDateTimeFromPosition(self, position):
        # bound the position by the available space that the user 
        # can see/scroll to
        yPosition = max(position.y, 0)
        xPosition = max(position.x, self.xOffset)
        
        yPosition = min(yPosition, self.hourHeight * 24 - 1)
        xPosition = min(xPosition, self.xOffset + self.dayWidth * self.parent.columns - 1)
        
        (startDay, endDay) = self.GetCurrentDateRange()

        # @@@ fixes Bug#1831, but doesn't really address the root cause
        # (the window is drawn with (0,0) virtual size on mac)
        if self.dayWidth > 0:
            deltaDays = (xPosition - self.xOffset) / self.dayWidth
        else:
            deltaDays = 0
        
        deltaHours = yPosition / self.hourHeight
        deltaMinutes = ((yPosition % self.hourHeight) * 60) / self.hourHeight
        deltaMinutes = int(deltaMinutes/15) * 15
        newTime = startDay + DateTime.RelativeDateTime(days=deltaDays,
                                                       hours=deltaHours,
                                                       minutes=deltaMinutes)
        return newTime

    def getPositionFromDateTime(self, datetime):
        (startDay, endDay) = self.GetCurrentDateRange()
        
        if datetime < startDay or \
           datetime > endDay:
            raise ValueError, "Must be visible on the calendar"
            
        delta = datetime - startDay
        x = (self.dayWidth * delta.day) + self.xOffset
        y = int(self.hourHeight * (datetime.hour + datetime.minute/float(60)))
        return wx.Point(x, y)
        
class WeekBlock(CalendarBlock):
    def __init__(self, *arguments, **keywords):
        super(WeekBlock, self).__init__ (*arguments, **keywords)

    def initAttributes(self):
        if not self.hasLocalAttributeValue('rangeStart'):
            self.dayMode = False
            self.setRange(DateTime.today())
        if not self.hasLocalAttributeValue('rangeIncrement'):
            self.rangeIncrement = DateTime.RelativeDateTime(days=self.daysPerView)
            
    def instantiateWidget(self):
        # @@@ KCP move to a callback that gets called from parcel loader
        # after item has all of its attributes assigned from parcel xml
        self.initAttributes()
        
        return wxWeekPanel(self.parentBlock.widget,
                           Block.Block.getWidgetID(self))

    def setRange(self, date):
        if self.daysPerView == 7:
            # if in week mode, start at the beginning of the week
            delta = DateTime.RelativeDateTime(days=-6,
                                              weekday=(DateTime.Sunday, 0))
            self.rangeStart = date + delta
        else:
            # otherwise, stick with the given date
            self.rangeStart = date
            
        if self.dayMode:
            self.selectedDate = date
        else:
            self.selectedDate = self.rangeStart

class wxInPlaceEditor(wx.TextCtrl):
    def __init__(self, *arguments, **keywords):
        super(wxInPlaceEditor, self).__init__(style=wx.TE_PROCESS_ENTER | wx.NO_BORDER,
                                              *arguments, **keywords)
        
        self.item = None
        self.Bind(wx.EVT_TEXT_ENTER, self.OnTextEnter)
        self.Bind(wx.EVT_KILL_FOCUS, self.OnTextEnter)
        self.Hide()

        #self.editor.Bind(wx.EVT_CHAR, self.OnChar)
        parent = self.GetParent()
        parent.Bind(wx.EVT_SIZE, self.OnSize)

    def SaveItem(self):
        if ((self.item != None) and (not self.IsBeingDeleted())):
            self.item.displayName = self.GetValue()
        
    def OnTextEnter(self, event):
        self.SaveItem()
        self.Hide()
        event.Skip()

    def OnChar(self, event):
        if (event.KeyCode() == wx.WXK_RETURN):
            if self.item != None:
                self.item.displayName = self.GetValue()
            self.Hide()
        event.Skip()

    def SetItem(self, item, position, size, pointSize):
        self.item = item
        self.SetValue(item.displayName)

        newSize = wx.Size(size.width, size.height)

        # GTK doesn't like making the editor taller than
        # the font, plus it doesn't honor the NOBORDER style
        # so we have to include 4 pixels for each border
        if '__WXGTK__' in wx.PlatformInfo:
            newSize.height = pointSize + 8

        self.SetSize(newSize)
        self.Move(position)

        self.SetInsertionPointEnd()
        self.SetSelection(-1, -1)
        self.Show()
        self.SetFocus()

    def OnSize(self, event):
        self.Hide()
        event.Skip()

