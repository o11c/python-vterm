This directory contains an *unmodified* copy of the vterm headers,
from the version that the python bindings were last modified for.

To update:

* grab the new headers and replace them in this directory.
* run `git diff`
* make any necessary changes to the CFFI code:
    * types and function declarations go in `vterm/_c_build.py`
    * macros and inline functions go in `vterm/c.py`
