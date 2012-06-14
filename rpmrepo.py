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
# Classes for dealing with RPM repositories (binary and source)
#

from __future__ import print_function
import gzip, os, sys, xml.parsers.expat
import customization, genutil

number_connections = 4
packagelist = []
packageattr = ['rpm:requires', 'rpm:provides', 'rpm:conflicts',
      'rpm:recommends', 'rpm:suggests', 'rpm:supplements', 'rpm:obsoletes', 'rpm:enhances']
packagecattr = ['name', 'arch', 'rpm:sourcerpm', 'checksum']
ignorenames = ['version', 'checksum', 'summary', 'description', 'packager', 'url', 'time', 'format', \
               'rpm:license', 'rpm:vendor', 'rpm:group', 'rpm:buildhost', \
               'rpm:header-range', 'rpm:sourcerpm', 'file', 'metadata', 'name', 'arch']
repomap = []
verbose = 0

########################## RPM Repo info #################################
def translate_reponame(obsname):
    for item in customization.packagecross:
        #print('translate_reponame:', obsname, item[0])
        if item[0] == obsname:
            return item[1]
    print('Error: translate_reponame failed', obsname)
    return None

#
# Class holding all configuration info about an RPM repository (URL, local file directory)
#
def create_repo_info(obsname):
    item = {}
    item['obsname'] = obsname
    item['reponame'] = translate_reponame(obsname)
    return item

#
# Class holding all info about a single RPM package (and points to the repository that contains it)
#
def create_package_info(repo):
    if repo not in repomap:
        repomap.append(repo)
    item = {}
    item['location'] = ''
    packagelist.append(item)
    return packagelist.index(item)

saveddatafilebase = 'sandbox/bbrepo.'
#
# Parse the repomd.xml and the xxx-primary.xml.gz file.
# This builds data structures of all the Provides/Requires/SRPM/RPM info for all packages
# in a single RPM repo.
#
class ParseRepomd:
    def __init__(self, rmap):
        global repomap, packagelist, saveddatafilebase, verbose
        self.namelist = {}
        # Gather info about RPMs for each repo associated with a linked source project
        for self.repo in rmap:
            self.curpack = None
            self.repo['basedir'] = customization.repobasedir + self.repo['reponame'] + '/'
            # First, parse the repomd.xml file to get the filename for xxx-primary.xml.gz
            self.xml = xml.parsers.expat.ParserCreate()
            self.xml.StartElementHandler = self.repomd_xml_start
            rname = self.repo['basedir'] + 'repodata/repomd.xml'
            if not os.path.exists(rname):
                print('Error: missing repodata:', rname)
                genutil.exitprocessing(-501)
            self.xml.Parse(open(rname).read())
        localfile = translate_reponame('localrpm') + '/'
        if os.path.exists(localfile + 'repodata/repomd.xml'):
            #print('*************** loading local rpm repo')
            self.curpack = None 
            self.repo = create_repo_info('localrpm')
            self.repo['basedir'] = localfile
            # First, parse the repomd.xml file to get the filename for xxx-primary.xml.gz
            self.xml = xml.parsers.expat.ParserCreate()
            self.xml.StartElementHandler = self.repomd_xml_start
            self.xml.Parse(open(self.repo['basedir'] + 'repodata/repomd.xml').read())
    def repomd_xml_start(self, name, attrs):
        if verbose > 0:
            print('Start repomd:', name, attrs)
        if name == 'data':
            self.repomdtype = attrs.get('type').encode('latin-1')
        elif name == 'location' and self.repomdtype == 'primary':
            # parse the xxx-primary.xml.gz file
            self.primaryxml = xml.parsers.expat.ParserCreate()
            self.primaryxml.StartElementHandler = self.primary_xml_start
            self.primaryxml.EndElementHandler = self.primary_xml_end
            self.primaryxml.CharacterDataHandler = self.xml_charhandler
            rname = self.repo['basedir'] + attrs.get('href').encode('latin-1')
            if not os.path.exists(rname):
                print('Error: missing repodata:', rname)
                genutil.exitprocessing(-501)
            fh = gzip.open(rname)
            self.primaryxml.Parse(fh.read())
            fh.close()
    def primary_xml_start(self, name, attrs):
        self.chardata = ''
        if verbose > 0:
            print('Start primaryxml:', name, attrs)
        if name == 'package':
            self.entrytype = ''
            self.curpack = create_package_info(self.repo)
        elif name == 'size' or name == 'location':
            pass
        elif name != 'rpm:entry':
            self.entrytype = name;
            if name not in ignorenames and name not in packageattr:
                if verbose > 0:
                    print('Start primaryxml:', name, attrs)
                pass
        elif self.entrytype in ['rpm:requires', 'rpm:provides']:
            ename = attrs.get('name').encode('latin-1')
            if packagelist[self.curpack].get(self.entrytype) is None:
                packagelist[self.curpack][self.entrytype] = []
            packagelist[self.curpack][self.entrytype].append(ename)
            if self.entrytype == 'rpm:requires':
                self.add_to_name(ename, True)
            elif self.entrytype == 'rpm:provides':
                self.add_to_name(ename, False)
        elif self.entrytype in packageattr:
            pass
        else:
            print('Start entry:', self.entrytype, attrs)
        # optimize xml character processing (this cuts XML parse time in 1/2)
        if name == 'file' or name in packagecattr or name == 'package':
            self.primaryxml.CharacterDataHandler = self.xml_charhandler
        else:
            self.primaryxml.CharacterDataHandler = None
    def xml_charhandler(self, data):
        self.chardata += data.encode('latin-1')
    def primary_xml_end(self, name):
        if verbose > 0:
            print('Pend ', name, ':', self.chardata)
        if name == 'file':
            self.add_to_name(self.chardata, False)
        elif name in packagecattr:
            packagelist[self.curpack][name] = self.chardata
        elif name == 'package':
            self.curpack = None
    def add_to_name(self, name, argrequires):
        # Class holding all provides/requires lists (for all repos)
        colonindex = name.find(':')
        if colonindex > 0:
            name = name[colonindex+1:]
        if not self.namelist.has_key(name):
            self.namelist[name] = {}
            self.namelist[name]['requires'] = []
            self.namelist[name]['provides'] = []
        if argrequires:
            self.namelist[name]['requires'].append(self.curpack)
        else:
            self.namelist[name]['provides'].append(self.curpack)
