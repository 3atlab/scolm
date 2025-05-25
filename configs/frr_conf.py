import datetime

import log2seq.header
from log2seq import LogParser
from log2seq import preset


CODEBASE_PATH = "../frr/"
DATABASE_FILE = "./data/frr_db.pkl"
TEST_FILE = "./sample_data/frr.log"
LOGGING_FUNCTIONS = [
    { "name": "flog_err_sys", "format_string_pos": 1 },
    { "name": "flog_err",     "format_string_pos": 1 },
    { "name": "flog_warn",    "format_string_pos": 1 },
    { "name": "zlog_err",     "format_string_pos": 0 },
    { "name": "zlog_debug",   "format_string_pos": 0 },
    { "name": "zlog_notice",  "format_string_pos": 0 },
    { "name": "zlog_info",    "format_string_pos": 0 },
    { "name": "zlog_warn",    "format_string_pos": 0 },
]
SPECIAL_RULES = {
    r"\%[0#+-]?[0-9*]*(?:\.\*?)?\d*(?:[hl]{1,2}|[jztL])?[diuoxXeEfgGaAcpsSn][A-Z0-9]+": "%s"
}


separators = "/ :[]\n\t"

log_header_rules = [
    log2seq.header.ItemGroup([
        log2seq.header.Digit("year"),
        log2seq.header.Digit("month"),
        log2seq.header.Digit("day"),
    ], separator=" /"),
    log2seq.header.Time(),
    log2seq.header.UserItem("component", r"[A-Z0-9]+"),
    log2seq.header.UserItem("element1", r"[A-Z0-9]{5}\-[A-Z0-9]{5}"),
    log2seq.header.UserItem("element2", r"EC\ \d+", optional=True),
    log2seq.header.Statement()
]

defaults = {
    "host": "N/A",
    "year": datetime.datetime.now().year,
    "month": datetime.datetime.now().month,
    "day": datetime.datetime.now().day,
}

header_parser = log2seq.header.HeaderParser(log_header_rules, separator=separators, defaults=defaults)

statement_parser = preset.default_statement_parser()

log_parser = LogParser(header_parser, statement_parser)
