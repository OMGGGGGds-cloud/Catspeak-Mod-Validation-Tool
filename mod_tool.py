#!/usr/bin/env python3
"""
Catspeak Mod Validation Tool  v2.0
====================================
Validates .meow (Catspeak) mod files, detects code errors,
and helps create new mods for any GameMaker game using Catspeak.

Usage:
  python mod_tool.py check <file.meow>         Validate a single mod file
  python mod_tool.py check-all [dir]           Validate all .meow files in directory
  python mod_tool.py init <name>               Create a new mod from template
  python mod_tool.py scan [dir]                List all mods in directory
  python mod_tool.py --generic check <file>    Pure Catspeak validation only
  python mod_tool.py --config <game.json> ...  Use custom game config
  python mod_tool.py --export-config <name>    Export a starter config file

Requirements: Python 3.7+ (no external dependencies)
"""

import sys
import os
import re
import json
from pathlib import Path
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple, Set
from datetime import datetime


# ============================================================================
# TOKENIZER / LEXER
# ============================================================================

class TokenType(Enum):
    # Keywords
    KW_LET = auto()
    KW_FUN = auto()
    KW_IF = auto()
    KW_ELSE = auto()
    KW_WHILE = auto()
    KW_RETURN = auto()
    KW_BREAK = auto()
    KW_CONTINUE = auto()
    KW_DO = auto()
    KW_MATCH = auto()
    KW_CASE = auto()
    KW_WITH = auto()
    KW_CATCH = auto()
    KW_THROW = auto()
    KW_NEW = auto()
    KW_AND = auto()
    KW_OR = auto()
    KW_XOR = auto()
    KW_TRUE = auto()
    KW_FALSE = auto()
    KW_UNDEFINED = auto()
    KW_INFINITY = auto()
    KW_NAN = auto()
    KW_SELF = auto()
    KW_OTHER = auto()
    KW_FOR = auto()       # reserved
    KW_LOOP = auto()      # reserved
    KW_PARAMS = auto()    # reserved
    KW_IMPL = auto()      # reserved

    # Literals
    IDENTIFIER = auto()
    RAW_IDENTIFIER = auto()
    NUMBER = auto()
    STRING = auto()
    CHAR = auto()
    COLOUR = auto()

    # Operators
    OP_ASSIGN = auto()        # =
    OP_ADD_ASSIGN = auto()    # +=
    OP_SUB_ASSIGN = auto()    # -=
    OP_MUL_ASSIGN = auto()    # *=
    OP_DIV_ASSIGN = auto()    # /=
    OP_ADD = auto()           # +
    OP_SUB = auto()           # -
    OP_MUL = auto()           # *
    OP_DIV = auto()           # /
    OP_INTDIV = auto()        # //
    OP_MOD = auto()           # %
    OP_EQ = auto()            # ==
    OP_NEQ = auto()           # !=
    OP_LT = auto()            # <
    OP_LTE = auto()           # <=
    OP_GT = auto()            # >
    OP_GTE = auto()           # >=
    OP_BITAND = auto()        # &
    OP_BITOR = auto()         # |
    OP_BITXOR = auto()        # ^
    OP_LSHIFT = auto()        # <<
    OP_RSHIFT = auto()        # >>
    OP_NOT = auto()           # !
    OP_BNOT = auto()          # ~
    OP_LPIPE = auto()         # <|
    OP_RPIPE = auto()         # |>

    # Punctuation
    DOT = auto()
    COMMA = auto()
    COLON = auto()
    SEMICOLON = auto()
    LPAREN = auto()
    RPAREN = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    LBRACE = auto()
    RBRACE = auto()

    # Special
    COMMENT = auto()
    NEWLINE = auto()
    EOF = auto()


KEYWORD_MAP: Dict[str, TokenType] = {
    "let": TokenType.KW_LET, "fun": TokenType.KW_FUN,
    "if": TokenType.KW_IF, "else": TokenType.KW_ELSE,
    "while": TokenType.KW_WHILE, "return": TokenType.KW_RETURN,
    "break": TokenType.KW_BREAK, "continue": TokenType.KW_CONTINUE,
    "do": TokenType.KW_DO, "match": TokenType.KW_MATCH,
    "case": TokenType.KW_CASE, "with": TokenType.KW_WITH,
    "catch": TokenType.KW_CATCH, "throw": TokenType.KW_THROW,
    "new": TokenType.KW_NEW,
    "and": TokenType.KW_AND, "or": TokenType.KW_OR, "xor": TokenType.KW_XOR,
    "true": TokenType.KW_TRUE, "false": TokenType.KW_FALSE,
    "undefined": TokenType.KW_UNDEFINED, "infinity": TokenType.KW_INFINITY,
    "NaN": TokenType.KW_NAN, "self": TokenType.KW_SELF,
    "other": TokenType.KW_OTHER, "for": TokenType.KW_FOR,
    "loop": TokenType.KW_LOOP, "params": TokenType.KW_PARAMS,
    "impl": TokenType.KW_IMPL,
}

# Reserved keywords that should not be used as identifiers
RESERVED_KEYWORDS = set(KEYWORD_MAP.keys())

# Catspeak operators sorted by length (longest first for greedy matching)
OPERATOR_MAP: List[Tuple[str, TokenType]] = sorted([
    ("+=", TokenType.OP_ADD_ASSIGN), ("-=", TokenType.OP_SUB_ASSIGN),
    ("*=", TokenType.OP_MUL_ASSIGN), ("/=", TokenType.OP_DIV_ASSIGN),
    ("==", TokenType.OP_EQ), ("!=", TokenType.OP_NEQ),
    ("<=", TokenType.OP_LTE), (">=", TokenType.OP_GTE),
    ("<<", TokenType.OP_LSHIFT), (">>", TokenType.OP_RSHIFT),
    ("<|", TokenType.OP_LPIPE), ("|>", TokenType.OP_RPIPE),
    ("//", TokenType.OP_INTDIV),
    ("=", TokenType.OP_ASSIGN), ("+", TokenType.OP_ADD),
    ("-", TokenType.OP_SUB), ("*", TokenType.OP_MUL),
    ("/", TokenType.OP_DIV), ("%", TokenType.OP_MOD),
    ("<", TokenType.OP_LT), (">", TokenType.OP_GT),
    ("&", TokenType.OP_BITAND), ("|", TokenType.OP_BITOR),
    ("^", TokenType.OP_BITXOR), ("!", TokenType.OP_NOT),
    ("~", TokenType.OP_BNOT),
], key=lambda x: -len(x[0]))


@dataclass
class Token:
    type: TokenType
    value: str
    line: int
    col: int

    def __repr__(self):
        return f"Token({self.type.name}, {self.value!r}, L{self.line}:{self.col})"


GML_TO_CATSPEAK_WARNINGS = {
    "var": "Use 'let' instead of 'var' for local variable declarations in Catspeak",
    "++": "Use 'x += 1' instead of 'x++' in Catspeak (++ is not an operator)",
    "--": "Use 'x -= 1' instead of 'x--' in Catspeak. Also, '--' starts a comment!",
    "function": "Use 'fun' keyword instead of 'function' in Catspeak",
    "for": "'for' loops don't exist in Catspeak. Use 'while' loops instead",
    "repeat": "'repeat' loops don't exist in Catspeak. Use 'while' loops instead",
    "switch": "'switch' doesn't exist in Catspeak. Use 'match' expressions instead",
    "globalvar": "Use 'global.xxx' syntax instead of 'globalvar' in Catspeak",
}


class LexerError(Exception):
    def __init__(self, message: str, line: int, col: int):
        self.message = message
        self.line = line
        self.col = col
        super().__init__(f"Line {line}:{col} - {message}")


class Lexer:
    """Tokenizes Catspeak source code."""

    def __init__(self, source: str, filename: str = "<input>"):
        self.source = source
        self.filename = filename
        self.pos = 0
        self.line = 1
        self.col = 1
        self.tokens: List[Token] = []

    def tokenize(self) -> List[Token]:
        """Tokenize the entire source and return list of tokens."""
        self.tokens = []
        while self.pos < len(self.source):
            try:
                self._next_token()
            except LexerError as e:
                # Emit error token and continue
                self.tokens.append(Token(TokenType.EOF, f"ERROR: {e.message}", e.line, e.col))
                # Skip to next line to recover
                while self.pos < len(self.source) and self.source[self.pos] != '\n':
                    self.pos += 1
                self.col = 1
        self.tokens.append(Token(TokenType.EOF, "", self.line, self.col))
        return self.tokens

    def _peek(self, n: int = 0) -> str:
        idx = self.pos + n
        if idx < len(self.source):
            return self.source[idx]
        return '\0'

    def _advance(self, n: int = 1) -> str:
        chars = []
        for _ in range(n):
            if self.pos < len(self.source):
                ch = self.source[self.pos]
                self.pos += 1
                if ch == '\n':
                    self.line += 1
                    self.col = 1
                else:
                    self.col += 1
                chars.append(ch)
        return ''.join(chars)

    def _skip_whitespace(self):
        while self.pos < len(self.source) and self.source[self.pos] in ' \t\r\v\f':
            self._advance()

    def _read_comment(self):
        start_line = self.line
        start_col = self.col
        comment = ""
        self._advance(2)  # skip --
        while self.pos < len(self.source) and self.source[self.pos] != '\n':
            comment += self._advance()
        self.tokens.append(Token(TokenType.COMMENT, comment.strip(), start_line, start_col))

    def _read_number(self) -> Token:
        start_line = self.line
        start_col = self.col
        num_str = ""

        # Check for hex (0x), binary (0b)
        if self._peek() == '0' and self._peek(1).lower() in ('x', 'b'):
            num_str += self._advance()  # consume '0'
            num_str += self._advance()  # consume 'x' or 'b'
            while self.pos < len(self.source) and (
                self.source[self.pos].isalnum() or self.source[self.pos] == '_'
            ):
                num_str += self._advance()
        else:
            # Decimal number
            while self.pos < len(self.source) and (
                self.source[self.pos].isdigit() or
                self.source[self.pos] == '.' or
                self.source[self.pos] == '_'
            ):
                # Don't consume '.' if next char after it isn't a digit
                if self.source[self.pos] == '.':
                    next_ch = self._peek(1)
                    if not (next_ch.isdigit() or next_ch == '_'):
                        break
                num_str += self._advance()

        return Token(TokenType.NUMBER, num_str, start_line, start_col)

    def _read_colour(self) -> Token:
        start_line = self.line
        start_col = self.col
        colour = self._advance()  # skip #
        while self.pos < len(self.source) and self.source[self.pos] in '0123456789ABCDEFabcdef':
            colour += self._advance()
        return Token(TokenType.COLOUR, f"#{colour}", start_line, start_col)

    def _read_string(self, raw: bool = False) -> Token:
        start_line = self.line
        start_col = self.col
        self._advance()  # skip opening "
        s = ""

        while self.pos < len(self.source):
            ch = self._peek()
            if ch == '\0':
                raise LexerError("Unterminated string literal", start_line, start_col)

            if not raw and ch == '\\':
                self._advance()
                escape = self._peek()
                valid_escapes = '"\\tnvfr'
                if escape in valid_escapes:
                    s += '\\' + self._advance()
                else:
                    # Line continuation or invalid escape
                    if escape == '\n':
                        self._advance()
                        s += '\\\n'
                    else:
                        s += '\\' + self._advance()
            elif ch == '"':
                break
            elif ch == '\n':
                s += self._advance()
            else:
                s += self._advance()

        if self.pos < len(self.source) and self.source[self.pos] == '"':
            self._advance()
        else:
            raise LexerError("Unterminated string literal", start_line, start_col)

        return Token(TokenType.STRING, s, start_line, start_col)

    def _read_char(self) -> Token:
        start_line = self.line
        start_col = self.col
        self._advance()  # skip '
        ch = ""

        if self._peek() == '\\':
            self._advance()
            ch = '\\' + self._advance()
        else:
            ch = self._advance()

        if self._peek() == "'":
            self._advance()
        else:
            raise LexerError("Unterminated character literal", start_line, start_col)

        return Token(TokenType.CHAR, ch, start_line, start_col)

    def _read_raw_identifier(self) -> Token:
        start_line = self.line
        start_col = self.col
        self._advance()  # skip `
        ident = ""
        while self.pos < len(self.source) and self.source[self.pos] != '`':
            if self.source[self.pos] == '\n':
                raise LexerError("Unterminated raw identifier", start_line, start_col)
            ident += self._advance()
        if self.pos < len(self.source):
            self._advance()  # skip closing `
        else:
            raise LexerError("Unterminated raw identifier", start_line, start_col)
        return Token(TokenType.RAW_IDENTIFIER, ident, start_line, start_col)

    def _read_identifier(self) -> Token:
        start_line = self.line
        start_col = self.col
        ident = ""
        while self.pos < len(self.source) and (
            self.source[self.pos].isalnum() or self.source[self.pos] == '_'
        ):
            ident += self._advance()

        # Check if it's a keyword
        if ident in KEYWORD_MAP:
            return Token(KEYWORD_MAP[ident], ident, start_line, start_col)

        return Token(TokenType.IDENTIFIER, ident, start_line, start_col)

    def _try_operator(self) -> Optional[Token]:
        start_line = self.line
        start_col = self.col

        for op_str, op_type in OPERATOR_MAP:
            if self.source[self.pos:].startswith(op_str):
                # Special handling: -- is always a comment, not subtraction
                if op_str == "-" and self._peek(1) == "-":
                    return None
                # Special handling: // is integer division, not comment
                if op_str == "//":
                    # But check it's not // followed by a comment in user's mind
                    pass  # IntDiv is valid in Catspeak

                token = Token(op_type, op_str, start_line, start_col)
                for _ in range(len(op_str)):
                    self._advance()
                return token
        return None

    def _next_token(self):
        self._skip_whitespace()

        if self.pos >= len(self.source):
            return

        ch = self.source[self.pos]

        # Check for comments first (-- at any point)
        if ch == '-' and self._peek(1) == '-':
            self._read_comment()
            return

        # Newlines
        if ch == '\n':
            self._advance()
            return

        # Numbers
        if ch.isdigit():
            self.tokens.append(self._read_number())
            return

        # Dot - could be number or member access
        if ch == '.':
            if self._peek(1).isdigit():
                self.tokens.append(self._read_number())
                return
            self.tokens.append(Token(TokenType.DOT, '.', self.line, self.col))
            self._advance()
            return

        # Colour codes
        if ch == '#':
            next_ch = self._peek(1)
            if next_ch in '0123456789ABCDEFabcdef':
                self.tokens.append(self._read_colour())
                return
            # Otherwise treat as error
            self._advance()
            return

        # Strings
        if ch == '@' and self._peek(1) == '"':
            self._advance()  # skip @
            self.tokens.append(self._read_string(raw=True))
            return
        if ch == '"':
            self.tokens.append(self._read_string())
            return

        # Char literals
        if ch == "'":
            self.tokens.append(self._read_char())
            return

        # Raw identifiers
        if ch == '`':
            self.tokens.append(self._read_raw_identifier())
            return

        # Identifiers and keywords
        if ch.isalpha() or ch == '_':
            self.tokens.append(self._read_identifier())
            return

        # Operators
        op_token = self._try_operator()
        if op_token:
            self.tokens.append(op_token)
            return

        # Punctuation
        punct_map = {
            '(': TokenType.LPAREN, ')': TokenType.RPAREN,
            '[': TokenType.LBRACKET, ']': TokenType.RBRACKET,
            '{': TokenType.LBRACE, '}': TokenType.RBRACE,
            ',': TokenType.COMMA, ':': TokenType.COLON,
            ';': TokenType.SEMICOLON,
        }
        if ch in punct_map:
            self.tokens.append(Token(punct_map[ch], ch, self.line, self.col))
            self._advance()
            return

        # Unknown character - skip with warning
        self._advance()


# ============================================================================
# DIAGNOSTICS
# ============================================================================

class Severity(Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"
    HINT = "HINT"


@dataclass
class Diagnostic:
    severity: Severity
    message: str
    line: int
    col: int
    code: str = ""
    source_line: str = ""

    def __str__(self):
        code_str = f" [{self.code}]" if self.code else ""
        return f"  {self.severity.value}: Line {self.line}:{self.col} - {self.message}{code_str}"


# ============================================================================
# SYNTAX VALIDATOR
# ============================================================================

class SyntaxValidator:
    """Validates Catspeak syntax: brace matching, basic structural checks."""

    def __init__(self, tokens: List[Token], source: str, filename: str):
        self.tokens = tokens
        self.source = source
        self.source_lines = source.split('\n')
        self.filename = filename
        self.diagnostics: List[Diagnostic] = []

    def _get_line(self, line_num: int) -> str:
        if 1 <= line_num <= len(self.source_lines):
            return self.source_lines[line_num - 1]
        return ""

    def _diag(self, severity: Severity, msg: str, line: int, col: int, code: str = ""):
        source_line = self._get_line(line).rstrip()
        self.diagnostics.append(Diagnostic(severity, msg, line, col, code, source_line))

    def validate(self) -> List[Diagnostic]:
        self._check_braces()
        self._check_structure()
        self._check_gml_pitfalls()
        return self.diagnostics

    def _check_braces(self):
        """Check for balanced parentheses, brackets, and braces."""
        stack: List[Tuple[str, int, int]] = []

        for token in self.tokens:
            opening = None
            closing = None

            if token.type == TokenType.LPAREN:
                opening = '('
                closing = ')'
            elif token.type == TokenType.LBRACKET:
                opening = '['
                closing = ']'
            elif token.type == TokenType.LBRACE:
                opening = '{'
                closing = '}'
            elif token.type in (TokenType.RPAREN, TokenType.RBRACKET, TokenType.RBRACE):
                closing_map = {
                    TokenType.RPAREN: ('(', TokenType.LPAREN),
                    TokenType.RBRACKET: ('[', TokenType.LBRACKET),
                    TokenType.RBRACE: ('{', TokenType.LBRACE),
                }
                expected_char, expected_type = closing_map[token.type]
                if not stack:
                    self._diag(Severity.ERROR,
                        f"Unexpected '{token.value}' - no matching opening bracket",
                        token.line, token.col, "E001")
                else:
                    last_char, last_line, last_col = stack.pop()
                    if last_char != expected_char:
                        self._diag(Severity.ERROR,
                            f"Mismatched bracket: expected '{self._closing_of(last_char)}' "
                            f"but found '{token.value}'",
                            token.line, token.col, "E002")
                continue

            if opening:
                stack.append((opening, token.line, token.col))

        # Unclosed brackets
        for char, line, col in stack:
            self._diag(Severity.ERROR,
                f"Unclosed '{char}' - missing '{self._closing_of(char)}'",
                line, col, "E003")

    def _closing_of(self, ch: str) -> str:
        return {'(': ')', '[': ']', '{': '}'}.get(ch, '?')

    def _check_structure(self):
        """Check basic structural requirements for mod files."""
        non_comment = [t for t in self.tokens
                       if t.type not in (TokenType.COMMENT, TokenType.NEWLINE, TokenType.EOF)]

        if len(non_comment) == 0:
            self._diag(Severity.ERROR, "File is empty", 1, 1, "E004")
            return

        last_token = non_comment[-1] if non_comment else None

        # Check for statements that must be at file level
        self._check_invalid_toplevel_constructs()

        # Check for return at end of file
        self._check_return_statement(last_token)

    def _check_invalid_toplevel_constructs(self):
        """Checks for constructs that shouldn't be at top level without proper context."""
        brace_depth = 0
        paren_depth = 0
        bracket_depth = 0
        in_fun_def = False
        fun_depth = 0  # brace depth when fun was defined

        for i, token in enumerate(self.tokens):
            if token.type == TokenType.LBRACE:
                brace_depth += 1
            elif token.type == TokenType.RBRACE:
                brace_depth -= 1
                if in_fun_def and brace_depth < fun_depth:
                    in_fun_def = False
            elif token.type == TokenType.LPAREN:
                paren_depth += 1
            elif token.type == TokenType.RPAREN:
                paren_depth -= 1
            elif token.type == TokenType.LBRACKET:
                bracket_depth += 1
            elif token.type == TokenType.RBRACKET:
                bracket_depth -= 1

            # Track function definitions
            if token.type == TokenType.KW_FUN and brace_depth == 0:
                # Check previous token for 'fun' keyword pattern
                in_fun_def = True
                fun_depth = brace_depth

            # Check `throw` outside function/catch context
            if token.type == TokenType.KW_THROW and brace_depth == 0:
                self._diag(Severity.WARNING,
                    "'throw' at file level may not be caught", token.line, token.col, "W004")

    def _check_return_statement(self, last_token):
        """Check that the file ends with a return statement (required for mods)."""
        # Look for top-level return
        brace_depth = 0
        found_return = False

        for token in self.tokens:
            if token.type == TokenType.LBRACE:
                brace_depth += 1
            elif token.type == TokenType.RBRACE:
                brace_depth -= 1
            elif token.type == TokenType.KW_RETURN and brace_depth == 0:
                found_return = True

        if not found_return:
            self._diag(Severity.WARNING,
                "Mod file should end with 'return <mod>' statement. "
                "Without it, the game won't receive your mod struct.",
                1, 1, "W005")

    def _code_parts_of_line(self, line: str) -> List[Tuple[int, str]]:
        """Extract parts of a line that are outside string/char literals.
        Returns list of (column, text) tuples for code portions only."""
        parts = []
        in_string = False
        in_char = False
        in_raw_string = False
        current_start = 0
        i = 0

        while i < len(line):
            ch = line[i]
            prev = line[i-1] if i > 0 else ''

            if not in_string and not in_char and not in_raw_string:
                if ch == '@' and i + 1 < len(line) and line[i+1] == '"':
                    in_raw_string = True
                    if i > current_start:
                        parts.append((current_start, line[current_start:i]))
                    i += 2
                    current_start = i
                    continue
                elif ch == '"':
                    in_string = True
                    if i > current_start:
                        parts.append((current_start, line[current_start:i]))
                    i += 1
                    current_start = i
                    continue
                elif ch == "'":
                    in_char = True
                    if i > current_start:
                        parts.append((current_start, line[current_start:i]))
                    # Character literal - skip it
                    i += 1
                    if i < len(line) and line[i] == '\\':
                        i += 1  # skip escape
                    if i < len(line):
                        i += 1  # skip closing char (or just the char)
                    if i < len(line) and line[i] == "'":
                        i += 1  # skip closing quote
                    current_start = i
                    continue
            elif in_string:
                if ch == '\\' and not in_raw_string:
                    i += 2  # skip escape sequence
                    continue
                elif ch == '"':
                    in_string = False
                    i += 1
                    current_start = i
                    continue
            elif in_raw_string:
                if ch == '"':
                    in_raw_string = False
                    i += 1
                    current_start = i
                    continue

            i += 1

        # Remaining code after last string
        if not in_string and not in_char and not in_raw_string and current_start < len(line):
            parts.append((current_start, line[current_start:]))

        return parts

    def _check_gml_pitfalls(self):
        """Check for common GML→Catspeak conversion mistakes in comments and strings."""
        # Check for GML-style comments using //
        source = self.source
        for i, line in enumerate(self.source_lines, 1):
            stripped = line.strip()

            # Check for `//` used as comments (very common mistake)
            stripped_line = stripped.lstrip()
            if stripped_line.startswith('//') and not stripped_line.startswith('///'):
                self._diag(Severity.WARNING,
                    "GML-style comment '//' detected. Catspeak uses '--' for comments. "
                    "'//' is the integer division operator in Catspeak.",
                    i, line.index('//') + 1, "W010")
            else:
                # Also check for inline // style comments (e.g. code // comment)
                # Look for // not inside a string
                in_str = False
                str_char = ''
                for j, ch in enumerate(line):
                    if ch in '"\'' and (j == 0 or line[j-1] != '\\'):
                        if not in_str:
                            in_str = True
                            str_char = ch
                        elif ch == str_char:
                            in_str = False
                    elif not in_str and ch == '/' and j + 1 < len(line) and line[j+1] == '/':
                        # Make sure it's not integer division (no space before, e.g. 5//2 is valid)
                        before = line[:j].rstrip()
                        is_intdiv = (before and before[-1].isdigit())
                        if not is_intdiv:
                            self._diag(Severity.WARNING,
                                "GML-style inline comment '//' detected. "
                                "Catspeak uses '--' for comments. '//' means integer division.",
                                i, j + 1, "W010")
                        break

            # Check for GML `var` declarations
            code_text = ' '.join(text for _, text in self._code_parts_of_line(line))
            if re.match(r'^\s*var\s+\w', stripped) and re.search(r'\bvar\b', code_text):
                self._diag(Severity.WARNING,
                    "GML 'var' keyword detected. Use 'let' instead in Catspeak.",
                    i, 1, "W011")

            # Check for `function` keyword (GML named function) - broader detection
            if re.search(r'\bfunction\b', stripped) and re.search(r'\bfunction\b', code_text) and 'fun ' not in stripped and 'fun(' not in stripped:
                self._diag(Severity.WARNING,
                    "GML 'function' keyword detected. Use anonymous functions with 'fun': "
                    "`name = fun(params) { ... }`",
                    i, 1, "W012")

            # Check for `repeat` loops
            if re.match(r'^\s*repeat\s*\(', stripped) and re.search(r'\brepeat\b', code_text):
                self._diag(Severity.WARNING,
                    "GML 'repeat' loop detected. Catspeak doesn't have repeat. "
                    "Use 'while' loops instead.",
                    i, 1, "W013")

            # Check for `switch` statements
            if re.match(r'^\s*switch\s*\(', stripped) and re.search(r'\bswitch\b', code_text):
                self._diag(Severity.WARNING,
                    "GML 'switch' statement detected. Catspeak uses 'match' expressions instead.",
                    i, 1, "W014")

            # Check for ternary `? :`
            if '?' in code_text and ':' in code_text and not stripped.lstrip().startswith('--'):
                self._diag(Severity.WARNING,
                    "Ternary operator '?' detected. Catspeak doesn't support '? :'. "
                    "Use 'if ... { } else { }' expressions instead.",
                    i, code_text.index('?') + 1, "W015")


# ============================================================================
# STONKS-9800 SPECIFIC LINTER
# ============================================================================

# ============================================================================
# GAME CONFIGURATION
# ============================================================================

@dataclass
class GameConfig:
    """Configuration for game-specific mod validation.
    Customize this for your GameMaker game to get tailored linting."""

    game_name: str = "Generic Catspeak Game"
    mod_struct_name: str = "mod"          # Name of the struct returned by the mod
    mod_file_extension: str = ".meow"     # File extension for mod files
    check_mod_struct: bool = True         # Validate mod struct and fields
    check_callbacks: bool = True          # Validate lifecycle callback names
    check_delay_action: bool = True       # Check delay_action registration
    check_global_access: bool = True      # Check global variable patterns
    check_draw_callbacks: bool = True     # Warn about loops in draw callbacks
    check_unknown_funcs: bool = True      # Flag unknown GML-looking function calls

    # Required fields in the mod struct
    required_fields: Set[str] = field(default_factory=lambda: {"name", "description"})

    # Known optional fields (for typo detection)
    optional_fields: Set[str] = field(default_factory=set)

    # Valid lifecycle callback names
    valid_callbacks: Set[str] = field(default_factory=set)

    # Known API functions exposed to Catspeak by your game
    known_api_functions: Set[str] = field(default_factory=set)

    # Callbacks that are draw-related (warn about heavy logic)
    draw_callbacks: Set[str] = field(default_factory=set)

    # Common global variables used by the game
    common_globals: Set[str] = field(default_factory=set)

    # Additional GML functions to suppress S007 info notices
    suppress_func_warnings: Set[str] = field(default_factory=set)


# Built-in: STONKS-9800 config (default)
STONKS_CONFIG = GameConfig(
    game_name="STONKS-9800",
    mod_struct_name="mod",
    required_fields={"name", "description"},
    optional_fields={
        "name_ja", "description_ja", "name_uk", "description_uk",
        "name_en", "description_en", "name_zh", "description_zh",
        "name_zht", "description_zht", "name_ko", "description_ko",
        "name_localized", "description_localized", "localization",
        "start_game", "start_new_game", "after_creating_character",
        "after_game_load", "new_day", "step", "draw", "draw_end",
        "draw_portrait_before", "draw_portrait_after",
        "draw_portrait_mini_before", "draw_portrait_mini_after",
        "bar_start", "bar_step", "bar_destroy", "bar_draw",
        "window_start", "window_destroy", "window_draw", "window_sprite",
        "meeting_start", "meeting_step", "meeting_draw",
    },
    valid_callbacks={
        "start_game", "start_new_game", "after_creating_character",
        "after_game_load", "new_day", "step", "draw", "draw_end",
        "draw_portrait_before", "draw_portrait_after",
        "draw_portrait_mini_before", "draw_portrait_mini_after",
        "bar_start", "bar_step", "bar_destroy", "bar_draw",
        "window_start", "window_destroy", "window_draw", "window_sprite",
        "meeting_start", "meeting_step", "meeting_draw",
    },
    known_api_functions={
        "mods_notify", "mods_create_company", "mod_register_func",
        "mods_resource_path", "mods_load_sprite", "mods_load_audio_stream",
        "mods_buffer_load", "mods_file_exists", "mods_csv_load", "mods_active_dir",
        "portrait_part_register", "portrait_extra_register",
        "delay_action", "change_friend", "calc_price_human", "draw_portrait",
        "txt", "company_info_reset", "generate_company",
        "create_notification", "create_question_many",
        "show_message", "show_debug_message",
        "get_integer", "get_string",
        "variable_global_exists", "variable_global_get", "variable_global_set",
        "array_push", "array_length", "array_pop",
        "string", "round", "floor", "ceil",
        "keyboard_check", "keyboard_check_pressed", "ord",
        "draw_set_color", "draw_set_alpha", "draw_text", "draw_rectangle",
        "draw_sprite", "sprite_add", "sprite_index",
        "audio_create_stream",
        "irandom_range", "choose",
        "date_create_datetime", "string_format",
        "asset_get_index",
    },
    draw_callbacks={
        "draw", "draw_end", "draw_portrait_before", "draw_portrait_after",
        "bar_draw", "window_draw", "meeting_draw",
    },
    common_globals={
        "money", "day", "happy", "stress", "karma", "prestige",
        "rynochek", "trend", "inflation", "language",
        "human_kol", "company_name", "company_price", "company_profit",
        "company_hype", "company_number_a", "company_limit",
    },
)

# Built-in: Generic Catspeak-only config (no game-specific checks)
GENERIC_CONFIG = GameConfig(
    game_name="Generic Catspeak Game",
    check_mod_struct=False,
    check_callbacks=False,
    check_delay_action=False,
    check_global_access=False,
    check_draw_callbacks=False,
    check_unknown_funcs=False,
)

# Common GML functions (used for S007 detection across all configs)
COMMON_GML_FUNCTIONS: Set[str] = {
    "show_message", "show_debug_message", "instance_create_depth",
    "instance_create_layer", "instance_create", "instance_destroy", "instance_exists",
    "game_end", "game_restart", "room_goto", "draw_self",
    "point_distance", "point_direction", "lengthdir_x", "lengthdir_y",
    "random", "random_range", "irandom", "ds_list_create", "ds_list_size",
    "ds_list_find_index", "ds_list_add",
    "ds_map_create", "ds_grid_create", "variable_instance_exists",
    "sprite_get_width", "sprite_get_height", "sprite_init",
    "surface_create", "surface_free", "surface_exists", "draw_surface",
    "audio_play_sound", "audio_play_sound_on", "audio_stop_sound", "audio_stop_all",
    "audio_destroy_stream", "audio_is_playing", "audio_sound_length",
    "audio_sound_get_track_position",
    "file_text_open_read", "file_text_read_string", "file_text_close",
    "ini_open", "ini_read_real", "ini_read_string", "ini_close",
    "buffer_create", "buffer_write", "buffer_read", "buffer_delete",
    "json_parse", "json_stringify",
}


class GameLinter:
    """Game-specific checks for mod .meow files. Configured via GameConfig."""

    def __init__(self, tokens: List[Token], source: str, filename: str,
                 config: GameConfig):
        self.tokens = tokens
        self.source = source
        self.source_lines = source.split('\n')
        self.filename = filename
        self.config = config
        self.diagnostics: List[Diagnostic] = []

    def _get_line(self, line_num: int) -> str:
        if 1 <= line_num <= len(self.source_lines):
            return self.source_lines[line_num - 1]
        return ""

    def _diag(self, severity: Severity, msg: str, line: int, col: int, code: str = ""):
        source_line = self._get_line(line).rstrip()
        self.diagnostics.append(Diagnostic(severity, msg, line, col, code, source_line))

    def lint(self) -> List[Diagnostic]:
        cfg = self.config
        if cfg.check_mod_struct:
            self._check_mod_struct()
        if cfg.check_callbacks:
            self._check_callback_names()
        if cfg.check_delay_action:
            self._check_delay_action_registration()
        if cfg.check_global_access:
            self._check_global_access()
        if cfg.check_unknown_funcs:
            self._check_unknown_identifiers()
        if cfg.check_draw_callbacks:
            self._check_draw_callbacks()
        return self.diagnostics

    def _check_mod_struct(self):
        """Check that the mod struct has required fields."""
        # Find 'mod' identifier assignment
        mod_line = None
        mod_fields: Dict[str, int] = {}

        brace_depth = 0
        in_mod_struct = False
        mod_struct_brace_start = 0

        for i, token in enumerate(self.tokens):
            if token.type == TokenType.LBRACE:
                brace_depth += 1
            elif token.type == TokenType.RBRACE:
                brace_depth -= 1
                if in_mod_struct and brace_depth < mod_struct_brace_start:
                    in_mod_struct = False

            # Track when we enter a struct assigned to 'mod' or 'let mod = {'
            if (token.type == TokenType.IDENTIFIER and
                token.value == "mod" and brace_depth == 0):
                # Check if preceded by 'let' (let mod = {) or plain (mod = {)
                prev_non_comment = None
                for k in range(i - 1, -1, -1):
                    if self.tokens[k].type != TokenType.COMMENT:
                        prev_non_comment = self.tokens[k]
                        break

                # Check if followed by = { or : {
                for j in range(i + 1, min(i + 6, len(self.tokens))):
                    if self.tokens[j].type == TokenType.LBRACE:
                        mod_line = token.line
                        in_mod_struct = True
                        mod_struct_brace_start = brace_depth
                        break
                    if self.tokens[j].type not in (TokenType.COMMENT, TokenType.OP_ASSIGN, TokenType.COLON):
                        break

            # Collect field names inside mod struct
            if in_mod_struct and brace_depth == mod_struct_brace_start + 1:
                if (token.type == TokenType.IDENTIFIER and
                    i + 1 < len(self.tokens) and
                    self.tokens[i + 1].type == TokenType.COLON):
                    mod_fields[token.value] = token.line

        if mod_line is None:
            self._diag(Severity.WARNING,
                f"No '{self.config.mod_struct_name}' struct definition found. "
                f"A {self.config.game_name} mod must define "
                f"a struct named '{self.config.mod_struct_name}' and return it.",
                1, 1, "S001")
            return

        # Check required fields
        for field in self.config.required_fields:
            if field not in mod_fields:
                self._diag(Severity.ERROR,
                    f"Mod struct missing required field: '{field}'. "
                    f"Every mod needs at least: {', '.join(sorted(self.config.required_fields))}.",
                    mod_line, 1, "S002")

        # Check for plausible typos in callback names
        self._check_typo_fields(mod_fields)

    def _check_typo_fields(self, mod_fields: Dict[str, int]):
        """Check for plausible typos in lifecycle callback field names."""
        cfg = self.config
        all_valid = cfg.valid_callbacks | cfg.required_fields | cfg.optional_fields

        for field, line in mod_fields.items():
            if field not in all_valid:
                # Check if it's close to a valid callback name
                for valid in cfg.valid_callbacks:
                    if self._levenshtein_ratio(field, valid) > 0.75:
                        self._diag(Severity.WARNING,
                            f"Unknown field '{field}' in mod struct. "
                            f"Did you mean '{valid}'?",
                            line, 1, "S003")
                        break
                else:
                    for valid in cfg.required_fields:
                        if self._levenshtein_ratio(field, valid) > 0.75:
                            self._diag(Severity.WARNING,
                                f"Unknown field '{field}' in mod struct. "
                                f"Did you mean '{valid}'?",
                                line, 1, "S003")
                            break

    def _levenshtein_ratio(self, a: str, b: str) -> float:
        """Simple similarity ratio between two strings."""
        if not a or not b:
            return 0.0
        if len(a) < len(b):
            a, b = b, a
        if len(b) == 0:
            return 0.0

        # Simple implementation for short strings
        prev = list(range(len(b) + 1))
        for i, ca in enumerate(a, 1):
            curr = [i]
            for j, cb in enumerate(b, 1):
                curr.append(min(
                    curr[-1] + 1,
                    prev[j] + 1,
                    prev[j - 1] + (0 if ca == cb else 1)
                ))
            prev = curr

        return 1.0 - (prev[-1] / max(len(a), len(b)))

    def _check_callback_names(self):
        """Check that callback function names in mod struct are valid."""
        non_comment = [t for t in self.tokens if t.type != TokenType.COMMENT]

        brace_depth = 0
        in_mod_struct = False
        mod_struct_brace = 0

        for i, token in enumerate(non_comment):
            if token.type == TokenType.LBRACE:
                brace_depth += 1
            elif token.type == TokenType.RBRACE:
                brace_depth -= 1
                if in_mod_struct and brace_depth < mod_struct_brace:
                    in_mod_struct = False

            if (token.type == TokenType.IDENTIFIER and
                token.value == "mod" and brace_depth == 0):
                for j in range(i + 1, min(i + 5, len(non_comment))):
                    if non_comment[j].type == TokenType.LBRACE:
                        in_mod_struct = True
                        mod_struct_brace = brace_depth
                        break
                    if non_comment[j].type not in (TokenType.COMMENT, TokenType.OP_ASSIGN):
                        break

    def _check_delay_action_registration(self):
        """Check delay_action usage is paired with mod_register_func."""
        registered_funcs: Set[str] = set()
        delayed_funcs: List[Tuple[str, int]] = []

        # Find all mod_register_func calls
        i = 0
        tokens = [t for t in self.tokens if t.type != TokenType.COMMENT]
        while i < len(tokens):
            token = tokens[i]
            if token.type == TokenType.IDENTIFIER and token.value == "mod_register_func":
                # Find the string argument
                j = i + 1
                while j < len(tokens) and tokens[j].type != TokenType.LPAREN:
                    j += 1
                j += 1
                if j < len(tokens) and tokens[j].type == TokenType.STRING:
                    registered_funcs.add(tokens[j].value)
            elif token.type == TokenType.IDENTIFIER and token.value == "delay_action":
                # Find the string argument (second arg)
                j = i + 1
                while j < len(tokens) and tokens[j].type != TokenType.LPAREN:
                    j += 1
                j += 1
                # Skip first argument (number)
                comma_count = 0
                while j < len(tokens):
                    if tokens[j].type == TokenType.COMMA:
                        comma_count += 1
                    if comma_count == 1 and tokens[j].type == TokenType.STRING:
                        delayed_funcs.append((tokens[j].value, tokens[j].line))
                        break
                    if comma_count > 1:
                        break
                    j += 1
            i += 1

        for func_name, line in delayed_funcs:
            if func_name not in registered_funcs:
                self._diag(Severity.WARNING,
                    f"delay_action references '{func_name}' but no matching "
                    f"mod_register_func('{func_name}', ...) call found. "
                    f"Without registration, the delayed function won't be called.",
                    line, 1, "S006")

    def _check_global_access(self):
        """Check for common global variable access patterns."""
        globals_used: Set[str] = set()

        tokens = [t for t in self.tokens if t.type != TokenType.COMMENT]
        for i in range(len(tokens) - 2):
            if (tokens[i].type == TokenType.IDENTIFIER and
                tokens[i].value == "global" and
                tokens[i + 1].type == TokenType.DOT and
                tokens[i + 2].type == TokenType.IDENTIFIER):
                globals_used.add(tokens[i + 2].value)

        # Note: config.common_globals can be used by external tooling
        # to highlight non-standard globals, but we don't flag them as errors

    def _check_unknown_identifiers(self):
        """Check for potentially undefined function calls."""
        non_comment = [t for t in self.tokens if t.type != TokenType.COMMENT]

        i = 0
        while i < len(non_comment) - 2:
            token = non_comment[i]
            # Function call pattern: identifier ( args )
            if (token.type == TokenType.IDENTIFIER and
                i + 1 < len(non_comment) and
                non_comment[i + 1].type == TokenType.LPAREN and
                i + 2 < len(non_comment)):
                func_name = token.value

                # Only check non-keyword, non-common identifiers
                if (func_name not in KEYWORD_MAP and
                    func_name not in self.config.known_api_functions and
                    func_name not in self.config.suppress_func_warnings and
                    func_name not in COMMON_GML_FUNCTIONS and
                    not func_name.startswith('_') and
                    not func_name.startswith('global') and
                    func_name not in ('mod', 'fun', 'array_push', 'array_length')):

                    # Check if it looks like a probable GML function name
                    gml_like = (
                        func_name.startswith('instance_') or
                        func_name.startswith('sprite_') or
                        func_name.startswith('audio_') or
                        func_name.startswith('ds_') or
                        func_name.startswith('surface_') or
                        func_name.startswith('buffer_') or
                        func_name.startswith('room_') or
                        func_name.startswith('game_') or
                        func_name.startswith('file_') or
                        func_name.startswith('json_') or
                        func_name.startswith('ini_')
                    )

                    # Don't flag user-defined variable calls (they might be functions)
                    # Only flag if we can't determine if it's defined earlier
                    # For simplicity, only flag GML-looking names
                    if gml_like:
                        self._diag(Severity.INFO,
                            f"Call to '{func_name}()' - this looks like a GML function. "
                            f"Make sure it's exposed through the Catspeak API or defined in your mod.",
                            token.line, token.col, "S007")

            i += 1

    def _check_draw_callbacks(self):
        """Check that draw callbacks don't contain heavy logic patterns."""
        draw_callbacks = self.config.draw_callbacks
        if not draw_callbacks:
            return

        non_comment = [t for t in self.tokens if t.type != TokenType.COMMENT]
        brace_depth = 0
        in_draw_callback = False
        draw_callback_depth = 0

        for i, token in enumerate(non_comment):
            if token.type == TokenType.LBRACE:
                brace_depth += 1
            elif token.type == TokenType.RBRACE:
                brace_depth -= 1
                if in_draw_callback and brace_depth < draw_callback_depth:
                    in_draw_callback = False

            # Detect draw callback definitions
            if (token.type == TokenType.IDENTIFIER and
                token.value in draw_callbacks and
                i + 1 < len(non_comment) and
                non_comment[i + 1].type == TokenType.COLON):
                # Check if followed by fun (
                for j in range(i + 2, min(i + 6, len(non_comment))):
                    if non_comment[j].type == TokenType.KW_FUN:
                        in_draw_callback = True
                        draw_callback_depth = brace_depth
                        break

            # Check for while loops inside draw callbacks
            if in_draw_callback and token.type == TokenType.KW_WHILE:
                self._diag(Severity.WARNING,
                    f"'while' loop found inside draw callback. "
                    f"Keep draw callbacks light to avoid frame drops.",
                    token.line, token.col, "S008")


# ============================================================================
# TEMPLATE GENERATOR
# ============================================================================

MOD_TEMPLATE = '''-- {mod_name}
-- Created with Catspeak Mod Tool on {date}
-- Author: {author}
-- Game: {game_name}

-- ============================================================
-- MOD DEFINITION
-- ============================================================

let mod = {{
  name: "{mod_name}",
  description: "{description}",
'''

ADVANCED_MOD_TEMPLATE = '''-- {mod_name}
-- Created with Catspeak Mod Tool on {date}
-- Author: {author}
-- Game: {game_name}
'''


class TemplateGenerator:
    """Generates .meow mod templates."""

    @staticmethod
    def generate(name: str, description: str = "",
                 author: str = "Mod Author",
                 advanced: bool = False,
                 game_name: str = "STONKS-9800") -> str:
        """Generate a .meow mod file template."""
        mod_name = name.replace('_', ' ').title()
        if not description:
            description = f"A mod for {game_name}."

        template = ADVANCED_MOD_TEMPLATE if advanced else MOD_TEMPLATE
        return template.format(
            mod_name=mod_name,
            description=description,
            author=author,
            date=datetime.now().strftime("%Y-%m-%d"),
            game_name=game_name,
        )


# ============================================================================
# MAIN TOOL CLASS
# ============================================================================

@dataclass
class ValidationResult:
    filename: str
    diagnostics: List[Diagnostic]
    error_count: int
    warning_count: int
    info_count: int

    @property
    def has_errors(self) -> bool:
        return self.error_count > 0

    @property
    def is_clean(self) -> bool:
        return len(self.diagnostics) == 0


class ModTool:
    """Main orchestrator for mod validation and creation."""

    def __init__(self, verbose: bool = False, config: "GameConfig | None" = None):
        self.verbose = verbose
        self.config = config if config else STONKS_CONFIG

    def validate_file(self, filepath: str) -> ValidationResult:
        """Validate a single .meow file."""
        path = Path(filepath)
        if not path.exists():
            print(f"Error: File '{filepath}' not found.")
            sys.exit(1)

        source = path.read_text(encoding='utf-8-sig')  # utf-8-sig strips BOM
        filename = path.name

        # Phase 1: Lex
        lexer = Lexer(source, filename)
        tokens = lexer.tokenize()

        # Check for lexer errors (error tokens)
        lex_errors = [t for t in tokens if t.value.startswith("ERROR:")]
        if lex_errors:
            diagnostics = []
            for t in lex_errors:
                diagnostics.append(Diagnostic(
                    Severity.ERROR,
                    t.value.replace("ERROR: ", ""),
                    t.line, t.col, "E000"
                ))

        # Phase 2: Syntax validation
        syntax = SyntaxValidator(tokens, source, filename)
        syn_diags = syntax.validate()

        # Phase 3: STONKS-specific linting
        linter = GameLinter(tokens, source, filename, self.config)
        stonks_diags = linter.lint()

        all_diags = syn_diags + stonks_diags

        # For lex errors that didn't already get added
        lex_errors = [t for t in tokens if t.value.startswith("ERROR:")]
        for t in lex_errors:
            found = False
            for d in all_diags:
                if d.line == t.line and d.col == t.col:
                    found = True
                    break
            if not found:
                all_diags.append(Diagnostic(
                    Severity.ERROR,
                    t.value.replace("ERROR: ", ""),
                    t.line, t.col, "E000"
                ))

        # Sort by line, then col
        all_diags.sort(key=lambda d: (d.line, d.col))

        error_count = sum(1 for d in all_diags if d.severity == Severity.ERROR)
        warning_count = sum(1 for d in all_diags if d.severity == Severity.WARNING)
        info_count = sum(1 for d in all_diags if d.severity in (Severity.INFO, Severity.HINT))

        return ValidationResult(filename, all_diags, error_count, warning_count, info_count)

    def check_all(self, mods_dir: str = "mods") -> List[ValidationResult]:
        """Check all .meow files in the mods directory."""
        mods_path = Path(mods_dir)
        if not mods_path.exists():
            print(f"Error: Directory '{mods_dir}' not found.")
            sys.exit(1)

        meow_files = list(mods_path.glob("*.meow"))
        if not meow_files:
            print(f"No .meow files found in '{mods_dir}'.")
            return []

        results = []
        for meow_file in meow_files:
            result = self.validate_file(str(meow_file))
            results.append(result)
        return results

    def scan_mods(self, mods_dir: str = "mods") -> List[Dict[str, str]]:
        """Scan mods directory and return basic info about each mod."""
        mods_path = Path(mods_dir)
        if not mods_path.exists():
            print(f"Error: Directory '{mods_dir}' not found.")
            return []

        mods_info = []
        for meow_file in sorted(mods_path.glob("*.meow")):
            try:
                source = meow_file.read_text(encoding='utf-8')
                # Extract name from mod struct
                name_match = re.search(r'name\s*:\s*"([^"]*)"', source)
                desc_match = re.search(r'description\s*:\s*"([^"]*)"', source)
                name = name_match.group(1) if name_match else meow_file.stem
                description = desc_match.group(1) if desc_match else "No description"

                mods_info.append({
                    "file": meow_file.name,
                    "name": name,
                    "description": description[:80],
                })
            except Exception as e:
                mods_info.append({
                    "file": meow_file.name,
                    "name": "???",
                    "description": f"Error reading: {e}",
                })
        return mods_info

    def print_result(self, result: ValidationResult):
        """Pretty-print a validation result."""
        if result.is_clean:
            print(f"  {result.filename}: OK (no issues found)")
            return

        # Color map (ANSI for terminal)
        color = {
            Severity.ERROR: '\033[91m',    # Red
            Severity.WARNING: '\033[93m',  # Yellow
            Severity.INFO: '\033[96m',     # Cyan
            Severity.HINT: '\033[90m',     # Gray
            'reset': '\033[0m',
        }

        # Windows fallback: no colors
        if os.name == 'nt':
            color = {k: '' for k in color}

        print(f"\n{'='*60}")
        print(f"  {result.filename}")
        print(f"  {'='*60}")

        if result.error_count + result.warning_count + result.info_count == 0:
            print(f"  {color[Severity.INFO]}OK - No issues found{color['reset']}")
            return

        print(f"  Errors: {result.error_count}  "
              f"Warnings: {result.warning_count}  "
              f"Info: {result.info_count}")
        print()

        for diag in result.diagnostics:
            sev_color = color.get(diag.severity, '')
            print(f"{sev_color}{diag}{color['reset']}")

            if self.verbose and diag.source_line:
                try:
                    print(f"    {diag.source_line.strip()[:100]}")
                except UnicodeEncodeError:
                    # Windows console encoding fallback
                    safe = diag.source_line.strip()[:100].encode('ascii', errors='replace').decode('ascii')
                    print(f"    {safe}")

        print()

    def print_summary(self, results: List[ValidationResult]):
        """Print a summary of all validation results."""
        if not results:
            return

        total_errors = sum(r.error_count for r in results)
        total_warnings = sum(r.warning_count for r in results)
        total_info = sum(r.info_count for r in results)
        clean = sum(1 for r in results if r.is_clean)

        print(f"\n{'='*60}")
        print(f"  SUMMARY: {len(results)} file(s) checked")
        print(f"  {'='*60}")
        print(f"  Clean:  {clean}")
        print(f"  Errors: {total_errors}")
        print(f"  Warnings: {total_warnings}")
        print(f"  Info: {total_info}")
        print()

        if total_errors > 0:
            print(f"  Files with errors:")
            for r in results:
                if r.error_count > 0:
                    print(f"    {r.filename} ({r.error_count} error(s))")
            print()

    def init_mod(self, name: str, output_dir: str = ".",
                 advanced: bool = False, author: str = "",
                 description: str = ""):
        """Create a new mod template file."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Sanitize filename
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', name.lower())
        if not safe_name.endswith('.meow'):
            safe_name += '.meow'

        filepath = output_path / safe_name
        if filepath.exists():
            print(f"Error: '{filepath}' already exists.")
            print(f"  Remove it first, or use a different name.")
            sys.exit(1)

        content = TemplateGenerator.generate(
            name=name,
            description=description or f"A mod for {self.config.game_name}.",
            author=author or "Mod Author",
            advanced=advanced,
            game_name=self.config.game_name,
        )

        filepath.write_text(content, encoding='utf-8')
        print(f"Created: {filepath}")
        print(f"  Mode: {'advanced' if advanced else 'basic'}")
        if author:
            print(f"  Author: {author}")


# ============================================================================
# CLI
# ============================================================================

def print_banner(config: "GameConfig | None" = None):
    name = config.game_name if config else "Catspeak"
    print(rf"""
  ╔════════════════════════════════════════════════╗
  ║     Catspeak Mod Validation Tool v2.0         ║
  ║     Game: {name:<35s} ║
  ╚════════════════════════════════════════════════╝
""")


def load_config_from_file(path: str) -> GameConfig:
    """Load a GameConfig from a JSON file."""
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Convert lists back to sets
    set_fields = [
        'required_fields', 'optional_fields', 'valid_callbacks',
        'known_api_functions', 'draw_callbacks', 'common_globals',
        'suppress_func_warnings'
    ]
    for field in set_fields:
        if field in data:
            data[field] = set(data[field])

    return GameConfig(**data)


def export_config(name: str, output_path: str):
    """Export a starter GameConfig JSON file for customizing."""
    config = {
        "game_name": name,
        "mod_struct_name": "mod",
        "mod_file_extension": ".meow",
        "check_mod_struct": True,
        "check_callbacks": True,
        "check_delay_action": True,
        "check_global_access": True,
        "check_draw_callbacks": True,
        "check_unknown_funcs": True,
        "required_fields": ["name", "description"],
        "optional_fields": [],
        "valid_callbacks": [
            "start_game", "start_new_game", "after_game_load",
            "new_day", "step", "draw", "draw_end"
        ],
        "known_api_functions": [],
        "draw_callbacks": ["draw", "draw_end"],
        "common_globals": [],
        "suppress_func_warnings": []
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, sort_keys=True)
    print(f"Config exported to: {output_path}")
    print(f"Edit this file to customize validation for '{name}', then run:")
    print(f"  python mod_tool.py --config {output_path} check <file.meow>")


def print_usage():
    print("""Usage:
  python mod_tool.py check <file.meow>          Validate a single mod
  python mod_tool.py check-all [dir]            Validate all .meow files in directory
  python mod_tool.py init <name>                Create a new mod from template
  python mod_tool.py init <name> --advanced     Create with advanced template
  python mod_tool.py scan [dir]                 List all mods in directory
  python mod_tool.py --generic check <file>     Pure Catspeak checks (no game rules)
  python mod_tool.py --config <game.json> ...   Use custom game configuration
  python mod_tool.py --export-config <name>     Export a starter config file
  python mod_tool.py --help                     Show this help

Options:
  --verbose, -v     Show source lines with diagnostics
  --output, -o DIR  Output directory for init command (default: current dir)
  --author NAME     Set author name for init command
  --desc TEXT       Set description for init command
  --generic         Run generic Catspeak-only validation (no game-specific rules)
  --config FILE     Load game configuration from a JSON file
""")



def main():
    args = sys.argv[1:]

    if not args or '--help' in args or '-h' in args:
        print_banner(STONKS_CONFIG)
        print_usage()
        return

    # Global flags
    verbose = '--verbose' in args or '-v' in args
    generic = '--generic' in args
    export_name = None
    config_path = None
    config = STONKS_CONFIG

    # Parse --export-config
    for i, arg in enumerate(args):
        if arg == '--export-config' and i + 1 < len(args):
            export_name = args[i + 1]
            break

    if export_name:
        safe = re.sub(r'[^a-zA-Z0-9_-]', '_', export_name.lower())
        path = f"{safe}_catspeak_config.json"
        export_config(export_name, path)
        return

    # Parse --config
    for i, arg in enumerate(args):
        if arg == '--config' and i + 1 < len(args):
            config_path = args[i + 1]
            break

    if config_path:
        if not Path(config_path).exists():
            print(f"Error: Config file '{config_path}' not found.")
            sys.exit(1)
        config = load_config_from_file(config_path)
    elif generic:
        config = GENERIC_CONFIG

    # Strip global flags and their values from args
    cleaned = []
    skip_next = False
    for a in args:
        if skip_next:
            skip_next = False
            continue
        if a in ('--verbose', '-v', '--generic'):
            continue
        if a in ('--config', '--export-config'):
            skip_next = True  # also skip the value that follows
            continue
        cleaned.append(a)
    args = cleaned

    command = args[0] if args else 'help'

    tool = ModTool(verbose=verbose, config=config)

    if command == 'check':
        if len(args) < 2:
            print("Error: 'check' requires a file path.")
            print("Usage: python mod_tool.py check <file.meow>")
            sys.exit(1)
        print_banner(config)
        result = tool.validate_file(args[1])
        tool.print_result(result)
        sys.exit(1 if result.has_errors else 0)

    elif command == 'check-all':
        dir_path = args[1] if len(args) > 1 else 'mods'
        print_banner(config)
        print(f"  Checking all .meow files in: {dir_path}")
        results = tool.check_all(dir_path)
        for result in results:
            tool.print_result(result)
        tool.print_summary(results)
        has_errors = any(r.has_errors for r in results)
        sys.exit(1 if has_errors else 0)

    elif command == 'init':
        if len(args) < 2:
            print("Error: 'init' requires a mod name.")
            print("Usage: python mod_tool.py init <name> [--advanced]")
            sys.exit(1)

        advanced = '--advanced' in args
        args_clean = [a for a in args if a != '--advanced']

        name = args_clean[1]

        # Parse additional options
        output_dir = '.'
        author = ''
        description = ''

        for i, arg in enumerate(args_clean):
            if arg == '-o' and i + 1 < len(args_clean):
                output_dir = args_clean[i + 1]
            elif arg == '--output' and i + 1 < len(args_clean):
                output_dir = args_clean[i + 1]
            elif arg == '--author' and i + 1 < len(args_clean):
                author = args_clean[i + 1]
            elif arg == '--desc' and i + 1 < len(args_clean):
                description = args_clean[i + 1]

        print_banner(config)
        tool.init_mod(name, output_dir, advanced, author, description)

    elif command == 'scan':
        dir_path = args[1] if len(args) > 1 else 'mods'
        print_banner(config)
        print(f"  Scanning mods in: {dir_path}\n")
        mods = tool.scan_mods(dir_path)
        if not mods:
            print("  No .meow files found.")
        for mod in mods:
            print(f"  {mod['file']}")
            print(f"    Name: {mod['name']}")
            print(f"    Desc: {mod['description']}")
            print()

    else:
        print(f"Unknown command: {command}")
        print_usage()
        sys.exit(1)


if __name__ == '__main__':
    main()
