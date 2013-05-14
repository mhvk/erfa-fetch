#!/usr/bin/env python
from __future__ import print_function

"""
This script downloads the latest SOFA, and then transforms the code to
include the appropriate copyright and function name changes.  It also
scruches all of the .c files into a single file.

In can be invoked directly on the commandline simple as::

python sofa_deriver.py

"""


#this is put at the *end* of the documentation comment for all C functions.
DEFAULT_INLINE_LICENSE_STR = """Copyright (c) 2013, <SOME LEGAL ORGANIZATION>
Licensed under a 3-clause BSD style license - see the end of this file."""

#This is placed at
DEFAULT_FILE_END_LICENSE_STR = """Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice,
  this list of conditions and the following disclaimer.
* Redistributions in binary form must reproduce the above copyright notice,
  this list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.
* Neither the name of <ORG> nor the names of its contributors
  may be used to endorse or promote products derived from this software
  without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF
THE POSSIBILITY OF SUCH DAMAGE.
"""


def reprocess_sofa_tarfile(sofatarfn, libname='erfa', func_prefix='era',
                           inlinelicensestr=DEFAULT_INLINE_LICENSE_STR,
                           endlicensestr=DEFAULT_FILE_END_LICENSE_STR,
                           verbose=True):
    """
    Takes a SOFA .tar.gz file and produces a derived version of the
    source code with custom licensing and copyright.

    The resulting source code will be placed in a directory matching
    `libname`.
    """
    import os
    import tarfile

    filecontents = {}
    # this dict maps filenames to the code in the form of a list of strings.
    # they do *not* have the end license, as that gets added when writing.

    #turn the license strings into a SOFA-style C comment
    inlinelicensestr = '**  ' + '\n**  '.join(inlinelicensestr.split('\n')) + '\n'
    endlicensestr = '**  ' + '\n**  '.join(endlicensestr.split('\n'))
    endlicensestr = '/*\n' + endlicensestr + '\n*/\n'

    #first open the tar file
    tfn = tarfile.open(sofatarfn)
    try:
        for ti in tfn:
            contents = None

            if ti.name.endswith('.h'):
                contents = reprocess_sofa_h_lines(tfn.extractfile(ti),
                                                  func_prefix,
                                                  libname,
                                                  inlinelicensestr)
            elif ti.name.endswith('.c'):
                contents = reprocess_sofa_c_lines(tfn.extractfile(ti),
                                                  func_prefix,
                                                  libname,
                                                  inlinelicensestr)
            #ignore everything else
            if contents is not None:
                # if "sofa" appears in the name, change appropriately
                filename = ti.name.split('/')[-1].replace('sofa', libname.lower())

                filecontents[filename] = contents

        #now write out all the files, including the end license
        dirnm = os.path.abspath(os.path.join('.', libname))
        if not os.path.isdir(dirnm):
            if verbose:
                print('Making directory', dirnm)
            os.mkdir(dirnm)



        for fn, lines in filecontents.iteritems():
            fullfn = os.path.join(dirnm, fn)

            if verbose:
                print('Writing to file', fullfn)
            with open(fullfn, 'w') as f:
                f.write(''.join(lines))
                f.write(endlicensestr)

    finally:
        tfn.close()


def reprocess_sofa_h_lines(inlns, func_prefix, libname, inlinelicensestr):
    outlns = []
    donewheader = False

    for l in inlns:
        if l.startswith('#'):
            #includes and #ifdef/#define directives
            outlns.append(l.replace('SOFA', libname.upper()).replace('sofa', libname.lower()))
        elif l.startswith('**'):
            if not donewheader:
                if l.startswith('**  This file is part of the International Astronomical Union'):
                    #after this it's all IAU/SOFA-specific stuff, so replace with ours
                    donewheader = True
                    outlns.append(inlinelicensestr)
                elif 's o f a' in l:
                    outlns.append(l.replace('s o f a', ' '.join(libname.lower())))
                else:
                    outlns.append(l.replace('SOFA', libname.upper()))

        elif l.startswith('/*----------------------------------------------------------------------'):
            #in license section at end of file
            outlns.append('\n')
            break
        else:
            outlns.append(l.replace('iau', func_prefix))


    return outlns


def reprocess_sofa_c_lines(inlns, func_prefix, libname, inlinelicensestr):
    spaced_prefix = ' '.join(func_prefix)

    outlns = []
    inhdr = True  # start inside the header before the function def'n
    insofapart = False  # the part of the header that's SOFA-specific
    replacedprefix = False  # indicates if the "iau" line has been hit
    replacedspacedprefix = False  # indicates if the "i a u" line has been hit
    incopyright = False  # indicates being inside the copyright/revision part of the doc comment of the SOFA function

    for l in inlns:
        if inhdr:
            if (not replacedprefix) and 'iau' in l:
                # this is the function definition and the end of the header
                outlns.append(l.replace('iau', func_prefix))
                replacedprefix = True
                inhdr = False
            else:
                # make sure the includes are correct for the new libname
                if 's o f a' in l:
                    #rare case - just the test file - so it gets a special if
                    l = l.replace('s o f a', ' '.join(libname.lower()))
                outlns.append(l.replace('sofa', libname.lower()).replace('SOFA', libname.upper()))
        elif insofapart:
            #don't write out any of the disclaimer about being part of SOFA
            if l.strip() == '**':
                insofapart = False
        elif l.startswith('**  This function is part of the International Astronomical Union'):
            insofapart = True
        elif (not replacedspacedprefix) and 'i a u' in l:
            outlns.append(l.replace('i a u', spaced_prefix))
            replacedspacedprefix = True
        elif incopyright:
            # skip the copyright/versioning section unless it's the end
            if l.startswith('*/'):  # indicates end of the doc comment
                incopyright = False
                outlns.append(l)
        elif l.startswith('/*----------------------------------------------------------------------'):
            #this means we are in the license section, so we are done
            #except for the final close-bracket always comes after the
            #license section
            outlns.append('}\n')
            break
        elif l.startswith('**  This revision:'):
            incopyright = True
            #start of the copyright/versioning section - need to strip this because it contains SOFA references.

            #but put in the correct inline license instead
            if inlinelicensestr:
                outlns.append(inlinelicensestr)
        else:
            # need to replace 'iau' b/c other SOFA functions are often called
            outlns.append(l.replace('iau', func_prefix).replace('sofa', libname))

    return outlns


def download_sofa(url=None, dlloc='.', verbose=True):
    """
    Downloads the latest version of SOFA (or one specified via `url`) to
    the `dlloc` directory.

    If `extract`, also extract that .tar.gz file
    """
    import os
    import urllib

    if url is None:
        url = _find_sofa_url_on_web_page()

    fn = url.split('/')[-1]
    if not os.path.isdir(dlloc):
        raise ValueError('Requested dlloc {0} is not a directory'.format(dlloc))

    fnpath = os.path.join(dlloc, fn)
    if verbose:
        print('Downloading {fn} to {fnpath}'.format(fn=fn, fnpath=fnpath))
    retfn, headers = urllib.urlretrieve(url, fnpath)

    return retfn


def _find_sofa_url_on_web_page(url='http://www.iausofa.org/current_C.html'):
    """
    Finds and returns the download URL for the latest C SOFA.
    """
    import urllib2
    from HTMLParser import HTMLParser

    # create a subclass and override the handler methods
    class SOFAParser(HTMLParser):
        def __init__(self):
            self.matched_urls = []
            HTMLParser.__init__(self)

        def handle_starttag(self, tag, attrs):
            if tag == 'a' and attrs[-1][-1].endswith('.tar.gz'):
                self.matched_urls.append(attrs[-1][-1])

    parser = SOFAParser()
    u = urllib2.urlopen(url)
    try:
        for l in u:
            parser.feed(l)
    finally:
        u.close()

    baseurl = '/'.join(url.split('/')[:-1])
    fullurls = [(baseurl + m) for m in parser.matched_urls]

    if len(fullurls) != 1:
        raise ValueError('Found *multiple* possible downloads: ' +
                         str(fullurls))

    return fullurls[0]


if __name__ == '__main__':
    import sys
    import glob
    import tarfile
    import argparse

    parser = argparse.ArgumentParser(description='Generates code derived from SOFA.')
    parser.add_argument('sofafile', nargs='?', default=None, help='The sofa '
                        '.tar.gz file to use.  If absent, the current '
                        'directory will be searched, and if still absent, the '
                        'latest sofa will be downloaded from the web.')
    parser.add_argument('--download', '-d', default=False, action='store_true',
                        help='Download the latest SOFA regardless regardless '
                        'of whether there is already a SOFA in the current '
                        'directory')
    parser.add_argument('--quiet', '-q', default=False, action='store_true',
                        help='Print less info to the terminal.')
    args = parser.parse_args()

    if args.download:
        if args.sofafile is not None:
            print('Cannot give both --download and sofafile!', file=sys.stderr)
            sys.exit(1)
        sofatarfn = download_sofa(verbose=not args.quiet)
    elif args.sofafile is not None:
        try:
            #try to open the file as a tar file
            f = tarfile.open(args.sofafile)
            f.close()
        except (IOError, tarfile.ReadError) as e:
            print('requested sofafile "{0}" is not a valid tar file: '
                  '"{1}"'.format(args.sofafile, e), file=sys.stderr)
            sys.exit(1)
        #all is ok - use the file below
        sofatarfn = args.sofafile
    else:
        lstar = glob.glob('sofa_c*.tar.gz')

        if len(lstar) > 1:
            print("Found multiple sofa_c*.tar.gz files: {0} - can't pick which "
                  "one to use:".format(lstar), file=sys.stderr)
            sys.exit(1)
        elif len(lstar) == 0:
            if not args.quiet:
                print('Did not find any sofa_c*.tar.gz files - downloading.')
            sofatarfn = download_sofa(verbose=not args.quiet)
        else:
            sofatarfn = lstar[0]  # there is only one
    if not args.quiet:
        print('Using sofa tarfile "{0}" for reprocessing'.format(sofatarfn))
    reprocess_sofa_tarfile(sofatarfn, verbose=not args.quiet)
