#
ORIGINAL_TGZ=`pwd`/system_libs.tgz
#TEMPDIR='/tmp'
TEMPDIR='tmp'
#BUILDD='tmp/BUILDROOT/arm-linux-androideabi-1-0.i386'
BUILDD='tmp/BUILDROOT/prebuilt-1-0.i386'
[ -e tmp/RPMS/noarch ] || mkdir -p tmp/RPMS/noarch
[ -e tmp/BUILD ] || mkdir -p tmp/BUILD
[ -e tmp/tmp ] || ln -s . tmp/tmp
[ -e $BUILDD ] || mkdir -p $BUILDD
(cd $BUILDD; tar xzf $ORIGINAL_TGZ)
[ -e $BUILDD/prebuilt/linux-x86 ] || ln -s ~/android/prebuilt/linux-x86 $BUILDD/prebuilt/linux-x86
./update.py $BUILDD/out/target/product/generic/system/bin/linker
#mv bboutfile $BUILDD/out/target/product/generic/system/bin/linker
#exit -1
defines=()
defines[${#defines[@]}]='--define'
defines[${#defines[@]}]="_topdir $TEMPDIR"
defines[${#defines[@]}]='--define'
defines[${#defines[@]}]="_tmppath $TEMPDIR"
defines[${#defines[@]}]='--define'
defines[${#defines[@]}]="_binaries_in_noarch_packages_terminate_build 0"
defines[${#defines[@]}]='--define'
defines[${#defines[@]}]="_unpackaged_files_terminate_build 0"
defines[${#defines[@]}]='--define'
defines[${#defines[@]}]='__check_files ""'
prof-rpmbuild -bb --root `pwd`/tmp/ --dbpath=`pwd`/tmp/ --macros=../suse/macros "${defines[@]}"  prebuilt.spec
