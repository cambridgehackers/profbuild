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
# Classes for dealing with source code repositories
#

from __future__ import print_function
import os, shutil, ParseOBS
import rpmrepo

##################### Info for processing of a source package ###########################
#
# Class for all of the 'processing context' when setting up/running rpmbuild
#
class PackageContext:
    def __init__(self, aargv, averbose, ahostarch, aforce):
        self.initok = False
        if len(aargv) != 3:
            print('PackageContext: argument vector too short:', aargv)
            return
        self.rootdir = os.path.dirname(aargv[0])
        self.rpmbuilddir = '/' + os.path.basename(aargv[0])
        self.verbose = averbose
        if self.verbose > 2:
            print('rootdirectory', self.rootdir)
        self.hostarch = ahostarch
        self.archtype = aargv[1]
        self.buildproject = aargv[2]
        self.inprocess = []
        self.pconfig = ParseOBS.ParseConfig(averbose, self.buildproject)
        self.packagecache = rpmrepo.ParseRepomd(self.pconfig.repository_map)
        self.initok = True
