#!/usr/bin/python

import HTMLParser, sys, urllib2
import gitclone

class MyHTMLParser(HTMLParser.HTMLParser):
    global fn
    def handle_starttag(self, tag, aattrs):
        #print "Encountered a start tag:", tag, aattrs
        attrs = dict(aattrs)
        p = attrs.get('href')
        if tag == 'a' and p is not None and p.endswith(';a=tree'):
            p = p[p.index('=')+1:p.index(';')]
            #fn.write(p[:p.rindex('/')] + ' ' + sys.argv[2] + '/' + p + '\n')
            fn.write(p + ' ' + sys.argv[2] + '/' + p + '\n')
    def handle_endtag(self, tag):
        pass
        #print "Encountered an end tag :", tag
    def handle_data(self, data):
        pass
        #print "Encountered some data  :", data

if len(sys.argv) != 3:
    print('sitecopy.py <httpurlname> <giturlname>')
    sys.exit(1)
tempfilename = 'xx.sitecopy.tempfile'
fn = open(tempfilename, 'w')
MyHTMLParser().feed(urllib2.urlopen(sys.argv[1]).read())
fn.close()
gitclone.main(False, tempfilename, False)
