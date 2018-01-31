import os.path
from shutil import copyfile
from ConfigParser import SafeConfigParser

from bwscanner.logger import log


def read_config(cfg_path):
    log.debug('reading config %s' % cfg_path)
    if not config_exists(cfg_path):
        copy_config(cfg_path)
    parser = SafeConfigParser()
    parser.read([cfg_path])
    # FIXME: handle section names
    section = 'default'
    return dict(parser.items(section))


def config_exists(cfg_path):
    return os.path.isfile(cfg_path)


def copy_config(cfg_path, cfg_default_path=None):
    if cfg_default_path is None:
        cfg_default_path = os.path.join(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))), 'data', 'config.ini')
    log.debug("cfg_default_path %s" % cfg_default_path)
    copyfile(cfg_default_path, cfg_path)
