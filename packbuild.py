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
import datetime, errno, fnmatch, glob, os, re, select, signal, shutil, string, subprocess, sys, time
import customization, genutil, sourcerepo, ParseOBS, ParseService

localpackages = []
localpackconf = 'proflocal'
max_rpmbuild_in_seconds = 1000

def expand_all_dependencies(context, atargetarch, archname, adependlist, aload_in_sysroot):
    def zypper_start(arch, arootdir):
        zswitches = '-n -q -q -x'
        zswitches = '-n -q -q'
        return 'env ' \
           + ' ZYPP_CONF=' \
           + customization.scripthome + '/' + arch + '.conf ZYPP_LOCKFILE_ROOT=' + arootdir \
           + ' ZYPPER_NOSCRIPTS=1 ZYPP_GLOBAL_PACKAGECACHE=1 "PX_MODULE_BLACKLIST=*" PX_MODULE_WHITELIST=config_envvar ' \
           + ' zypper ' + zswitches + ' --pkg-cache-dir /var/tmp/zypp-packagecache-$USER --root ' + arootdir + ' '
    context.pconfig.prepare_prjconf_info(atargetarch, archname)
    dependlist = adependlist
    if dependlist is None:
        dependlist = context.pconfig.configlists['Preinstall'] + context.pconfig.configlists['Required'] + context.pconfig.configlists['Support']
    if context.verbose > 1:
        print('expand_all_dependencies', atargetarch, archname, adependlist is not None, aload_in_sysroot, len(dependlist))
    newlist = []
    tstrs = ''
    tstrr = ''
    tstrrt = ''
    for name in dependlist:
        if name.strip() == '' or name in ['filesystem', 'aaa_base', 'config(bash)']:
            continue
        if False and name in ['coreutils', 'bind-libs', 'bind-utils', 'ncurses-devel', 'openldap2-client', 'rpm', 'libzio', 'libnscd']:
            # in NT, coreutils conflicts with mktemp
            # bind-libs and bind-utils, openldap2-client requires libcrypto that conflicts with openssl
            # ncurses-devel requires uninstallable libncurses5
            # rpm uses popt, which conflicts
            #    libpopt0-1.16-8.2.i586[MTB]
            #    armv7hl-baselayer-sysroot-0-3.1.i586[MTNT]
            #    i586-baselayer-sysroot
            continue
        for subitem in context.pconfig.configlists['Substitute']:
            if name == subitem[0]:
                #print('subst', name, subitem[1])
                name = subitem[1]
        if name.endswith('%{gcc_version}'):
            print('ignoring dependency:', name)
            continue
        newlist.append(name)
    if context.verbose > 4:
        print('expand_all_dep', len(newlist))
    for name in newlist:
        tname = ' "' + name + '"'
        rootstring = ''
        if aload_in_sysroot:
            rootstring = 'SYSROOT'
        if not aload_in_sysroot or customization.FORCE_HOST_TOOLS(name):
            if name.startswith('injection-armv7hl-'):
                if name.startswith('injection-armv7hl-target'):
                    continue
                tstrrt = tstrrt + tname
            else:
                tstrr = tstrr + tname
            rootstring = ''
        elif (name in context.inprocess and not customization.FORCE_TARGET(name)) \
          or name.startswith('injection-armv7hl-host'):
            continue
        else:
            tstrs = tstrs + tname
        context.inprocess.append(rootstring + name)
    #temprpmdir = ' ' + os.path.dirname(context.rootdir) + '/RPMS/noarch/'
    temprpmdir = ' ' + os.getcwd() + '/'
    tzpack = temprpmdir + 'tzdata-1-0.noarch.rpm'
    if not os.path.exists(tzpack.strip()):
         tzpack = ''
    #    genutil.runcall('./rebuild_fake.sh', '.')
    if context.verbose > 2:
        print('adependlist:', adependlist is not None, aload_in_sysroot)
        print('tstrrt:', tstrrt)
        print('tstrs:', tstrs)
    if adependlist is None:
        if tstrrt != '':
            #tstrrt = tstrrt + temprpmdir + 'notarget-1-0.noarch.rpm' + tzpack
            print('zypper_start(armv7hl, rootdir in ' + tstrrt)
            genutil.runcall(zypper_start('armv7hl', context.rootdir) + 'in --no-recommends ' + tstrrt, context.rootdir)
        if tstrr != '':
            #tstrr = tstrr + ' injection-i586-host-glibc' + temprpmdir + 'busybox-1-0.noarch.rpm'
            tstrr = tstrr + ' qemu ' + temprpmdir + 'noarch/prebuilt-android-ndk-1-0.noarch.rpm ' + temprpmdir + 'noarch/prebuilt-arm-linux-androideabi-1-0.noarch.rpm'
            print('zypper_start(i586, rootdir in ' + tstrr)
            genutil.runcall(zypper_start('i586', context.rootdir) + 'in --no-recommends ' + tstrr, context.rootdir)
        if context.verbose > 2:
            print('zypper: ****** bbbbefore moving directories ***', aload_in_sysroot, not os.path.exists(context.rootdir + '/sysroot/etc'))
        if aload_in_sysroot and not os.path.exists(context.rootdir + '/sysroot/etc'):
            os.remove(context.rootdir + '/etc/zypp')
            shutil.move(context.rootdir + '/usr/include', context.rootdir + '/sysroot/usr/include')
            shutil.move(context.rootdir + '/usr/share', context.rootdir + '/sysroot/usr/share')
            shutil.move(context.rootdir + '/etc', context.rootdir + '/sysroot/etc')
            os.symlink('../../../zypp', context.rootdir + '/sysroot/etc/zypp')
            os.symlink('../sysroot/usr/include', context.rootdir + '/usr/include')
            os.symlink('../sysroot/usr/share', context.rootdir + '/usr/share')
            os.symlink('../sysroot/etc', context.rootdir + '/etc')
    if tstrs != '':
        tstrs = tstrs + temprpmdir + 'busybox-1-0.noarch.rpm' + tzpack
        print('zypper_start(armv7hl, /sysroot in ' + tstrs)
        genutil.runcall(zypper_start('armv7hl', context.rootdir + '/sysroot') + 'in --no-recommends ' + tstrs, context.rootdir + '/sysroot')
    #
    # Fixup links in /sysroot/usr/lib that point to /lib.  They should point to /sysroot/lib
    #
    for singlefile in glob.glob(context.rootdir + '/sysroot/usr/lib/*'):
        if os.path.islink(singlefile):
            tarfile = os.readlink(singlefile)
            if len(tarfile) > 0 and tarfile[0] == '/' and (len(tarfile) < 9 or tarfile[:8] != '/sysroot'):
                os.remove(singlefile)
                #print('relink /sysroot' + tarfile, singlefile)
                os.symlink('/sysroot' + tarfile, singlefile)
        basefile = os.path.basename(singlefile)
        rootfile = context.rootdir + '/usr/lib/' + basefile
        if os.path.isdir(singlefile) and not os.path.lexists(rootfile):
            os.symlink('/sysroot/usr/lib/' + basefile, rootfile)
    for root, dirnames, filenames in os.walk(context.rootdir):
        for filename in fnmatch.filter(filenames, '*.rpmnew'):
            fname = os.path.join(root, filename)
            #print("foundnew", fname, fname[:-7])
            os.rename(fname, fname[:-7])

#
# Build a 'generic' chroot/sysroot for this architecture (no spec files used).
#
def make_chroot_template(context):
    if os.path.exists(context.rootdir + '/inprocess'):
        return
    if not os.path.exists(os.path.dirname(context.rootdir) + '/zypp.i586'):
        genutil.exitprocessing(-110)
    print('make_template: start', context.rootdir)
    genutil.init_file_script(context.verbose, customization.file_initial(context.archtype), context.rootdir)
    genutil.runcall('(cd ' + customization.scriptdir + '/template; tar cf - .) | tar xf -', context.rootdir)
    genutil.runcall(customization.sudoprog + ' mknod -m a=rw ' + context.rootdir + '/dev/null c 1 3', '.')
    genutil.runcall(customization.sudoprog + ' mkfifo ' + context.rootdir + '/dev/log/main', '.')
    rcallbase = 'prof-rpm --nochroot --quiet ' + genutil.rpmmacros() + ' --root=' + context.rootdir
    #genutil.runcall(rcallbase + ' --initdb', '.')
    #genutil.runcall(rcallbase + '/sysroot --initdb', '.')
    #process required RPMs for generic prjconf template
    expand_all_dependencies(context, None, context.hostarch, None, False)
    print('temporarily skip generic ARM package install')
    #expand_all_dependencies(context, context.archtype, context.archtype, None, True)
    genutil.init_file_script(context.verbose, customization.file_edit_list(context.archtype), context.rootdir)
    for singlefile in glob.glob(context.rootdir + '/opt/*/lib/*'):
        snew = os.path.basename(singlefile)
        if not os.path.lexists(context.rootdir + '/lib/' + snew):
            lname = singlefile[len(context.rootdir):]
            #print('linking ' + lname, context.rootdir + '/lib/' + snew)
            os.symlink(lname, context.rootdir + '/lib/' + snew)
    fh = open(context.rootdir + '/root/.rpmmacros', 'wa')
    for inp in context.pconfig.macrodefs:
        fh.write(inp + '\n')
    if False:
        fh.write(customization.disable_check_section())
    fh.close()
    genutil.run_ldconfig(context.rootdir)
    genutil.write_list(context.inprocess, context.rootdir + '/inprocess.tmp')
    os.rename(context.rootdir + '/inprocess.tmp', context.rootdir + '/inprocess')
    # to run 'script' in this chroot, the following is needed:
    #    mount -t devpts -o newinstance -o ptmxmode=0666 devpts /dev/pts


#
# Build all the specfiles in the source package directory
#
def rpmbuild_one_directory(context, do_not_run_rpmbuild, apackagename):
    global localpackages, localpackconf
    context.packagename = apackagename
    bdir = context.rootdir + context.rpmbuilddir
    subprocess.call(customization.sudoprog + ' rm -rf ' + bdir + ' 2>/dev/null', shell=True, cwd='.')
    statitem = open('/proc/stat').readlines()
    for i, item in enumerate(statitem):
        if item.startswith('cpu'):
           customization.job_count = int(1.5 * i)
    genlockfile = context.rootdir + '/gglock'
    mylock = genutil.LockHandler(genlockfile)
    genutil.chroot_makedirs(context.rootdir)
    mylock.lock_wait('')
    make_chroot_template(context)
    mylock.lock_clear('')
    if os.path.exists(localpackconf):
        localpackages = open(localpackconf).read().split('\n')
        if '' in localpackages:
            localpackages.remove('')
        #print('local packages', localpackages)
    this_local = False
    if apackagename in localpackages:
        print('DDDDDDDDDDDDDDDlocalpackage', apackagename)
        this_local = True

    genutil.chroot_makedirs(bdir)
    for item in ['SOURCES', 'BUILD', 'RPMS', 'SOURCES', 'SPECS', 'SRPMS', 'BUILDROOT']:
        genutil.chroot_makedirs(bdir + '/' + item)
    sdir = bdir + '/SOURCES/'

    buildproject = context.buildproject
    buildpackagename = context.packagename
    while True:
        masterfh = ParseOBS.ParsePackage(customization.buildbase + buildproject + '/' + buildpackagename + '._manifest').filelist
        for masterline in masterfh:
            filename, filesize, objectfile, checksum = masterline.split()
            if context.verbose > 0:
                print('cp ' + customization.buildbase + '../' + objectfile + ' ' + sdir + filename)
            genutil.runcall('cp ' + customization.buildbase + '../' + objectfile + ' ' + sdir + filename, '.')
        buildproject, buildpackagename = ParseOBS.ParsePackageLink(sdir + '_link', buildproject).linkproject()
        if buildpackagename is None:
            break
        os.remove(sdir + '_link')
    #
    # Process _service files
    #
    servicep = ParseService.ParseService(context.verbose, sdir + '_service', this_local)
    fh = open(bdir + '/build.servicing.tmp', 'w')
    curitem = servicep.servicelist
    while curitem is not None:
        #print('curitem', curitem.service, json.dumps(curitem.data))
        urlname = curitem.data['url']
        if urlname != '':
             #print('url', urlname)
             fh.write(urlname + '\n')
        curitem = curitem.next
    fh.close()
    os.rename(bdir + '/build.servicing.tmp', bdir + '/build.servicing')
    sts = servicep.process(sdir, None, None)
    if sts != 0:
        genutil.exitprocessing(sts)

    #
    # Run rpmbuild on each of the spec files in the source directory
    #
    for singlefile in glob.glob(sdir + '*.spec'):
        data = open(singlefile).readlines()
        for linenum, inline in enumerate(data):
            if '#%' in inline:
                print('**** BOGUS SPEC FILE "#%" comment line ****: line', linenum, ':', inline)
        #genutil.runcall('sed -i.001 -e "s/#%/#BOGUS/g" ' + singlefile, '.')
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
                and not item.startswith('BuildEnhances:') and not item.startswith('BuildSupplements') \
                and not item.startswith('PreReq:'):
                fh.write(item)
        fh.close()

        #
        # Extract BuildRequires from spec file
        #
        srequires = genutil.spec_requires(context.verbose, singlefile, context.archtype, bdir, \
            '--rcfile=' + customization.scriptdir + '/rpm-rpmspec.rpmrc')
        if srequires is None:
            continue

        open(bdir + '/build.afterservice', 'w').write('started')
        os.remove(bdir + '/build.servicing')
        if not os.path.lexists(context.rootdir + '/sysroot' + context.rpmbuilddir):
            os.symlink(context.rpmbuilddir, context.rootdir + '/sysroot' + context.rpmbuilddir)
        #
        # Resolve/load all the rpms implied by the BuildRequires
        #
        mylock.lock_wait('')
        context.inprocess = genutil.read_list(context.rootdir + '/inprocess')
        expand_all_dependencies(context, context.archtype, context.archtype, srequires, True)
        if True:
            for linkfile in glob.glob(context.rootdir + '/sysroot' + '/usr/lib/' + '*.la'):
                if not os.path.exists(linkfile + '.001'):
                    if context.verbose > 0:
                        print('running sed -i.001 -e "s/\/usr\/lib/\/sysroot&/g" ' + linkfile)
                    genutil.runcall('sed -i.001 -e "s/\/sysroot\/usr\/lib/\/usr\/lib/g" -e "s/\/usr\/lib/\/sysroot&/g" ' + linkfile, '.')
                snew = os.path.basename(linkfile)
                if not os.path.lexists(context.rootdir + '/usr/lib/' + snew):
                    lname = linkfile[len(context.rootdir):]
                    if context.verbose > 2:
                        print('linking ' + lname, context.rootdir + '/usr/lib/' + snew)
                    os.symlink(lname, context.rootdir + '/usr/lib/' + snew)
            for linkfile in glob.glob(context.rootdir + '/sysroot/usr/bin/*'):
                snew = os.path.basename(linkfile)
                #print('snew', snew)
                if not os.path.lexists(context.rootdir + '/usr/bin/' + snew):
                    lname = linkfile[len(context.rootdir):]
                    if context.verbose > 2:
                        print('linking ' + lname, context.rootdir + '/usr/bin/' + snew)
                    os.symlink(lname, context.rootdir + '/usr/bin/' + snew)
            genutil.run_ldconfig(context.rootdir)
            genutil.write_list(context.inprocess, context.rootdir + '/inprocess.tmp')
            if os.path.exists(context.rootdir + '/inprocess'):
                os.remove(context.rootdir + '/inprocess')
            os.rename(context.rootdir + '/inprocess.tmp', context.rootdir + '/inprocess')
        mylock.lock_clear('')
        #
        # write a script for invoking 'rpmbuild' in the chroot
        #
        fh = open(bdir + '/build.command', 'wa')
        fh.write(customization.rpmbuild_commands(context.archtype, os.path.basename(singlefile), context.verbose, context.rpmbuilddir))
        fh.close()
        print('Building:', os.path.basename(singlefile))
        if do_not_run_rpmbuild:
            return 0
        cmd = [customization.sudoprog, 'chroot', context.rootdir, 'sh']
        if context.verbose > 0:
            cmd.append('-x')
        cmd.append(context.rpmbuilddir + '/build.command')
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # setup a timer in case qemu locks up
        def watchdog_timeout(signum, frame):
            print('**** watchdog_timeout expired', os.path.basename(singlefile))
            genutil.runcall(customization.sudoprog + ' kill -- -' + str(p.pid), '.')
        signal.signal(signal.SIGALRM, watchdog_timeout)
        signal.alarm(max_rpmbuild_in_seconds)
        read_set = [p.stdout, p.stderr]
        outline = ''
        while read_set:
            try:
                rlist, wlist, xlist = select.select(read_set, [], [])
            except select.error, e:
                if e.args[0] == errno.EINTR:
                    continue
                raise
            for fh in rlist:
                data = os.read(fh.fileno(), 8192)
                if data == "":
                    fh.close()
                    read_set.remove(fh)
                #sys.stdout.write(data)
                outline = outline + data
                while True:
                    ind = outline.find('\n')
                    if ind == -1:
                        break
                    incomp = outline.find('/bin/ld: skipping incompatible ')
                    if incomp == -1 or incomp > ind:
                        sys.stdout.write(outline[:ind+1])
                    outline = outline[ind+1:]
        sys.stdout.write(outline)
        p.wait()
        return p.returncode

#
######## main #########
#

def main(aargv):
    do_not_run = False
    forcerepomd = False
    verbose = 0
    argindex = 1
    retval = -1
    while argindex < len(aargv) and aargv[argindex][0] == '-':
        if aargv[argindex] == '-v':
            verbose += 1
        elif aargv[argindex] == '-n':
            do_not_run = True
        argindex += 1
    if argindex + 4 != len(aargv):
        print('packbuild.py [-v] [-n] [-r] [-b] <chroot_dirname> <archname> <projectname> <packagename>')
        sys.exit(1)
    context = sourcerepo.PackageContext(aargv[argindex:-1], verbose, 'i586', forcerepomd)
    genutil.startprocessing(aargv[argindex+3])
    packagedir = customization.buildbase + context.buildproject + '/' + aargv[argindex+3]
    if not os.path.exists(packagedir + '._manifest'):
        print('package not found', packagedir)
        return
    if ParseOBS.ParsePackageMeta(packagedir + '._meta').disabled(context.archtype):
        print("package disabled", aargv[argindex+3])
        genutil.exitprocessing(15)
    if context.initok:
        if aargv[argindex+3] in customization.bannedpackages:
            print('ignorepackagebuild... !!!:', aargv[argindex+3])
            genutil.exitprocessing(20)
        print("*********************** ", aargv[argindex+3], aargv[argindex], os.getpgrp())
        retval = rpmbuild_one_directory(context, do_not_run, aargv[argindex+3])
    genutil.exitprocessing(retval)
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv))
