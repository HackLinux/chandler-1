#!/usr/bin/env python

"""Unit tests for M2Crypto.SSL.

Copyright (c) 2000-2001 Ng Pheng Siong. All rights reserved."""

RCS_id='$Id$'

import os, socket, string, sys, tempfile, thread, time, unittest
from M2Crypto import Rand, SSL

srv_host = 'localhost'
srv_port = 64000

class SSLClientTestCase(unittest.TestCase):

    def start_server(self, args):
        pid = os.fork()
        if pid == 0:
            os.execvp('openssl', args)
        else:
            time.sleep(0.5)
            return pid

    def stop_server(self, pid):
        os.kill(pid, 1)
        os.waitpid(pid, 0)

    def http_get(self, s):
        s.send('GET / HTTP/1.0\n\n') 
        resp = ''
        while 1:
            try:
                r = s.recv(4096)
                if not r:
                    break
            except SSL.SSLError: # s_server throws an 'unexpected eof'...
                break
            resp = resp + r 
        return resp

    def setUp(self):
        self.srv_host = srv_host
        self.srv_port = srv_port
        self.srv_addr = (srv_host, srv_port)
        self.srv_url = 'https://%s:%s/' % (srv_host, srv_port)
        self.args = ['s_server', '-quiet', '-www', '-accept', str(self.srv_port)]

    def tearDown(self):
        global srv_port
        srv_port = srv_port - 1

    def test_server_simple(self):
        pid = self.start_server(self.args)
        ctx = SSL.Context()
        s = SSL.Connection(ctx)
        s.connect(self.srv_addr)
        data = self.http_get(s)
        s.close()
        self.stop_server(pid)
        self.failIf(string.find(data, 's_server -quiet -www') == -1)

    def test_tls1_nok(self):
        self.args.append('-no_tls1')
        pid = self.start_server(self.args)
        ctx = SSL.Context('tlsv1')
        s = SSL.Connection(ctx)
        try:
            s.connect(self.srv_addr)
        except SSL.SSLError, e:
            self.failUnless(e[0], 'wrong version number')
        s.close()
        self.stop_server(pid)

    def test_tls1_ok(self):
        self.args.append('-tls1')
        pid = self.start_server(self.args)
        ctx = SSL.Context('tlsv1')
        s = SSL.Connection(ctx)
        s.connect(self.srv_addr)
        data = self.http_get(s)
        s.close()
        self.stop_server(pid)
        self.failIf(string.find(data, 's_server -quiet -www') == -1)

    def test_cipher_mismatch(self):
        self.args = self.args + ['-cipher', 'EXP-RC4-MD5']
        pid = self.start_server(self.args)
        ctx = SSL.Context()
        s = SSL.Connection(ctx)
        s.set_cipher_list('EXP-RC2-CBC-MD5')
        try:
            s.connect(self.srv_addr)
        except SSL.SSLError, e:
            self.failUnless(e[0], 'sslv3 alert handshake failure')
        s.close()
        self.stop_server(pid)
        
    def test_no_such_cipher(self):
        self.args = self.args + ['-cipher', 'EXP-RC4-MD5']
        pid = self.start_server(self.args)
        ctx = SSL.Context()
        s = SSL.Connection(ctx)
        s.set_cipher_list('EXP-RC2-MD5')
        try:
            s.connect(self.srv_addr)
        except SSL.SSLError, e:
            self.failUnless(e[0], 'no ciphers available')
        s.close()
        self.stop_server(pid)
        
    def test_cipher_ok(self):
        self.args = self.args + ['-cipher', 'EXP-RC4-MD5']
        pid = self.start_server(self.args)
        ctx = SSL.Context()
        s = SSL.Connection(ctx)
        s.set_cipher_list('EXP-RC4-MD5')
        s.connect(self.srv_addr)
        data = self.http_get(s)
        s.close()
        self.stop_server(pid)
        self.failIf(string.find(data, 's_server -quiet -www') == -1)


def suite():
    return unittest.makeSuite(SSLClientTestCase)
    

def zap_servers():
    s = 's_server'
    fn = tempfile.mktemp() 
    cmd = 'ps | egrep %s > %s' % (s, fn)
    os.system(cmd)
    f = open(fn)
    while 1:
        ps = f.readline()
        if not ps:
            break
        chunk = string.split(ps)
        pid, cmd = chunk[0], chunk[4]
        if cmd == s:
            os.kill(int(pid), 1)
    f.close()
    os.unlink(fn)


if __name__ == '__main__':
    try:
        Rand.load_file('../randpool.dat', -1) 
        unittest.TextTestRunner().run(suite())
        Rand.save_file('../randpool.dat')
    finally:
        zap_servers()


"""
Client tests:
- server -verify
- server -Verify
- server -nbio
- server -nbio_test
- server -nocert
+ simple server test
+ server -cipher
+ server -tls1
+ server -no_tls1

Server tests:
- ???

Others:
- ssl_dispatcher
- SSLServer
- ForkingSSLServer
- ThreadingSSLServer
"""
