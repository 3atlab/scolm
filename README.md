# SCOLM: Source Code Origins of Log Messages

SCOLM is a tool that lets developers and system operators identify real-world log messages and return their exact origin. By analysing the source code, SCOLM is able to build precise templates, and uses them to match log messages at very high speed; 1 million lines per minute single-threaded is the expected speed on modern hardware.

- Source: [https://github.com/3atlab/scolm](https://github.com/3atlab/scolm)
- Bug reports: [https://github.com/3atlab/scolm/issues](https://github.com/3atlab/scolm/issues)
- Author: [Gaspard Damoiseau-Malraux](https://github.com/biskweet)
- Maintainers: [Gaspard Damoiseau-Malraux](https://github.com/biskweet) and [Satoru Kobayashi](https://github.com/cpflat/)
- License: [https://opensource.org/license/apache-2-0](https://opensource.org/license/apache-2-0)

## Tutorial: how to use SCOLM

### Setup

- **⚠️ We recommend installing/updating [Amulog](https://github.com/amulog/amulog) manually from the official repository.**

With your Python virtual environment activated, clone Amulog and install it manually:
```bash
git clone https://github.com/amulog/amulog
cd amulog/
python3 setup.py install
```
In addition, [universal-ctags](https://github.com/universal-ctags/ctags) must be installed on you system for analysing the source code.

Finally, go back to the directory of SCOLM and run `pip install -r requirements.txt`.

### Preparing data

You can use any target software as long as it is coded in C language. The source code must exist locally on your machine, and the path specified in the config file must be consistent with the actual path to the source code. This is necessary for SCOLM to know which directory it should scan. Here is an example of a valid file tree:
```
/home/user/
├── frr/
│   └── ...  
└── scolm/
    ├── configs/
    │   ├── frr_conf.py <-- must reference /home/user/frr
    │   └── ...
    ├── main.py
    └── ...
```
Note: relative paths are also valid.

Once your config file is complete and the dependencies are installed, you can run the template generation with
```py
python3 main.py -c [CONFIG FILE RELATIVE PATH] [OPTIONS]
```
See the help flag `-h` for more information.

### Running SCOLM on log data

We provide sample data in this repository for you to try. It originates from FRRouting 8.5, meaning that in order to be able to scan the right source code, you must have the sources of FRR with HEAD positioned on branch `tags/frr-8.5`. Then, you can test SCOLM yourself simply by running the following command:
```bash
$ python3 main.py -c configs/frr_conf.py -b  # -b for "benchmark"
```
Output:
```
Filtering files for logging functions... 774 processed
Parsing files... 913 of 913
Gathering templates... 7509 of 7509 7421 usable templates
Grouping 7420 of 7421... 6481 unique templates
--- 456/456 (4.100799560546875e-05 s) (1 matches)     
Results on 456 logs for scolm:
 - Total time:      0.043059 seconds
 - Average per log:   0.000094 sec
 - When a match exists:   0.000094 sec
 - Match rate on given dataset: 100.00%
 - Number of results:
  - 0 results:  0
  - 1 results:  452
  - 2 results:  4
  - 3 results:  0
  - 4 results:  0
  - 5 results:  0
  - 6 results:  0
  - 7 results:  0
  - 8 results:  0
  - 9 results:  0
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

This work will be demonstrated at COMPSAC 2025.
