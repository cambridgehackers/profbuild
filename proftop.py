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
# View current build status
#

import datetime, errno, glob, json, os, re, select, signal, shutil, string, subprocess, sys, time
import customization

#
######## main #########
#
def main(aargv):
    quit_run = False
    if len(aargv) > 0 and aargv[0] == '-q':
        quit_run = True
    mastertime = 0
    starttime = datetime.datetime.utcnow()
    data = open('/proc/self/stat').read().split()
    startjiffie = int(data[21])
    HZ = 100
    sspl_last = [0,0,0,0,0]
    while True:
        totals = []
        for sline in glob.glob('/proc/[0-9]*/stat'):
            try:
                data = open(sline).read().split()
                totals.append(data)
            except:
                pass
        mastermin = int(mastertime/60)
        statitem = open('/proc/stat').readlines()
        sspl = statitem[0].split()[1:]
        idletotal = 1
        for i in range(0, len(sspl_last)):
            sspl_last[i] = int(sspl[i]) - int(sspl_last[i])
            idletotal = idletotal + sspl_last[i]
        #waiting = sspl_last[4] / float(idletotal)
        idletotal = int((sspl_last[3] * 1000) / float(idletotal))
        sspl_last = sspl
        outlist = []
        grouplist = []
        for sitem in totals:
            if sitem[1] == '(python)':
                masterpid = sitem[0]
                try:
                    data = open('/proc/' + masterpid + '/cmdline').read().split('\x00')
                except:
                    continue
                if len(data) > 2 and data[1].endswith('master.py'):
                    deltasec = int((startjiffie - int(sitem[21]))/HZ)
                    mastertime = (datetime.datetime.utcnow() - starttime).seconds + deltasec
                if len(data) < 2 or not data[1].endswith('packbuild.py'):
                    continue
                cutime = 0
                cstime = 0
                taskl = ''
                grouplist.append(masterpid)
                for stemp in totals:
                    if stemp[4] == masterpid:
                        cutime += int(stemp[13])
                        cstime += int(stemp[14])
                        taskl += ':' +stemp[1]
                deltasec = int((startjiffie - int(sitem[21]))/HZ)
                i = 2
                while data[i][0] == '-':
                    i += 1
                foo = ((datetime.datetime.utcnow() - starttime).seconds + deltasec,\
                       masterpid, os.path.basename(data[i]), data[i+3], cutime, cstime )
                for i, item in enumerate(outlist):
                     if item[0] < foo[0]:
                         outlist.insert(i, foo)
                         foo = None
                         break
                if foo is not None:
                    outlist.append(foo)
        if quit_run:
            for item in grouplist:
                print('item', item)
                subprocess.call(customization.sudoprog + ' kill -- -' + item, shell=True)
            break
        sys.stdout.write('\x1b[2J\x1b[H                   profbuild idle ' + str(idletotal/float(10)) + '%      ' \
            + ' elapsed ' + str(mastermin) + ':' + str(mastertime - 60 * mastermin) \
            + '\nelapsed   pgid       id                      package          incremental time\n')
        for item in outlist:
            print(' %6d %6s %8s %40s %6d %6d' % item)
        sys.stdout.write('\x1b[15;0H')
        if os.path.exists('xx.schedule'):
            subprocess.call('sort -n -r xx.schedule | head | pr -t -W 80', shell=True)
        time.sleep(1)
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
