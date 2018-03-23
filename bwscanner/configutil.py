import os.path
from ConfigParser import SafeConfigParser
from pkg_resources import resource_string

from bwscanner.logger import log


def read_config(cfg_path):
    log.debug('Reading config %s' % cfg_path)
    if not config_exists(cfg_path):
        copy_config(cfg_path)
    parser = SafeConfigParser()
    parser.read([cfg_path])
    cfg_dict = dict(parser.items('default'))
    int_keys = cfg_dict['int_keys'].split(' ')
    bool_keys = cfg_dict['bool_keys'].split(' ')
    for k in int_keys:
        cfg_dict[k] = int(cfg_dict[k])
    for i in bool_keys:
        cfg_dict[k] = bool(cfg_dict[k])
    bw_files = dict(parser.items('bw_files'))
    cfg_bw_files = {}
    for k, v in bw_files.items():
        print(k, v)
        if 'm' in k:
            number = k.rstrip('m')
            size = 1024 * int(number)
            cfg_bw_files[size] = (k.upper(), v)
    cfg_dict['bw_files'] = cfg_bw_files
    return cfg_dict


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
