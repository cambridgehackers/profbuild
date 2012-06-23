#!/bin/bash -x

SCRIPTDIR="$( cd "$( dirname "$0" )" && pwd )"
ROOTDIR=`pwd`/sandbox
TEMPDIR=$ROOTDIR/tmp
ORIGDIR=`pwd`
ARCH=i586
ABS=""

if test -z "$1"; then
    echo "$0 <repofile>"
    exit 1
fi
if test "${1:0:1}" != "/" ; then
    ABS="$PWD/"
fi
PARAMFILE=$ABS$1
echo PARAMFILE
rm -rf $ROOTDIR/zypp* $TEMPDIR
mkdir -p $TEMPDIR$HOME $TEMPDIR/etc
ln -s $HOME/.zypp $TEMPDIR$HOME/.zypp
BLIST="PX_MODULE_BLACKLIST=*"

pushd $TEMPDIR
ls $SCRIPTDIR/*.conf | while read CONFFILE
do
    ARCH=`basename ${CONFFILE%.conf}`
    ZYPP="env RPM_ROOTDIR=$TEMPDIR/ \
          ZYPP_CONF=$CONFFILE ZYPP_LOCKFILE_ROOT=$TEMPDIR ZYPPER_NOSCRIPTS=1 ZYPP_GLOBAL_PACKAGECACHE=1 \
          $BLIST PX_MODULE_WHITELIST=config_envvar \
          zypper --pkg-cache-dir /var/tmp/zypp-packagecache-$USER --root $TEMPDIR"
    $ZYPP addrepo $PARAMFILE
    $ZYPP refresh
    $ZYPP lr
    find . -name zypp\*
    mv $TEMPDIR/var/cache/zypp $ROOTDIR/zypp.$ARCH
    [ -e $ROOTDIR/zypp ] || mv $TEMPDIR/etc/zypp $ROOTDIR/zypp
    #rm -rf $TEMPDIR/etc
done
popd
rm -rf $TEMPDIR
