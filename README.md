# Contents
* [About](#about)
  * [Feature overview](#feature-overview)
  * [Supported platforms](#supported-platforms)
  * [Dependencies](#dependencies)
* [Configuration](#configuration)
  * [Compilation database](#compilation-database)
    * [compile_commands.json](#compile-commands-json)
    * [compile_flags.txt](#compile-flags-txt)
* [Example of configuration](#example-of-configuration)
* [FAQ](#faq)
* [Screenshots](#screenshots)

# About

`cxxd` is a C/C++ language server which offers rich support for features that aid the process of source code navigation, editing, source code formatting, static analysis etc. One can utilize it, for example, to bring IDE-like features to an editor of your choice.

## Feature overview

Feature | Status | [cxxd-vim frontend](https://github.com/JBakamovic/cxxd-vim)
------------ | :-------------: | :-------------:
Indexer | :heavy_check_mark: | :heavy_check_mark:
Indexer-diagnostics | :heavy_check_mark: | :heavy_check_mark:
Code-completion | :heavy_check_mark: | :heavy_check_mark:
Semantic-syntax-highlighting | :heavy_check_mark: | :heavy_check_mark:
Find-all-references | :heavy_check_mark: | :heavy_check_mark:
Go-to-definition | :heavy_check_mark: | :heavy_check_mark:
Go-to-include | :heavy_check_mark: | :heavy_check_mark:
Type-hints | :heavy_check_mark: | :heavy_check_mark:
Fixits-and-diagnostics | :heavy_check_mark: | :heavy_check_mark:
Clang-tidy integration | :heavy_check_mark: | :heavy_check_mark:
Clang-format integration | :heavy_check_mark: | :heavy_check_mark:
JSON-compilation-database integration | :heavy_check_mark: | :heavy_check_mark:
Plain-text-compilation-database integration | :heavy_check_mark: | :heavy_check_mark:
Arbitrary build targets integration | :heavy_check_mark: | :heavy_check_mark:
Per-repository cxxd custom configuration (JSON) | :heavy_check_mark: | :heavy_check_mark:

In essence, the main idea behind it is very much alike to what [`LSP`](https://microsoft.github.io/language-server-protocol/) offers 
and its implementations like [`clangd`](https://clang.llvm.org/extra/clangd.html).

## Supported platforms
Platform | Status | Comments
------------ | :-------------: | :-------------:
Linux | :heavy_check_mark: | Main development environment of this project.
Other platforms | :x: | Not officially tested but should work wherever `python3` and `libclang` is available

## Supported frontends (editors)

Editor | Link | Description
------------ | ------------- | -------------
Vim | [`cxxd-vim`](https://github.com/JBakamovic/cxxd-vim) | A PoC Vim plugin integration that I did for this project and which became my daily driver since then.

## Dependencies

Required: `Python3`, `libclang` (with `Python` bindings)

Optional: `clang-format`, `clang-tidy`

Platform | Install
------------ | -------------
`Fedora` | `sudo dnf install python3 clang-devel clang-libs clang-tools-extra && pip install --user clang`
`Debian` | `sudo apt-get install python3 libclang-dev clang-tidy clang-format && pip install --user clang`

# Configuration

To run `cxxd` server against the source code one should provide `.cxxd_config.json` configuration file and put it into the root of the project repository.

This file can be used to provide project-specific configurations such as:

Category | Type | Value | Description
------------ | ------------- | ------------- | ------------- 
 `configuration` | | | `cxxd` at the bare minimum requires either `compile_commands.json` or `compile_flags.txt` to be provided with the project.
 . | `type` | `compilation-database`, `compile-flags`, `auto-discovery` | Depending on how do you want to run `cxxd` server against your project select one of those options. While `compilation-database` is the most recommended way which should be used for real-world projects, `compile-flags` is provided only for convenience purposes and should be used only for a very simple and small projects. With `auto-discovery` option, `cxxd` will try to figure out itself what type of configuration is project using. If no `type` is provided then `cxxd` will fallback to implicit `auto-discovery-try-harder` mode.
 . | `compilation-database` | `target : { build-target1:build-dir1, ..., build-targetN:build-dirN}` | Real-world projects will have different build target configurations and `target` field can be used to define a list of relevant build targets and their accompanying build directories. E.g. `compilation-database : { target : { 'debug': 'build/debug', 'relwithdebinfo': 'build/relwithdebinfo', 'debug-asan': 'build/debug-asan'}}`
 . | `compile-flags` | Same as with `compilation-database` option. | Same as with `compilation-database` option.
 . | `auto-discovery` | `search-paths: [list of directories]` | Cannot be used for defining arbitrary build targets. Provided only as a quickstart convenience method. Use `search-paths` field to provide a list of directories where `cxxd` will look for `compile_commands.json` or `compile_flags.txt`. If not provided `cxxd` will use some of the implicitly predefined search paths.
 `project-builder` | | | To make use of previously defined build-targets from `configuration::compilation-database` or `configuration::compile-flags` here we can define the actual build commands to be run by `cxxd` server.
 . | `target` | `target : { build-target1: { cmd: build-target1-specific-build-cmd }, ..., build-targetN: {cmd: build-targetN-specific-build-cmd}` | Mind that build-target names used here must match the build-target names used in `configuration::compilation-database` or `configuration::compile-flags`. Example of build-target commands: `target : { 'debug': 'cmake . -GNinja -DCMAKE_BUILD_TYPE=Debug -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DCMAKE_CXX_COMPILER_LAUNCHER=ccache && ninja', 'relwithdebinfo': 'cmake . -GNinja -DCMAKE_BUILD_TYPE=RelWithDebInfo -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DCMAKE_CXX_COMPILER_LAUNCHER=ccache && ninja', 'debug-asan': 'cmake . -GNinja -DCMAKE_BUILD_TYPE=Debug -DENABLE_ASAN=ON -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DCMAKE_CXX_COMPILER_LAUNCHER=ccache && ninja'}}`. You can add any amount of arbitrary build target commands here.
  `indexer` | | | Source-code indexing related settings.
 . | `exclude-dirs` | A list of directories | Used as a hint to `cxxd` indexer to exclude certain <directory> from being indexed. Commonly these can be directories such as `build`, `cmake`, `external`, `third-party` etc.
 . | `extra-file-extensions` | A list of file extensions| Used as a hint to `cxxd` indexer to also index files with non-standard C or C++ extensions that your project might be using. `cxxd` will try hard to implicitly identify most of the non-standard C and C++ extensions found in the wild but in case it doesn't, this is a setting for it.
  `clang-format` | | | Here we can customize how we want to use `clang-format` for given repository.
 . | `binary` | path-to-specific-clang-format-binary | Sometimes system-wide installed `clang-format` version will not match the needs of real-world projects. It can be either too old or too recent. This setting allows to set the specific version of `clang-format` binary provided that the one exists in the given path. E.g. `'binary': '/opt/clang+llvm-8.0.0-x86_64-linux-gnu/bin/clang-format'`.
 . | `args` | `clang-format` specific cmd-line args | Here we can provide a list of any arguments that we want to pass over to `clang-format` invocation. For example, applying `clang-format` immediatelly and in-place following the `clang-format` configuration hosted by our repository can be done with `'args' : { '-i' : true, '--style' : 'file' }`. We can use this list to basically pass any argument that given version of `clang-format` can recognize and tweak it according to the project-specific needs.
 `clang-tidy` | | | Here we can customize how we want to use `clang-tidy` for given repository.
 . | `binary` | path-to-specific-clang-tidy-binary | Sometimes system-wide installed `clang-tidy` version will not match the needs of real-world projects. It can be either too old or too recent. This setting allows to set the specific version of `clang-tidy` binary provided that the one exists in the given path. E.g. `'binary': '/opt/clang+llvm-8.0.0-x86_64-linux-gnu/bin/clang-tidy'`.
 . | `args` | `clang-tidy` specific cmd-line args | Here we can provide a list of any arguments that we want to pass over to `clang-tidy` invocation. For example, to enable bugprone, cppcoreguidelines and readability `clang-tidy` checks we would do `'args' : { '-checks' : "'-*,bugprone-*,cppcoreguidelines-*,readability-*'", "-extra-arg" : "'-Wno-unknown-warning-option'", '-header-filter' : '.*' }`. We can use this list to basically pass any argument that given version of `clang-tidy` can recognize and tweak it according to the project-specific needs.
 `clang` | | | Here we can optionally set some of the `clang`-specific settings. Should be needed very rarely.
 . | `library-file` | path-to-specific-libclang-so-library | When updating your system, sometimes a new version of `libclang` can introduce bugs or changes in behavior which will result with glitches in the usage experience. Same can happen with the python bindings of `libclang`. Because `cxxd` does not have a capacity to be tested against every version of `libclang` and its python bindings, `library-file` serves the purpose to tell `cxxd` to use a certain version of `libclang`. If not provided, `cxxd` will by default use the system-wide one, which in most cases should be enough. However, if you suddenly start to experience the issues, which you have not before, this should be a first thing to check. And possibly revert the `libclang` version to an earlier one. E.g. `'library-file': '/usr/lib64/libclang.so.14.0.5'`.

## Compilation database

Compilation database is a requirement for `cxxd`. It can come in two different forms: `compile_commands.json` (recommended) or `compile_flags.txt` (should be used only as a fallback when generating `compile_commands.json` is not possible)

### compile_commands.json

TL;DR in CMake projects you would simply add `-DCMAKE_EXPORT_COMPILE_COMMANDS=ON` to your CMake build invocation call. Or you could bake this setting into the `CMakeLists.txt` with `set(CMAKE_EXPORT_COMPILE_COMMANDS ON)`. And you're done.

`CMake`/`Bazel`/`waf`/`Qbs`/`ninja`/`clang` have native and built-in support for generating this type of compilation database. [Here's](https://sarcasm.github.io/notes/dev/compilation-database.html#build-systems-and-compilers) a good summary on how to use each of those. If you don't use any of those build systems, then [same page](https://sarcasm.github.io/notes/dev/compilation-database.html#specialized-tools) provides another good summary on how to try to generate the compilation database in alternative ways.

### compile_flags.txt

If generating the `compile_commands.json` is not possible to achieve within your environment, you can hand-code the build flags yourself and put it into the file named `compile_flags.txt`. E.g.

```
-I./lib
-I./include
-DFEATURE_XX
-DFEATURE_YY
-Wall
-Werror
```

# Example of configuration

For completness and quickstart sake here's an example of a config file that I used while hacking on the MySQL database engine at Oracle. You can use it as starting point to create your own.

I used out-of-source builds with plenty of different ways to build and test the code. My regular workflow included running both sanitized (ASAN, UBSAN) and non-sanitized `debug` or `relwithdebinfo` builds. Sometimes I also had to test or backport the changes from MySQL 8.x to MySQL 5.x so I also had the build targets for that purpose. Later on I even tweaked the build target commands to include the way to run the build in distributed fashion through `distcc` and `icecream`.

`clang-format` version had to strictly adhere to specific version declared to be used by MySQL. Occassionally this version would be bumped so I also occassionally bumped the version in the config file.

Some parts of the MySQL used non-standard file extensions for the source code such as `*.ic`, `.i` or `*.tpp`. To make them visible to the `cxxd` indexer I have enumerated them in the `extra-file-extensions` field. Similarly, I have hinted the `cxxd` indexer not to index 3rd-party source code that is found in `extra` directory.

```
{
    "configuration" : {
        "type" : "compilation-database",
        "compilation-database" : {
            "target" : {
                "debug" : "../build/trunk/debug",
                "debug_asan" : "../build/trunk/debug_asan",
                "debug_ubsan" : "../build/trunk/debug_ubsan",
                "relwithdebinfo" : "../build/trunk/relwithdebinfo",
                "relwithdebinfo_asan" : "../build/trunk/relwithdebinfo_asan",
                "relwithdebinfo_ubsan" : "../build/trunk/relwithdebinfo_ubsan",
                "debug5" : "../build/5.x/debug",
                "relwithdebinfo5" : "../build/5.x/relwithdebinfo",
             }
        }
    },
    "indexer" : {
        "exclude-dirs" : [
            "extra"
        ],
        "extra-file-extensions" : [
            ".ic",
            ".i",
            ".tpp"
        ]
    },
    "clang-tidy" : {
        "args" : {
            "-checks" : "'-*,bugprone-*,cert-*,clang-analyzer-*,-clang-analyzer-osx*,misc-*,performance-*,portability-*,readability-*",
            "-extra-arg" : "'-Wno-unknown-warning-option'",
            "-header-filter" : ".*"
        }
    },
    "clang-format" : {
        "binary" : "/opt/clang+llvm-8.0.0-x86_64-linux-gnu/bin/clang-format",
        "args" : {
            "-i" : true,
            "--style" : "file"
        }
    },
    "project-builder" : {
        "target" : {
            "debug" : {
                "cmd" : "cmake ../../../trunk -GNinja -DCMAKE_BUILD_TYPE=Debug -DDOWNLOAD_BOOST=ON -DWITH_BOOST=../ -DWITH_UNIT_TESTS=ON -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DCMAKE_CXX_COMPILER_LAUNCHER=ccache && ninja"
            },
            "debug_asan" : {
                "cmd" : "cmake ../../../trunk -GNinja -DCMAKE_BUILD_TYPE=Debug -DDOWNLOAD_BOOST=ON -DWITH_BOOST=../ -DWITH_UNIT_TESTS=ON -DWITH_ASAN=ON -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DCMAKE_CXX_COMPILER_LAUNCHER=ccache && ninja"
            },
            "debug_ubsan" : {
                "cmd" : "cmake ../../../trunk -GNinja -DCMAKE_BUILD_TYPE=Debug -DDOWNLOAD_BOOST=ON -DWITH_BOOST=../ -DWITH_UNIT_TESTS=ON -DWITH_UBSAN=ON -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DCMAKE_CXX_COMPILER_LAUNCHER=ccache && ninja"
            },
            "relwithdebinfo" : {
                "cmd" : "cmake ../../../trunk -GNinja -DCMAKE_BUILD_TYPE=RelWithDebInfo -DDOWNLOAD_BOOST=ON -DWITH_BOOST=../ -DWITH_UNIT_TESTS=ON -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DCMAKE_CXX_COMPILER_LAUNCHER=ccache && ninja"
            },
            "relwithdebinfo_asan" : {
                "cmd" : "cmake ../../../trunk -GNinja -DCMAKE_BUILD_TYPE=RelWithDebInfo -DDOWNLOAD_BOOST=ON -DWITH_BOOST=../ -DWITH_UNIT_TESTS=ON -DWITH_ASAN=ON -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DCMAKE_CXX_COMPILER_LAUNCHER=ccache && ninja"
            },
            "relwithdebinfo_ubsan" : {
                "cmd" : "cmake ../../../trunk -GNinja -DCMAKE_BUILD_TYPE=RelWithDebInfo -DDOWNLOAD_BOOST=ON -DWITH_BOOST=../ -DWITH_UNIT_TESTS=ON -DWITH_UBSAN=ON -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DCMAKE_CXX_COMPILER_LAUNCHER=ccache && ninja"
            },
            "debug5" : {
                "cmd" : "cmake ../../../5.x -GNinja -DCMAKE_BUILD_TYPE=Debug -DDOWNLOAD_BOOST=ON -DWITH_BOOST=../ -DWITH_UNIT_TESTS=ON -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DCMAKE_CXX_COMPILER_LAUNCHER=ccache && ninja"
            },
            "relwithdebinfo5" : {
                "cmd" : "cmake ../../../5.x -GNinja -DCMAKE_BUILD_TYPE=RelWithDebInfo -DDOWNLOAD_BOOST=ON -DWITH_BOOST=../ -DWITH_UNIT_TESTS=ON -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DCMAKE_CXX_COMPILER_LAUNCHER=ccache && ninja"
            },
        }
    }
}
```

# FAQ

## How do I make use of this in <insert_environment_of_your_choice>?

Currently there's only a Vim [cxxd-vim](https://github.com/JBakamovic/cxxd-vim) plugin that I have developed as a PoC and which I have been using as my daily driver since then. On a semi-regular base I try to keep it up to date with the bugfixes and less often with the new features.

To integrate `cxxd` with another editor one should read through the [architecture overview](arch.md). Also, file a ticket if you need help.

## What about clangd and other language server implementations

Fun fact: this project actually started to grow the [whole idea and implementation](https://github.com/JBakamovic/yavide/commit/1100b027ba80637c2382913cb14f1a8ea34f3930#diff-a74ad8dfacd4f985eb3977517615ce25) 
before [LSP (and clangd) has been put into life](https://code.visualstudio.com/blogs/2016/06/27/common-language-protocol). And I am basically hacking on `cxxd` and `cxxd-vim` codebase since then. But I do it only occassionaly and as much as my spare time allows me to.

It turns out that writing a language server implementation on top of the `libclang` backend is a mine field. Complex C and C++ compilation process doesn't make this situation any easier. Variety of build systems available and multitude of different ways on how you can build a model of your code due to arbitary number of build targets also makes it a bigger challenge. And only because I implemented both the language server side and the UI frontend side that accompanies it, and everything from the scratch, it happens that I find it easier (and more fun!) to hack through my own codebase and learning something new rather than waiting on other similar tools to provide the fixes, if at all. I tried many of them and they all experience from same or similar issues I stumble upon as well. YMMV of course.

I also implemented a non-LSP compatible protocol which means that I am free to decide and integrate whatever I find interesting for a development workflow. One such example is support for arbitrary build targets which happens to have an actual impact on how the language server backend will understand your code or will not. Browsing or indexing or code-completion context isn't the same across "debug" or "debug-with-some-fancy-feature" or "relwithdebinfo" targets. For that reason, `cxxd` is always started against the specific build target.

# Screenshots

To see how it looks like in action you may have a look at the [screenshots from cxxd-vim](https://github.com/JBakamovic/cxxd-vim/blob/master/README.md#screenshots).