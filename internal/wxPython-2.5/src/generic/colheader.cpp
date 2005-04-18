///////////////////////////////////////////////////////////////////////////////
// Name:		generic/colheader.cpp
// Purpose:	2-platform (Mac,MSW) + generic implementation of a native-appearance column header
// Author:	David Surovell
// Modified by:
// Created:	01.01.2005
// RCS-ID:
// Copyright:
// License:
///////////////////////////////////////////////////////////////////////////////

// ============================================================================
// declarations
// ============================================================================

// ----------------------------------------------------------------------------
// headers
// ----------------------------------------------------------------------------

#if defined(__GNUG__) && !defined(NO_GCC_PRAGMA)
	#pragma implementation "colheader.h"
#endif

// For compilers that support precompilation, includes "wx.h".
#include "wx/wxprec.h"

#if defined(__BORLANDC__)
	#pragma hdrstop
#endif

//#if wxUSE_COLUMNHEADER

#if defined(__WXMSW__)
	#define _WIN32_WINNT	0x5010
	#include <commctrl.h>
#elif defined(__WXMAC__)
	#include <TextEdit.h>
#endif

#if !defined(WX_PRECOMP)
	#include "wx/settings.h"
	#include "wx/listbox.h"
	#include "wx/dcclient.h"
	#include "wx/bitmap.h"
	#include "wx/gdicmn.h"
	#include "wx/colour.h"
#endif

#if defined(__WXMAC__)
#include "wx/mac/uma.h"
#endif

#include "wx/renderer.h"
#include "wx/colheader.h"

// ----------------------------------------------------------------------------
// wxWin macros
// ----------------------------------------------------------------------------

BEGIN_EVENT_TABLE(wxColumnHeader, wxControl)
	EVT_PAINT(wxColumnHeader::OnPaint)
	EVT_LEFT_DOWN(wxColumnHeader::OnClick)
	EVT_LEFT_DCLICK(wxColumnHeader::OnDoubleClick)
END_EVENT_TABLE()

#if wxUSE_EXTENDED_RTTI
WX_DEFINE_FLAGS( wxColumnHeaderStyle )

wxBEGIN_FLAGS( wxColumnHeaderStyle )
	// new style border flags:
	// we put them first to use them for streaming out
	wxFLAGS_MEMBER(wxBORDER_SIMPLE)
	wxFLAGS_MEMBER(wxBORDER_SUNKEN)
	wxFLAGS_MEMBER(wxBORDER_DOUBLE)
	wxFLAGS_MEMBER(wxBORDER_RAISED)
	wxFLAGS_MEMBER(wxBORDER_STATIC)
	wxFLAGS_MEMBER(wxBORDER_NONE)

	// old style border flags
	wxFLAGS_MEMBER(wxSIMPLE_BORDER)
	wxFLAGS_MEMBER(wxSUNKEN_BORDER)
	wxFLAGS_MEMBER(wxDOUBLE_BORDER)
	wxFLAGS_MEMBER(wxRAISED_BORDER)
	wxFLAGS_MEMBER(wxSTATIC_BORDER)
	wxFLAGS_MEMBER(wxBORDER)

	// standard window styles
	wxFLAGS_MEMBER(wxTAB_TRAVERSAL)
	wxFLAGS_MEMBER(wxCLIP_CHILDREN)
	wxFLAGS_MEMBER(wxTRANSPARENT_WINDOW)
	wxFLAGS_MEMBER(wxWANTS_CHARS)
	wxFLAGS_MEMBER(wxFULL_REPAINT_ON_RESIZE)
	wxFLAGS_MEMBER(wxALWAYS_SHOW_SB)
wxEND_FLAGS( wxColumnHeaderStyle )

IMPLEMENT_DYNAMIC_CLASS_XTI(wxColumnHeader, wxControl, "wx/colheader.h")

wxBEGIN_PROPERTIES_TABLE(wxColumnHeader)
	wxEVENT_RANGE_PROPERTY( Updated, wxEVT_COLUMNHEADER_SELCHANGED, wxEVT_COLUMNHEADER_DOUBLECLICKED, wxColumnHeaderEvent )
	wxHIDE_PROPERTY( Children )
	wxPROPERTY( 0 /*flags*/ , wxT("Helpstring"), wxT("group"))
	wxPROPERTY_FLAGS( WindowStyle, wxColumnHeaderStyle, long, SetWindowStyleFlag, GetWindowStyleFlag, , 0 /*flags*/, wxT("Helpstring"), wxT("group") ) // style
wxEND_PROPERTIES_TABLE()

wxBEGIN_HANDLERS_TABLE(wxColumnHeader)
wxEND_HANDLERS_TABLE()

wxCONSTRUCTOR_5( wxColumnHeader, wxWindow*, Parent, wxWindowID, Id, wxPoint, Position, wxSize, Size, long, WindowStyle )
#else
IMPLEMENT_DYNAMIC_CLASS(wxColumnHeader, wxControl)
#endif
IMPLEMENT_DYNAMIC_CLASS(wxColumnHeaderEvent, wxCommandEvent)

// ----------------------------------------------------------------------------
// events
// ----------------------------------------------------------------------------

DEFINE_EVENT_TYPE(wxEVT_COLUMNHEADER_SELCHANGED)
DEFINE_EVENT_TYPE(wxEVT_COLUMNHEADER_DOUBLECLICKED)

// ============================================================================
// implementation
// ============================================================================

// ----------------------------------------------------------------------------
// wxColumnHeader
// ----------------------------------------------------------------------------

wxColumnHeader::wxColumnHeader()
{
	Init();
}

// ================
#if 0
#pragma mark -
#endif

wxColumnHeader::wxColumnHeader(
	wxWindow			*parent,
	wxWindowID			id,
	const wxPoint		&pos,
	const wxSize		&size,
	long				style,
	const wxString		&name )
{
	Init();

	(void)Create( parent, id, pos, size, style, name );
}

wxColumnHeader::~wxColumnHeader()
{
	DisposeItemList();
}

void wxColumnHeader::Init( void )
{
	m_NativeBoundsR.x =
	m_NativeBoundsR.y =
	m_NativeBoundsR.width =
	m_NativeBoundsR.height = 0;

	m_ItemList = NULL;
	m_ItemCount = 0;
	m_ItemSelected = wxCOLUMNHEADER_HITTEST_NoPart;

	m_SelectionColour.Set( 0x66, 0x66, 0x66 );

#if defined(__WXMSW__) || defined(__WXMAC__)
	m_BFixedHeight = true;
#else
	m_BFixedHeight = false;
#endif

#if defined(__WXMAC__)
	// NB: or kThemeSystemFontTag, kThemeViewsFontTag
	m_Font.MacCreateThemeFont( kThemeSmallSystemFont );
	m_SelectionDrawStyle = wxCOLUMNHEADER_SELECTIONDRAWSTYLE_Native;
#else
	m_Font.SetFamily( 0 );
	m_SelectionDrawStyle = wxCOLUMNHEADER_SELECTIONDRAWSTYLE_Underline;
#endif

	m_BProportionalResizing = true;
	m_BVisibleSelection = true;

#if wxUSE_UNICODE
	m_BUseUnicode = true;
#else
	m_BUseUnicode = false;
#endif
}

bool wxColumnHeader::Create(
	wxWindow			*parent,
	wxWindowID			id,
	const wxPoint		&pos,
	const wxSize		&size,
	long				style,
	const wxString		&name )
{
wxString		localName;
wxSize		actualSize;
bool			bResultV;

	localName = name;

	actualSize = size;
	if (m_BFixedHeight)
	{
		actualSize = CalculateDefaultSize();
		if (size.x > 0)
			actualSize.x = size.x;
	}

	// NB: the CreateControl call crashes on MacOS
#if defined(__WXMSW__)
	// NB: this is a string from Win32 headers and is conditionally defined as Unicode or ANSI,
	// hence, no _T() nor wxT() macro is desirable
	localName = WC_HEADER;
	bResultV =
		CreateControl(
			parent, id, pos, actualSize,
			style, wxDefaultValidator, localName );

	if (bResultV)
	{
	WXDWORD		msStyle, exstyle;

		msStyle = MSWGetStyle( style, &exstyle );
		bResultV = MSWCreateControl( localName, msStyle, pos, actualSize, wxEmptyString, exstyle );
	}

#else
	bResultV =
		wxControl::Create(
			parent, id, pos, actualSize,
			style, wxDefaultValidator, localName );
#endif

#if 0
	if (bResultV)
	{
		// NB: is any of this necessary??

		// needed to get the arrow keys normally used for dialog navigation
		SetWindowStyle( style );

		// we need to set the position as well because the main control position is not
		// the same as the one specified in pos if we have the controls above it
		SetBestSize( actualSize );
		SetPosition( pos );
	}
#endif

	// NB: is this advisable?
	wxControl::DoGetPosition( &(m_NativeBoundsR.x), &(m_NativeBoundsR.y) );
	wxControl::DoGetSize( &(m_NativeBoundsR.width), &(m_NativeBoundsR.height) );

	return bResultV;
}

// virtual
bool wxColumnHeader::Destroy( void )
{
bool		bResultV;

	bResultV = wxControl::Destroy();

	return bResultV;
}

// virtual
bool wxColumnHeader::Show(
	bool		bShow )
{
bool		bResultV;

	bResultV = wxControl::Show( bShow );

	return bResultV;
}

// virtual
bool wxColumnHeader::Enable(
	bool		bEnable )
{
long		i;
bool		bResultV;

	if (bEnable == IsEnabled())
		return bEnable;

	bResultV = wxControl::Enable( bEnable );

	for (i=0; i<m_ItemCount; i++)
	{
		if ((m_ItemList != NULL) && (m_ItemList[i] != NULL))
			m_ItemList[i]->SetFlagAttribute( wxCOLUMNHEADER_FLAGATTR_Enabled, bEnable );

		RefreshItem( i );
	}

	// force a redraw
	SetViewDirty();

	return bResultV;
}

// ----------------------------------------------------------------------------
// size management
// ----------------------------------------------------------------------------

// virtual
void wxColumnHeader::DoMoveWindow(
	int		x,
	int		y,
	int		width,
	int		height )
{
int		yDiff;

	yDiff = 0;

	wxControl::DoMoveWindow( x, y + yDiff, width, height - yDiff );

	// NB: is this advisable?
	wxControl::DoGetPosition( &(m_NativeBoundsR.x), &(m_NativeBoundsR.y) );
}

// virtual
wxSize wxColumnHeader::DoGetBestSize( void ) const
{
wxSize	bestSize;

	bestSize = CalculateDefaultSize();
	CacheBestSize( bestSize );

	return bestSize;
}

wxSize wxColumnHeader::CalculateDefaultSize( void ) const
{
wxWindow	*parentW;
wxSize		bestSize;

	// best width is parent's width; height is fixed by native drawing routines
	parentW = GetParent();
	if (parentW != NULL)
		parentW->GetClientSize( &(bestSize.x), &(bestSize.y) );
	else
		// FIXME: ugly
		bestSize.x = 0;
	bestSize.y = 20;

#if defined(__WXMSW__)
	{
	HDLAYOUT	hdl;
	WINDOWPOS	wp;
	HWND		targetViewRef;
	RECT			boundsR;

		targetViewRef = GetHwnd();
		boundsR.left = boundsR.top = 0;
		boundsR.right = bestSize.x;
		boundsR.bottom = bestSize.y;
		hdl.prc = &boundsR;
		hdl.pwpos = &wp;
		if (Header_Layout( targetViewRef, (LPARAM)&hdl ) != 0)
			bestSize.y = wp.cy;
	}

#elif defined(__WXMAC__)
	{
	SInt32		standardHeight;
	OSStatus		errStatus;

		errStatus = GetThemeMetric( kThemeMetricListHeaderHeight, &standardHeight );
		bestSize.y = standardHeight;
	}
#endif

#if 0
	if (! HasFlag( wxBORDER_NONE ))
	{
		// the border would clip the last line otherwise
		bestSize.x += 4;
		bestSize.y += 6;
	}
#endif

	return bestSize;
}

// virtual
void wxColumnHeader::DoSetSize(
	int		x,
	int		y,
	int		width,
	int		height,
	int		sizeFlags )
{
wxSize		actualSize;

	// FIXME: should be - invalidate( origBoundsR )

	// NB: correct height for native platform limitations
	actualSize = CalculateDefaultSize();
	height = actualSize.y;

	wxControl::DoSetSize( x, y, width, height, sizeFlags );

	if (m_BProportionalResizing)
		RescaleToFit( width );

	// NB: is this advisable?
	wxControl::DoGetPosition( &(m_NativeBoundsR.x), &(m_NativeBoundsR.y) );
	wxControl::DoGetSize( &(m_NativeBoundsR.width), &(m_NativeBoundsR.height) );

	// FIXME: should be - invalidate( newBoundsR )
	// RecalculateItemExtents();
	SetViewDirty();
}

// ----------------------------------------------------------------------------
// drawing
// ----------------------------------------------------------------------------

// virtual
void wxColumnHeader::OnPaint(
	wxPaintEvent		& WXUNUSED(event) )
{
	Draw();

#if 0 && defined(__WXMSW__)
	// NB: moved all drawing code into (where else?) ::Draw

	// these work...
//	event.Skip();
//	wxWindowMSW::MSWDefWindowProc( WM_PAINT, 0, 0 );

	// ...and these fail to work.
//	wxControl::OnPaint( event );
//	wxWindow::OnPaint( event );
//	wxControl::MSWWindowProc( WM_PAINT, 0, 0 );
//	::DefWindowProc( GetHwnd(), WM_PAINT, 0, 0 );
#endif
}

// ----------------------------------------------------------------------------
// mouse handling
// ----------------------------------------------------------------------------

void wxColumnHeader::OnDoubleClick(
	wxMouseEvent		&event )
{
long		itemIndex;

	itemIndex = HitTest( event.GetPosition() );
	if (itemIndex >= wxCOLUMNHEADER_HITTEST_ItemZero)
	{
		// NB: just call the single click handler for the present
		OnClick( event );

		// NB: unused for the present
		//GenerateEvent( wxEVT_COLUMNHEADER_DOUBLECLICKED );
	}
	else
	{
		event.Skip();
	}
}

void wxColumnHeader::OnClick(
	wxMouseEvent		&event )
{
long		itemIndex;

	itemIndex = HitTest( event.GetPosition() );
	switch (itemIndex)
	{
	default:
		if (itemIndex >= wxCOLUMNHEADER_HITTEST_ItemZero)
		{
			if (IsEnabled())
			{
				OnClick_SelectOrToggleSort( itemIndex, true );
				GenerateEvent( wxEVT_COLUMNHEADER_SELCHANGED );
			}
			break;
		}
		else
		{
			// unknown message - unhandled - fall through
			//wxLogDebug( _T("wxColumnHeader::OnClick - unknown hittest code") );
		}

	case wxCOLUMNHEADER_HITTEST_NoPart:
		event.Skip();
		break;
	}
}

void wxColumnHeader::OnClick_SelectOrToggleSort(
	long				itemIndex,
	bool				bToggleSortDirection )
{
long			curSelectionIndex;

	curSelectionIndex = GetSelectedItem();
	if (itemIndex != m_ItemSelected)
	{
		SetSelectedItem( itemIndex );
	}
	else if (bToggleSortDirection)
	{
	wxColumnHeaderItem	*item;
	bool				bSortFlag;

		item = ((m_ItemList != NULL) ? m_ItemList[itemIndex] : NULL);
		if (item != NULL)
			if (item->GetFlagAttribute( wxCOLUMNHEADER_FLAGATTR_SortEnabled ))
			{
				bSortFlag = item->GetFlagAttribute( wxCOLUMNHEADER_FLAGATTR_SortDirection );
				item->SetFlagAttribute( wxCOLUMNHEADER_FLAGATTR_SortDirection, ! bSortFlag );

				if (m_BVisibleSelection)
				{
					RefreshItem( itemIndex );
					SetViewDirty();
				}
			}

		// for testing: can induce text wrapping outside of bounds rect
//		item->SetLabelText( _wxT("���� YOW! ����") );
	}
}

// static
wxVisualAttributes wxColumnHeader::GetClassDefaultAttributes(
	wxWindowVariant		variant )
{
	// FIXME: is this dependency necessary?
	// use the same color scheme as wxListBox
	return wxListBox::GetClassDefaultAttributes( variant );
}

// ================
#if 0
#pragma mark -
#endif

void wxColumnHeader::GetSelectionColour(
	wxColor			&targetColour ) const
{
	targetColour = m_SelectionColour;
}

void wxColumnHeader::SetSelectionColour(
	const wxColor		&targetColour )
{
	m_SelectionColour = targetColour;
}

long wxColumnHeader::GetSelectionDrawStyle( void ) const
{
	return m_SelectionDrawStyle;
}

// NB: this has no effect on the Mac selection UI,
// which is well-defined.
//
void wxColumnHeader::SetSelectionDrawStyle(
	long			styleValue )
{
	if (m_SelectionDrawStyle == styleValue)
		return;
	if ((styleValue < wxCOLUMNHEADER_SELECTIONDRAWSTYLE_FIRST)
			|| (styleValue > wxCOLUMNHEADER_SELECTIONDRAWSTYLE_LAST))
		return;

	m_SelectionDrawStyle = styleValue;

#if !defined(__WXMAC__)
	if (m_ItemSelected >= 0)
	{
		RefreshItem( m_ItemSelected );
		SetViewDirty();
	}
#endif
}

bool wxColumnHeader::GetFlagProportionalResizing( void ) const
{
	return m_BProportionalResizing;
}

void wxColumnHeader::SetFlagProportionalResizing(
	bool			bFlagValue )
{
	if (m_BProportionalResizing == bFlagValue)
		return;

	m_BProportionalResizing = bFlagValue;
}

bool wxColumnHeader::GetFlagVisibleSelection( void ) const
{
	return m_BVisibleSelection;
}

void wxColumnHeader::SetFlagVisibleSelection(
	bool			bFlagValue )
{
	if (m_BVisibleSelection == bFlagValue)
		return;

	m_BVisibleSelection = bFlagValue;

	if (m_ItemSelected >= 0)
	{
		RefreshItem( m_ItemSelected );
		SetViewDirty();
	}
}

bool wxColumnHeader::GetFlagUnicode( void ) const
{
	return m_BUseUnicode;
}

// NB: this routine shouldn't really exist
//
void wxColumnHeader::SetFlagUnicode(
	bool			bFlagValue )
{
	if (m_BUseUnicode == bFlagValue)
		return;

	// m_BUseUnicode = bFlagValue;
}

// ================
#if 0
#pragma mark -
#endif

// ----------------------------------------------------------------------------
// utility
// ----------------------------------------------------------------------------

long wxColumnHeader::GetTotalUIExtent( void ) const
{
long		extentX, i;

	extentX = 0;
	if (m_ItemList != NULL)
		for (i=0; i<m_ItemCount; i++)
		{
			if (m_ItemList[i] != NULL)
				extentX += m_ItemList[i]->m_ExtentX;
		}

	return extentX;
}

bool wxColumnHeader::RescaleToFit(
	long				newWidth )
{
long		scaleItemCount, scaleItemAmount, i;
long		deltaX, summerX, originX, incX;

	if ((newWidth <= 0) || (m_ItemList == NULL))
		return false;

	// count non-fixed-width items and tabulate size
	scaleItemCount = 0;
	scaleItemAmount = 0;
	for (i=0; i<m_ItemCount; i++)
	{
		if ((m_ItemList[i] == NULL) || m_ItemList[i]->m_BFixedWidth)
			continue;

		scaleItemCount++;
		scaleItemAmount += m_ItemList[i]->m_ExtentX;
	}

	// determine width delta
	deltaX = newWidth - m_NativeBoundsR.width;
	summerX = deltaX;
	originX = 0;

	// move and resize items as appropriate
	for (i=0; i<m_ItemCount; i++)
	{
		if (m_ItemList[i] == NULL)
			continue;

		// move to new origin
		m_ItemList[i]->m_OriginX = originX;

		// resize item, if non-fixed
		if (! m_ItemList[i]->m_BFixedWidth)
		{
			scaleItemCount--;

			if (scaleItemCount > 0)
				incX = (deltaX * m_ItemList[i]->m_ExtentX) / scaleItemAmount;
			else
				incX = summerX;
			m_ItemList[i]->m_ExtentX += incX;

			summerX -= incX;
		}

		originX += m_ItemList[i]->m_ExtentX;
	}

	for (i=0; i<m_ItemCount; i++)
		RefreshItem( i );
	SetViewDirty();

	return true;
}

bool wxColumnHeader::ResizeToFit( void )
{
long		extentX;
bool		bScaling;

	// temporarily turn off proportional resizing
	bScaling = m_BProportionalResizing;
	m_BProportionalResizing = false;

	extentX = GetTotalUIExtent();
	DoSetSize( m_NativeBoundsR.x, m_NativeBoundsR.y, extentX, m_NativeBoundsR.height, 0 );

	m_BProportionalResizing = true;

	return true;
}

bool wxColumnHeader::ResizeDivision(
	long				itemIndex,
	long				originX )
{
wxColumnHeaderItem		*itemRef1, *itemRef2;
long						deltaV;

	if ((itemIndex <= 0) || (itemIndex >= m_ItemCount))
		return false;

	itemRef1 = GetItemRef( itemIndex - 1 );
	itemRef2 = GetItemRef( itemIndex );
	if ((itemRef1 == NULL) || (itemRef2 == NULL))
		return false;

	if ((originX <= itemRef1->m_OriginX) || (originX >= itemRef2->m_OriginX + itemRef2->m_ExtentX))
		return false;

	deltaV = itemRef2->m_OriginX - originX;

	itemRef1->m_ExtentX -= deltaV;
	itemRef2->m_ExtentX += deltaV;
	itemRef2->m_OriginX = itemRef1->m_OriginX + itemRef1->m_ExtentX;

	RefreshItem( itemIndex - 1 );
	RefreshItem( itemIndex );
	SetViewDirty();

	return true;
}

// ================
#if 0
#pragma mark -
#endif

long wxColumnHeader::GetItemCount( void ) const
{
	return (long)m_ItemCount;
}

long wxColumnHeader::GetSelectedItem( void ) const
{
	return m_ItemSelected;
}

void wxColumnHeader::SetSelectedItem(
	long			itemIndex )
{
long		i;
bool		bSelected;

	if (m_ItemSelected != itemIndex)
	{
		for (i=0; i<m_ItemCount; i++)
		{
			bSelected = (i == itemIndex);
			if ((m_ItemList != NULL) && (m_ItemList[i] != NULL))
				m_ItemList[i]->SetFlagAttribute( wxCOLUMNHEADER_FLAGATTR_Selected, bSelected );

			RefreshItem( i );
		}

		m_ItemSelected = itemIndex;

		SetViewDirty();
	}
}

void wxColumnHeader::DeleteItem(
	long			itemIndex )
{
long		i;

	if ((itemIndex >= 0) && (itemIndex < m_ItemCount))
	{
#if defined(__WXMSW__)
		(void)MSWItemDelete( itemIndex );
#endif

		if (m_ItemList != NULL)
		{
			if (m_ItemCount > 1)
			{
				// delete the target item
				delete m_ItemList[itemIndex];

				// close the list hole
				for (i=itemIndex; i<m_ItemCount-1; i++)
					m_ItemList[i] = m_ItemList[i + 1];

				// leave a NULL spot at the end
				m_ItemList[m_ItemCount - 1] = NULL;
				m_ItemCount--;

				// recalculate item origins
				RecalculateItemExtents();
			}
			else
				DisposeItemList();

			// if this item was selected, then there is a selection no longer
			if (m_ItemSelected == itemIndex)
				m_ItemSelected = wxCOLUMNHEADER_HITTEST_NoPart;

			// NB: AddItem doesn't do this
			SetViewDirty();
		}
	}
}

void wxColumnHeader::AppendItem(
	const wxString		&textBuffer,
	long				textJust,
	long				extentX,
	bool				bSelected,
	bool				bSortEnabled,
	bool				bSortAscending )
{
	AddItem( -1, textBuffer, textJust, extentX, bSelected, bSortEnabled, bSortAscending );
}

void wxColumnHeader::AddItem(
	long				beforeIndex,
	const wxString		&textBuffer,
	long				textJust,
	long				extentX,
	bool				bSelected,
	bool				bSortEnabled,
	bool				bSortAscending )
{
wxColumnHeaderItem		itemInfo;
wxSize					targetExtent;
long					originX;

	// set invariant values
	itemInfo.m_BEnabled = true;

	// set specified values
	itemInfo.m_LabelTextRef = textBuffer;
	itemInfo.m_TextJust = textJust;
	itemInfo.m_ExtentX = extentX;
	itemInfo.m_BSelected = ((m_ItemSelected < 0) ? bSelected : false);
	itemInfo.m_BSortEnabled = bSortEnabled;
	itemInfo.m_BSortAscending = bSortAscending;

	if ((beforeIndex < 0) || (beforeIndex > m_ItemCount))
		beforeIndex = m_ItemCount;

	// determine new item origin
	if (beforeIndex > 0)
	{
		targetExtent = GetUIExtent( beforeIndex - 1 );
		originX = ((targetExtent.x > 0) ? targetExtent.x : 0);
		itemInfo.m_OriginX = originX + targetExtent.y;
	}
	else
		itemInfo.m_OriginX = 0;

	AddItemList( &itemInfo, 1, beforeIndex );
}

void wxColumnHeader::AddItemList(
	const wxColumnHeaderItem		*itemList,
	long							itemCount,
	long							beforeIndex )
{
wxColumnHeaderItem	**newItemList;
long				targetIndex, i;
bool				bIsSelected;

	if ((itemList == NULL) || (itemCount <= 0))
		return;

	if ((beforeIndex < 0) || (beforeIndex > m_ItemCount))
		beforeIndex = m_ItemCount;

	// allocate new item list and copy the original list items into it
	newItemList = (wxColumnHeaderItem**)calloc( m_ItemCount + itemCount, sizeof(wxColumnHeaderItem*) );
	if (m_ItemList != NULL)
	{
		for (i=0; i<m_ItemCount; i++)
		{
			targetIndex = ((i < beforeIndex) ? i : itemCount + i);
			newItemList[targetIndex] = m_ItemList[i];
		}

		free( m_ItemList );
	}
	m_ItemList = newItemList;

	// append the new items
	for (i=0; i<itemCount; i++)
	{
		targetIndex = beforeIndex + i;
		m_ItemList[targetIndex] = new wxColumnHeaderItem( &itemList[i] );

		bIsSelected = (m_ItemList[targetIndex]->m_BSelected && m_ItemList[targetIndex]->m_BEnabled);

#if defined(__WXMSW__)
		MSWItemInsert(
			targetIndex,
			m_ItemList[targetIndex]->m_ExtentX,
			m_ItemList[targetIndex]->m_LabelTextRef.c_str(),
			m_ItemList[targetIndex]->m_TextJust,
			m_BUseUnicode,
			bIsSelected,
			m_ItemList[targetIndex]->m_BSortEnabled,
			m_ItemList[targetIndex]->m_BSortAscending );
#endif

		if (bIsSelected && (m_ItemSelected < 0))
			m_ItemSelected = targetIndex;
	}

	// update the item count
	m_ItemCount += itemCount;

	// if this was an insertion, refresh the end items
	if (beforeIndex < m_ItemCount - itemCount)
	{
		RecalculateItemExtents();
		for (i=0; i<itemCount; i++)
			RefreshItem( i + (m_ItemCount - itemCount) );
	}

	// if this moves the selection, reset it
	if (m_ItemSelected >= beforeIndex)
	{
	long		savedIndex;

		savedIndex = m_ItemSelected;
		m_ItemSelected = wxCOLUMNHEADER_HITTEST_NoPart;
		SetSelectedItem( savedIndex );
	}

	SetViewDirty();
}

void wxColumnHeader::DisposeItemList( void )
{
long		i;

	if (m_ItemList != NULL)
	{
		for (i=0; i<m_ItemCount; i++)
			delete m_ItemList[i];

		free( m_ItemList );
		m_ItemList = NULL;
	}

	m_ItemCount = 0;
	m_ItemSelected = wxCOLUMNHEADER_HITTEST_NoPart;
}

bool wxColumnHeader::GetItemData(
	long							itemIndex,
	wxColumnHeaderItem				*info ) const
{
wxColumnHeaderItem		*itemRef;
bool					bResultV;

	itemRef = GetItemRef( itemIndex );
	bResultV = (itemRef != NULL);
	if (bResultV)
		itemRef->GetItemData( info );

	return bResultV;
}

bool wxColumnHeader::SetItemData(
	long							itemIndex,
	const wxColumnHeaderItem		*info )
{
wxColumnHeaderItem		*itemRef;
bool					bResultV;

	itemRef = GetItemRef( itemIndex );
	bResultV = (itemRef != NULL);
	if (bResultV)
		itemRef->SetItemData( info );

	return bResultV;
}

bool wxColumnHeader::GetItemBounds(
	long				itemIndex,
	wxRect			*boundsR ) const
{
wxColumnHeaderItem		*itemRef;
bool					bResultV;

	if (boundsR == NULL)
		return false;

	itemRef = GetItemRef( itemIndex );
	bResultV = (itemRef != NULL);

	// is this item beyond the right edge?
	if (bResultV)
		bResultV = (itemRef->m_OriginX < m_NativeBoundsR.width);

	if (bResultV)
	{
		boundsR->x = itemRef->m_OriginX;
		boundsR->y = 0; // m_NativeBoundsR.y;
		boundsR->width = itemRef->m_ExtentX + 1;
		boundsR->height = m_NativeBoundsR.height;

		if (boundsR->width > m_NativeBoundsR.width - itemRef->m_OriginX)
			boundsR->width = m_NativeBoundsR.width - itemRef->m_OriginX;
	}
	else
	{
		boundsR->x =
		boundsR->y =
		boundsR->width =
		boundsR->height = 0;
	}

	return bResultV;
}

wxColumnHeaderItem * wxColumnHeader::GetItemRef(
	long			itemIndex ) const
{
	if ((itemIndex >= 0) && (itemIndex < m_ItemCount))
		return m_ItemList[itemIndex];
	else
		return NULL;
}

void wxColumnHeader::GetBitmapRef(
	long				itemIndex,
	wxBitmap			&bitmapRef ) const
{
wxColumnHeaderItem		*itemRef;
bool					bResultV;

	itemRef = GetItemRef( itemIndex );
	bResultV = (itemRef != NULL);
	if (bResultV)
	{
		itemRef->GetBitmapRef( bitmapRef );
	}
	else
	{
//		bitmapRef.SetOK( false );
	}
}

void wxColumnHeader::SetBitmapRef(
	long				itemIndex,
	wxBitmap			&bitmapRef )
{
wxColumnHeaderItem		*itemRef;
wxRect					boundsR;

	itemRef = GetItemRef( itemIndex );
	if (itemRef != NULL)
	{
		GetItemBounds( itemIndex, &boundsR );
		itemRef->SetBitmapRef( bitmapRef, &boundsR );
		RefreshItem( itemIndex );
	}
}

wxString wxColumnHeader::GetLabelText(
	long				itemIndex ) const
{
wxColumnHeaderItem		*itemRef;
wxString				textBuffer;
bool					bResultV;

	itemRef = GetItemRef( itemIndex );
	bResultV = (itemRef != NULL);
	if (bResultV)
	{
		(void)itemRef->GetLabelText( textBuffer );
	}
	else
	{
		textBuffer = _T("");
	}

	return textBuffer;
}

void wxColumnHeader::SetLabelText(
	long				itemIndex,
	const wxString		&textBuffer )
{
wxColumnHeaderItem		*itemRef;

	itemRef = GetItemRef( itemIndex );
	if (itemRef != NULL)
	{
		itemRef->SetLabelText( textBuffer );
		RefreshItem( itemIndex );
	}
}

long wxColumnHeader::GetLabelJustification(
	long				itemIndex ) const
{
wxColumnHeaderItem		*itemRef;
long						textJust;

	itemRef = GetItemRef( itemIndex );
	if (itemRef != NULL)
		textJust = itemRef->GetLabelJustification();
	else
		textJust = 0;

	return textJust;
}

void wxColumnHeader::SetLabelJustification(
	long				itemIndex,
	long				textJust )
{
wxColumnHeaderItem		*itemRef;

	itemRef = GetItemRef( itemIndex );
	if (itemRef != NULL)
	{
		itemRef->SetLabelJustification( textJust );
		RefreshItem( itemIndex );
	}
}

wxSize wxColumnHeader::GetUIExtent(
	long				itemIndex ) const
{
wxColumnHeaderItem		*itemRef;
wxSize					extentPt;
long					originX, extentX;
bool					bResultV;

	itemRef = GetItemRef( itemIndex );
	bResultV = (itemRef != NULL);
	if (bResultV)
	{
		itemRef->GetUIExtent( originX, extentX );
	}
	else
	{
		originX =
		extentX = 0;
	}

	extentPt.x = originX;
	extentPt.y = extentX;

	return extentPt;
}

void wxColumnHeader::SetUIExtent(
	long				itemIndex,
	wxSize			&extentPt )
{
wxColumnHeaderItem		*itemRef;

	itemRef = GetItemRef( itemIndex );
	if (itemRef != NULL)
	{
		itemRef->SetUIExtent( extentPt.x, extentPt.y );

		RecalculateItemExtents();
		RefreshItem( itemIndex );
	}
}

bool wxColumnHeader::GetFlagAttribute(
	long						itemIndex,
	wxColumnHeaderFlagAttr		flagEnum ) const
{
wxColumnHeaderItem		*itemRef;
bool					bResultV;

	itemRef = GetItemRef( itemIndex );
	bResultV = (itemRef != NULL);
	if (bResultV)
		bResultV = itemRef->GetFlagAttribute( flagEnum );

	return bResultV;
}

bool wxColumnHeader::SetFlagAttribute(
	long						itemIndex,
	wxColumnHeaderFlagAttr		flagEnum,
	bool						bFlagValue )
{
wxColumnHeaderItem		*itemRef;
bool					bResultV;

	itemRef = GetItemRef( itemIndex );
	bResultV = (itemRef != NULL);
	if (bResultV)
	{
		if (itemRef->SetFlagAttribute( flagEnum, bFlagValue ))
			RefreshItem( itemIndex );
	}

	return bResultV;
}

wxColumnHeaderHitTestResult wxColumnHeader::HitTest(
	const wxPoint		&locationPt )
{
wxColumnHeaderHitTestResult		resultV;

	resultV = wxCOLUMNHEADER_HITTEST_NoPart;

#if defined(__WXMSW__)
RECT		boundsR;
HWND		targetViewRef;
long			itemCount, i;

	targetViewRef = GetHwnd();
	if (targetViewRef == NULL)
	{
		//wxLogDebug( _T("targetViewRef = GetHwnd failed (NULL)") );
		return resultV;
	}

	itemCount = Header_GetItemCount( targetViewRef );
	for (i=0; i<itemCount; i++)
	{
		Header_GetItemRect( targetViewRef, i, &boundsR );
		if ((locationPt.x >= boundsR.left) && (locationPt.x < boundsR.right)
			&& (locationPt.y >= boundsR.top) && (locationPt.y < boundsR.bottom))
		{
			resultV = (wxColumnHeaderHitTestResult)i;
			break;
		}
	}
#else
long		i;

	for (i=0; i<m_ItemCount; i++)
		if (m_ItemList[i] != NULL)
			if (m_ItemList[i]->HitTest( locationPt ) != 0)
			{
				resultV = (wxColumnHeaderHitTestResult)i;
				break;
			}
#endif

	return resultV;
}

long wxColumnHeader::Draw( void )
{
wxRect		boundsR;
long			resultV;

	resultV = 0;

#if defined(__WXMSW__)
	// render native control window
	wxWindowMSW::MSWDefWindowProc( WM_PAINT, 0, 0 );

	// MSW case - add selection indicator - no native mechanism exists
	if (m_BVisibleSelection && (m_ItemSelected >= 0))
		if (GetItemBounds( m_ItemSelected, &boundsR ))
		{
		wxClientDC		dc( this );

			wxColumnHeaderItem::GenericDrawSelection( &dc, &boundsR, &m_SelectionColour, m_SelectionDrawStyle );
		}

#else
wxClientDC	dc( this );
long			i;

	dc.SetFont( m_Font );

	for (i=0; i<m_ItemCount; i++)
		if (GetItemBounds( i, &boundsR ))
		{
			dc.SetClippingRegion( boundsR.x, boundsR.y, boundsR.width, boundsR.height );

#if defined(__WXMAC__)
			// MacOS case - selection indicator is drawn as needed
			resultV |= m_ItemList[i]->MacDrawItem( this, &dc, &boundsR, m_BUseUnicode, m_BVisibleSelection );

#else
			// generic case - add selection indicator
			resultV |= m_ItemList[i]->GenericDrawItem( this, &dc, &boundsR, m_BUseUnicode, m_BVisibleSelection );
			if (m_BVisibleSelection && (i == m_ItemSelected))
				wxColumnHeaderItem::GenericDrawSelection( &dc, &boundsR, &m_SelectionColour, m_SelectionDrawStyle );
#endif
		}

	dc.DestroyClippingRegion();
#endif

	return resultV;
}

void wxColumnHeader::SetViewDirty( void )
{
	Refresh( true, NULL );
}

void wxColumnHeader::RefreshItem(
	long			itemIndex )
{
#if defined(__WXMSW__)
	// NB: need to update native item
	MSWItemRefresh( itemIndex, false );
#endif
}

void wxColumnHeader::RecalculateItemExtents( void )
{
long		originX, i;

	if (m_ItemList != NULL)
	{
		originX = 0;
		for (i=0; i<m_ItemCount; i++)
			if (m_ItemList[i] != NULL)
			{
				m_ItemList[i]->m_OriginX = originX;
				originX += m_ItemList[i]->m_ExtentX;
			}
	}
}

wxSize wxColumnHeader::GetLabelTextExtent(
	wxClientDC			*dc,
	const wxString			&targetStr )
{
wxSize		resultV;

	resultV.x = resultV.y = 0;

	if (targetStr.IsEmpty())
		return resultV;

#if defined(__WXMAC__)
wxMacCFStringHolder	cfString( targetStr, m_Font.GetEncoding() );
Point					xyPt;
SInt16				baselineV;

	xyPt.h = xyPt.v = 0;

	GetThemeTextDimensions(
		(CFStringRef)cfString,
		m_Font.MacGetThemeFontID(),
		kThemeStateActive,
		false,
		&xyPt,
		&baselineV );

	resultV.x = (wxCoord)(xyPt.h);
	resultV.y = (wxCoord)(xyPt.v);

#else
wxCoord		targetWidth, targetHeight;

	if (dc != NULL)
	{
		dc->SetFont( m_Font );
		dc->GetTextExtent(
			targetStr,
			&targetWidth, &targetHeight,
			NULL, NULL, NULL );

		resultV.x = (wxCoord)targetWidth;
		resultV.y = (wxCoord)targetHeight;
	}
#endif

	return resultV;
}

// ================
#if 0
#pragma mark -
#endif

#if defined(__WXMAC__)
// virtual
void wxColumnHeader::MacControlUserPaneActivateProc(
	bool			bActivating )
{
	// FIXME: is this the right way to handle activate events ???
	Enable( bActivating );
}
#endif

#if defined(__WXMSW__)
// virtual
WXDWORD wxColumnHeader::MSWGetStyle(
	long			style,
	WXDWORD			*exstyle ) const
{
WXDWORD		msStyle;

	style = (style & ~wxBORDER_MASK) | wxBORDER_NONE;

	// FIXME: is WS_CLIPSIBLINGS necessary ???
	msStyle = wxControl::MSWGetStyle( style, exstyle );
	msStyle |= HDS_BUTTONS | HDS_FLAT | HDS_HORZ;
	msStyle |= WS_CLIPSIBLINGS;

	return msStyle;
}

long wxColumnHeader::MSWItemInsert(
	long			iInsertAfter,
	long			nWidth,
	const void		*titleText,
	long			textJust,
	bool			WXUNUSED(bUseUnicode),
	bool			bSelected,
	bool			bSortEnabled,
	bool			bSortAscending )
{
HDITEM		itemData;
HWND		targetViewRef;
long		resultV;

	targetViewRef = GetHwnd();
	if (targetViewRef == NULL)
	{
		//wxLogDebug( _T("MSWItemInsert - GetHwnd failed (NULL)") );
		return (-1L);
	}

//	wxLogDebug( _T("MSWItemInsert - item text [%s]"), (const TCHAR*)titleText );

	ZeroMemory( &itemData, sizeof(itemData) );
	itemData.mask = HDI_TEXT | HDI_FORMAT | HDI_WIDTH;
	itemData.pszText = (LPTSTR)titleText;
	itemData.cxy = (int)nWidth;
	itemData.cchTextMax = 256;
//	itemData.cchTextMax = sizeof(itemData.pszText) / sizeof(itemData.pszText[0]);
	itemData.fmt = wxColumnHeaderItem::ConvertJustification( textJust, TRUE ) | HDF_STRING;
	if (bSelected && bSortEnabled)
		itemData.fmt |= (bSortAscending ? HDF_SORTUP : HDF_SORTDOWN);

	resultV = (long)Header_InsertItem( targetViewRef, (int)iInsertAfter, &itemData );
//	resultV = (long)SendMessage( mViewRef, bUseUnicode ? HDM_INSERTITEMW : HDM_INSERTITEMA, (WPARAM)iInsertAfter, (LPARAM)&itemData );

	if (resultV < 0)
		wxLogDebug( _T("MSWItemInsert - SendMessage failed") );

	return resultV;
}

long wxColumnHeader::MSWItemDelete(
	long			itemIndex )
{
HWND		targetViewRef;
long		resultV;

	targetViewRef = GetHwnd();
	if (targetViewRef == NULL)
	{
		//wxLogDebug( _T("MSWItemDelete - GetHwnd failed (NULL)") );
		return (-1L);
	}

	resultV = (long)Header_DeleteItem( targetViewRef, itemIndex );

	if (resultV == 0)
		wxLogDebug( _T("MSWItemDelete - SendMessage failed") );

	return resultV;
}

long wxColumnHeader::MSWItemRefresh(
	long			itemIndex,
	bool			bCheckChanged )
{
wxColumnHeaderItem		*itemRef;
HDITEM					itemData;
HWND					targetViewRef;
LONG						newFmt;
long					resultV;

	itemRef = GetItemRef( itemIndex );
	if (itemRef == NULL)
		return (-1L);

	targetViewRef = GetHwnd();
	if (targetViewRef == NULL)
	{
		//wxLogDebug( _T("MSWItemRefresh - GetHwnd failed (NULL)") );
		return (-1L);
	}

	// FIXME: protect against HBMP leaks?
	ZeroMemory( &itemData, sizeof(itemData) );
	itemData.mask = HDI_FORMAT | HDI_WIDTH;
	resultV = (long)Header_GetItem( targetViewRef, itemIndex, &itemData );

	itemData.mask = HDI_TEXT | HDI_FORMAT | HDI_WIDTH;
	itemData.pszText = NULL;
	itemData.cxy = (int)(itemRef->m_ExtentX);
	itemData.cchTextMax = 256;
//	itemData.cchTextMax = sizeof(itemData.pszText) / sizeof(itemData.pszText[0]);

	// add sort arrows as needed
	newFmt = wxColumnHeaderItem::ConvertJustification( itemRef->m_TextJust, TRUE );
	if (itemRef->m_BSelected && itemRef->m_BEnabled && itemRef->m_BSortEnabled)
		newFmt |= (itemRef->m_BSortAscending ? HDF_SORTUP : HDF_SORTDOWN);

	// NB: should sort arrows and bitmaps be MutEx?
	if (itemRef->HasValidBitmapRef( itemRef->m_BitmapRef ))
	{
		// add bitmap reference
		newFmt |= HDF_BITMAP;
		itemData.mask |= HDI_BITMAP;
		itemData.hbm = (HBITMAP)(itemRef->m_BitmapRef->GetHBITMAP());
	}
	else
	{
		// add string reference
		newFmt |= HDF_STRING;
		itemData.pszText = (LPTSTR)(itemRef->m_LabelTextRef.c_str());
	}

	if (! bCheckChanged || (itemData.fmt != newFmt))
	{
		itemData.fmt = newFmt;
		resultV = (long)Header_SetItem( targetViewRef, itemIndex, &itemData );
//		resultV = (long)SendMessage( mViewRef, itemRef->m_BTextUnicode ? HDM_SETITEMW : HDM_SETITEMA, (WPARAM)itemIndex, (LPARAM)&itemData );
	}
	else
		resultV = 1;

	if (resultV == 0)
		wxLogDebug( _T("MSWItemRefresh - SendMessage failed") );

	return resultV;
}
#endif

// ================
#if 0
#pragma mark -
#endif

void wxColumnHeader::GenerateEvent(
	wxEventType		eventType )
{
wxColumnHeaderEvent	event( this, eventType );

	(void)GetEventHandler()->ProcessEvent( event );
}

// ================
#if 0
#pragma mark -
#endif

// ----------------------------------------------------------------------------
// wxColumnHeaderEvent
// ----------------------------------------------------------------------------

wxColumnHeaderEvent::wxColumnHeaderEvent(
	wxColumnHeader	*col,
	wxEventType		type )
	:
	wxCommandEvent( type, col->GetId() )
{
	SetEventObject( col );
}

void wxColumnHeaderEvent::Init( void )
{
}

// ================
#if 0
#pragma mark -
#endif

wxColumnHeaderItem::wxColumnHeaderItem()
	:
	m_TextJust( 0 )
	, m_BitmapRef( NULL )
	, m_OriginX( 0 )
	, m_ExtentX( 0 )
	, m_BEnabled( FALSE )
	, m_BSelected( FALSE )
	, m_BSortEnabled( FALSE )
	, m_BSortAscending( FALSE )
	, m_BFixedWidth( FALSE )
{
	m_LabelTextExtent.x =
	m_LabelTextExtent.y = (-1);
}

wxColumnHeaderItem::wxColumnHeaderItem(
	const wxColumnHeaderItem		*info )
	:
	m_TextJust( 0 )
	, m_BitmapRef( NULL )
	, m_OriginX( 0 )
	, m_ExtentX( 0 )
	, m_BEnabled( FALSE )
	, m_BSelected( FALSE )
	, m_BSortEnabled( FALSE )
	, m_BSortAscending( FALSE )
	, m_BFixedWidth( FALSE )
{
	m_LabelTextExtent.x =
	m_LabelTextExtent.y = (-1);
	SetItemData( info );
}

wxColumnHeaderItem::~wxColumnHeaderItem()
{
	delete m_BitmapRef;
}

// NB: a copy and nothing else...
//
void wxColumnHeaderItem::GetItemData(
	wxColumnHeaderItem			*info ) const
{
	if (info == NULL)
		return;

	info->m_TextJust = m_TextJust;
	info->m_LabelTextExtent = m_LabelTextExtent;
	info->m_OriginX = m_OriginX;
	info->m_ExtentX = m_ExtentX;
	info->m_BEnabled = m_BEnabled;
	info->m_BSelected = m_BSelected;
	info->m_BSortEnabled = m_BSortEnabled;
	info->m_BSortAscending = m_BSortAscending;
	info->m_BFixedWidth = m_BFixedWidth;

	GetLabelText( info->m_LabelTextRef );

	if (info->m_BitmapRef != m_BitmapRef)
		if (info->m_BitmapRef != NULL)
			GetBitmapRef( *(info->m_BitmapRef) );
}

void wxColumnHeaderItem::SetItemData(
	const wxColumnHeaderItem		*info )
{
	if (info == NULL)
		return;

	m_TextJust = info->m_TextJust;
	m_LabelTextExtent = info->m_LabelTextExtent;
	m_OriginX = info->m_OriginX;
	m_ExtentX = info->m_ExtentX;
	m_BEnabled = info->m_BEnabled;
	m_BSelected = info->m_BSelected;
	m_BSortEnabled = info->m_BSortEnabled;
	m_BSortAscending = info->m_BSortAscending;
	m_BFixedWidth = info->m_BFixedWidth;

	SetLabelText( info->m_LabelTextRef );

	if (info->m_BitmapRef != m_BitmapRef)
		SetBitmapRef( *(info->m_BitmapRef), NULL );
}

void wxColumnHeaderItem::GetBitmapRef(
	wxBitmap			&bitmapRef ) const
{
	if (m_BitmapRef != NULL)
		bitmapRef = *m_BitmapRef;
//	else
//		bitmapRef.SetOK( false );
}

void wxColumnHeaderItem::SetBitmapRef(
	wxBitmap			&bitmapRef,
	const wxRect		*boundsR )
{
wxRect			targetBoundsR;

	delete m_BitmapRef;
	m_BitmapRef = NULL;

	if ((boundsR != NULL) && HasValidBitmapRef( &bitmapRef ))
	{
		GenericGetBitmapItemBounds( boundsR, m_TextJust, NULL, &targetBoundsR );
		if ((bitmapRef.GetWidth() > targetBoundsR.width) || (bitmapRef.GetHeight() > targetBoundsR.height))
		{
		wxBitmap		localBitmap;

			// copy from the upper left-hand corner
			targetBoundsR.x = targetBoundsR.y = 0;
			localBitmap = bitmapRef.GetSubBitmap( targetBoundsR );
			m_BitmapRef = new wxBitmap( localBitmap );
		}
		else
		{
			// copy the entire bitmap
			m_BitmapRef = new wxBitmap( bitmapRef );
		}
	}
	else
	{
		// this case is OK - can be used to clear an existing bitmap
		// wxLogDebug( _T("wxColumnHeaderItem::SetBitmapRef failed") );
	}
}

void wxColumnHeaderItem::GetLabelText(
	wxString			&textBuffer ) const
{
	textBuffer = m_LabelTextRef;
}

void wxColumnHeaderItem::SetLabelText(
	const wxString		&textBuffer )
{
	m_LabelTextExtent.x =
	m_LabelTextExtent.y = (-1);
	m_LabelTextRef = textBuffer;
}

long wxColumnHeaderItem::GetLabelJustification( void ) const
{
	return m_TextJust;
}

void wxColumnHeaderItem::SetLabelJustification(
	long				textJust )
{
	m_TextJust = textJust;
}

void wxColumnHeaderItem::GetUIExtent(
	long			&originX,
	long			&extentX ) const
{
	originX = m_OriginX;
	extentX = m_ExtentX;
}

void wxColumnHeaderItem::SetUIExtent(
	long			originX,
	long			extentX )
{
	wxUnusedVar( originX );

	// NB: not currently permitted
//	if ((originX >= 0) && (m_OriginX != originX))
//		m_OriginX = originX;

	if ((extentX >= 0) && (m_ExtentX != extentX))
		m_ExtentX = extentX;
}

// NB: horizontal item layout is as follows:
// || InsetX | label text or bitmap | InsetX | sort arrow | InsetX ||
//
void wxColumnHeaderItem::GetTextUIExtent(
	long			&originX,
	long			&extentX ) const
{
	originX = m_OriginX + wxCHI_kMetricInsetX;
	if (extentX > m_ExtentX)
		extentX = m_ExtentX;

	extentX = m_ExtentX - ((3 * wxCHI_kMetricInsetX) + wxCHI_kMetricArrowSizeX);
	if (extentX < 0)
		extentX = 0;
}

bool wxColumnHeaderItem::GetFlagAttribute(
	wxColumnHeaderFlagAttr		flagEnum ) const
{
bool			bResult;

	bResult = false;

	switch (flagEnum)
	{
	case wxCOLUMNHEADER_FLAGATTR_Enabled:
		bResult = m_BEnabled;
		break;

	case wxCOLUMNHEADER_FLAGATTR_Selected:
		bResult = m_BSelected;
		break;

	case wxCOLUMNHEADER_FLAGATTR_SortEnabled:
		bResult = m_BSortEnabled;
		break;

	case wxCOLUMNHEADER_FLAGATTR_SortDirection:
		bResult = m_BSortAscending;
		break;

	case wxCOLUMNHEADER_FLAGATTR_FixedWidth:
		bResult = m_BFixedWidth;
		break;

	default:
		break;
	}

	return bResult;
}

bool wxColumnHeaderItem::SetFlagAttribute(
	wxColumnHeaderFlagAttr		flagEnum,
	bool						bFlagValue )
{
bool			bResult;

	bResult = true;

	switch (flagEnum)
	{
	case wxCOLUMNHEADER_FLAGATTR_Enabled:
		m_BEnabled = bFlagValue;
		break;

	case wxCOLUMNHEADER_FLAGATTR_Selected:
		m_BSelected = bFlagValue;
		break;

	case wxCOLUMNHEADER_FLAGATTR_SortEnabled:
		m_BSortEnabled = bFlagValue;
		break;

	case wxCOLUMNHEADER_FLAGATTR_SortDirection:
		m_BSortAscending = bFlagValue;
		break;

	case wxCOLUMNHEADER_FLAGATTR_FixedWidth:
		m_BFixedWidth = bFlagValue;
		break;

	default:
		bResult = false;
		break;
	}

	return bResult;
}

long wxColumnHeaderItem::HitTest(
	const wxPoint		&locationPt ) const
{
long		targetX, resultV;

	targetX = locationPt.x;
	resultV = ((targetX >= m_OriginX) && (targetX < m_OriginX + m_ExtentX));

	return resultV;
}

#if defined(__WXMAC__)
long wxColumnHeaderItem::MacDrawItem(
	wxWindow		*parentW,
	wxClientDC		*dc,
	const wxRect		*boundsR,
	bool				bUseUnicode,
	bool				bVisibleSelection )
{
ThemeButtonDrawInfo		drawInfo;
Rect					qdBoundsR;
long					nativeTextJust;
SInt16				nativeFontID;
bool					bSelected, bHasIcon;
OSStatus				errStatus;

//	if ((boundsR == NULL) || boundsR->IsEmpty())
	if (boundsR == NULL)
		return (-1L);

	errStatus = noErr;

	qdBoundsR.left = boundsR->x;
	qdBoundsR.right = qdBoundsR.left + boundsR->width;
	qdBoundsR.top = boundsR->y;
	qdBoundsR.bottom = qdBoundsR.top + boundsR->height;

	// determine selection and bitmap rendering conditions
	bSelected = m_BSelected && bVisibleSelection;
	bHasIcon = ((dc != NULL) && HasValidBitmapRef( m_BitmapRef ));

	// a broken, dead attempt to tinge the background
// Collection	origCol, newCol;
// RGBColor	tintRGB = { 0xFFFF, 0x0000, 0xFFFF };
//	errStatus = SetAppearanceTintColor( &tintRGB, origCol, newCol );

	if (m_BEnabled)
		drawInfo.state = (bSelected && bVisibleSelection ? kThemeStateActive: kThemeStateInactive);
	else
		drawInfo.state = (bSelected && bVisibleSelection ? kThemeStateUnavailable : kThemeStateUnavailableInactive);
//	drawInfo.state = kThemeStatePressed;

	// zero draws w/o theme background shading
	drawInfo.value = (SInt32)m_BSelected && bVisibleSelection;

	drawInfo.adornment = (m_BSortAscending ? kThemeAdornmentNone : kThemeAdornmentArrowDoubleArrow);
//	drawInfo.adornment = kThemeAdornmentNone;					// doesn't work - draws down arrow !!
//	drawInfo.adornment = kThemeAdornmentDefault;				// doesn't work - draws down arrow !!
//	drawInfo.adornment = kThemeAdornmentHeaderButtonShadowOnly;	// doesn't work - draws down arrow !!
//	drawInfo.adornment = kThemeAdornmentArrowDoubleArrow;		// doesn't work - same as "up-arrow" !!
//	drawInfo.adornment = kThemeAdornmentHeaderMenuButton;		// right-pointing arrow on left side
//	drawInfo.adornment = kThemeAdornmentHeaderButtonSortUp;
//	drawInfo.adornment = kThemeAdornmentArrowDownArrow;

	// NB: DrawThemeButton height is fixed, regardless of the boundsRect argument!
	if (! m_BSortEnabled)
		MacDrawThemeBackgroundNoArrows( &qdBoundsR, bSelected && m_BEnabled );
	else
		errStatus = DrawThemeButton( &qdBoundsR, kThemeListHeaderButton, &drawInfo, NULL, NULL, NULL, 0 );

	// end of the dead attempt to tinge the background
//	errStatus = RestoreTheme( origCol, newCol );

	// exclude button adornment areas from further drawing consideration
	qdBoundsR.top += 1;
	qdBoundsR.left += wxCHI_kMetricInsetX;
	qdBoundsR.right -= (m_BSortEnabled ? wxCHI_kMetricArrowSizeX + wxCHI_kMetricInsetX : wxCHI_kMetricInsetX);

	nativeTextJust = ConvertJustification( m_TextJust, TRUE );

	// render the label text as/if specified
	if (! bHasIcon && ! m_LabelTextRef.IsEmpty())
	{
		nativeFontID = dc->GetFont().MacGetThemeFontID();

		if (bUseUnicode)
		{
		wxMacCFStringHolder	localCFSHolder( m_LabelTextRef, wxFONTENCODING_UNICODE );

			errStatus =
				(OSStatus)DrawThemeTextBox(
					(CFStringRef)localCFSHolder,
					nativeFontID, drawInfo.state, true,
					&qdBoundsR, nativeTextJust, NULL );
		}
		else
		{
		CFStringRef			cfLabelText;

			cfLabelText = CFStringCreateWithCString( NULL, (const char*)(m_LabelTextRef.c_str()), kCFStringEncodingMacRoman );
			if (cfLabelText != NULL)
			{
				errStatus =
					(OSStatus)DrawThemeTextBox(
						cfLabelText,
						nativeFontID, drawInfo.state, true,
						&qdBoundsR, nativeTextJust, NULL );

				CFRelease( cfLabelText );
			}
		}
	}

	// render the bitmap, should one be present
	if (bHasIcon)
	{
	wxRect		subItemBoundsR;

		GenericGetBitmapItemBounds( boundsR, m_TextJust, m_BitmapRef, &subItemBoundsR );
		dc->DrawBitmap( *m_BitmapRef, subItemBoundsR.x, subItemBoundsR.y, false );
	}

	return (long)errStatus;
}
#endif

long wxColumnHeaderItem::GenericDrawItem(
	wxWindow		*parentW,
	wxClientDC		*dc,
	const wxRect		*boundsR,
	bool				bUseUnicode,
	bool				bVisibleSelection )
{
wxRect				localBoundsR, subItemBoundsR;
long					originX, insetX;
bool					bSelected, bHasIcon;

	wxUnusedVar( bUseUnicode );

//	if ((boundsR == NULL) || boundsR->IsEmpty())
	if (boundsR == NULL)
		return (-1L);

	if ((parentW == NULL) || (dc == NULL))
		return (-1L);

	// determine selection and bitmap rendering conditions
	bSelected = m_BSelected && bVisibleSelection;
	bHasIcon = ((dc != NULL) && HasValidBitmapRef( m_BitmapRef ));

	// draw column header background:
	// leverage native (GTK?) wxRenderer
	localBoundsR = *boundsR;
	wxRendererNative::Get().DrawHeaderButton( parentW, *dc, localBoundsR );

	// draw text label, with justification
	insetX = wxCHI_kMetricInsetX;
	originX = localBoundsR.x;

	switch (m_TextJust)
	{
	case wxCOLUMNHEADER_JUST_Right:
	case wxCOLUMNHEADER_JUST_Center:
		if ((m_LabelTextExtent.x < 0) || (m_LabelTextExtent.y < 0))
		{
		wxCoord		targetWidth, targetHeight;

			dc->GetTextExtent(
				m_LabelTextRef,
				&targetWidth, &targetHeight,
				NULL, NULL, NULL );

			m_LabelTextExtent.x = targetWidth;
			m_LabelTextExtent.y = targetHeight;
		}
		if (m_ExtentX > m_LabelTextExtent.x)
		{
			if (m_TextJust == wxCOLUMNHEADER_JUST_Center)
				originX += (m_ExtentX - m_LabelTextExtent.x) / 2;
			else
				originX += m_ExtentX - (m_LabelTextExtent.x + insetX);
		}
		break;

	case wxCOLUMNHEADER_JUST_Left:
	default:
		originX += insetX;
		break;
	}

	// FIXME: need to clip long text items
	if (! bHasIcon && ! m_LabelTextRef.IsEmpty())
		dc->DrawText( m_LabelTextRef.c_str(), originX, localBoundsR.y + 1 );

	// draw sort direction arrows (if specified)
	// NB: what if icon avail? mutually exclusive?
	if (bSelected && m_BSortEnabled)
	{
		GenericGetSortArrowBounds( &localBoundsR, &subItemBoundsR );
		GenericDrawSortArrow( dc, &subItemBoundsR, m_BSortAscending );
	}

	// render the bitmap, should one be present
	if (bHasIcon)
	{
		GenericGetBitmapItemBounds( &localBoundsR, m_TextJust, m_BitmapRef, &subItemBoundsR );
		dc->DrawBitmap( *m_BitmapRef, subItemBoundsR.x, subItemBoundsR.y, false );
	}

	return 0;
}

long wxColumnHeaderItem::TruncateLabelText(
	wxDC			*dc,
	wxString			&targetStr,
	long				maxWidth,
	long				&charCount )
{
wxString		truncStr, ellipsisStr;
wxCoord		targetWidth, targetHeight, ellipsisWidth;
bool			bContinue;

	if ((dc == NULL) || (maxWidth <= 0))
		return 0;

	charCount = targetStr.Length();
	if (charCount <= 0)
		return 0;

	// determine the minimum width
	ellipsisStr = wxString( wxT("...") );
	dc->GetTextExtent( ellipsisStr, &ellipsisWidth, &targetHeight );
	if (ellipsisWidth > maxWidth)
		return 0;

	// determine if the string can fit inside the current width
	dc->GetTextExtent( targetStr, &targetWidth, &targetHeight );
	bContinue = (targetWidth > maxWidth);

	if (bContinue)
	{
		charCount--;

		if (charCount > 0)
		{
			truncStr = targetStr.Left( charCount );
			dc->GetTextExtent( truncStr, &targetWidth, &targetHeight );
			bContinue = (targetWidth + ellipsisWidth > maxWidth);

			if (! bContinue)
				targetStr = truncStr + ellipsisStr;
		}
		else
		{
			targetStr = ellipsisStr;
			targetWidth = ellipsisWidth;
			bContinue = false;
		}
	}

	return (long)targetWidth;
}

// ================
#if 0
#pragma mark -
#endif

#if defined(__WXMAC__)
// static
void wxColumnHeaderItem::MacDrawThemeBackgroundNoArrows(
	const void				*boundsR,
	bool					bSelected )
{
ThemeButtonDrawInfo	drawInfo;
Rect				qdBoundsR;
RgnHandle			savedClipRgn;
OSStatus			errStatus;

	if ((boundsR == NULL) || EmptyRect( (const Rect*)boundsR ))
		return;

	qdBoundsR = *(const Rect*)boundsR;

	// NB: zero draws w/o theme background shading
	drawInfo.value = (SInt32)bSelected;
	drawInfo.state = (bSelected ? kThemeStateActive: kThemeStateInactive);
	drawInfo.adornment = kThemeAdornmentNone;

	// clip down to the item bounds
	savedClipRgn = NewRgn();
	GetClip( savedClipRgn );
	ClipRect( &qdBoundsR );

	// first, render the entire area normally: fill, border and arrows
	errStatus = DrawThemeButton( &qdBoundsR, kThemeListHeaderButton, &drawInfo, NULL, NULL, NULL, 0 );

	// now render fill over the arrows, but preserve the right-side one-pixel border
	qdBoundsR.right--;
	ClipRect( &qdBoundsR );
	qdBoundsR.right += 25;
	errStatus = DrawThemeButton( &qdBoundsR, kThemeListHeaderButton, &drawInfo, NULL, NULL, NULL, 0 );

	// restore the clip region
	SetClip( savedClipRgn );
	DisposeRgn( savedClipRgn );
}
#endif

// static
void wxColumnHeaderItem::GenericDrawSelection(
	wxClientDC			*dc,
	const wxRect			*boundsR,
	const wxColour			*targetColour,
	long					drawStyle )
{
wxPen		targetPen( *wxLIGHT_GREY, 1, wxSOLID );
long			borderWidth, offsetY;


	if ((dc == NULL) || (boundsR == NULL))
		return;

	if (targetColour != NULL)
		targetPen.SetColour( *targetColour );

#if 0
	wxLogDebug(
		_T("GenericDrawSelection: [%ld, %ld, %ld, %ld]"),
		boundsR->x, boundsR->y, boundsR->width, boundsR->height );
#endif

	switch (drawStyle)
	{
	case wxCOLUMNHEADER_SELECTIONDRAWSTYLE_None:
	case wxCOLUMNHEADER_SELECTIONDRAWSTYLE_Native:
	case wxCOLUMNHEADER_SELECTIONDRAWSTYLE_BoldLabel:
		// performed elsewheres or not at all
		break;

	case wxCOLUMNHEADER_SELECTIONDRAWSTYLE_Grey:
	case wxCOLUMNHEADER_SELECTIONDRAWSTYLE_InvertBevel:
	case wxCOLUMNHEADER_SELECTIONDRAWSTYLE_Bullet:
		// NB: not yet implemented
		break;

	case wxCOLUMNHEADER_SELECTIONDRAWSTYLE_Frame:
		// frame border style
		borderWidth = 2;
		targetPen.SetWidth( borderWidth );
		dc->SetPen( targetPen );
		dc->SetBrush( *wxTRANSPARENT_BRUSH );

		dc->DrawRectangle(
			boundsR->x,
			boundsR->y,
			boundsR->width - borderWidth,
			boundsR->height );
		break;

	case wxCOLUMNHEADER_SELECTIONDRAWSTYLE_Underline:
	case wxCOLUMNHEADER_SELECTIONDRAWSTYLE_Overline:
	default:
		// underline style - similar to MSW rollover drawing
		// overline style - similar to MSW tab highlighting
		borderWidth = 6;
		targetPen.SetWidth( borderWidth );
		dc->SetPen( targetPen );

		offsetY = 0;
		if (drawStyle == wxCOLUMNHEADER_SELECTIONDRAWSTYLE_Underline)
			offsetY = boundsR->height;

		dc->DrawLine(
			boundsR->x,
			boundsR->y + offsetY,
			boundsR->x + boundsR->width - borderWidth,
			boundsR->y + offsetY );
		break;
	}
}

// static
void wxColumnHeaderItem::GenericGetSortArrowBounds(
	const wxRect			*itemBoundsR,
	wxRect				*targetBoundsR )
{
int		sizeX, sizeY, insetX;

	if (targetBoundsR == NULL)
		return;

	if (itemBoundsR != NULL)
	{
		sizeX = wxCHI_kMetricArrowSizeX;
		sizeY = wxCHI_kMetricArrowSizeY;
		insetX = wxCHI_kMetricInsetX;

		targetBoundsR->x = itemBoundsR->x + itemBoundsR->width - (sizeX + insetX);
		targetBoundsR->y = itemBoundsR->y + (itemBoundsR->height - sizeY) / 2;
		targetBoundsR->width = sizeX;
		targetBoundsR->height = sizeY;
	}
	else
	{
		targetBoundsR->x =
		targetBoundsR->y =
		targetBoundsR->width =
		targetBoundsR->height = 0;
	}
}

// static
void wxColumnHeaderItem::GenericDrawSortArrow(
	wxClientDC			*dc,
	const wxRect			*boundsR,
	bool					bSortAscending )
{
wxPoint		triPt[3];

	if ((dc == NULL) || (boundsR == NULL))
		return;

	if (bSortAscending)
	{
		triPt[0].x = boundsR->width / 2;
		triPt[0].y = 0;
		triPt[1].x = boundsR->width;
		triPt[1].y = boundsR->height;
		triPt[2].x = 0;
		triPt[2].y = boundsR->height;
	}
	else
	{
		triPt[0].x = 0;
		triPt[0].y = 0;
		triPt[1].x = boundsR->width;
		triPt[1].y = 0;
		triPt[2].x = boundsR->width / 2;
		triPt[2].y = boundsR->height;
	}

	dc->DrawPolygon( 3, triPt, boundsR->x, boundsR->y );
}

// static
void wxColumnHeaderItem::GenericGetBitmapItemBounds(
	const wxRect			*itemBoundsR,
	long					targetJustification,
	const wxBitmap		*targetBitmap,
	wxRect				*targetBoundsR )
{
int		sizeX, sizeY, insetX;

	if (targetBoundsR == NULL)
		return;

	if (itemBoundsR != NULL)
	{
		sizeX = wxCHI_kMetricBitmapSizeX;
		sizeY = wxCHI_kMetricBitmapSizeY;
		insetX = wxCHI_kMetricInsetX;

		targetBoundsR->x = itemBoundsR->x;
		targetBoundsR->y = (itemBoundsR->height - sizeY) / 2;
//		targetBoundsR->y = itemBoundsR->y + (itemBoundsR->height - sizeY) / 2;
		targetBoundsR->width = sizeX;
		targetBoundsR->height = sizeY;

		switch (targetJustification)
		{
		case wxCOLUMNHEADER_JUST_Right:
			targetBoundsR->x += (itemBoundsR->width - sizeX) - insetX;
			break;

		case wxCOLUMNHEADER_JUST_Center:
			targetBoundsR->x += (itemBoundsR->width - sizeX) / 2;
			break;

		case wxCOLUMNHEADER_JUST_Left:
		default:
			targetBoundsR->x += insetX;
			break;
		}

		// if a bitmap was specified and it's smaller than the default bounds,
		// center and shrink to fit
		if (targetBitmap != NULL)
		{
		long		deltaV;

			deltaV = targetBitmap->GetWidth() - targetBoundsR->width;
			if (deltaV > 0)
			{
				targetBoundsR->width -= deltaV;
				targetBoundsR->x += deltaV;
			}

			deltaV = targetBitmap->GetHeight() - targetBoundsR->height;
			if (deltaV > 0)
			{
				targetBoundsR->height -= deltaV;
				targetBoundsR->y += deltaV;
			}
		}
	}
	else
	{
		targetBoundsR->x =
		targetBoundsR->y =
		targetBoundsR->width =
		targetBoundsR->height = 0;
	}
}

// static
bool wxColumnHeaderItem::HasValidBitmapRef(
	const wxBitmap		*bitmapRef )
{
bool		bResultV;

	bResultV = ((bitmapRef != NULL) && bitmapRef->Ok());

	return bResultV;
}

// static
long wxColumnHeaderItem::ConvertJustification(
	long			sourceEnum,
	bool			bToNative )
{
typedef struct { long valA; long valB; } AnonLongPair;
static AnonLongPair	sMap[] =
{
#if defined(__WXMSW__)
	{ wxCOLUMNHEADER_JUST_Left, HDF_LEFT }
	, { wxCOLUMNHEADER_JUST_Center, HDF_CENTER }
	, { wxCOLUMNHEADER_JUST_Right, HDF_RIGHT }
#elif defined(__WXMAC__)
	{ wxCOLUMNHEADER_JUST_Left, teJustLeft }
	, { wxCOLUMNHEADER_JUST_Center, teJustCenter }
	, { wxCOLUMNHEADER_JUST_Right, teJustRight }
#else
	// FIXME: generic - wild guess - irrelevant
	{ wxCOLUMNHEADER_JUST_Left, 0 }
	, { wxCOLUMNHEADER_JUST_Center, 1 }
	, { wxCOLUMNHEADER_JUST_Right, 2 }
#endif
};

long		defaultResultV, itemCount, i;

	itemCount = (long)(sizeof(sMap) / sizeof(*sMap));

	if (bToNative)
	{
		defaultResultV = sMap[0].valB;

		for (i=0; i<itemCount; i++)
		{
			if (sMap[i].valA == sourceEnum)
				return sMap[i].valB;
		}
	}
	else
	{
		defaultResultV = sMap[0].valA;

		for (i=0; i<itemCount; i++)
		{
			if (sMap[i].valB == sourceEnum)
				return sMap[i].valA;
		}
	}

	return defaultResultV;
}


// #endif // wxUSE_COLUMNHEADER

