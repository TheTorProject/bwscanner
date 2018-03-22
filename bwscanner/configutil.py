import os.path
from ConfigParser import SafeConfigParser
from pkg_resources import resource_string

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
    # FIXME: obtain the path instead of the content
    if cfg_default_path is None:
        content = resource_string(__name__, 'data/config.ini')
    else:
        with open(cfg_default_path) as fp:
            content = cfg_default_path.read()
    log.debug("cfg_default_path %s" % cfg_default_path)
    with open(cfg_path, 'w') as fp:
        fp.write(content)
