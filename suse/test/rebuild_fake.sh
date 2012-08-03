#

[ -e sandbox/RPMS ] || mkdir sandbox/RPMS
[ -e sandbox/BUILD ] || mkdir sandbox/BUILD
TEMPDIR=`pwd`/sandbox
defines=()
defines[${#defines[@]}]='--define'
defines[${#defines[@]}]="_topdir $TEMPDIR"
defines[${#defines[@]}]='--define'
defines[${#defines[@]}]="_tmppath $TEMPDIR"
prof-rpmbuild -bb --root `pwd` --dbpath=`pwd` --macros=../macros "${defines[@]}"  ignore.spec
