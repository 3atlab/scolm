import datetime

import log2seq.header
from log2seq import LogParser
from log2seq import preset


CODEBASE_PATH = "../../../dhcpcd"
DATABASE_FILE = "dhcpcd_db.pkl"
TEST_FILE = "./dhcpcd.log"
SPECIAL_RULES = {}
LOGGING_FUNCTIONS = [
    { "name": "logdebug",       "format_string_pos": 0 },
    { "name": "logdebugx",      "format_string_pos": 0 },
    { "name": "loginfo",        "format_string_pos": 0 },
    { "name": "loginfox",       "format_string_pos": 0 },
    { "name": "logwarn",        "format_string_pos": 0 },
    { "name": "logwarnx",       "format_string_pos": 0 },
    { "name": "logerr",         "format_string_pos": 0 },
    { "name": "logerrx",        "format_string_pos": 0 },
    { "name": "logmessage",     "format_string_pos": 1 },
    { "name": "logerrmessage",  "format_string_pos": 1 },
]


separators = " :[]"

log_header_rules = [
    log2seq.header.MonthAbbreviation(),
    log2seq.header.Digit("day"),
    log2seq.header.Time(),
    log2seq.header.Hostname("host"),
    log2seq.header.UserItem("component", r"[a-zA-Z0-9()._-]+"),
    log2seq.header.Digit("processid"),
    log2seq.header.Statement()
]


format_string_header_rules = [
    log2seq.header.Statement()
]

defaults = {
    "host": "N/A",
    "year": datetime.datetime.now().year,
    "month": datetime.datetime.now().month,
    "day": datetime.datetime.now().day,
}

header_parser = log2seq.header.HeaderParser(log_header_rules, separator=separators, defaults=defaults)
format_string_header_parser = log2seq.header.HeaderParser(format_string_header_rules, separator=separators, defaults=defaults)

statement_parser = preset.default_statement_parser()

log_parser = LogParser(header_parser, statement_parser)
format_string_parser = LogParser(format_string_header_parser, statement_parser)
