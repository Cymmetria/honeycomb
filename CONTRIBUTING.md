# Contributing to Honeycomb

Pull requests are welcome! Please make sure to follow coding style requirements
and confirm all tests pass before opening a PR.

Honeycomb uses the latest stable versions of Python2/3, this guide uses pyenv
to make managing python versions easier but feel free to use whatever you like
as long as you pass the tests :)

## Set up development environment

Make sure you have both python 2.7 and 3.6 available as they are required for testing.

### Install pyenv
See https://github.com/pyenv/pyenv#installation for full instructions on how to install pyenv.
=======
Follow instructions to init pyenv and add it to your bashrc/zshrc file.

### Install python 2 and 3
    $ pyenv install 2.7.14
    $ pyenv install 3.6.3
    $ pyenv global 2.7.14 3.6.3


### Set up virtualenv and install honeycomb in editable mode
    $ git clone git@github.com:Cymmetria/honeycomb.git
    $ cd honeycomb
    $ virtualenv venv
    $ source venv/bin/activate
    $ pip install -r requirements-dev.txt  # will install tox
    $ pip install --editable .


### Make sure tests are working
    $ tox

This will run all the existing tests, do not start coding before you resolve any local configuration issues.
