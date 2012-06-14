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
import customization, downloadmanager, glob, os, sys, pycurl, xml.parsers.expat, shutil, ParseOBS

#homeurl = "https://api.opensuse.org"
homeurl = "https://mobs-api.europe.nokia.com"
number_connections = 4
package_attributes = [ ('', '._manifest'), ('/_meta', '._meta'), ('/_attribute', '._attribute')]
project_list = []
total_file_list = []
MAX_FILE_SIZE = 130000000

#class DummyPackageInfo:
#    class DummyProjectInfo:
#        data = {}
#    def __init__(self, aurl, aname, achecksum):
#        self.url = homeurl + aurl
#        self.location = aname
#        self.repo = self.DummyProjectInfo()
#        self.csum = achecksum
#    def checksum(self):
#        return self.csum

def verify_package(filename):
    masterfh = ParseOBS.ParsePackage(filename).filelist
    # basename/repo/projectname/filename
    basename = os.path.dirname(os.path.dirname(os.path.dirname(filename))) + '/'
    packn, fileExtension = os.path.splitext(os.path.basename(filename))
    packname = '/' + os.path.basename(os.path.dirname(filename)) + '/' + packn + '/'
    #print('verify_package', filename, basename, masterfh, "manifest", filename, packname, packn)
    for masterline in masterfh:
        itemname, filesize, itemobjname, checksum = masterline.split()
        #print("pack", itemname, "size", filesize, "new", itemobjname)
        if int(filesize) > MAX_FILE_SIZE:
            print("Warning: longfile, don't download:", itemname, "size", filesize, "new", itemobjname)
            continue
        thispack = {}
        thispack['url'] = homeurl + '/source' + packname + itemname
        thispack['location'] = basename + itemobjname
        thispack['repo'] = None
        thispack['checksum'] = checksum
        #([DummyPackageInfo('/source' + packname + itemname, basename + itemobjname, checksum)], None)
        downmgr.check_file([thispack], None)
        total_file_list.append(basename + itemobjname)

def process_file(msg):
    #print('filename', msg.filename)
    total_file_list.append(msg.filename)
    fh = open(msg.filename)
    data = fh.read()
    fh.close()
    if msg.filename.endswith('_pattern') and data == '<directory name="_pattern" rev="pattern" srcmd5="pattern">\n</directory>\n':
        data = ''
    if msg.filename.endswith('_pubkey') and data.startswith('<status code="404">'):
        data = ''
    if msg.filename.endswith('_attribute') and data == '<attributes>\n</attributes>\n':
        data = ''
    if msg.filename.endswith('_meta') and data.endswith('">\n  <title></title>\n  <description>\n\n  </description>\n</package>\n'):
        data = ''
    if len(data) == 0:
        os.remove(msg.filename)
    elif msg.filename.endswith('/_packagelist'):
        projectname2 = os.path.dirname(msg.filename)
        proj = ParseOBS.ParseProject(projectname2)
        proj.process(data)
        packagelist = proj.allpackages
        for pname in packagelist:
            verify_package(projectname2 + '/' + pname + '._manifest')
            for url, file in package_attributes:
                total_file_list.append(projectname2 + '/' + pname + file)
        packagelist = proj.updatelist
        print("parseproject", projectname2, packagelist)
        for pname in packagelist:
            for url, file in package_attributes:
                 downmgr.loadfile('/source/' + os.path.basename(projectname2) + '/' + pname + url, projectname2 + '/' + pname + file, process_file)
    elif msg.filename.endswith('/_source'):
        parse_source_list(os.path.dirname(msg.filename), data)
    elif msg.filename.endswith('/_request'):
        parse_request(os.path.dirname(msg.filename), data)
    elif msg.filename.endswith('._manifest'):
        verify_package(msg.filename)

def parse_source_list(dirname, data):
    global project_list
    def source_start_element(name, attrs):
        for attrName in attrs.keys():
            if attrName == 'name':
                name = attrs.get('name').encode('latin-1')
                runproj = True
                for bname in customization.blacklist:
                    if name.startswith(bname):
                        runproj = False
                        break
                if runproj:
                    project_list.append(name)
    print('parse_source_list', dirname)
    xparser = xml.parsers.expat.ParserCreate()
    xparser.StartElementHandler = source_start_element
    xparser.Parse(data)
    for name in project_list:
        #print('project:', name)
        dname = dirname + '/' + name
        if not os.path.exists(dname):
            print('making projectdir', name)
            os.mkdir(dname)
        for url, file in [('?view=info', '/_packagelist'), ('/_config', '/_config'),
            ('/_meta', '/_meta'), ('/_pattern', '/_pattern'), ('/_pubkey', '/_pubkey')]:
            downmgr.loadfile('/source/' + name + url, dname + file, process_file)

def parse_request(dirname, data):
    def request_start_element(name, attrs):
        #print('req', name, attrs)
        if name == 'entry':
            reqnum = attrs.get('name').encode('latin-1')
            total_file_list.append(dirname + '/_requests/' + reqnum)
            if not os.path.exists(dirname + '/_requests/' + reqnum):
                downmgr.loadfile('/request/' + reqnum, dirname + '/_requests/' + reqnum, process_file)
    xparser = xml.parsers.expat.ParserCreate()
    xparser.StartElementHandler = request_start_element
    xparser.Parse(data)

###### main ######

def main(dirname):
    global downmgr
    if os.path.exists('./bb.lockfile'):
        os.remove('./bb.lockfile')
    downmgr = downloadmanager.RepoDownload(1, './bb.lockfile', homeurl)
    downmgr.loadfile('/source', dirname + '/_source', process_file)
    if not os.path.exists(dirname + '/_requests'):
        os.makedirs(dirname + '/_requests')
    downmgr.loadfile('/request', dirname + '/_request', process_file)
    downmgr.process()
    for projectname in os.listdir(dirname):
        if not projectname in project_list:
            if projectname not in ['_source', '_request', '_requests']:
                print('removetree', dirname + '/' + projectname)
                shutil.rmtree(dirname + '/' + projectname)
    for singlefile in glob.glob(dirname + '/*/*'):
        if singlefile not in total_file_list:
            print('removefile', singlefile)
            os.remove(singlefile)
    for singlefile in glob.glob(os.path.dirname(dirname) + '/objects*/*/*'):
        if singlefile not in total_file_list:
            print('remove objectfile', singlefile)
            os.remove(singlefile)

if __name__ == '__main__':
    main(os.path.expanduser('~/mirror/mobs/repo'))

