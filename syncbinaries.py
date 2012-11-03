#!/usr/bin/env python
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

import HTMLParser, os, sys, urllib2, subprocess
#import gitclone

class MyHTMLParser(HTMLParser.HTMLParser):
    global fn
    def handle_starttag(self, tag, aattrs):
        #print "Encountered a start tag:", tag, aattrs
        attrs = dict(aattrs)
        p = attrs.get('href')
        if tag == 'a' and p is not None and p.startswith('http') and p.endswith('tgz'):
            #print "File:", tag, aattrs
            fn.write('wget -N ' + p + '\n')
    def handle_endtag(self, tag):
        pass
        #print "Encountered an end tag :", tag
    def handle_data(self, data):
        pass
        #print "Encountered some data  :", data

if len(sys.argv) != 2:
    print('getfiles.py <httpurlname>')
    sys.exit(1)
tempfilename = 'xx.sitecopy.tempfile'
fn = open(tempfilename, 'w')
in_repository = False
MyHTMLParser().feed(urllib2.urlopen(sys.argv[1]).read())
fn.close()
subprocess.call('sh -x ' + tempfilename, shell=True)
#os.remove(tempfilename)
