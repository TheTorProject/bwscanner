from setuptools import setup, find_packages

__version__ = '0.0.1'
__author__ = 'aagbsn'
__contact__ = 'aagbsn@torproject.org'
__url__ = 'https://github.com/TheTorProject/bwscanner'  # TODO: publish this
__license__ = 'GPL'
__copyright__ = ''

setup(name='bwscanner',  # TODO: pick a better name
      version=__version__,
      description='Tor Bandwidth Scanner',
      long_description=__doc__,
      keywords=['python', 'twisted', 'txtorcon', 'tor', 'metrics'],
      install_requires=open('requirements.txt').readlines(),
      classifiers=[
        'Framework :: Twisted',
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GPL License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2.7',
        'Topic :: System :: Networking',
        'Topic :: Internet :: Proxy Servers',
        'Topic :: Internet',
        'Topic :: Security',
        'Topic :: Utilities'],
      author=__author__,
      author_email=__contact__,
      url=__url__,
      license=__license__,
      packages=find_packages(),
      extras_require={
        'dev': ['ipython', 'pyflakes', 'pep8'],
        'test': ['tox', 'pytest'],
        'doc': ['sphinx', 'pylint']
      },
      python_requires=">=2.7",
      # data_files = [('path', ['filename'])]
      include_package_data=True,
      entry_points={
        "console_scripts": [
            'bwscan = bwscanner.scanner:start',
        ]},
     )
