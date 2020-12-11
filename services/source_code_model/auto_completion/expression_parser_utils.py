def is_identifier(char):
    is_digit = char.isdigit()
    is_alpha = char.isalpha()
    is_underscore = char == '_'
    return is_digit or is_alpha or is_underscore

def is_scope_operator(expr):
    if len(expr) < 2:
        return False
    return expr[0] == ':' and expr[1] == ':'

def is_member_of_ptr(expr):
    if len(expr) < 2:
        return False
    return expr[0] == '-' and expr[1] == '>'

def is_member_of_object(expr):
    if len(expr) < 2:
        return False
    if expr[1] == '.':
        if is_identifier(expr[0]):
            return True
        elif expr[0] == ')':
            return True
        elif expr[0] == ']':
            return True
    return False

def is_ptr_to_member_of_object(expr):
    if len(expr) < 2:
        return False
    return expr[0] == '.' and expr[1] == '*'

def is_ptr_to_member_of_ptr(expr):
    if len(expr) < 2:
        return False
    return expr[0] == '>' and expr[1] == '*'

def is_member_access(expr):
    return is_member_of_object(expr) or is_member_of_ptr(expr) or is_ptr_to_member_of_object(expr) or is_ptr_to_member_of_ptr(expr)

def is_special_character(char):
    special_characters = [
        '`',
        '~',
        '!',
        '@',
        '#',
        '$',
        '%',
        '^',
        '&',
        '*',
        '(',
        ')',
        #'_',
        '+',
        '-',
        '=',
        '/',
        '\\',
        '?',
        '|',
        '{',
        '}',
        '[',
        ']',
        '.',
        ',',
        '>',
        '<',
        ';',
        ':',
        '\'',
        '"',
    ]
    return char in special_characters

def is_carriage_return(c):
    return c == '\n' or c == '\r'

def is_semicolon(c):
    return c == ';'

def is_whitespace(c):
    return c.isspace()

def is_opening_paren(c):
    return c == '(' or c == '[' or c == '{'

def is_closing_paren(c):
    return c == ')' or c == ']' or c == '}'

def is_paren(c):
    return is_opening_paren(c) or is_closing_paren(c)

def last_occurence_of_non_identifier(string):
    for idx, char in enumerate(string[::-1]):
        if not is_identifier(char):
            return idx
    return -1 # a non-identifier is not found
