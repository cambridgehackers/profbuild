#! /usr/bin/env python
# Copyright (c) 2012 Nokia Corporation
# Original author John Ankcorn
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

#
# Class for managing parallel download of files over http/https using mCurl.
# In particular, supports checking of sha256 and conditionally downloading in
# case of a mismatch.
#

from __future__ import print_function
import errno, os, pycurl, hashlib, signal, sys, time
import customization, genutil, rpmrepo

number_connections = 4

#
# Class for checking sha256 for repo files and downloading where necessary (in parallel).
# There is nothing specific about RPM files; any file with a sha256 hash can be checked/downloaded.
#
class RepoDownload:
    def __init__(self, averbose, alockfilename, aurlbase):
        self.verbose = averbose
        self.urlbase = aurlbase
        self.repobasedir = ''
        if self.urlbase == '':
            self.repobasedir = customization.repobasedir
        self.lockfn = genutil.LockHandler(alockfilename)
        self.queue = []
    # Check the sha256 for a downloaded file, adding it to queue[] where necessary
    def check_file(self, arglist, cb_function):
        #print('check_file', arglist)
        for argpack in arglist:
            repoitemname = ''
            if argpack['repo'] is not None:
                repoitem = rpmrepo.repomap[argpack['repo']]
                repoitemname = repoitem['reponame']
            thisname = repoitemname + '/' + argpack['location']
            if self.verbose > 4:
                print('checkfile: ', argpack['location'], 'checksum', argpack['checksum'], 'cb_function', cb_function)
            tname = thisname
            if tname[0] != '/':
                tname = self.repobasedir + thisname
            try:
                fh = open(tname, 'rb')
                if argpack['url'] is None:
                    m = hashlib.sha256()
                else:
                    m = hashlib.md5()
                while 1:
                    data = fh.read(8192)
                    if not data:
                        break
                    m.update(data)
                fh.close()
                actualmd5 = m.hexdigest()
                #print(tname, argpack['checksum'], actualmd5)
                if argpack['checksum'] == actualmd5:
                    if cb_function is not None:
                        print('parse!!', tname)
                        cb_function(argpack['location'])
                    continue
            except IOError as errno:
                thisdir = os.path.dirname(tname)
                genutil.chroot_makedirs(thisdir)
            if self.verbose > 0:
                print('eappend', thisname, 'cb_function', cb_function)
            if argpack['url'] is None:
                self.queue.append((self.ZypperMap(repoitemname) + argpack['location'], repoitemname + '/' + argpack['location'], cb_function))
            else:
                self.queue.append((argpack['url'], repoitemname + '/' + argpack['location'], cb_function))
    def ZypperMap(self, reponame):
        fh = open(customization.zypper_info_dir + os.path.basename(reponame) + '.repo')
        for inpline in fh:
            if inpline.startswith('baseurl='):
                return inpline[8:].strip() + '/'
        fh.close()
        return None
    def loadfile(self, url, filename, cb_function):
        #print('loadfile', url, filename)
        genutil.chroot_makedirs(os.path.dirname(filename))
        self.queue.append((self.urlbase + url, filename, cb_function))
    # Start downloading next file (multiple files are downloaded at the same time)
    def makenew(self):
        c = self.freelist.pop()
        c.url, thislocation, c.cb_function = self.queue.pop(0)
        c.filename = self.repobasedir + thislocation
        if self.verbose > 0:
            print('starting', c.url, c.filename)
        c.f = open(c.filename, 'wb')
        c.setopt(c.URL, c.url.encode('latin-1'))
        #c.setopt(c.VERBOSE, 1)
        c.setopt(c.SSL_VERIFYPEER, 0)
        c.setopt(c.SSL_VERIFYHOST, 0)
        #c.setopt(c.ISSUERCERT, 'mobs-repo.europe.nokia.com.pem.cer')
        c.setopt(c.WRITEFUNCTION, c.f.write)
        c.setopt(c.NETRC, c.NETRC_OPTIONAL)
        self.curlm.add_handle(c)
    # Loop processing all file download requests from queueu[]
    def process(self):
        self.curlm = pycurl.CurlMulti()
        self.curlm.handles = []
        for i in range(number_connections):
            self.curlm.handles.append(pycurl.Curl())
        self.freelist = self.curlm.handles[:]
        if self.verbose > 0:
            print("selfq", self.queue)
            print("RepoDownload: queue", [location for repo, location, cbfunc in self.queue])

        self.lockfn.lock_wait('')
        signal.signal(signal.SIGINT, self.lockfn.lock_clear_null)
        in_process = 0
        while len(self.queue) or in_process > 0:
            while self.queue and self.freelist:
                self.makenew()
                in_process = in_process + 1
            while 1:
                ret, num_handles = self.curlm.perform()
                if ret != pycurl.E_CALL_MULTI_PERFORM: break
            while num_handles:
                ret = self.curlm.select(1.0)
                if ret == -1:  continue
                while 1:
                    ret, num_handles = self.curlm.perform()
                    #print("return ", ret, "handl ", num_handles)
                    num_q, ok_list, err_list = self.curlm.info_read()
                    #print("num_q ", num_q, "ok", ok_list, "err", err_list)
                    for curlmsg in ok_list:
                        retcode = curlmsg.getinfo(pycurl.HTTP_CODE)
                        #print("curl ", curlmsg, "done ", retcode)
                        curlmsg.f.close()
                        self.curlm.remove_handle(curlmsg)
                        #print("ending", curlmsg.url, curlmsg.filename)
                        if int(retcode) == 200 and curlmsg.cb_function is not None:
                            curlmsg.cb_function(curlmsg)
                        elif int(retcode) != 200 and os.path.exists(curlmsg.filename):
                            print('***** download failed: Code', retcode, 'Url', curlmsg.url)
                            print(open(curlmsg.filename).read())
                            os.remove(curlmsg.filename)
                            if int(retcode) != 404:
                                genutil.exitprocessing(-70)
                        self.freelist.append(curlmsg)
                    for curlmsg, errno, errmsg in err_list:
                        retcode = curlmsg.getinfo(pycurl.HTTP_CODE)
                        #print("errcurl ", curlmsg, "errerrno ", errno, "errerrmsg ", errmsg)
                        print('Error in download: errno ', errno, 'Code', retcode, curlmsg.getinfo(pycurl.EFFECTIVE_URL), errmsg)
                        curlmsg.f.close()
                        self.curlm.remove_handle(curlmsg)
                        self.freelist.append(curlmsg)
                        genutil.exitprocessing(-72)
                    in_process = in_process - len(ok_list) - len(err_list)
                    if num_q == 0:
                        break
                    if ret != pycurl.E_CALL_MULTI_PERFORM:
                        break
            self.curlm.select(1.0)
        self.lockfn.lock_clear('')
