"""M2Crypto wrapper for OpenSSL X509 API.

This module has evolved based on the needs of supporting X.509 
certificate operations (mainly attribute getters for 
authentication purposes) from within an SSL connection.

Copyright (c) 1999-2003 Ng Pheng Siong. All rights reserved.

Open Source Applications Foundation (OSAF) has extended the functionality
to make it possible to create and verify certificates programmatically.

Epydoc comments also by OSAF.

OSAF Changes copyright (c) 2004 Open Source Applications Foundation.
Author: Heikki Toivonen
"""

RCS_id='$Id$'

# M2Crypto
import ASN1, BIO, Err
import m2

class X509Error(Exception): pass

m2.x509_init(X509Error)

V_OK = m2.X509_V_OK

class X509_Store_Context:
    def __init__(self, x509_store_ctx, _pyfree=0):
        self.ctx = x509_store_ctx
        self._pyfree = _pyfree

    #def __del__(self):
    # XXX verify this method
    #    m2.x509_store_ctx_cleanup(self.ctx)


class X509_Name:

    nid = {'C'  : m2.NID_countryName,
           'SP' : m2.NID_stateOrProvinceName,
           'L'  : m2.NID_localityName,
           'O'  : m2.NID_organizationName,
           'OU' : m2.NID_organizationalUnitName,
           'CN' : m2.NID_commonName,
           'Email' : m2.NID_pkcs9_emailAddress,
           'emailAddress': m2.NID_pkcs9_emailAddress}

    def __init__(self, x509_name=None, _pyfree=0):
        if x509_name is not None:
            assert m2.x509_name_type_check(x509_name), "'x509_name' type error"
            self.x509_name = x509_name
        else:
            self.x509_name = m2.x509_name_new()
        self._pyfree = _pyfree

    def __del__(self):
        try:
            if self._pyfree:
                m2.x509_name_free(self.x509_name)
        except AttributeError:
            pass

    def __str__(self):
        assert m2.x509_name_type_check(self.x509_name), "'x509_name' type error" 
        return m2.x509_name_oneline(self.x509_name)

    def __getattr__(self, attr):
        if attr in self.nid.keys():
            assert m2.x509_name_type_check(self.x509_name), "'x509_name' type error" 
            return m2.x509_name_by_nid(self.x509_name, self.nid[attr])
        else:
            raise AttributeError, (self, attr)

    def __setattr__(self, attr, value):
        if attr in self.nid.keys():
            assert m2.x509_name_type_check(self.x509_name), "'x509_name' type error"
            return m2.x509_name_set_by_nid(self.x509_name, self.nid[attr], value)
        else:
            self.__dict__[attr] = value


class X509:

    """
    Object interface to an X.509 digital certificate.
    """

    def __init__(self, x509=None, _pyfree=0):
        if x509 is not None:
            assert m2.x509_type_check(x509), "'x509' type error"
            self.x509 = x509
        else:
            self.x509 = m2.x509_new()
        self._pyfree = _pyfree

    def __del__(self):
        try:
            if self._pyfree:
                m2.x509_free(self.x509)
        except AttributeError:
            pass

    def _ptr(self):
        assert m2.x509_type_check(self.x509), "'x509' type error"
        return self.x509

    def as_text(self):
        assert m2.x509_type_check(self.x509), "'x509' type error"
        buf=BIO.MemoryBuffer()
        m2.x509_print(buf.bio_ptr(), self.x509)
        return buf.read_all()

    def as_der(self):
        assert m2.x509_type_check(self.x509), "'x509' type error"
        buf=BIO.MemoryBuffer()
        m2.i2d_x509(buf.bio_ptr(), self.x509)
        return buf.read_all()

    def get_version(self):
        assert m2.x509_type_check(self.x509), "'x509' type error"
        return m2.x509_get_version(self.x509)

    def set_version(self, version):
        """
        Set version.

        @type version:  an integer
        @param version: Version number.
        @rtype:         an integer
        @return:        Returns 0 on failure.
        """
        assert m2.x509_type_check(self.x509), "'x509' type error"    
        return m2.x509_set_version(self.x509, version)

    def get_serial_number(self):
        assert m2.x509_type_check(self.x509), "'x509' type error"
        asn1_integer = m2.x509_get_serial_number(self.x509)
        return m2.asn1_integer_get(asn1_integer)

    def get_not_before(self):
        assert m2.x509_type_check(self.x509), "'x509' type error"
        return ASN1.ASN1_UTCTIME(m2.x509_get_not_before(self.x509))

    def get_not_after(self):
        assert m2.x509_type_check(self.x509), "'x509' type error"
        return ASN1.ASN1_UTCTIME(m2.x509_get_not_after(self.x509))

    def get_pubkey(self):
        assert m2.x509_type_check(self.x509), "'x509' type error"
        return m2.x509_get_pubkey(self.x509)

    def set_pubkey(self, pkey):
        """
        Set the public key for the certificate

        @type pkey:  EVP_PKEY
        @param pkey: Public key
        @rtype:      XXX
        @return:     XXX
        """
        assert m2.x509_type_check(self.x509), "'x509' type error"
        return m2.x509_set_pubkey(self.x509, pkey.pkey)

    def get_issuer(self):
        assert m2.x509_type_check(self.x509), "'x509' type error"
        return X509_Name(m2.x509_get_issuer_name(self.x509))

    def set_issuer(self, name):
        """
        Set issuer name.

        @type name:     X509_Name
        @param name:    subjectName field.
        @rtype:         XXX
        @return:        XXX
        """
        assert m2.x509_type_check(self.x509), "'x509' type error"
        return m2.x509_set_issuer_name(self.x509, name.x509_name)

    def get_subject(self):
        assert m2.x509_type_check(self.x509), "'x509' type error"
        return X509_Name(m2.x509_get_subject_name(self.x509))

    def set_subject(self, name):
        """
        Set subject name.

        @type name:     X509_Name
        @param name:    subjectName field.
        @rtype:         XXX
        @return:        XXX
        """
        assert m2.x509_type_check(self.x509), "'x509' type error"
        return m2.x509_set_subject_name(self.x509, name.x509_name)

    def sign(self, pkey, md):
        """
        Sign the certificate.

        @type pkey:  EVP_PKEY
        @param pkey: Public key
        @type md:    string
        @param md:   Message digest algorithm to use for signing, for example
                     'sha1'.
        @rtype:      XXX
        @return:     XXX
        """
        assert m2.x509_type_check(self.x509), "'x509' type error"        
        mda = getattr(m2, md)
        if not mda:
            raise ValueError, ('unknown message digest', md)
        return m2.x509_sign(self.x509, pkey.pkey, mda())

def load_cert(file):
    bio = BIO.openfile(file)
    return load_cert_bio(bio)


def load_cert_bio(bio):
    return X509(m2.x509_read_pem(bio._ptr()), 1)


class X509_Store:
    def __init__(self, store=None, _pyfree=0):
        if store is not None:
            self.store = store
            self._pyfree = _pyfree
        else:
            self.store = m2.x509_store_new()
            self._pyfree = 1

    def __del__(self):
        if self._pyfree:
            m2.x509_store_free(self.store)

    def _ptr(self):
        return self.store

    def load_info(self, file):
        m2.x509_store_load_locations(self.store, file)

    load_locations = load_info
         
    def add_x509(self, x509):
        assert isinstance(x509, X509)
        return m2.x509_store_add_cert(self.store, x509._ptr())


class X509_Stack:
    def __init__(self, stack=None, _pyfree=0):
        if stack is not None:
            self.stack = stack
            self._pyfree = _pyfree
        else:
            self.stack = m2.sk_x509_new_null()
            self._pyfree = 1
        self._refkeeper = {}

    def __del__(self):
        if self._pyfree:
            m2.sk_x509_free(self.stack)

    def __len__(self):
        return m2.sk_x509_num(self.stack)

    def __getitem__(self, idx):
        if idx < 0 or idx >= m2.sk_x509_num(self.stack):
            raise IndexError, 'index out of range'
        v=m2.sk_x509_value(self.stack, idx)
        return X509(v)

    def _ptr(self):
        return self.stack

    def push(self, x509):
        assert isinstance(x509, X509)
        self._refkeeper[x509._ptr()] = x509
        return m2.sk_x509_push(self.stack, x509._ptr())

    def pop(self):
        x509_ptr = m2.sk_x509_pop(self.stack)
        del self._refkeeper[x509_ptr]


class Request:
    """
    An X509 certificate request. A request is required to make a certificate.
    """
    def __init__(self, req=None, _pyfree=0):
        if req is not None:
            self.req = req
            self._pyfree = _pyfree
        else:
            self.req = m2.x509_req_new()
            self._pyfree = 1

    def __del__(self):
        if self._pyfree:
            m2.x509_req_free(self.req)

    def as_text(self):
        buf=BIO.MemoryBuffer()
        m2.x509_req_print(buf.bio_ptr(), self.req)
        return buf.read_all()

    def as_pem(self):
        buf=BIO.MemoryBuffer()
        m2.x509_req_write_pem(buf.bio_ptr(), self.req)
        return buf.read_all()

    def save_pem(self, filename):
        bio=BIO.openfile(filename, 'wb')
        return m2.x509_req_write_pem(bio.bio_ptr(), self.req)

    def get_pubkey(self):
        """
        Get the public key for the request.

        @rtype:      EVP_PKEY
        @return:     Public key from the request.
        """
        return m2.x509_req_get_pubkey(self.req)

    def set_pubkey(self, pkey):
        """
        Set the public key for the request.

        @type pkey:  EVP_PKEY
        @param pkey: Public key
        @rtype:      XXX
        @return:     XXX
        """
        return m2.x509_req_set_pubkey(self.req, pkey.pkey)

    def get_subject(self):
        return X509_Name(m2.x509_req_get_subject_name(self.req))

    def set_subject(self, name):
        """
        Set subject name.

        @type name:     X509_Name
        @param name:    subjectName field.
        @rtype:         XXX
        @return:        XXX
        """
        return m2.x509_req_set_subject_name(self.req, name.x509_name)

    def set_version(self, version):
        """
        Set version.

        @type version:  integer
        @param version: Version number.
        @rtype:         integer
        @return:        Returns 0 on failure.
        """
        return m2.x509_req_set_version(self.req, version)

    def verify(self, pkey):
        return m2.x509_req_verify(self.req, pkey)

    def sign(self, pkey, md):
        mda = getattr(m2, md)
        if not mda:
            raise ValueError, ('unknown message digest', md)
        return m2.x509_req_sign(self.req, pkey.pkey, mda())

def load_request(pemfile):
    f=BIO.openfile(pemfile)
    cptr=m2.x509_req_read_pem(f.bio_ptr())
    f.close()
    if cptr is None:
        raise Err.get_error()
    return Request(cptr, 1)


class CRL:
    def __init__(self, crl=None, _pyfree=0):
        if crl is not None:
            self.crl = crl
            self._pyfree = _pyfree
        else:
            self.crl = m2.x509_crl_new()
            self._pyfree = 1

    def __del__(self):
        if self._pyfree:
            m2.x509_crl_free(self.crl)

    def as_text(self):
        buf=BIO.MemoryBuffer()
        m2.x509_crl_print(buf.bio_ptr(), self.crl)
        return buf.read_all()

def load_crl(pemfile):
    f=BIO.openfile(pemfile)
    cptr=m2.x509_crl_read_pem(f.bio_ptr())
    f.close()
    if cptr is None:
        raise Err.get_error()
    return CRL(cptr, 1)


