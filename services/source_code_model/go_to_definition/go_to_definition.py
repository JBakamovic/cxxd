from builtins import str
from builtins import object
import logging
import os

class GoToDefinition(object):
    def __init__(self, parser, symbol_db, project_root_directory):
        self.parser = parser
        self.symbol_db = symbol_db
        self.project_root_directory = project_root_directory

    def __call__(self, args):
        original_filename = str(args[0])
        contents_filename = str(args[1])
        line              = int(args[2])
        column            = int(args[3])

        def_filename, def_line, def_column = None, None, None
        cursor = self.parser.get_cursor(
                    self.parser.parse(contents_filename, original_filename),
                    line, column
                )
        definition = self.parser.get_definition(cursor)

        # If unsuccessful, try once more by extracting the definition from indexed symbol database
        if not definition:
            logging.error('{0}'.format(cursor.referenced.get_usr() if cursor.referenced else cursor.get_usr()))
            definition = self.symbol_db.fetch_symbol_definition_by_usr(
                            cursor.referenced.get_usr() if cursor.referenced else cursor.get_usr(),
                         )
            if definition:
                def_filename, def_line, def_column = os.path.join(
                        self.project_root_directory, self.symbol_db.get_symbol_filename(definition[0])
                    ), self.symbol_db.get_symbol_line(definition[0]), self.symbol_db.get_symbol_column(definition[0])
        else:
            loc = definition.location
            def_filename, def_line, def_column = loc.file.name, loc.line, loc.column

        # If we are currently editing the file and our resulting cursor is exactly in that file,
        # then we should be reporting original filename instead of the temporary one.
        # That makes it possible to jump to definitions in edited (and not yet saved) files.
        if contents_filename != original_filename:
            if def_filename == contents_filename:
                def_filename = original_filename

        return def_filename is not None, [def_filename, def_line, def_column]
