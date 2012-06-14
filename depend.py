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
# Classes for running rpmbuild on each spec file in a source code directory.
# In addition, _service files are processed.
#

from __future__ import print_function
import datetime, errno, glob, json, os, re, select, signal, shutil, string, subprocess, sys, time
import customization, genutil, ParseOBS, ParseService

#
######## main #########
#
class ParseSpecs:
    def __init__(self, verbose, rootdir, archtype, abuildproject, aargv):
        sdir = rootdir + '/SOURCES/'
        archivedir = rootdir + 'specdata'
        print('adir', archivedir)
        self.namelist = {}
        if os.path.exists(archivedir):
            fh = open(archivedir, 'r')
            self.namelist = json.load(fh)
            fh.close()
            return
        itemlist = aargv
        if itemlist == []:
            for sfile in glob.glob(customization.buildbase + abuildproject + '/*._manifest'):
                itemlist.append(os.path.basename(sfile)[:-10])
        for buildpackagename in itemlist:
            buildproject = abuildproject
            genutil.runcall('rm -rf ' + sdir, '.')
            genutil.chroot_makedirs(sdir)
            print('package', buildpackagename)
            tempname = buildpackagename
            while True:
                masterfh = ParseOBS.ParsePackage(customization.buildbase + buildproject + '/' + tempname + '._manifest').filelist
                for masterline in masterfh:
                    filename, filesize, objectfile, checksum = masterline.split()
                    genutil.runcall('ln -s ' + customization.buildbase + '../' + objectfile + ' ' + sdir + filename, '.')
                buildproject, tempname = ParseOBS.ParsePackageLink(sdir + '_link', buildproject).linkproject()
                if tempname is None:
                    break
                genutil.runcall('rm ' + sdir + '/*', '.')
            if os.path.islink(sdir + '_service'):
                if self.namelist.get(buildpackagename) is not None and self.namelist[buildpackagename]['hash'] == os.readlink(sdir + '_service'):
                    #print("found match", buildpackagename)
                    continue
            #
            # Process _service files
            #
            if ParseService.ParseService(verbose, sdir + '_service', False).process(sdir, None, None) != 0:
                continue
            for singlefile in glob.glob(sdir + '*.spec'):
                hash = ''
                if os.path.islink(singlefile):
                    hash = os.readlink(singlefile)
                elif os.path.islink(sdir + '_service'):
                    hash = os.readlink(sdir + '_service')
                if self.namelist.get(buildpackagename) is not None and self.namelist[buildpackagename]['hash'] == hash:
                    #print("found match", buildpackagename)
                    continue
                #
                # clean %changelog entries from spec file
                #
                data = open(singlefile).readlines()
                pchange = False
                fh = open(singlefile, 'w')
                for item in data:
                    if pchange and re.match(r'\s*%[^%]', item) is not None:
                       pchange = False
                    if re.match(r'\s*%changelog', item) is not None:
                        pchange = True
                    if not pchange and not item.startswith('Recommends:') and not item.startswith('Suggests:') \
                        and not item.startswith('Enhances:') and not item.startswith('Supplements') \
                        and not item.startswith('BuildRecommends:') and not item.startswith('BuildSuggests:') \
                        and not item.startswith('BuildEnhances:') and not item.startswith('BuildSupplements'):
                        fh.write(item)
                fh.close()
                #
                # Extract BuildRequires from spec file
                #
                sreq = genutil.spec_requires(verbose, singlefile, archtype, rootdir + '/', \
                        '--rcfile=' + customization.scriptdir + '/rpm-rpmspec.rpmrc')
                if self.namelist.get(buildpackagename) is None:
                    self.namelist[buildpackagename] = {}
                self.namelist[buildpackagename]['requires'] = sreq
                self.namelist[buildpackagename]['hash'] = hash
                #print('hash', hash, 'sreq', sreq)
            genutil.runcall('rm -rf ' + sdir, '.')
        fh = open(archivedir, 'w')
        json.dump(self.namelist, fh)
        fh.close()
def depend_list(verbose, rootdir, archtype, abuildproject, aargv):
    s = ParseSpecs(verbose, rootdir, archtype, abuildproject, aargv)
    for key, val in s.namelist.iteritems():
        foo = []
        for item in val['requires']:
            if item not in ['gdb', 'gcc-c++', 'cmake', 'bison', 'texinfo', 'python', 'pkgconfig', 'doxygen', 'automake', 'autoconf', 'libtool',\
                  'libqt5base-devel-tools', 'bash', 'glibc-static', 'fdupes', 'gcc', 'libxml2-python', 'flex', \
                  'rpm', 'byacc', 'sed', 'p7zip', 'patchelf', 'qt5tools' ]:
                foo.append(item)
        if foo != []:
            print('item', key, foo)
        #else:
        #    print('item', key)

if __name__ == '__main__':
    sys.exit(depend_list(0, 'sandbox/ssspecs', 'armv7hl', 'MT', sys.argv[1:]))
