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
verbose = 0
def process_fetch(aurldirectory, selfurl, submodule):
    global trace_only
    rfdir = aurldirectory
    if not os.path.exists(rfdir):
        rfdir = os.path.dirname(rfdir)
        print('Clone repo ', selfurl, 'into', rfdir)
        genutil.chroot_makedirs(rfdir)
        cmd = ['clone', '--no-checkout', selfurl]
    else:
        print('Fetch repo ', aurldirectory)
        cmd = ['fetch'];
    if trace_only:
        print('cmd', cmd)
    elif run_git(cmd, rfdir):
        if submodule:
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

def main(atrace, filename, submodule, athread_limit, afinish_delay):
    global trace_only
    trace_only = atrace
    runq = []
    fn = open(filename, 'r')
    for foo in fn:
        item = foo.split(' ')
        #print(item)
        t = threading.Thread(target=process_fetch, args=(item[0], item[1], submodule, ))
        t.start()
        runq.append(t)
        while len(runq) > athread_limit:
            time.sleep(0.5)
            for item in runq:
                if not item.isAlive():
                    item.join()
                    runq.remove(item)
    finishdelay = 0
    while len(runq) > 0:
        for item in runq:
            if item.isAlive():
                if finishdelay > afinish_delay:
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
    atrace = False
    if len(sys.argv) < 2:
        print('gitclone.py [-t] <list_of_repos_and_directories_file>')
        sys.exit(1)
    p = sys.argv[1]
    if len(sys.argv) > 2:
        if sys.argv[1] == '-t':
            atrace = True
            p = sys.argv[2]
    main(atrace, p, True, MAX_THREAD_LIMIT, FINISH_DELAY_TIME)
