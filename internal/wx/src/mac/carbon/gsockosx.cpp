/* -------------------------------------------------------------------------
 * Project:     GSocket (Generic Socket) for WX
 * Name:        gsockosx.c
 * Copyright:   (c) Brian Victor
 * Licence:     wxWindows Licence
 * Purpose:     GSocket: Mac OS X mach-o part
 * CVSID:   $Id$
 * Mac code by Brian Victor, February 2002.  Email comments to bhv1@psu.edu
 * ------------------------------------------------------------------------- */

#include "wx/setup.h"

#if wxUSE_SOCKETS

#include <stdlib.h>
#include "wx/gsocket.h"
#include "wx/unix/gsockunx.h"

#include <CoreFoundation/CoreFoundation.h>

#define ALL_CALLBACK_TYPES (kCFSocketReadCallBack | kCFSocketWriteCallBack | kCFSocketConnectCallBack)

struct MacGSocketData
{
  CFSocketRef socket;
  CFRunLoopSourceRef source;
};

// Sockets must use the event loop on the main thread
// We will store the main loop's reference when Initialize is called
static CFRunLoopRef s_mainRunLoop = NULL;

void Mac_Socket_Callback(CFSocketRef s, CFSocketCallBackType callbackType,
                         CFDataRef address, const void* data, void* info)
{
  GSocket* socket = (GSocket*)info;
  struct MacGSocketData* macdata;
  macdata = (struct MacGSocketData*)socket->m_gui_dependent;
  if (!macdata) return;
  switch (callbackType)
  {
    case kCFSocketConnectCallBack:
      assert(!socket->m_server);
      socket->Detected_Write();
      break;
    case kCFSocketReadCallBack:
      socket->Detected_Read();
      break;
    case kCFSocketWriteCallBack:
      socket->Detected_Write();
      break;
    default:
      break;  /* We shouldn't get here. */
  }
}

struct MacGSocketData* _GSocket_Get_Mac_Socket(GSocket *socket)
{
  /* If socket is already created, returns a pointer to the data */
  /* Otherwise, creates socket and returns the pointer */
  CFSocketContext cont;
  struct MacGSocketData* data = (struct MacGSocketData*)socket->m_gui_dependent;

  if (data && data->source) return data;

  /* CFSocket has not been created, create it: */
  if (socket->m_fd < 0 || !data) return NULL;
  cont.version = 0; cont.retain = NULL;
  cont.release = NULL; cont.copyDescription = NULL;
  cont.info = socket;

  CFSocketRef cf = CFSocketCreateWithNative(NULL, socket->m_fd,
  			ALL_CALLBACK_TYPES, Mac_Socket_Callback, &cont);
  CFRunLoopSourceRef source = CFSocketCreateRunLoopSource(NULL, cf, 0);
  assert(source);
  socket->m_gui_dependent = (char*)data;

  /* Keep the source and the socket around. */
  data->source = source;
  data->socket = cf;

  return data;
}

bool GSocketGUIFunctionsTableConcrete::CanUseEventLoop()
{   return true; }

bool GSocketGUIFunctionsTableConcrete::OnInit(void)
{
    // No need to store the main loop again
    if (s_mainRunLoop != NULL)
        return true;

    // Get the loop for the main thread so our events will actually fire.
    // The common socket.cpp code will assert if initialize is called from a
    // secondary thread, otherwise Mac would have the same problems as MSW
    s_mainRunLoop = CFRunLoopGetCurrent();
    CFRetain(s_mainRunLoop);

    return true;
}

void GSocketGUIFunctionsTableConcrete::OnExit(void)
{
    // Release the reference count, and set the reference back to NULL
    CFRelease(s_mainRunLoop);
    s_mainRunLoop = NULL;
}

bool GSocketGUIFunctionsTableConcrete::Init_Socket(GSocket *socket)
{
    struct MacGSocketData *data = (struct MacGSocketData *)malloc(sizeof(struct MacGSocketData));
    if (data)
    {
        socket->m_gui_dependent = (char*)data;
        data->socket = NULL;
        data->source = NULL;
        return 1;
    }
    return 0;
}

void GSocketGUIFunctionsTableConcrete::Destroy_Socket(GSocket *socket)
{
    struct MacGSocketData *data = (struct MacGSocketData*)(socket->m_gui_dependent);
    if (data)
    {
        CFRelease(data->socket);
        free(data);
    }
}

void GSocketGUIFunctionsTableConcrete::Install_Callback(GSocket *socket, GSocketEvent event)
{
    int c;
    struct MacGSocketData* data = _GSocket_Get_Mac_Socket(socket);
    if (!data) return;
    switch (event)
    {
     case GSOCK_CONNECTION:
         if(socket->m_server)
            c = kCFSocketReadCallBack;
         else
            c = kCFSocketConnectCallBack;
         break;
     case GSOCK_LOST:
     case GSOCK_INPUT:
         c = kCFSocketReadCallBack;
         break;
     case GSOCK_OUTPUT:
         c = kCFSocketWriteCallBack;
         break;
     default:
         c = 0;
    }
    CFSocketEnableCallBacks(data->socket, c);
}

void GSocketGUIFunctionsTableConcrete::Uninstall_Callback(GSocket *socket, GSocketEvent event)
{
    int c;
    struct MacGSocketData* data = _GSocket_Get_Mac_Socket(socket);
    if (!data) return;
    switch (event)
    {
     case GSOCK_CONNECTION:
         if(socket->m_server)
            c = kCFSocketReadCallBack;
         else
            c = kCFSocketConnectCallBack;
         break;
     case GSOCK_LOST:
     case GSOCK_INPUT:
         c = kCFSocketReadCallBack;
         break;
     case GSOCK_OUTPUT:
         c = kCFSocketWriteCallBack;
         break;
     default:
         c = 0;
    }
    CFSocketDisableCallBacks(data->socket, c);
}

void GSocketGUIFunctionsTableConcrete::Enable_Events(GSocket *socket)
{
    struct MacGSocketData* data = _GSocket_Get_Mac_Socket(socket);
    if (!data) return;

    CFRunLoopAddSource(s_mainRunLoop, data->source, kCFRunLoopCommonModes);
}

void GSocketGUIFunctionsTableConcrete::Disable_Events(GSocket *socket)
{
    struct MacGSocketData* data = _GSocket_Get_Mac_Socket(socket);
    if (!data) return;

    /* CFSocketInvalidate does CFRunLoopRemoveSource anyway */
    CFRunLoopRemoveSource(s_mainRunLoop, data->source, kCFRunLoopCommonModes);
    CFSocketInvalidate(data->socket);
}

#endif // wxUSE_SOCKETS
