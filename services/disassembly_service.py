import cxxfilt
import io
import json
import logging
import os
import shlex
import subprocess
import tempfile
import time

import cxxd.parser.clang_parser
import cxxd.parser.tunit_cache
import cxxd.service

class DisassemblyRequestId():
    LIST_TARGETS = 0x0
    LIST_SYMBOL_CANDIDATES = 0x1
    DISASSEMBLE = 0x2
    ASM_INSTRUCTION_INFO = 0x3

class NmSymbol:
    def __init__(self, name, type, addr, offset, filename, line_nr):
        self._name = name
        try:
            # Sometimes I stumble upon on a symbol which cannot be demangled so let's handle that case and use mangled name instead
            self._demangled_name = cxxfilt.demangle(name)
        except:
            self._demangled_name = name
        self._type = type
        self._addr = addr
        self._offset = offset
        self._filename = filename
        self._line_nr = line_nr

    @property
    def name(self):
        return self._name

    @property
    def demangled_name(self):
        return self._demangled_name

    @property
    def type(self):
        return self._type

    @property
    def addr(self):
        return self._addr

    @property
    def offset(self):
        return self._offset

    @property
    def location(self):
        if self._filename == '' and self._line_nr == '':
            return ''
        return self._filename + ':' + self._line_nr

    def __repr__(self):
        return self.demangled_name + ' ' + self.type + ' ' + self.addr + ' ' + self.offset + ' ' + self.location

    @staticmethod
    def make(nm_output):
        # nm output format depends on how we invoke it but should usually contain at least the following details
        #   <mangled_symbol> <symbol_type> <symbol_value>
        # Additionally, we may ask for <path_to_source_code>:<line> which the symbol entry corresponds to but this
        # information in some cases isn't available.
        nm = nm_output.split()
        location = nm[4].split(':') if len(nm) > 4 else ['', '']
        return NmSymbol(nm[0], nm[1], nm[2], nm[3], location[0], location[1])

class Disassembly(cxxd.service.Service):
    def __init__(self, project_root_directory, cxxd_config_parser, target, service_plugin):
        cxxd.service.Service.__init__(self, service_plugin)
        self.project_root_directory = project_root_directory
        self.cxxd_config_parser = cxxd_config_parser
        self.parser = cxxd.parser.clang_parser.ClangParser(
            cxxd_config_parser.get_configuration_for_target(target),
            cxxd.parser.tunit_cache.TranslationUnitCache(cxxd.parser.tunit_cache.FifoCache(20)),
            cxxd_config_parser.get_clang_library_file(),
        )
        self.amd64_asm_json = os.path.join(os.path.abspath(os.path.dirname(__file__)), '../asm/asm-docs-amd64.json')
        self.build_dir = cxxd_config_parser.get_project_builder_build_dir(target)
        self.target_lookup_dir = os.path.join(self.project_root_directory, self.build_dir)
        self.service = {
            DisassemblyRequestId.LIST_TARGETS : self._list_targets,
            DisassemblyRequestId.LIST_SYMBOL_CANDIDATES : self._list_symbol_candidates,
            DisassemblyRequestId.DISASSEMBLE : self._disassemble,
            DisassemblyRequestId.ASM_INSTRUCTION_INFO: self._info_on_asm_instruction,
        }
        self.disassembly_output = None
        self.disassembly_binary = None
        self.nm_binary = None
        self.last_disassembled_binary = None
        self.last_disassembled_timestamp = None

    def startup_callback(self, args):
        logging.info('Disassembly service started.')
        self.disassembly_binary = self.cxxd_config_parser.get_disassembly_binary_path()
        self.nm_binary = self.cxxd_config_parser.get_nm_binary_path()
        if self.disassembly_binary is None or self.nm_binary is None:
            logging.error('Revisit your .cxxd_config or update your system-wide installation of objdump and nm.')
            return False, []
        self.disassembly_output = tempfile.NamedTemporaryFile(suffix='_disassembly_output.asm')
        self.disassembly_targets_filter = self.cxxd_config_parser.get_disassembly_targets_filter()
        self.cxxd_config_objdump_options = self._cxxd_config_objdump_options()
        return True, []

    def shutdown_callback(self, args):
        logging.info('Disassembly service stopped.')
        return True, []

    def _unknown_service(self, args):
        logging.error("Unknown service triggered! Valid services are: {0}".format(self.service))
        return False, None

    def _list_targets(self, args):
        def matches_disassembly_filter(target):
            for f in self.disassembly_targets_filter:
                if f in target:
                    return True
            return False

        logging.info('Listing targets in {}'.format(self.target_lookup_dir))
        target_candidates = []
        proc = subprocess.Popen(["find", self.target_lookup_dir, "-type", "f", "-executable"], stdout=subprocess.PIPE)
        for target in io.TextIOWrapper(proc.stdout, encoding="utf-8"):
            if not matches_disassembly_filter(target):
                target_candidates.append(target)
        target_candidates.sort()
        logging.info('Targets found: {}'.format(target_candidates))
        return True, target_candidates

    def _list_symbol_candidates(self, args):
        target, filename, line, col = args
        logging.info('About to search for symbol candidates in target \'{}\' by using the symbol at {}:{},{}'.format(target, filename, line, col))

        tunit = self.parser.parse(filename, filename)
        cursor = self.parser.get_cursor(tunit, int(line), int(col))
        definition = self.parser.get_definition(cursor)
        symbol_ast_name = self.parser.get_ast_node_name(definition) if definition is not None else ''
        mangled_symbol = definition.mangled_name if definition is not None else ''
        mangled = []
        ast = []
        self.candidates = []

        logging.info('Symbol mangled name: {}'.format(mangled_symbol))
        logging.info('Symbol AST node name: {}'.format(symbol_ast_name))

        cmd = self.nm_binary + ' -P --size-sort ' + target
        logging.info('Command \'{}\''.format(cmd))
        with subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE) as proc:
            for entry in io.TextIOWrapper(proc.stdout, encoding="utf-8"):
                if len(mangled_symbol):
                    if mangled_symbol in entry:
                        logging.debug('Mangled symbol found {}'.format(entry))
                        mangled.append(NmSymbol.make(entry))
                        break
                if len(symbol_ast_name):
                    if symbol_ast_name in entry:
                        logging.debug('Approximate symbol found {}'.format(entry))
                        ast.append(NmSymbol.make(entry))
        self.candidates = mangled if len(mangled) else ast
        self.candidates = sorted(self.candidates, key=lambda symbol: symbol.demangled_name)
        logging.info(self.candidates)
        return True, list(self.candidates)

    def _disassemble(self, args):
        target = args[0]
        symbol_entry_idx = int(args[1])
        symbol = self.candidates[symbol_entry_idx]

        # Only disassemble when:
        #  (1) we haven't done it already or
        #  (2) we switched to a new target or
        #  (3) we disassembled it already and kept the same target but have recompiled it
        if self.last_disassembled_binary is None or self.last_disassembled_binary != target or self.last_disassembled_timestamp != os.path.getmtime(target):
            logging.info('Disassemblying  the target \'{}\' to search for the symbol \'{}\''.format(target, symbol.name))
            cmd = self.disassembly_binary + ' -d -C --no-show-raw-insn '  + self.cxxd_config_objdump_options + ' ' + target
            with open(self.disassembly_output.name, 'w') as f:
                ret = subprocess.call(cmd, shell=True, stdout=f)
                logging.info("Disassembly completed. Command = '{}'".format(cmd))
                self.last_disassembled_binary = target
                self.last_disassembled_timestamp = os.path.getmtime(target)
        else:
            logging.info('Target {} was already disassembled. Reusing it.'.format(target))

        return True, [self.disassembly_output.name, symbol.addr, symbol.offset]

    def _info_on_asm_instruction(self, args):
        instruction = str(args[0])
        with open(self.amd64_asm_json) as f:
            asm = json.load(f)
            if instruction.upper() in asm:
                return True, [
                        asm[instruction.upper()]['tooltip'],
                        asm[instruction.upper()]['body'],
                        asm[instruction.upper()]['url']
                    ]
            # Instruction not found, try searching against the synonyms (subset of)
            # Some instructions have the synonyms
            candidates = [val for key,val in asm.items() if instruction.upper() in key]
            for instr in candidates:
                for synonym in instr['names']:
                    if synonym == instruction.upper():
                        return True,  [
                            instr['tooltip'],
                            instr['body'],
                            instr['url']
                    ]
            # If that didn't work out, try harder by creating a list of (instr-name, [instr-name-synonyms]) tuples
            candidates = [(key,val['names']) for key,val in asm.items()]
            # And then search through this list to try finding the synonym
            for instr,synonyms in candidates:
                for synonym in synonyms:
                    if synonym == instruction.upper():
                        return True,  [
                            asm[instr]['tooltip'],
                            asm[instr]['body'],
                            asm[instr]['url']
                        ]
        return True, ['', '', '']

    def _cxxd_config_objdump_options(self):
        args = ''
        intermix_with_source_code = self.cxxd_config_parser.get_disassembly_intermix_with_src_code()
        visualize_jumps = self.cxxd_config_parser.get_disassembly_visualize_jumps()
        syntax = self.cxxd_config_parser.get_disassembly_syntax()
        # Default is not to intermix source code with assembly
        if intermix_with_source_code is not None:
            if intermix_with_source_code:
                args = args + ' -S '
        # Default is to visualize the jumps
        if visualize_jumps is not None:
            if visualize_jumps:
                args = args + ' --visualize-jumps '
        else:
            args = args + ' --visualize-jumps '
        # Default is the intel syntax (assuming x86-64 for now)
        if syntax is not None:
            args = args + ' -M ' + syntax + ' '
        else:
            args = args + ' -M intel '
        return args

    def __call__(self, args):
        return self.service.get(int(args[0]), self._unknown_service)(args[1:len(args)])
