import sys
from twisted.internet.protocol import Factory
from twisted.logger import (FileLogObserver, FilteringLogObserver, globalLogPublisher, Logger,
                            LogLevel, LogLevelFilterPredicate, formatEvent, formatTime)
from twisted.python.logfile import DailyLogFile


def log_event_format(event):
    return u"{0} [{1}]: {2}\n".format(formatTime(event["log_time"]),
                                      event["log_level"].name.upper(),
                                      formatEvent(event))


# Disable Factory starting and stopping log messages
Factory.noisy = False
log = Logger("bwscanner")


def setup_logging(log_level, log_name, log_directory=""):
    """
    Configure the logger to use the specified log file and log level
    """
    log_filter = LogLevelFilterPredicate()
    log_filter.setLogLevelForNamespace(
        "bwscanner", LogLevel.levelWithName(log_level.lower()))

    # Set up logging
    log_file = DailyLogFile(log_name, log_directory)
    file_observer = FileLogObserver(log_file, log_event_format)
    console_observer = FileLogObserver(sys.stdout, log_event_format)

    file_filter_observer = FilteringLogObserver(file_observer, (log_filter,))
    console_filter_observer = FilteringLogObserver(
        console_observer, (log_filter,))

    globalLogPublisher.addObserver(file_filter_observer)
    globalLogPublisher.addObserver(console_filter_observer)
