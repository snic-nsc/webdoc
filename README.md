# webdoc
Generate static website catalog of installed software at NSC.

# Usage

`python nsc-webdoc.py SOFTWARE_ROOT`

SOFTWARE_ROOT is the root directory of your software is installed.

Generates static website in `./output/`, and a file name cache in `./filenames.cache`.

Options:

* -v,--verbose: Print extra info.
* -d,--dryrun: Don't actually do anything.
* -s,--system: Generate documentation for a specific system.
* -r,--rebuild: Scan file system and rebuild file name cache.

# Dependencies

* [Multimarkdown](http://fletcherpenney.net/multimarkdown/)
* Python2 packages: yaml, mako
