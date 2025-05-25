import math
import re

import numpy


FORMAT_SPECIFIER_GENERIC = r"\%(?P<flags>[ 0#+-]?)"             \
                           r"(?P<width>(?:[1-9]\d*|\*)?)"       \
                           r"(?P<precision>(?:\.(?:\d+|\*)?)?)" \
                           r"(?P<length>(?:[hl]{1,2}|[jztL])?)" \
                           r"(?P<spec>[diuoxXeEfgGaAcpsSn])"

MEANINGLESS_STRS = [ ':', ' ', '->' ]


class NullStream:
    def write(self, *args, **kwargs):
        ...

    def writelines(self, *args, **kwargs):
        ...

    def close(self, *args, **kwargs):
        ...


def get_occurence_lines(function, source_lines):
    line_numbers = []

    # Skip wrapper functions (vnc_zlog_debug_verbose for zlog_debug for example)
    regex = re.compile(fr"(?<!\w){function}[ |\n|\t]*\(")

    for line_number, line in enumerate(source_lines):
        if regex.search(line):
            line_numbers.append(line_number + 1)

    return line_numbers


def find_caller(line_number, ctags_data):
    for function in ctags_data:
        if function['line'] < line_number < function['end']:
            return function  # Return full object
    return None


def format_specifier_to_regex(match) -> str:
    flags, width, _, _, spec = match.groups()

    padding_char = " "
    padding_direction = "left"

    if spec in "xX":
        regex = r"[0-9a-fA-F]+"

        if "#" in flags:
            regex = f"0{spec}" + regex

    elif spec in "diou":
        regex = r"\-?\d+"

    elif spec in "fFeEaA":
        if spec in "aA":
            if spec == "a":
                regex = r"(?:\-?0x[0-9a-f](.[0-9a-f]*)?p[\+\-]\d+"
            else:  # spec == "A"
                regex = r"(?:\-?0x[0-9A-F](.[0-9A-F]*)?p[\+\-]\d+"

        elif spec in "eE":
            regex = rf"(?:\-?\d+(?:\.\d*)?{spec}[\+\-]\d\d+"

        else:  # spec in "fF":
            regex = r"(?:\-?\d+(?:\.\d*)?"

        if spec in "fea":
            regex = regex + r")|(?:\-inf(?:inity)?|nan)"
        else:  # spec in "FEA":
            regex = regex + r")|(?:\-INF(?:INITY)?|NAN)"

    elif spec in "gG":
        if spec == "g":
            regex = r"(?:\-?\d+(?:\.\d*)?(?:e[\+\-]\d\d+)?)|(?:\-?inf(?:inity)?|nan)"
        else:
            regex = r"(?:\-?\d+(?:\.\d*)?(?:E[\+\-]\d\d+)?)|(?:\-?INF(?:INITY)?|NAN)"

    elif spec == "c":
        regex = r"."

    elif spec == "s":
        regex = r".*?"

    elif spec == "p":
        regex = r"0x[0-9a-fA-F]+"

    else:
        raise Exception(f"Unknown format specifier: {spec}")

    regex = "(" + regex + ")"

    # Configuring padding (this block and the one below)
    if "+" in flags:
        regex = r"\+?" + regex
    elif " " in flags:
        regex = r"\ ?" + regex

    if "-" in flags:
        padding_direction = "right"
    elif "0" in flags:
        padding_char = "0"

    # Applying padding
    if width == "*":
        if padding_direction == "left":
            regex = re.escape(padding_char) + "*" + regex
        else:  # if padding_direction == "right"
            regex = regex + re.escape(padding_char) + "*"
    elif width != '':
        width = int(width)

        if padding_direction == "left":
            regex = re.escape(padding_char) + f"{{0,{width}}}" + regex
        else:  # if padding_direction == "right"
            regex = regex + re.escape(padding_char) + f"{{0,{width}}}"

    return regex


def regexify_format_str(string, logging_function):
    res = ""
    i = 0
    for match in re.finditer(FORMAT_SPECIFIER_GENERIC, string):
        res += re.escape(string[i:match.start()])
        res += format_specifier_to_regex(match)

        i = match.end()

    res += re.escape(string[i:])

    if "prefix" in logging_function:
        res = logging_function["prefix"] + res

    if "suffix" in logging_function:
        res = res + logging_function["suffix"]

    return "^" + res + "$"


def extract_args(code: str) -> list[str]:
    quotes_count = 0
    parenthesis = 0
    braces = 0
    brackets = 0

    args = []

    for i, char in enumerate(code):
        if char == '(':
            code = code[i:]
            break

    index = 1

    for i, char in enumerate(code):
        if char == '"' and ((i == 0) or (i > 0 and code[i-1] != '\\')):
            quotes_count += 1

        elif quotes_count % 2 == 0:
            if char == ',' and parenthesis == 1 and brackets == 0 and braces == 0:
                args.append(code[index:i].strip(" \n\t"))
                index = i + 1

            elif char == '(':
                parenthesis += 1

            elif char == ')':
                parenthesis -= 1

            elif char == '{':
                braces += 1

            elif char == '}':
                braces -= 1

            elif char == '[':
                brackets += 1

            elif char == ']':
                brackets -= 1

    args.append(code[index:-1].strip(" \n\t"))

    if args == ['']:
        raise ValueError("Empty call?")

    return args


def extract_templates_from_format_string(format_string: str, logging_function: dict, special_rules: dict[str, str]) -> tuple[str, str]:
    format_string_clean = re.sub(r"\"\s*\"", '', format_string)
    matches = list(re.finditer(r"\"((?:(?=(?:\\)*)\\.|.)*?)\"", format_string_clean))

    concatenated = '%$$'.join([
        match.group(1).encode().decode("unicode_escape").strip("\n")
        for match in matches
    ])

    try:
        if matches[0].start() > 0:
            concatenated = "%$$" + concatenated
        if matches[-1].end() < len(format_string_clean):
            concatenated = concatenated + "%$$"

        concatenated = re.sub(r"\%\%?\$\$", "%s", concatenated)
    except Exception:
        raise ValueError("Code is not a regular logging function call")

    if is_generic_format_string(concatenated, special_rules):
        raise ValueError("Useless template")  # Skip useless format strings such as "%s" or "%s: %d"

    # Escape %%
    concatenated = concatenated.replace("%%", "$$%$$")

    # Preprocess for custom specifiers
    for rule, placeholder in special_rules.items():
        # We need to replace with some markers so it doesn't get misinterpreted on the next step
        concatenated = re.sub(rule, placeholder, concatenated)

    # Don't forget to remove markers where not wanted
    regex = regexify_format_str(concatenated, logging_function).replace(r"\$\$", '')
    amulog_tpl = formatstring2amulog(concatenated.replace("\n", ""), logging_function)

    return regex, amulog_tpl


def log2words(log: str) -> list[str]:
    return re.split(r"\s+", log.strip(" \n\t"))  # Remove all multiple spaces


def formatstring2amulog(format_string: str, logging_function) -> str:
    words = log2words(format_string)

    res = ' '.join(map(
        lambda word: "**" if "%" in word else word,
        words
    ))

    if "prefix" in logging_function:
        res = "** " + res

    if "suffix" in logging_function:
        res = res + " **"

    return res


def is_generic_format_string(string, special_rules):
    for rule in special_rules:
        string = re.sub(rule, '', string)

    string = re.sub(FORMAT_SPECIFIER_GENERIC, '', string)

    for substr in MEANINGLESS_STRS:
        string = string.replace(substr, '')

    return string == ''


def is_generic_amulog(amulog_tpl: str):
    return amulog_tpl.replace('**', '').strip(' ') == ''


def template_sorter(regex: str) -> float:
    pos = regex.find("(.*?)")
    if pos == -1:
        pos = math.inf
    return pos


def find_end_of_function_call(code: str) -> int:
    quotes_count = 0
    parenthesis_count = 0
    for i, char in enumerate(code):
        if char == ')' and quotes_count % 2 == 0 and parenthesis_count == 1:
            return i + 1
        elif char == '(' and quotes_count % 2 == 0:
            parenthesis_count += 1
        elif char == ')' and quotes_count % 2 == 0:
            parenthesis_count -= 1
        if char == '"' and i > 0 and code[i-1] != '\\':
            quotes_count += 1
    return -1


# =========================================================
# ------- Credits to KOBAYASHI Satoru and NGUYEN Thieu ----

class Config:
    SPE_CHAR = "**"


WILDCARD_REGEX = re.compile(re.escape(Config.SPE_CHAR))
WHITESPACE_REGEX = re.compile(r"\s+")


def reformat_template(pattern, message):
    # match variable parts of the message with given template
    matchobj = re.match(pattern, message)
    assert matchobj is not None

    # get boolean index of variable part in the message
    variable_index = numpy.array([False] * len(message))
    n_variables = len(matchobj.groups())
    for i in range(n_variables):
        # i+1 because matchobject group index starts from 1
        variable_index[matchobj.start(i+1):matchobj.end(i+1)] = True

    # get chr index of segmented words of the message
    segmented_word_span = []  # tuple of (start, end) corresponding to chr index of words
    start_point = 0
    while start_point < len(message):
        matchobj = WHITESPACE_REGEX.search(message[start_point:])
        if matchobj:
            segmented_word_span.append((start_point, start_point + matchobj.start()))
            start_point = start_point + matchobj.end()
        else:
            segmented_word_span.append((start_point, len(message)))
            break

    # generate new template that can be consistently segmented with whitespaces
    new_tpl = []
    for wstart, wend in segmented_word_span:
        if True in variable_index[wstart:wend]:
            # a word including variable part -> replace with one wildcard
            new_tpl.append(Config.SPE_CHAR)
        else:
            # a word without variable part -> as is
            new_tpl.append(message[wstart:wend])
    return " ".join(new_tpl)

# =========================================================
