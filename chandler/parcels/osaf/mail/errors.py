__revision__  = "$Revision$"
__date__      = "$Date$"
__copyright__ = "Copyright (c) 2005 Open Source Applications Foundation"
__license__   = "http://osafoundation.org/Chandler_0.1_license_terms.htm"

class MailException(Exception):
    """Base class for all Chandler mail related exceptions"""

class IMAPException(MailException):
    """Base class for all Chandler IMAP based exceptions"""

class SMTPException(MailException):
    """Base class for all Chandler SMTP based exceptions"""

"""Code return by M2Crypto when a certificate can not be verified"""
M2CRYPTO_CERTIFICATE_VERIFY_FAILED  = 18

__SMTP_PREFIX        = "twisted.mail.smtp."
__IMAP4_PREFIX       = "twisted.mail.imap4."
__TWISTED_PREFIX     = "twisted.internet.error."
__M2CRYPTO_PREFIX    = "M2Crypto.BIO."
__MAILSERVICE_PREFIX = "osaf.mail.errors."

AUTH_DECLINED_ERROR       = __SMTP_PREFIX + "AUTHDeclinedError"
TLS_ERROR                 = __SMTP_PREFIX + "TLSError"
SMTP_DELIVERY_ERROR       = __SMTP_PREFIX + "SMTPDeliveryError"
SMTP_CONNECT_ERROR        = __SMTP_PREFIX + "SMTPConnectError"
SMTP_PROTOCOL_ERROR       = __SMTP_PREFIX + "SMTPProtocolError"
CONNECT_ERROR             = __TWISTED_PREFIX + "ConnectError"
CONNECT_BIND_ERROR        = __TWISTED_PREFIX + "ConnectBindError"
UNKNOWN_HOST_ERROR        = __TWISTED_PREFIX + "UnknownHostError"
TIMEOUT_ERROR             = __TWISTED_PREFIX + "TimeoutError"
M2CRYPTO_ERROR            = __M2CRYPTO_PREFIX + "BIOError"
SSL_ERROR                 = __TWISTED_PREFIX + "SSLError"
DNS_LOOKUP_ERROR          = __TWISTED_PREFIX + "DNSLookupError"
CONNECTION_REFUSED_ERROR  = __TWISTED_PREFIX + "ConnectionRefusedError"
MAIL_EXCEPTION            = __MAILSERVICE_PREFIX + "MailException"
IMAP_EXCEPTION            = __MAILSERVICE_PREFIX + "IMAPException"
SMTP_EXCEPTION            = __MAILSERVICE_PREFIX + "SMTPException"

""" Contains common transport error codes used by the mail service"""
__offset = 600

DNS_LOOKUP_CODE         = __offset + 1
DELIVERY_CODE           = __offset + 2
PROTOCOL_CODE           = __offset + 3
CONNECTION_CODE         = __offset + 4
BIND_CODE               = __offset + 5
UNKNOWN_HOST_CODE       = __offset + 6
TIMEOUT_CODE            = __offset + 8
SSL_CODE                = __offset + 9
CONNECTION_REFUSED_CODE = __offset + 10
UNKNOWN_CODE            = __offset + 11
MISSING_VALUE_CODE      = __offset + 12
M2CRYPTO_CODE           = __offset + 13
