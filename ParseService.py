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

from __future__ import print_function
import json, glob, os, re, shutil, sys, string, subprocess, time, threading, xml.parsers.expat
import customization, genutil, ParseOBS, ParseService
from git.git_command import GitCommand
from git.error import GitError

MAX_THREAD_LIMIT = 40
FINISH_DELAY_TIME = 20
queue = []
verbose = 0
def process_tar(outfile, aurldirectory, atargetdir, asubdir, arevision, aservice, scm_origin_data, alocal):
    #print('outf', outfile, 'dir', aurldirectory)
    scm_filename = outfile + '/scm_origin'
    tscm_filename = atargetdir + scm_filename
    genutil.chroot_makedirs(os.path.dirname(tscm_filename))
    open(tscm_filename, 'w').write(scm_origin_data)
    print('process_tar: local', alocal, outfile, aurldirectory, atargetdir, asubdir, arevision, aservice)
    if alocal:
        aurldirectory = 'local/' + outfile
    else:
        try:
            if not run_git(['checkout', '--quiet', '--force', arevision], aurldirectory):
                return -3
        except GitError:
            print('Repository not found: git', aurldirectory, ' *********************************')
            return -4
    tarfile = atargetdir + '_service:' + aservice + ':' + outfile + '.tar '
    runcall('tar cf ' + tarfile + '--exclude=.git --transform "s,^' + asubdir + '\/,' + outfile + '/," ' + asubdir, aurldirectory)
    runcall('tar uf ' + tarfile + scm_filename, atargetdir)
    os.remove(tscm_filename)
    return 0
def process_fetch(aurldirectory, selfurl):
    global trace_only
    rfdir = aurldirectory
    if not os.path.exists(rfdir):
        rfdir = os.path.dirname(rfdir)
        print('Clone repo ', selfurl, 'into', rfdir)
        genutil.chroot_makedirs(rfdir)
        cmd = ['clone', selfurl]
    else:
        print('Fetch repo ', aurldirectory)
        cmd = ['fetch'];
    if trace_only:
        print('cmd', cmd)
    elif run_git(cmd, rfdir):
        run_git(['submodule', 'init'], aurldirectory)
        run_git(['submodule', 'sync'], aurldirectory)
        run_git(['submodule', 'update'], aurldirectory)
def runcall(command, dirname):
    if verbose > 0:
        print('run command', command)
    subprocess.call(command, shell=True, cwd=dirname, stdout=sys.stdout, stderr=sys.stdout)
def run_git(acommand, adir):
    if GitCommand(None, acommand, cwd=adir).Wait() != 0:
        print('gitcommand error: failed ', acommand, ' ***************************************')
        return False
    return True

class ServiceItem:
    def __init__(self):
        self.service = ''
        self.data = {}
        self.data['archive'] = ''
        self.data['compression'] = ''
        self.data['revision'] = ''
        self.data['files'] = []
        self.data['subdir'] = '.'
        self.data['url'] = ''
        self.param = ' --outdir ./tmp'
        self.next = None
class ParseService:
    def __init__(self, averbose, afilename, alocal):
        verbose = averbose
        self.verbose = averbose
        self.filename = afilename
        self.local = alocal
        self.showvalue = False
        self.content = ''
        self.name = ''
        self.servicelist = None
        self.curitem = None
        self.scmversion = '0'
        self.return_code = 0
        if os.path.exists(self.filename):
            x = xml.parsers.expat.ParserCreate()
            x.StartElementHandler = self.start_element
            x.EndElementHandler = self.end_element
            x.CharacterDataHandler = self.char_data
            fh = open(self.filename)
            x.Parse(fh.read())
            fh.close()
    def start_element(self, name, attrs):
        if self.verbose > 3:
            print('start', name, attrs)
        self.content = ''
        if name == 'service':
            temp = ServiceItem()
            if self.servicelist is None:
                self.servicelist = temp
            else:
                self.curitem.next = temp
            self.curitem = temp
            self.curitem.service = attrs.get('name')
            if self.curitem.service in ['tar_scm', 'mt_tar_scm']:
                self.scmversion = '0'
        else:
            self.name = attrs.get('name')
            if name == 'param' and self.name == 'url':
                self.showvalue = True
    def end_element(self, name):
        if self.name is not None and self.name != '':
            if self.curitem.service == 'extract_file' and self.name == 'files':
                self.curitem.data['files'].append(self.content)
            elif self.curitem.service in ['extract_file', 'recompress']:
                self.curitem.data[self.name] = self.content
            elif self.curitem.service == 'mt_relicense_qt':
                self.curitem.param =  ' --' + self.name + ' ' + self.content + self.curitem.param
            elif self.curitem.service in ['tar_scm', 'mt_tar_scm']:
                if self.name == 'version':
                    self.scmversion = self.content
                    if self.curitem.service == 'tar_scm':
                        self.curitem.data['tar_scm'] = self.content
                    #print('scmversion', self.scmversion, 'tar_scm_version', self.curitem.data.get('tar_scm'))
                elif self.name in ['filename', 'subdir', 'revision']:
                    self.curitem.data[self.name] = self.content
        elif name == 'service' and self.curitem.service:
            if self.verbose > 3:
                print('end', self.curitem.service)
        if self.showvalue:
            self.content = self.content.strip()
            self.curitem.data['url'] = self.content.replace('scmc.source.nokia.com', 'source.nokia.com')
            self.curitem.data['url'] = self.curitem.data['url'].replace('https://git.gitorious.org/', 'git://git.gitorious.org/')
        self.content = ''
        self.name = ''
        self.showvalue = False
    def char_data(self, chrs):
        self.content = self.content + chrs
    def process(self, atargetdir, repolist, auser_name):
        curitem = self.servicelist
        if auser_name is None:
            if atargetdir[0] != '/':
                atargetdir = os.getcwd() + '/' + atargetdir
        while curitem is not None:
            before, sep, urldirectory = curitem.data['url'].rpartition('//');
            before, sep, urldirectory = urldirectory.rpartition('@');
            urldirectory = urldirectory.replace(':29418/', '/');
            urldirectory = urldirectory.replace(':', '/');
            if urldirectory.endswith('.git'):
                urldirectory = urldirectory[:-4]
            urldirectory = customization.mirrordir + urldirectory
            if self.verbose > 3:
                print('curitem', curitem.service, json.dumps(curitem.data))
                runcall('ls -l *', atargetdir)
            if curitem.service in ['tar_scm', 'mt_tar_scm']:
                outfile = curitem.data.get('filename')
                if self.verbose > 3:
                    print("tar", outfile, 'url', urldirectory)
                if outfile is None:
                    outfile = os.path.basename(urldirectory)
                if curitem.data.get('tar_scm') is not None:
                    outfile = outfile + '-' + curitem.data['tar_scm']
                if auser_name is None:
                    ret = process_tar(outfile, urldirectory, atargetdir, curitem.data['subdir'], curitem.data['revision'], curitem.service, \
                        'Package: ' + os.path.basename(urldirectory) + '\nVersion: ' + self.scmversion \
                      + '\nURL: ' + curitem.data['url'] + '\nCommit: ' + curitem.data['revision'] + '\n', self.local)
                    if ret != 0:
                        self.return_code = ret
                elif curitem.data['url'] is not None and not curitem.data['url'] in repolist:
                    curitem.data['url'] = curitem.data['url'].replace('ssh://obs_user@', 'ssh://' + auser_name + '@')
                    repolist.append(curitem.data['url'])
                    queue.append((urldirectory, curitem.data['url']))
            elif auser_name is not None or self.return_code != 0:
                pass
            elif curitem.service == 'extract_file':
                for efile in curitem.data['files']:
                    runcall('tar -xf ' + atargetdir + curitem.data['archive'] + ' --wildcards  "' + efile + '"', atargetdir)
                    for singlefile in glob.glob(atargetdir + efile):
                        runcall('cp ' + singlefile + ' _service:extract_file:' + os.path.basename(singlefile), atargetdir)
            elif curitem.service == 'recompress':
                if self.verbose > 3:
                    print('compressing', atargetdir + curitem.data['file'], curitem.data['compression'])
                if curitem.data['compression'] == 'bz2':
                    runcall('bzip2 ' + curitem.data['file'], atargetdir)
                elif curitem.data['compression'] == 'gz':
                    runcall('gzip ' + curitem.data['file'], atargetdir)
            elif curitem.service in ['mt_add_metadata', 'mt_pre_checkin', 'mt_relicense_qt']:
                os.mkdir(atargetdir + 'tmp')
                runcall(customization.scriptdir + curitem.service + curitem.param, atargetdir)
                if curitem.service == 'mt_relicense_qt':
                    for singlefile in glob.glob(atargetdir + 'tmp/*'):
                        runcall('mv ' + singlefile + ' _service:' + curitem.service + ':' + os.path.basename(singlefile), atargetdir)
                    if self.verbose > 3:
                        runcall('ls -l *', atargetdir)
                else:
                    runcall('mv tmp/* .', atargetdir)
                os.rmdir(atargetdir + 'tmp')
            elif curitem.service == 'set_version':
                runcall('sed -i.001 -e "s/^Version:.*/Version: ' + self.scmversion + '/" ' + '*.spec', atargetdir)
            curitem = curitem.next
        if atargetdir is not None:
            for singlefile in glob.glob(atargetdir + '_service*:*'):
                if os.path.isfile(singlefile):
                    snew = re.sub(r'_service.*:', '', os.path.basename(singlefile))
                    if self.verbose > 3:
                        print("copying", singlefile, "to", snew)
                    shutil.move(singlefile, atargetdir + snew)
        return self.return_code

def main():
    repolist = []
    for file in glob.glob(customization.sourcerepo + 'repo/*/*._manifest'):
        masterfh = ParseOBS.ParsePackage(file).filelist
        for masterline in masterfh:
            filename, filesize, objectfile, checksum = masterline.split()
            if filename == '_service':
                #print("*********************", os.path.basename(file)[:-10])
                s = ParseService(0, customization.sourcerepo + objectfile, False).process(None, repolist, customization.username)
    runq = []
    while queue != []:
        item = queue.pop()
        t = threading.Thread(target=process_fetch, args=(item[0], item[1],))
        t.start()
        runq.append(t)
        while len(runq) > MAX_THREAD_LIMIT:
            time.sleep(0.5)
            for item in runq:
                if not item.isAlive():
                    item.join()
                    runq.remove(item)
    finishdelay = 0
    while len(runq) > 0:
        for item in runq:
            if item.isAlive():
                if finishdelay > FINISH_DELAY_TIME:
                    for thread in runq:
#threading.enumerate():
                        if thread.isAlive():
                            print('Timeout: killing', thread)
                            try:
                                thread._Thread__stop()
                            except:
                                print(str(thread.getName()) + ' could not be terminated')
            else:
                item.join()
                runq.remove(item)
                finishdelay = 0
        time.sleep(0.5)
        finishdelay += 1

if __name__ == '__main__':
    global trace_only
    trace_only = False
    if len(sys.argv) > 1:
        if sys.argv[1] == '-t':
            trace_only = True
    main()
