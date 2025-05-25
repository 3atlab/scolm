import argparse
import random
import importlib

from database import Database


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', "--conf", type=str, help='Specify configuration file', required=True)
    parser.add_argument('-b', "--benchmark", action='store_true', help='Run benchmarks')
    parser.add_argument('-f', "--forcerebuild", action='store_true', help='Force rebuilding the database from source')
    args = parser.parse_args()

    conf = importlib.import_module(args.conf.replace("/", ".").replace(".py", ""))

    FORCE_REBUILD = args.forcerebuild
    RUN_BENCHMARKS = args.benchmark

    db = Database(conf.CODEBASE_PATH, conf.DATABASE_FILE)

    db.build_db(conf.LOGGING_FUNCTIONS, conf.SPECIAL_RULES, force_rebuild=FORCE_REBUILD, prefill_wspt=True)
    db.set_log2seq_parser(conf.log_parser)

    if RUN_BENCHMARKS:
        with open(conf.TEST_FILE, "r", encoding="utf8") as f:
            logs = f.read().strip("\n").split("\n")

        random.shuffle(logs)

        test_logs = logs
        i = 1000000
        results = []
        res_set = dict()

        try:
            db.benchmark(db.find_matches, test_logs, title="scolm", regex_fallback=True)

        except KeyboardInterrupt:
            print("Stopped")
