#
""""""
import os.path
import click

DEFAULT = {
    'data_dir': click.get_app_dir('bwscanner'),
    'measurement_dir': os.path.join(click.get_app_dir('bwscanner'),
                                    'measurements'),
    'tor_dir': os.path.join(click.get_app_dir('bwscanner'),
                            'tordata'),
    'logfile': os.path.join(click.get_app_dir('bwscanner'),
                            'bwscanner.log'),
    'loglevel': 'debug',
    'baseurl': 'https://siv.sunet.se/bwauth/',
    'launch_tor': True,
    'circuit_build_timeout': 20,
    'partitions': 1,
    'current_partition': 1,
    'timeout': 120,
    'request_limit': 10
}
BW_FILES = {
    64*1024: ("64M", "6258de4f4d602be75a3458117b29d2c580c4bcb7ba5b9d2c4135c7603109f554"),
    32*1024: ("32M", "5a5d66d7865f09498d776f20c9e9791b055a4fff357185f84fb4ecfca7da93f0"),
    16*1024: ("16M", "6258de4f4d602be75a3458117b29d2c580c4bcb7ba5b9d2c4135c7603109f554"),
    8*1024: ("8M", "738c5604295b9377f7636ce0c2c116f093bb50372f589a6c2332a3bb6bba096a"),
    4*1024: ("4M", "4daaa42377d3c87577797d44a8fa569038e7a9d6a5d417a09d8ba41a69456164"),
    2*1024: ("2M", "3e39b0bb92912cf1ad6c01fb7c9d592e814a691c61de1f649416f6bba2d15082"),
}
TOR_OPTIONS = {
    'LearnCircuitBuildTimeout': 0,  # Disable adaptive circuit timeouts.
    'CircuitBuildTimeout': 20,
    'UseEntryGuards': 0,  # Disable UseEntryGuards to avoid PathBias warnings.
    'UseMicroDescriptors': 0,
    'FetchUselessDescriptors': 1,
    'FetchDirInfoEarly': 1,
    'FetchDirInfoExtraEarly': 1,
    'SafeLogging': 0,
    'LogTimeGranularity': 1,
}
