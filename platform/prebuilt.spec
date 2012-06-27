
Name: prebuilt
Version: 1
Release: 0
License: GPL
Summary: prebuilt stuff

%description

%package arm-linux-androideabi
BuildArch: noarch
Summary: gcc cross compiler and /usr/include, /usr/lib

%description arm-linux-androideabi

%files arm-linux-androideabi
/prebuilt/linux-x86/toolchain/arm-linux-androideabi-4.4.x
/prebuilt/ndk/android-ndk-r7/platforms/android-14/arch-arm/usr

%package android-ndk
BuildArch: noarch
Summary: /usr/lib

%description android-ndk

%files android-ndk
/out
