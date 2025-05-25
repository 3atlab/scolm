# SCOLM: Source Code Origins of Log Messages

SCOLM is a tool that lets developers and system operators identify real-world log messages and return their exact origin. By analysing the source code, SCOLM is able to build precise templates, and uses them to match log messages at very high speed; 1 million lines per minute single-threaded is the expected speed on modern hardware.

## Tutorial: how to use SCOLM

### Running SCOLM on log data

**⚠️ We recommend installing/updating [Amulog](https://github.com/amulog/amulog) manually by cloning the official repository and running `python3 setup.py install`.** In addition, [universal-ctags](https://github.com/universal-ctags/ctags) must be installed on you system for analysing the source code.

We provide sample data in this repository for you to try. It originates from FRRouting 8.5, and you can test SCOLM yourself simply by running the following command:
```bash
$ python3 main.py -c configs/frr_conf.py -b
```

#### 1. Providing a valid config

SCOLM takes as input a Python config file (`example_conf.py`) which provides all the necessary information to parse code and build a database.

Examples of config files can be found in [`configs/`](https://github.com/3atlab/scolm/tree/main/release).
The information that needs to be filled out is:
- `CODEBASE_PATH`: path to the directory that contains the code of the target software
- `DATABASE_FILE`: path to the file where a snapshot of the DB should be stored ([`pickle`](https://docs.python.org/3/library/pickle.html) format)
- `LOGGING_FUNCTIONS`: a list of the logging functions that SCOLM should look for. The information for each function is a dictionary with the following keys/values:
  - `name`: *(str)* name of the function (e.g. _flog_err_, _printf_, etc.)
  - `format_string_pos`: *(int)* position of the format string in the original function's arguments. For example, the signature for _printf_ is `int printf(const char * format, ...)`, meaning that the value here should be `0`: the position of the format string is `0`. Another example is `void flog_err(int id, const char * format, ...)`: in that case, the value should be `1`.
- `SPECIAL_RULES`: *(dict[str, str])* when a software uses custom C format specifiers, this is the place to specify how to recognize those special format specifiers and how they should be treated (e.g. `{ "some regex": "%d", "other regex": "%f", ... }`).
- `separator`: *(str)* separator characters used in the log header part for proper parsing.
- `log_header_rules`: [log2seq](https://github.com/amulog/log2seq)-style header rules, see the configs provided for examples.

The rest of the config files should be identical from the that in the examples provided.

#### 2. Using SCOLM

1. **Running a benchmark from the provided config examples**

```
usage: main.py [-h] -c CONF [-b] [-f]

options:
  -h, --help            show this help message and exit
  -c CONF, --conf CONF  Specify configuration file
  -b, --benchmark       Run benchmark
  -f, --forcerebuild    Force rebuilding the database from source
```

2. **Running SCOLM from a script**

```py
# First, import the database class from the database file
from database import Database

# Also import the config file needed. That can be either by a static import:
import frr_conf as conf
# Or with a dynamic import from the arguments:
conf = importlib.import_module("frr_conf")  # No ".py" here, and / in the path are replaced with .

# Create an instance of the database and run the build
db = Database(conf.CODEBASE_PATH, conf.DATABASE_FILE)
db.build_db(conf.LOGGING_FUNCTIONS, conf.SPECIAL_RULES, force_rebuild=FORCE_REBUILD, prefill_wspt=True)
# By default, force_rebuild and prefill_wspt are set to True

# Now given a log message `log`, we simply run the search
log = "2023/07/19 08:20:22 ZEBRA: [HSYZM-HV7HF] Extended Error: Carrier for nexthop device is down"
results = db.find_matches(log, regex_fallback=True)
# regex_fallback defaults to True and indicates whether SCOLM should look into the regex table
# in case of a failed search in the WSPT
```

## Reference
If you use this code, please consider citing:
```bibtex
@inproceedings{DamoiseauMalraux2025,
  author = {Damoiseau-Malraux, Gaspard and Kobayashi, Satoru and Fukuda, Kensuke},
  title = {Automatically pinpointing original logging functions from log messages for network troubleshooting},
  year = {2025}
}
```
