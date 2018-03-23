import os.path
from setuptools import setup, find_packages


def get_version():
    with open(os.path.join("bwscanner", "__init__.py")) as f:
        for line in f:
            if "__version__" in line.strip():
                version = line.split("=", 1)[1].strip().strip('"')
                return version


__version__ = get_version()
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
      data_files=[],
      entry_points={
        "console_scripts": [
            'bwscan = bwscanner.scanner:cli',
        ]},
     )
