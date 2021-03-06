#!/usr/bin/env python
"""
This script downloads the latest SOFA, and then transforms the code to
include the appropriate copyright and function name changes.

In can be invoked directly on the commandline simple as::

  python sofa_deriver.py

Or do::

  python sofa_deriver.py --help

To see the options.

"""

import re
import sys


DEFAULT_INLINE_LICENSE_STR = """
Copyright (C) 2013-{curryr}, NumFOCUS Foundation.
Derived, with permission, from the SOFA library.  See notes at end of file.
"""[1:-1]

DEFAULT_FILE_END_LICENSE_STR = """

Copyright (C) 2013-{curryr}, NumFOCUS Foundation.
All rights reserved.

This library is derived, with permission, from the International
Astronomical Union's "Standards of Fundamental Astronomy" library,
available from http://www.iausofa.org.

The {libnameuppercase} version is intended to retain identical functionality to
the SOFA library, but made distinct through different function and
file names, as set out in the SOFA license conditions.  The SOFA
original has a role as a reference standard for the IAU and IERS,
and consequently redistribution is permitted only in its unaltered
state.  The {libnameuppercase} version is not subject to this restriction and
therefore can be included in distributions which do not support the
concept of "read only" software.

Although the intent is to replicate the SOFA API (other than
replacement of prefix names) and results (with the exception of
bugs;  any that are discovered will be fixed), SOFA is not
responsible for any errors found in this version of the library.

If you wish to acknowledge the SOFA heritage, please acknowledge
that you are using a library derived from SOFA, rather than SOFA
itself.


TERMS AND CONDITIONS

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions
are met:

1 Redistributions of source code must retain the above copyright
  notice, this list of conditions and the following disclaimer.

2 Redistributions in binary form must reproduce the above copyright
  notice, this list of conditions and the following disclaimer in
  the documentation and/or other materials provided with the
  distribution.

3 Neither the name of the Standards Of Fundamental Astronomy Board,
  the International Astronomical Union nor the names of its
  contributors may be used to endorse or promote products derived
  from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
FOR A PARTICULAR PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL THE
COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.
"""


def reprocess_sofa_tarfile(sofatarfn, libname='erfa', func_prefix='era',
                           inlinelicensestr=DEFAULT_INLINE_LICENSE_STR,
                           endlicensestr=DEFAULT_FILE_END_LICENSE_STR,
                           verbose=True, copyrightyear=None):
    """
    Takes a SOFA .tar.gz file and produces a derived version of the
    source code with custom licensing and copyright.

    The resulting source code will be placed in a directory matching
    `libname`.

    Note that `inlinelicensestr` and `endlicensestr` should be plain
    license/copyright statements (possibly with ``{libnameuppercase}`` or
    ``{curryr}``), and this function will convert them to a C comment.
    """
    import os
    import tarfile
    import datetime

    # This dict maps filenames to the code in the form of a list of strings.
    # They do *not* have the end license, as that gets added when writing.
    filecontents = {}

    # This is the current year for whoever is running this.
    if copyrightyear is None:
        copyrightyear = datetime.datetime.now().year
        if copyrightyear < 2013:
            print("WARNING: Your system thinks the year is < 2013, which is "
                  "impossible unless you have fallen through a wormhole. "
                  "You'll need to set your clock correctly or use the "
                  "copyright-year argument for the copyright year to be "
                  "correct.")

    # Turn the license strings into a SOFA-style C comment.
    inlinelicensestr = inlinelicensestr.format(libnameuppercase=libname.upper(),
                                               curryr=copyrightyear)
    inlinelicensestr = '**  ' + '\n**  '.join(inlinelicensestr.split('\n')) + '\n'
    endlicensestr = endlicensestr.format(libnameuppercase=libname.upper(),
                                         curryr=copyrightyear)
    endlicensestr = '**  ' + '\n**  '.join(endlicensestr.split('\n'))
    endlicensestr = '/*' + ('-' * 70) + '\n' + endlicensestr + '\n*/\n'
    # First open the tar file.
    tfn = tarfile.open(sofatarfn)
    try:
        # Extract macro names from sofam.h, except SOFAMHDEF,
        # which we will use it later.
        macros = []
        macros_exclude = ['SOFAMHDEF']

        for ti in tfn:
            contents = None

            if ti.name.endswith('t_sofa_c.c'):
                # Test file.
                contents = reprocess_sofa_test_lines(tfn.extractfile(ti),
                                                     func_prefix,
                                                     libname,
                                                     inlinelicensestr)
            elif ti.name.endswith('.h'):
                extractedh = list(tfn.extractfile(ti))
                if ti.name.endswith('sofam.h'):
                    macros = extract_macro_names(extractedh, macros_exclude)
                contents = reprocess_sofa_h_lines(extractedh,
                                                  func_prefix,
                                                  libname,
                                                  inlinelicensestr)
            elif ti.name.endswith('.c'):
                contents = reprocess_sofa_c_lines(tfn.extractfile(ti),
                                                  func_prefix,
                                                  libname,
                                                  inlinelicensestr)
            # Ignore everything else.
            if contents is not None:
                # If "sofa" appears in the name, change appropriately.
                filename = ti.name.split('/')[-1].replace('sofa', libname.lower())

                filecontents[filename] = contents

        # Now write out all the files, including the end license.
        dirnm = os.path.abspath(os.path.join('.', libname))
        if not os.path.isdir(dirnm):
            if verbose:
                print('Making directory', dirnm)
            os.mkdir(dirnm)

        # Prepare to prefix the macros.
        # This is done here instead of in the `reprocess_sofa_*_lines`
        # functions because the macros have to be extracted from sofam.h, and
        # there's no guarantee above that it will come first.

        # Given a re match obj, return the match (the macro name),
        # prefixed and upper cased.
        def prefix_macro(matchobj):
            macro = matchobj.group(0)
            return 'ERFA_%s' % macro.upper()

        # Precompile a regular expresion for each macro name.
        repls = [re.compile(r'\b%s\b' % macro) for macro in macros]

        for fn, lines in filecontents.items():
            fullfn = os.path.join(dirnm, fn)

            if verbose:
                check_for_sofa(lines, fn)

            alllines = ''.join(lines)
            # Join the lines and replace the macros with the versions with
            # an ERFA prefix.
            for repl in repls:
                alllines = repl.sub(prefix_macro, alllines)

            if verbose:
                print('Writing to file', fullfn)
            with open(fullfn, 'w') as f:
                f.write(alllines)
                f.write(endlicensestr)

    finally:
        tfn.close()


def reprocess_sofa_h_lines(inlns, func_prefix, libname, inlinelicensestr):
    outlns = []
    donewheader = False

    for ln in inlns:
        ln = ln.decode()
        if ln.startswith('#'):
            # Includes and #ifdef/#define directives.
            outlns.append(ln.replace('SOFA', libname.upper())
                          .replace('sofa', libname.lower()))
        elif ln.startswith('**'):
            if not donewheader:
                if ln.startswith('**  This file is part of the International Astronomical Union'):
                    # After this it's all IAU/SOFA-specific stuff,
                    # so replace with ours.
                    donewheader = True
                    outlns.append(inlinelicensestr)
                elif 's o f a' in ln:
                    outlns.append(ln.replace('s o f a', ' '.join(libname.lower())))
                else:
                    outlns.append(ln.replace('SOFA', libname.upper()))

        elif ln.startswith('/*----------------------------------------------------------------------'):
            # In license section at end of file.
            outlns.append('\n')
            break
        else:
            outlns.append(ln.replace('iau', func_prefix))

    return outlns


def reprocess_sofa_c_lines(inlns, func_prefix, libname, inlinelicensestr):
    spaced_prefix = ' '.join(func_prefix)

    outlns = []
    inhdr = True  # Start inside the header before the function definition.
    insofapart = False  # The part of the header that's SOFA-specific.
    replacedprefix = False  # Indicates if the "iau" line has been hit.
    replacedspacedprefix = False  # Indicates if the "i a u" line has been hit.
    incopyright = False  # Indicates being inside the copyright/revision part of the doc comment of the SOFA function

    for ln in inlns:
        ln = ln.decode()
        if inhdr:
            if (not replacedprefix) and 'iau' in ln:
                # This is the function definition and the end of the header.
                outlns.append(ln.replace('iau', func_prefix))
                replacedprefix = True
                inhdr = False
            else:
                # Make sure the includes are correct for the new libname.
                outlns.append(ln.replace('sofa', libname.lower()).replace('SOFA', libname.upper()))
        elif insofapart:
            # Don't write out any of the disclaimer about being part of SOFA.
            if ln.strip() == '**':
                insofapart = False
        elif ln.startswith('**  This function is part of the International Astronomical Union'):
            insofapart = True
        elif ln.startswith('**  Status:'):
            # Don't include the status line which states if a function is
            # canonical - ERFA isn't "canonical" as it is not IAU official.
            if outlns[-1].strip() == '**':
                # Also drop the line with just '**' before it.
                del outlns[-1]
        elif (not replacedspacedprefix) and 'i a u' in ln:
            outlns.append(ln.replace('i a u', spaced_prefix))
            replacedspacedprefix = True
        elif incopyright:
            # Skip the copyright/versioning section unless it's the end.
            if ln.startswith('*/'):  # Indicates end of the doc comment.
                incopyright = False
                outlns.append(ln)
        elif ln.startswith('/*----------------------------------------------------------------------'):
            # This means we are in the license section, so we are done
            # except for the final close-bracket always comes after the
            # license section.
            outlns.append('}\n')
            break
        elif ln.startswith('**  This revision:'):
            incopyright = True
            # Start of the copyright/versioning section - need to strip this
            # because it contains SOFA references.  Instead, put this line
            # with useful date information and the correct inline license.
            outlns.append(ln)
            if inlinelicensestr:
                outlns.append('**\n')
                outlns.append(inlinelicensestr)
        else:
            # Need to replace 'iau' b/c other SOFA functions are often called.
            outlns.append(ln.replace('iau', func_prefix)
                          .replace('sofa', libname)
                          .replace('SOFA', libname.upper()))

    return outlns


def reprocess_sofa_test_lines(inlns, func_prefix, libname, inlinelicensestr):
    spaced_libname = ' '.join(libname)
    libnamelow = libname.lower()
    libnameup = libname.upper()

    outlns = []
    inhdr = True
    insofapart = False
    for ln in inlns:
        ln = ln.decode()
        if inhdr:
            if ln.startswith('**  SOFA release'):
                insofapart = True

            if insofapart:
                if ln.startswith('*/'):
                    insofapart = inhdr = False
                    outlns.append(ln)
                continue

            ln = ln.replace('s o f a', spaced_libname)

        elif ln.startswith('/*----------------------------------------------------------------------'):
            # This means we are starting the license section, so we are done.
            # Note that prior to SOFA 20170420, this was absent from t_erfa_c.c.
            break

        ln = ln.replace('iau', func_prefix)
        ln = ln.replace('sofa', libnamelow)
        ln = ln.replace('SOFA', libnameup)

        outlns.append(ln)

    return outlns


def extract_macro_names(m, exclude):
    macros = []
    prog = re.compile(r'\s*#\s*define\s*\b(\w*)\b')
    for line in m:
        line = line.decode()
        result = prog.match(line)
        if result:
            macro = result.group(1)
            if macro not in exclude:
                macros.append(macro)
    return macros


# These strings are "acceptable" uses of the "SOFA" text.
ACCEPTSOFASTRS = ['Derived, with permission, from the SOFA library']


def check_for_sofa(lns, fn='', printfile=sys.stderr):
    if isinstance(lns, str):
        lns = lns.split('\n')
    for i, ln in enumerate(lns):
        if 'sofa' in ln.lower():
            for s in ACCEPTSOFASTRS:
                if s in ln:
                    # Means skip the "else" part.
                    break
            else:
                infile = 'in file "{0}" at line {1}'.format(fn, i)
                print('WARNING: Found "SOFA"{infile}:\n{ln}'.format(infile=infile, ln=ln), file=printfile)


def download_sofa(url=None, dlloc='.', verbose=True):
    """
    Downloads the latest version of SOFA (or one specified via `url`) to
    the `dlloc` directory.

    If `extract`, also extract that .tar.gz file.
    """
    import os
    from six.moves.urllib.request import urlretrieve

    if url is None:
        url = _find_sofa_url_on_web_page()

    fn = url.split('/')[-1]
    if not os.path.isdir(dlloc):
        raise ValueError('Requested dlloc {0} is not a directory.'.format(dlloc))

    fnpath = os.path.join(dlloc, fn)
    if verbose:
        print('Downloading {fn} to {fnpath}'.format(fn=fn, fnpath=fnpath))
    retfn, headers = urlretrieve(url, fnpath)

    return retfn


def _find_sofa_url_on_web_page(url='http://www.iausofa.org/current_C.html'):
    """
    Finds and returns the download URL for the latest C SOFA.
    """
    from urllib.request import urlopen
    from html.parser import HTMLParser

    # Create a subclass to override the handler methods.
    class SOFAParser(HTMLParser):
        def __init__(self):
            self.matched_urls = []
            super().__init__()

        def handle_starttag(self, tag, attrs):
            if tag == 'a' and attrs[-1][-1].endswith('.tar.gz'):
                self.matched_urls.append(attrs[-1][-1])

    parser = SOFAParser()
    u = urlopen(url)
    try:
        for ln in u:
            parser.feed(ln.decode())
    finally:
        u.close()

    baseurl = '/'.join(url.split('/')[:-1])
    fullurls = [(baseurl + m) for m in parser.matched_urls]

    if len(fullurls) != 1:
        raise ValueError('Found *multiple* possible downloads: ' +
                         str(fullurls))

    return fullurls[0]


if __name__ == '__main__':
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
                        'directory.')
    parser.add_argument('--copyright-year', '-y', default=None,
                        help='The "current" year for the purposes of the end '
                              'of the copyright in each file.  If not given, '
                              'defaults to the current year when this script '
                              'is run.')
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
            # Try to open the file as a tar file.
            f = tarfile.open(args.sofafile)
            f.close()
        except (IOError, tarfile.ReadError) as e:
            print('requested sofafile "{0}" is not a valid tar file: '
                  '"{1}"'.format(args.sofafile, e), file=sys.stderr)
            sys.exit(1)
        # All is ok - use the file below.
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
            sofatarfn = lstar[0]  # There is only one.

    if not args.quiet:
        print('Using sofa tarfile "{0}" for reprocessing.'.format(sofatarfn))

    reprocess_sofa_tarfile(sofatarfn, verbose=not args.quiet,
                           copyrightyear=args.copyright_year)

    if not args.quiet:
        print('\nCreated new set of source files based on SOFA version '
              '"{0}".'.format(sofatarfn.replace('sofa_c-', '').replace('.tar.gz', '')))
        print('Be sure to update any relevant version information when you '
              'copy this to its new home.')
