|GitHub license| |PyPI| |Read the Docs| |Travis| |Updates| |Codecov| |Gitter|

.. |honeycomb_logo| image:: https://i.imgur.com/x9rdRlF.png
   :alt: Honeycomb
   :target: https://github.com/Cymmetria/honeycomb
.. |GitHub license| image:: https://img.shields.io/github/license/Cymmetria/honeycomb.svg
   :alt: GitHub license
   :target: https://github.com/Cymmetria/honeycomb/blob/master/LICENSE
.. |PyPI| image:: https://img.shields.io/pypi/v/honeycomb-framework.svg
   :alt: PyPI
   :target: https://pypi.org/project/honeycomb-framework/
.. |Read the Docs| image:: https://img.shields.io/readthedocs/honeycomb/master.svg
   :alt: Read the Docs
   :target: http://honeycomb.cymmetria.com
.. |Travis| image:: https://img.shields.io/travis/Cymmetria/honeycomb.svg
   :alt: Travis
   :target: https://travis-ci.com/Cymmetria/honeycomb
.. |Updates| image:: https://pyup.io/repos/github/Cymmetria/honeycomb/shield.svg
    :target: https://pyup.io/repos/github/Cymmetria/honeycomb/
    :alt: Updates
.. |Codecov| image:: https://img.shields.io/codecov/c/github/Cymmetria/honeycomb.svg
   :alt: Codecov
   :target: https://codecov.io/gh/Cymmetria/honeycomb
.. |Gitter| image:: https://badges.gitter.im/cymmetria/honeycomb.svg
   :alt: Join the chat at https://gitter.im/cymmetria/honeycomb
   :target: https://gitter.im/cymmetria/honeycomb

|honeycomb_logo|

Honeycomb - An extensible honeypot framework
============================================

Honeycomb is an open-source honeypot framework created by Cymmetria_.

.. _Cymmetria: https://cymmetria.com

Honeycomb allows running honeypots with various integrations from a public library of plugins at https://github.com/Cymmetria/honeycomb_plugins

Writing new honeypot services and integrations for honeycomb is super easy!
See the `plugins repo <http://honeycomb.cymmetria.com/projects/honeycomb-plugins/en/latest/>`_ for more info.

Full CLI documentation can be found at http://honeycomb.cymmetria.com/en/latest/cli.html

Usage
-----

Using pip::

    $ pip install honeycomb-framework
    $ honeycomb --help

Using Docker::

    $ docker run -v honeycomb.yml:/usr/share/honeycomb/honeycomb.yml cymmetria/honeycomb
