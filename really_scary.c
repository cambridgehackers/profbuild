// Copyright (c) 2012 Nokia Corporation
// Original author John Ankcorn
//
// Permission is hereby granted, free of charge, to any person obtaining a
// copy of this software and associated documentation files (the "Software"),
// to deal in the Software without restriction, including without limitation
// the rights to use, copy, modify, merge, publish, distribute, sublicense,
// and/or sell copies of the Software, and to permit persons to whom the
// Software is furnished to do so, subject to the following conditions:
//
// The above copyright notice and this permission notice shall be included
// in all copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
// OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
// THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
// FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
// DEALINGS IN THE SOFTWARE.

#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <unistd.h>
#include <libgen.h>

static char *checkname[] = {
    "/usr/sbin/chroot",
    "/bin/chmod",
    "/bin/rm",
    "/bin/kill",
    "/bin/mknod",
    "/home/jca/bin/prof-rpm",
    NULL};
static char *envp[] = {
    "HOME=/root",
    NULL};

int main(int argc, char *argv[])
{
char *myargv[100 + 1];
int len = sizeof(myargv)/sizeof(myargv[0]);
int i;

    if (argc < 2) {
        printf ("really_scary <params>\n");
        exit(-1);
    }
    if (len > argc)
        len = argc;
    for (i = 0; i < len-1; i++)
       myargv[i] = argv[i+1];
    myargv[len-1] = NULL;
    char **p = checkname;
    setuid(0);
    setgid(0);
    while (*p) {
        if (!strcmp(basename(*p), myargv[0]))
            return execve(*p, myargv, envp);
        p++;
    }
    printf ("command not allowed %s\n", basename(myargv[0]));
    return -1;
}
