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
import os, xml.parsers.expat
import customization, genutil, rpmrepo

class ParsePackage:
    def __init__(self, filename):
        self.filelist = []
        self.package_md5 = ''
        x = xml.parsers.expat.ParserCreate()
        x.StartElementHandler = self.start_element_package
        try:
            fh = open(filename)
            x.Parse(fh.read())
            fh.close()
        except IOError:
            pass
    def start_element_package(self, name, attrs):
        objdir = 'objects'
        pname=None
        pmd5=None
        psize=None
        bindir = '/'
        #print("ParsePackage: name ", name, "attr ", attrs)
        if name == 'entry':
            pname = attrs.get('name') #.encode('latin-1')
            pmd5 = attrs.get('md5') #.encode('latin-1')
            psize = attrs.get('size') #.encode('latin-1')
            if pname != None and pmd5 != None and psize != None:
                #pname = pname.decode()
                #pmd5 = str(pmd5, encoding='latin-1')
                #psize = str(psize, encoding='latin-1')
                if pname.endswith('.tar.gz') or pname.endswith('.tar.bz2') or \
                   pname.endswith('.tgz') or pname.endswith('.zip') or \
                   pname.endswith('.xz') or pname.endswith('.jar'):
                    bindir = 'b/'
                self.filelist.append((pname + ' ' + psize + ' ' + objdir + bindir + pmd5[:2] + '/' + pmd5[2:] + ' ' + pmd5))
        elif name == 'directory':
            for attrName in attrs.keys():
                if attrName == 'srcmd5':
                    self.package_md5 = attrs.get('srcmd5') #.encode('latin-1')
        elif name == 'serviceinfo':
            for attrName in attrs.keys():
                if attrName == 'xsrcmd5':
                    self.package_md5 = attrs.get('xsrcmd5') #.encode('latin-1')

#
# Class for parsing _meta file for a package
#
class ParsePackageMeta:
    def __init__(self, filename):
        self.filepresent = False
        self.showvalue = False
        self.next = None
        self.disable_list = []
        x = xml.parsers.expat.ParserCreate()
        x.StartElementHandler = self.start_element
        if os.path.exists(filename):
            self.filepresent = True
            fh = open(filename)
            x.Parse(fh.read())
            fh.close()
    def start_element(self, name, attrs):
        #print('start', name, attrs)
        if name == 'disable':
            self.disable_list.append(attrs.get('arch'))
    def disabled(self, archname):
        return self.filepresent and archname in self.disable_list

class ParsePackageLink:
    def __init__(self, filename, aproject):
        #print("ParsePackageLink", filename)
        self.buildproject = aproject
        self.buildpackagename = None
        x = xml.parsers.expat.ParserCreate()
        x.StartElementHandler = self.start_element
        if os.path.exists(filename):
            fh = open(filename)
            x.Parse(fh.read())
            fh.close()
    def start_element(self, name, attrs):
        #print('start', name, attrs)
        if name == 'link':
            self.buildpackagename = attrs.get('package')
            #print('ParsePackageLink new:', self.buildpackagename)
    def linkproject(self):
        return self.buildproject, self.buildpackagename

class ParseProject:
    def __init__(self, projname):
        self.xml = xml.parsers.expat.ParserCreate()
        self.xml.StartElementHandler = self.start_element_project
        #self.xml.EndElementHandler = self.end_element
        #self.xml.CharacterDataHandler = self.char_data
        self.project = projname
        self.updatelist = []
        self.allpackages = []
    def process(self, data):
        try:
            self.xml.Parse(data)
        except xml.parsers.expat.ExpatError:
            print('XML Parse failure for', self.project)
            print(data)
    def start_element_project(self, name, attrs):
        pname = None
        pmd5 = None
        #print('Start project:', name, attrs)
        for attrName in attrs.keys():
            if attrName == 'srcmd5' and pmd5 is None:
                pmd5 = attrs.get('srcmd5') #.encode('latin-1')
            elif attrName == 'lsrcmd5':
                pmd5 = attrs.get('lsrcmd5') #.encode('latin-1')
            elif attrName == 'name':
                pname = attrs.get('name').encode('latin-1')
            elif attrName == 'package':
                pname = attrs.get('package') #.encode('latin-1')
        if pname is not None and pmd5 is not None:
            filename = self.project + '/' + pname + '._manifest'
            self.allpackages.append(pname)
            if os.path.exists(filename) and pmd5 != ParsePackage(filename).package_md5:
                print('removing packageinfo', filename, pmd5)
                os.remove(filename)
            if not os.path.exists(filename):
                self.updatelist.append(pname)

#
# Class for parsing _meta file for the project
#
class ParseProjectMeta:
    def __init__(self, filename):
        self.showvalue = False
        self.content = ''
        self.nextproject = None
        x = xml.parsers.expat.ParserCreate()
        x.StartElementHandler = self.start_element
        fh = open(filename)
        x.Parse(fh.read())
        fh.close()
    def start_element(self, name, attrs):
        #print('start', name, attrs)
        project = attrs.get('project')
        if name == 'path' \
          and (attrs.get('repository') == 'standard' or attrs.get('repository') == 'openSUSE_12.1') \
          and project is not None:
            self.nextproject = project
        self.content = ''

######################### Source Project Info ###############################
#
# Parse the prjconf file, stepping back through all linked projects
#
class ParseConfig:
    configwords = ['Ignore', 'ExportFilter', 'Keep', 'Runscripts', 'Prefer',
        'Support', 'Preinstall', 'Patterntype', 'Release', 'Required']
    configdoublewords = ['ExportFilter', 'Substitute']
    def __init__(self, averbose, abuildproject):
        global verbose
        verbose = averbose
        self.repository_map = []
        self.macrodefs = []
        self.fconfig = []
        self.configlists = {}
        # First, construct a list of all linked projects into repository_map[]
        projectname = abuildproject
        while projectname is not None and os.path.exists(customization.buildbase + projectname + '/_meta'):
            if verbose > 1:
                print('ParseConfig: append', projectname)
            self.repository_map.append(rpmrepo.create_repo_info(projectname))
            projectname = ParseProjectMeta(customization.buildbase + projectname + '/_meta').nextproject
        self.repository_map.reverse()
        # Now, go through repository_map[], concatenating the RPM configuration data and RPM macro data
        # into fconfig[] and macrodefs[], respectively
        for curproject in self.repository_map:
            filename = customization.buildbase + curproject['obsname'] + '/_config'
            #print('item', curproject.repo['reponame'], 'filename', filename)
            if os.path.exists(filename):
                fh = open(filename)
                parsemacro = False
                for line in fh:
                    line = line.strip()
                    if line.startswith('Macros:'):
                        parsemacro = True
                    elif parsemacro:
                        self.macrodefs.append(line)
                    else:
                        self.fconfig.append(line)
                fh.close()
    def process_config(self, inpline):
        colonindex = inpline.find(':')
        if colonindex > 0 and inpline[:colonindex] in self.configdoublewords:
            inplist = inpline[colonindex+1:].split()
            self.configlists[inpline[:colonindex]].append(inplist)
        elif colonindex > 0 and inpline[:colonindex] in self.configwords:
            inplist = inpline[colonindex+1:].split()
            for item in inplist:
                if item == '!*':
                    self.configlists[inpline[:colonindex]] = []
                elif item[0] == '!':
                    self.configlists[inpline[:colonindex]].delete(item[1:])
                else:
                    self.configlists[inpline[:colonindex]].append(item)
        elif len(inpline) != 0:
            print('line', inpline)
    def prepare_prjconf_info(self, atarget_arch, aarch):
        for inpline in self.configwords + self.configdoublewords:
            self.configlists[inpline] = []
        genutil.eval_config(self.fconfig, atarget_arch, aarch, self.process_config)
