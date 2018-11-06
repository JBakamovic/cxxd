import os
import tempfile

class FileGenerator():
    @staticmethod
    def gen_header_file_containing_includes_only(edited=False):
        fd = tempfile.NamedTemporaryFile(suffix='.cpp', bufsize=0)
        if edited:
            fd.write('\
#include <vector>           \n\
                            \n\
#include <map>              \n\
                            \n\
            ')
        else:
            fd.write('\
#include <vector>           \n\
#include <map>              \n\
            ')
        return fd

    @staticmethod
    def gen_simple_cpp_file(edited=False):
        fd = tempfile.NamedTemporaryFile(suffix='.cpp', bufsize=0)
        if edited:
            fd.write('\
#include <vector>           \n\
                            \n\
                            \n\
int foobar() {              \n\
    return 0;               \n\
}                           \n\
                            \n\
int main() {                \n\
    std::vector<int> v;     \n\
    int result = foobar();  \n\
    return result;          \n\
}                           \n\
                            \n\
int fun() {                 \n\
    return 1;               \n\
}                           \n\
            ')
        else:
            fd.write('\
#include <vector>           \n\
                            \n\
int foobar() {              \n\
    return 0;               \n\
}                           \n\
                            \n\
int main() {                \n\
    std::vector<int> v;     \n\
    return foobar();        \n\
}                           \n\
                            \n\
int fun() {                 \n\
    return 1;               \n\
}                           \n\
            ')
        return fd

    @staticmethod
    def gen_broken_cpp_file(edited=False):
        fd = tempfile.NamedTemporaryFile(suffix='.cpp', bufsize=0)
        if edited:
            fd.write('\
#include <vector>           \n\
#include "does_not_exist.h" \n\
                            \n\
trigger compile error       \n\
                            \n\
int foobar() {              \n\
    return 0;               \n\
}                           \n\
                            \n\
int main() {                \n\
    std::vector<int> v;     \n\
    return foobar();        \n\
}                           \n\
                            \n\
int fun() {                 \n\
    return bar();           \n\
}                           \n\
            ')
        else:
            fd.write('\
#include <vector>           \n\
#include "does_not_exist.h" \n\
                            \n\
                            \n\
trigger compile error       \n\
                            \n\
int foobar() {              \n\
    return 0;               \n\
}                           \n\
                            \n\
int main() {                \n\
    std::vector<int> v;     \n\
    return foobar();        \n\
}                           \n\
                            \n\
int fun() {                 \n\
    return bar();           \n\
}                           \n\
            ')
        return fd

    @staticmethod
    def gen_txt_compilation_database():
        txt_compile_flags = [
            '-D_GLIBCXX_DEBUG',
            '-Wabi',
            '-Wconversion',
            '-Winline',
        ]
        fd = open(tempfile.gettempdir() + os.path.sep + 'compile_flags.txt', 'w', 0)
        fd.write('\n'.join(txt_compile_flags))
        return fd

    @staticmethod
    def gen_json_compilation_database(filename):
        fd = open(tempfile.gettempdir() + os.path.sep + 'compile_commands.json', 'w', 0)
        fd.write(('\
[                                               \n\
{{                                              \n\
    "directory": "{0}",                         \n\
    "command": "/usr/bin/c++ -o {1}.o -c {2}",  \n\
    "file": "{3}"                               \n\
}}                                              \n\
]                                               \n\
        ').format(tempfile.gettempdir(), filename, filename, filename))
        return fd

    @staticmethod
    def gen_clang_format_config_file():
        fd = tempfile.NamedTemporaryFile(suffix='.clang-format', bufsize=0)
        fd.write('\
BasedOnStyle: LLVM                      \n\
AccessModifierOffset: -4                \n\
AlwaysBreakTemplateDeclarations: true   \n\
ColumnLimit: 100                        \n\
Cpp11BracedListStyle: true              \n\
IndentWidth: 4                          \n\
MaxEmptyLinesToKeep: 2                  \n\
PointerBindsToType: true                \n\
Standard: Cpp11                         \n\
TabWidth: 4                             \n\
        ')
        return fd

    @staticmethod
    def gen_cxxd_config_filename():
        fd = open(tempfile.gettempdir() + os.path.sep + '.cxxd_config.json', 'w', 0)
        fd.write('\
{                                               \n\
    "indexer" : {                               \n\
        "exclude-dirs": [                       \n\
            "test",                             \n\
            "CMake",                            \n\
            "CMakeFiles"                        \n\
         ]                                      \n\
    },                                          \n\
    "clang-tidy" : {                            \n\
        "args": {                               \n\
            "-analyze-temporary-dtors" : true,  \n\
            "-explain-config" : false,          \n\
            "-format-style" : "llvm"            \n\
        }                                       \n\
    },                                          \n\
    "clang-format" : {                          \n\
        "args": {                               \n\
            "-sort-includes" : true,            \n\
            "-style" : "llvm",                  \n\
            "-verbose" : true                   \n\
        }                                       \n\
    },                                          \n\
    "project-builder" : {                       \n\
        "args": {                               \n\
            "--verbose" : true                  \n\
        }                                       \n\
    }                                           \n\
}                                               \n\
        ')
        return fd

    @staticmethod
    def gen_empty_cxxd_config_filename():
        fd = open(tempfile.gettempdir() + os.path.sep + '.empty_cxxd_config.json', 'w', 0)
        fd.write('\
{                                               \n\
    "indexer" : {                               \n\
        "exclude-dirs": [                       \n\
         ]                                      \n\
    },                                          \n\
    "clang-tidy" : {                            \n\
        "args": {                               \n\
        }                                       \n\
    },                                          \n\
    "clang-format" : {                          \n\
        "args": {                               \n\
        }                                       \n\
    },                                          \n\
    "project-builder" : {                       \n\
        "args": {                               \n\
        }                                       \n\
    }                                           \n\
}                                               \n\
        ')
        return fd

    @staticmethod
    def close_gen_file(fd):
        os.remove(fd.name)
