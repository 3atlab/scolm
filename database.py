import json
import os.path
import pickle
import re
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime

import utils

from amulog.lt_search import LTSearchTreeNew
from log2seq._common import LogParser


def verbose_print(*args, **kwargs):
    print(*args, **kwargs, file=sys.stderr)


class Database:
    DEFAULT_DB_PATH = "db.pkl"

    @staticmethod
    def benchmark(function, logs: list[str], title="bench_details", *args, **kwargs):
        found_counter = 0
        match_time = 0
        total_time = 0
        n = len(logs)

        no_matches = [0] * 10

        records = []

        for i in range(n):
            log = logs[i]
            try:
                tic = time.time()
                matches = function(log, *args, **kwargs)
                toc = time.time()
            except Exception as err:
                print("Exception while executing the matching algorithm:", err)
                continue

            verbose_print(f"\r--- {str(i+1).zfill(len(str(n)))}/{n} ({toc - tic} s) ({len(matches)} matches)    ", end='')

            if len(matches) > 0:
                found_counter += 1
                match_time += toc - tic

            total_time += toc - tic
            records.append({ "result": matches, "time": toc - tic, "log": log })

            no_matches[len(matches)] += 1

        verbose_print(f"\nResults on {n} logs for {title}:")
        verbose_print(f" - Total time:\t\t\t{total_time:f} seconds")
        verbose_print(f" - Average per log:\t\t{total_time / n:f} sec")
        verbose_print(f" - When a match exists:\t\t{match_time / n:f} sec")
        verbose_print(f" - Match rate on given dataset:\t{100 * found_counter / n:.2f}%")
        verbose_print( " - Number of results:")
        for i, number in enumerate(no_matches):
            verbose_print(f"\t- {i} results:\t{number}")

        filename = title + f"{datetime.now().isoformat().replace(':', '.')}.pkl"
        with open(os.path.join("benchmarks", filename), "wb") as f:
            pickle.dump(records, f)

        return total_time

    @staticmethod
    def _find_logging_occurences_in_source(logging_functions: list[dict], codebase: str) -> list:
        logging_files = []
        all_c_file_paths = Path(codebase).rglob('*.c')

        for i, path in enumerate(all_c_file_paths):
            with open(path, 'r', encoding="utf8", errors="ignore") as file:
                source_code = file.read()

            source_lines = source_code.split('\n')

            # Get line numbers for each file where any logging function appears
            for function in logging_functions:
                if function["name"] not in source_code:
                    continue  # Skip it

                line_numbers = utils.get_occurence_lines(function["name"], source_lines)

                logging_files.append([ str(path), line_numbers, function ])

            verbose_print('\rFiltering files for logging functions...', i, 'processed', end='')

        verbose_print()
        return logging_files

    @staticmethod
    def _find_logs_callers(logging_files: list) -> list[dict]:
        verbose_print('Parsing files... ', end='')
        log_sources = []
        count = 0
        total = len(logging_files)

        for path, line_numbers, function in logging_files:
            out = subprocess.check_output([ 'ctags', '--fields=+ne-tP', '--output-format=json', '--c-kinds=f', '-o', '-', path ])
            # We assume nothing crashed the subprocess
            out = '[' + out.decode()[:-1].replace('\n', ',') + ']'  # Convert multiple json objects to a json list of objects

            ctags_data = json.loads(out)

            # For each occurence of the logging function, check whether a C function contains it
            for line_number in line_numbers:
                caller = utils.find_caller(line_number, ctags_data)

                if caller is not None:  # Caller was found
                    log_sources.append(caller | {
                        "logging_line": line_number,
                        "logging_function": function,
                    })
                else:
                    # Caller not found, add the entry although with less information than with ctags
                    log_sources.append({
                        "path": path,
                        "logging_line": line_number,
                        "logging_function": function,
                    })

            count += 1
            verbose_print('\rParsing files...', count, 'of', total, end='')

        verbose_print()
        return log_sources

    @staticmethod
    def _generate_templates(logs_callers: list[dict], special_rules) -> list[dict]:
        database = []
        count = 0
        total = len(logs_callers)

        for occurrence in logs_callers:
            count += 1

            with open(occurrence['path'], 'r', encoding="utf8") as f:
                source_code = f.read()

            relevant_source_code = source_code.split('\n', occurrence['logging_line'] - 1)[-1]

            # Adjusting for the beginning of the logging function
            match = re.search(
                rf"\W{occurrence['logging_function']['name']}(?: |\t|\n|)*\(",
                relevant_source_code[:relevant_source_code.find("\n")]
            )
            if match is None:
                continue

            beginning = match.start() + 1
            relevant_source_code = relevant_source_code[beginning:]

            # Detecting the end of the function call
            end = utils.find_end_of_function_call(relevant_source_code)

            if end == -1:
                continue

            function_call = relevant_source_code[:end]

            format_string_pos = occurrence["logging_function"]["format_string_pos"]

            try:
                args = utils.extract_args(function_call)
                regex_template, amulog_tpl = utils.extract_templates_from_format_string(
                    args[format_string_pos].replace("\n", ""),
                    occurrence["logging_function"],
                    special_rules
                )
            except ValueError:
                continue  # We sometimes encounter logging functions that are invalid or useless, skip them

            database.append(occurrence | { "template": re.compile(regex_template), "amulog_template": amulog_tpl })

            verbose_print('\rGathering templates...', count, 'of', total, end=' ')

        verbose_print(len(database), "usable templates")
        return database

    @staticmethod
    def _group_duplicates(occurences: list[dict]) -> dict[re.Pattern, list[dict]]:
        total = len(occurences)
        templates_clean = {}
        for i, occurence in enumerate(occurences):
            regex: re.Pattern = occurence["template"]
            occurence = { key: value for key, value in occurence.items() if key not in ( "template", "_type", "kind", "format_string_pos" ) }

            # If it's the first time we see this regex template we create an entry with the regex as key
            if regex not in templates_clean:
                templates_clean[regex] = [ occurence ]  # Add it to the list

            else:
                # Otherwise we add it to the right list
                templates_clean[regex].append(occurence)

            verbose_print("\rGrouping", i, "of", total, end='... ')

        verbose_print(len(templates_clean), "unique templates")
        return templates_clean

    def __init__(self, codebase_path: str, db_path=None, verbose=False):
        self.regexdb: dict[re.Pattern, list] = {}
        self.regextpl: list[re.Pattern] = []
        self.amulog_templates_map: dict[str, set] = {}
        self.amulog_templates: list[str] = []
        self.wspt = LTSearchTreeNew()
        self.codebase_path = codebase_path
        self.db_path = db_path or Database.DEFAULT_DB_PATH
        self.verbose_stream = sys.stderr if verbose else utils.NullStream()
        self.log2seq_parser: LogParser

        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs("benchmarks", exist_ok=True)

    def build_db(self, logging_functions: list[dict], special_rules, force_rebuild=False, prefill_wspt=True):
        if not force_rebuild and self.db_path and os.path.exists(self.db_path):
            # Load database
            with open(self.db_path, 'rb') as f:
                templates_clean = pickle.load(f)

        else:
            # Construct database by parsing
            logging_files = Database._find_logging_occurences_in_source(logging_functions, self.codebase_path)
            logs_callers = Database._find_logs_callers(logging_files)
            templates = Database._generate_templates(logs_callers, special_rules)
            templates_clean = Database._group_duplicates(templates)

            with open(self.db_path, 'wb') as f:
                pickle.dump(templates_clean, f)

        # amulogtpl_map is a dict which values are the keys in regexdb and regextpl
        # it is useful when we need to associate an amulog-style log to the corresponding regexes
        self.regexdb = templates_clean
        self.regextpl = list(self.regexdb.keys())

        if prefill_wspt:
            # Fill up self.amulogtpl_map with the amulog templates and their corresponding regex
            for regex, occurence in templates_clean.items():
                amulog_tpl = occurence[0]["amulog_template"]

                if amulog_tpl not in self.amulog_templates_map:
                    self.amulog_templates_map[amulog_tpl] = set()

                self.amulog_templates_map[amulog_tpl].add(regex)

            # Now fill up the data structure with the templates (tree is recommended)
            self.amulog_templates = list(self.amulog_templates_map.keys())
            for i, amulog_template in enumerate(self.amulog_templates):
                words = amulog_template.split(" ")
                self.wspt.add(i, words)

    def set_log2seq_parser(self, log2seq_parser: LogParser):
        self.log2seq_parser = log2seq_parser

    def _find_regex_matches(self, log: str, regex_templates: set[re.Pattern]) -> dict[str, list]:
        res = {}
        for template in regex_templates:
            if template.match(log):
                res[template.pattern] = self.regexdb[template]
        return res

    def find_matches(self, line: str, regex_fallback=True):
        parsed = self.log2seq_parser.process_line(line)
        if parsed is None:
            return { }

        log = parsed["message"]

        words = utils.log2words(log)

        tpl_index = self.wspt.search(words)

        if tpl_index is not None:
            # We found a match in the ltmap, return all matching candidates
            amulog_tpl = self.amulog_templates[tpl_index]  # Amulog template corresponding to the index

            if regex_fallback and utils.is_generic_amulog(amulog_tpl):
                return self._fallback_regex_matching(log)

            # Retreive all the regex templates associated with that amulog template
            regex_candidates = self.amulog_templates_map[amulog_tpl]

            matching_regexes = self._find_regex_matches(log, regex_candidates)

            return matching_regexes
        else:
            if regex_fallback:
                # The Amulog-tree based approach did not find any match for the log, we fallback on the slow
                # but exhaustive regex matching and will create new amulog templates based on our results
                return self._fallback_regex_matching(log)

            else:
                return { }

    def find_regex_matches(self, line: str, regex_templates: set[re.Pattern]) -> dict[str, list]:
        parsed = self.log2seq_parser.process_line(line)

        if parsed is None:
            return { }

        log = parsed["message"]
        return self._find_regex_matches(log, regex_templates)

    def _fallback_regex_matching(self, log: str):
        """
        Fallback method for exhaustive regex matching and creating new amulog templates.
        """

        templates = set()

        # We iterate on Amulog templates in order to have the connection with their corresp. regex templates
        for regex_template in self.regextpl:
            if regex_template.match(log):
                templates.add(( regex_template, self.regexdb[regex_template][0]["amulog_template"] ))

        matching_regexes = {}

        # Now we create and insert new templates into the tree
        min_id = len(self.amulog_templates)
        i = 0
        flag = False
        for (regex_template, amulog_template, *_) in templates:
            try:
                new_amulog = utils.reformat_template(regex_template, log)
            except AssertionError:
                # The regex matches but Amulog failed to produce a working modified template
                print(f'Cannot adjust template "{amulog_template}" for log: "{log}". Corresponding '
                      f'regex: /{regex_template}/')
                flag = True
                continue

            # Return the subset containing regexes Amulog is able to use (the rest is usually false positives)
            matching_regexes[regex_template] = self.regexdb[regex_template]

            # if not utils.is_generic_amulog(new_amulog):
            # If the new amulog template is not "generic" (eg, ** ** ** **) then add it to the tree
            self.wspt.add(min_id + i, new_amulog.split(" "))
            i += 1

            # And into the rest of the database
            self.amulog_templates.append(new_amulog)
            if new_amulog not in self.amulog_templates_map:
                self.amulog_templates_map[new_amulog] = set()
            self.amulog_templates_map[new_amulog].add(regex_template)

        if flag:
            verbose_print(matching_regexes)

        return matching_regexes
