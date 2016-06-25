from setuptools import setup, find_packages

__version__ = '0.0.1'
__author__ = 'aagbsn'
__contact__ = 'aagbsn@torproject.org'
__url__ = '' # TODO: publish this
__license__ = ''
__copyright__ = ''

setup(name='bwscanner', # TODO: pick a better name
      version=__version__,
      description='Tor Bandwidth Scanner',
      long_description=__doc__,
      keywords=['python', 'twisted', 'txtorcon', 'tor', 'metrics'],
      install_requires=open('requirements.txt').readlines(),

      # TODO: complete the classifiers
      #classifiers = ['Framework :: Twisted', 'Programming Language :: Python']
      classifiers=[],
      author=__author__,
      author_email=__contact__,
      url=__url__,
      license=__license__,
      packages=find_packages(),
      # data_files = [('path', ['filename'])]
      data_files=[]
     )
