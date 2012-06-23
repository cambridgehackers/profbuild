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
# General utilities used.
#

from __future__ import print_function
import datetime, errno, glob, gzip, os, shutil, stat, string, subprocess, sys, time, tokenize
#from cStringIO import StringIO
from io import StringIO
import customization
maxlocktimeout = 500
startname = ''
starttime = datetime.datetime.utcnow()
lockfiles_used = []

def rpmmacros():
    retval = '--macros=' + customization.scriptdir + 'macros'
    retval += ':' + customization.scriptdir + 'suse_macros'
    return retval

def get_output(acommand):
    p = subprocess.Popen(acommand, shell=False, stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    pstdout, pstderr = p.communicate()
    for inp in pstderr.split('\n'):
        if inp != '':
             print('Error: stderr from ', acommand, ':', inp)
    ret = p.returncode
    if ret != 0:
        print('Error: bad returncode', ret, 'from', acommand)
        exitprocessing(-44)
    return pstdout

#
# Simple RPM macro expression evaluator used for parsing prjconf files
#
def rpm_macro_eval(inputline, archname, atarget_arch):
    verbose = 0
    parg = ['rpm', rpmmacros()]
    if atarget_arch is not None:
        parg.append('--define=targ_arch ' + atarget_arch)
    parg.append('--eval=' + inputline)
    retval = unicode(get_output(parg))
    #print('callrpm', parg, 'retval', retval.strip())
    tokstream = tokenize.generate_tokens(StringIO(retval).next)
    prevnum = None
    prevval = None
    prevop = None
    for toknum, tokval, _, _, _  in tokstream:
        if verbose > 4:
            print('rpm_macro_eval parse:', toknum, tokval)
        if toknum == tokenize.NUMBER or toknum == tokenize.STRING:
            pass
        elif toknum == tokenize.NAME:
            if archname is not None and archname == tokval:
                prevnum = tokenize.NUMBER
                prevval = '1'
                break
        elif toknum == tokenize.OP:
            prevop = tokval
            continue
        elif toknum in [tokenize.INDENT, tokenize.DEDENT, tokenize.NEWLINE, tokenize.NL, tokenize.ENDMARKER]:
            continue
        else:
            print('tok', toknum, 'name', tokenize.tok_name[toknum], 'tokval', tokval)
            continue
        if prevop is not None:
            if prevop == '==':
                if prevnum == toknum and prevval == tokval:
                    tokval = '1'
                else:
                    tokval = '0'
                toknum = tokenize.NUMBER
            elif prevop == '|':
                pass
            elif prevop == '%' and toknum == tokenize.NAME:
                print('opertor%', tokval)
            else:
                print('unknown operator', prevop)
            prevop = None
        prevnum = toknum
        prevval = tokval
    retcode = ( prevnum == tokenize.NUMBER and int(prevval) != 0 )
    #print('finished', retcode, 'tokname', tokenize.tok_name[prevnum], 'tokval', prevval)
    return retcode

def eval_config(aconfig, atarget_arch, aarch, process_item):
    thisconfig = customization.editconfig(aconfig, aarch)
    # now parse/process config info
    skipline = False
    fh = open('bozo', 'wa')
    nest = 0
    lineno = 0
    skipflag = [False, False, False, False, False, False]
    for inpline in thisconfig:
        lineno += 1
        fh.write (inpline + '\n')
        if nest == 1 and inpline.startswith('%else'):
            skipline = not skipline
        elif inpline.startswith('%endif'):
            #print('lineendif', lineno, 'nest', nest)
            nest -= 1
            skipline = skipflag[nest]
        elif inpline.startswith('%ifarch'):
            #print('lineifarch', lineno, 'nest', nest)
            skipflag[nest] = skipline
            if not skipline:
                skipline = not rpm_macro_eval(inpline[7:], aarch, atarget_arch)
            nest += 1
        elif inpline.startswith('%if'):
            #print('lineif', lineno, 'nest', nest)
            skipflag[nest] = skipline
            if not skipline:
                skipline = not rpm_macro_eval(inpline[3:], None, atarget_arch)
            nest += 1
        elif not skipline:
            process_item(inpline)
    fh.close()

#
# use 'rpmspec' to extract all the BuildRequires from the spec file
# (and postprocess to cleanup the output)
#
def spec_requires(verbose, singlefile, aarchtype, atopdir, arcfile):
    retval = ''
    pcall = ['rpmspec', rpmmacros(), '-q', '--define', '_topdir ' + atopdir, '--srpm']
    if arcfile is not None:
        pcall.append(arcfile)
    pcall.append(r'--qf=[%|VERBOSE?{%{REQUIREFLAGS:deptype}: }:{}|%{REQUIRENAME} %{REQUIREFLAGS:depflags} %{REQUIREVERSION}\n]')
    for item in ['--define', 'buildroot /tmp', '--target', aarchtype, singlefile]:
        pcall.append(item)
    if verbose > 4:
        print("processing spec_requires", pcall)
    retval = get_output(pcall)
    srequires = retval.split('\n')
    for i in range(len(srequires)):
        index = srequires[i].find(' ')
        if index > 1:
            srequires[i] = srequires[i][:index]
    if '' in srequires:
        srequires.remove('')
    if verbose > 4 and len(srequires) > 0:
        print("srequires", srequires)
    return srequires

def runcall(command, dirname):
    #print('run command', command)
    sts = subprocess.call(command, shell=True, cwd=dirname, stdout=sys.stdout, stderr=sys.stdout)
    if sts != 0:
         print('problem with subprocess.call: ', command, 'dir='+dirname)
         exitprocessing(-11)

def chroot_makedirs(adir):
    if not os.path.lexists(adir):
        os.makedirs(adir, 0o777)
        os.chmod(adir, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)

# Process a file init script for prepopulating the chroot
def init_file_script(verbose, listp, arootdir):
    for inp in listp:
        if verbose > 3:
            print(inp)
        if inp[0] == 'dir':
            if verbose > 3:
                print('makedir', inp[1])
            chroot_makedirs(arootdir + inp[1])
        elif inp[0] == 'sed':
            if verbose > 3:
                print('makesed', inp[1], arootdir + inp[2])
                print('sed -i.001 -e "' + inp[1] + '" ' + arootdir + inp[2], '.')
            runcall('sed -i.001 -e "' + inp[1] + '" ' + arootdir + inp[2], '.')
        elif inp[0] == 'mv':
            if verbose > 3:
                print('makemv', arootdir + inp[1], arootdir + inp[2])
            chroot_makedirs(arootdir + os.path.dirname(inp[2]))
            if os.path.exists(arootdir + inp[1]):
                shutil.move(arootdir + inp[1], arootdir + inp[2])
        elif inp[0] == 'ln':
            if verbose > 3:
                print('makeln', inp[1], arootdir + inp[2])
            chroot_makedirs(arootdir + os.path.dirname(inp[2]))
            if not os.path.exists(arootdir + inp[2]):
                os.symlink(inp[1], arootdir + inp[2])
        elif inp[0] == 'rm':
            if verbose > 3:
                print('makerm', arootdir + inp[1])
            for singlefile in glob.glob(arootdir + inp[1]):
                os.remove(singlefile)
        elif inp[0] == 'touch':
            if verbose > 3:
                print('maketouch', inp[1])
            chroot_makedirs(arootdir + os.path.dirname(inp[1]))
            fh = open(arootdir + inp[1], 'wa')
            fh.close()
        else:
            print('unknown', inp)

def run_ldconfig(arootdir):
    runcall(customization.sudoprog + ' chroot ' + arootdir + ' /sbin/ldconfig 2>/dev/null', '.')
    #change annoying permissions
    runcall(customization.sudoprog + ' chmod a+r ' + arootdir + '/var/cache/ldconfig', '.')

def rpm_evaluate(aattribute, aname):
    return get_output(['rpm', '-qp', '--nodigest', '--nosignature', '--qf', '%{' + aattribute + '}', aname])

def write_list(adata, aname):
    fh = open(aname, 'wa')
    for inp in adata:
        fh.write(inp + '\n')
    fh.close()

def read_list(aname):
    fh = open(aname)
    tempin = fh.readlines()
    fh.close()
    for i in range(len(tempin)):
        tempin[i] = tempin[i].strip()
    return tempin

class LockHandler:
    def __init__(self, abasefile):
        self.lockfilename = ''
        self.lockfd = -1
        self.lockfilename = abasefile
    def lock_wait(self, aext):
        timelimit = 1
        while self.lockfilename is not None:
            try:
                self.lockfd = os.open(self.lockfilename + aext, os.O_CREAT|os.O_EXCL|os.O_RDWR)
                os.write(self.lockfd, str(os.getpgrp()) + ' ' + startname)
                #print('***** lock_wait:', self.lockfilename + aext)
                break;
            except OSError as e:
                print("blocked for locking", self.lockfilename + aext)
                time.sleep(5)
                timelimit = timelimit + 1
                if timelimit > maxlocktimeout or e.errno != errno.EEXIST:
                    os.unlink(self.lockfilename + aext)
                    print("timelimit", timelimit, e.errno, errno.EEXIST)
                    raise
        lockfiles_used.append(self.lockfilename + aext)
    def lock_clear(self, aext):
        lockfiles_used.remove(self.lockfilename + aext)
        if self.lockfd >= 0:
            try:
                os.close(self.lockfd)
            except OSError:
                pass
        try:
            os.unlink(self.lockfilename + aext)
        except OSError:
            pass
    def lock_clear_null(self):
        self.lock_clear('')

def startprocessing(aname):
    global startname, starttime
    starttime = datetime.datetime.utcnow()
    startname = aname

def exitprocessing(retval):
    global startname, starttime
    for fname in lockfiles_used:
        #print('Error: clearing lockfile', fname)
        os.remove(fname)
    print("*********************** done", retval, startname, (datetime.datetime.utcnow() - starttime).seconds)
    sys.exit(0)
