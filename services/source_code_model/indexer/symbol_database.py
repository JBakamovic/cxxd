from builtins import object
import logging
import sqlite3
import sys

class DiagnosticsSortingStrategyId(object):
    BY_NONE          = 0x0
    BY_SEVERITY_ASC  = 0x1
    BY_SEVERITY_DESC = 0x2
    BY_FILENAME      = 0x3

class SymbolDatabase(object):
    VERSION_MAJOR = 0
    VERSION_MINOR = 2

    def __init__(self, db_filename = None):
        self.filename = db_filename
        if db_filename:
            try:
                self.db_connection = sqlite3.connect(db_filename)
            except:
                logging.error(sys.exc_info())
        else:
            self.db_connection = None

    def __del__(self):
        if self.db_connection:
            try:
                self.db_connection.close()
            except:
                logging.error(sys.exc_info())

    def open(self, db_filename):
        if not self.db_connection:
            try:
                self.db_connection = sqlite3.connect(db_filename)
                self.filename = db_filename
            except:
                logging.error(sys.exc_info())

    def close(self):
        if self.db_connection:
            try:
                self.db_connection.close()
                self.db_connection = None
            except:
                logging.error(sys.exc_info())

    def is_open(self):
        return self.db_connection is not None

    def get_symbol_filename(self, row):
        return row[0].encode('utf8', 'ignore')

    def get_symbol_line(self, row):
        return row[1]

    def get_symbol_column(self, row):
        return row[2]

    def get_symbol_usr(self, row):
        return row[3].encode('utf8', 'ignore')

    def get_symbol_context(self, row):
        return row[4].encode('utf8', 'ignore')

    def get_symbol_kind(self, row):
        return row[5]

    def get_symbol_is_definition(self, row):
        return row[6]

    def get_diagnostics_id(self, row):
        return row[0]

    def get_diagnostics_filename(self, row):
        return row[1].encode('utf8', 'ignore')

    def get_diagnostics_line(self, row):
        return row[2]

    def get_diagnostics_column(self, row):
        return row[3]

    def get_diagnostics_description(self, row):
        return row[4].encode('utf8', 'ignore')

    def get_diagnostics_severity(self, row):
        return row[5]

    def get_diagnostics_details_id(self, row):
        return row[0]

    def get_diagnostics_details_filename(self, row):
        return row[1].encode('utf8', 'ignore')

    def get_diagnostics_details_line(self, row):
        return row[2]

    def get_diagnostics_details_column(self, row):
        return row[3]

    def get_diagnostics_details_description(self, row):
        return row[4].encode('utf8', 'ignore')

    def get_diagnostics_details_severity(self, row):
        return row[5]

    def fetch_all_symbols(self):
        rows = []
        try:
            # TODO Use generators
            rows = self.db_connection.cursor().execute('SELECT * FROM symbol').fetchall()
        except:
            logging.error(sys.exc_info())
        return rows

    def fetch_symbols_by_usr(self, usr):
        rows = []
        try:
            rows = self.db_connection.cursor().execute('SELECT * FROM symbol WHERE usr=?', (usr,)).fetchall()
        except:
            logging.error(sys.exc_info())
        return rows

    def fetch_symbol_definition_by_usr(self, usr):
        rows = []
        try:
            rows = self.db_connection.cursor().execute('SELECT * FROM symbol WHERE usr=? AND is_definition=1',(usr,)).fetchall()
        except:
            logging.error(sys.exc_info())
        return rows

    def fetch_all_diagnostics(self, sorting_strategy):
        rows = []
        try:
            # TODO Use generators
            if sorting_strategy == DiagnosticsSortingStrategyId.BY_NONE:
                rows = self.db_connection.cursor().execute('SELECT * FROM diagnostics').fetchall()
            elif sorting_strategy == DiagnosticsSortingStrategyId.BY_SEVERITY_ASC:
                rows = self.db_connection.cursor().execute('SELECT * FROM diagnostics ORDER BY severity ASC').fetchall()
            elif sorting_strategy == DiagnosticsSortingStrategyId.BY_SEVERITY_DESC:
                rows = self.db_connection.cursor().execute('SELECT * FROM diagnostics ORDER BY severity DESC').fetchall()
            elif sorting_strategy == DiagnosticsSortingStrategyId.BY_FILENAME:
                rows = self.db_connection.cursor().execute('SELECT * FROM diagnostics ORDER BY filename ASC').fetchall()
            else:
                logging.error('Inexisting diagnostics sorting strategy chosen!')
        except:
            logging.error(sys.exc_info())
        return rows

    def fetch_diagnostics_details(self, diagnostics_id):
        rows = []
        try:
            # TODO Use generators
            rows = self.db_connection.cursor().execute('SELECT * FROM diagnostics_details WHERE diagnostics_id = ?', (diagnostics_id,)).fetchall()
        except:
            logging.error(sys.exc_info())
        return rows

    def fetch_all_diagnostics_details(self):
        rows = []
        try:
            # TODO Use generators
            rows = self.db_connection.cursor().execute('SELECT * FROM diagnostics_details').fetchall()
        except:
            logging.error(sys.exc_info())
        return rows

    def fetch_schema_version(self):
        rows = []
        try:
            rows = self.db_connection.cursor().execute('SELECT * FROM version').fetchall()
        except:
            logging.error(sys.exc_info())
        return rows[0][0], rows[0][1]

    def insert_symbol_entry(self, filename, line, column, unique_id, context, symbol_kind, is_definition):
        try:
            if unique_id != '':
                self.db_connection.cursor().execute('INSERT INTO symbol VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (
                        filename.decode('utf8', 'ignore') if isinstance(filename, str) else filename,     # NOTE Decoding an already UTF-8 encoded
                        line,                                                                   #      string (unicode) raises an exception.
                        column,                                                                 #      Therefore 'isinstance' check.
                        unique_id.decode('utf8', 'ignore') if isinstance(unique_id, str) else unique_id,
                        context.decode('utf8', 'ignore') if isinstance(context, str) else context,
                        symbol_kind,
                        is_definition,
                    )
                )
        except sqlite3.ProgrammingError as e:
            logging.error(
                'Failed to insert \'[{0}, {1}, {2}, {3}, {4}, {5}, {6}]\' into the database. Exception details: \'{7}\''.format(
                    filename, line, column, unique_id, context, symbol_kind, is_definition, e
                )
            )
        except sqlite3.IntegrityError:
            pass # NOTE Very much expected to be triggered during indexer operation and not an error
        except:
            logging.error('Unexpected exception {0}'.format(sys.exc_info()))

    def insert_diagnostics_entry(self, filename, line, column, description, severity):
        diagnostics_id = None
        try:
            cursor = self.db_connection.cursor()
            cursor.execute('INSERT INTO diagnostics(filename, line, column, description, severity) VALUES (?, ?, ?, ?, ?)',
                (
                    filename.decode('utf8', 'ignore') if isinstance(filename, str) else filename,     # NOTE Decoding an already UTF-8 encoded
                    line,                                                                   #      string (unicode) raises an exception.
                    column,                                                                 #      Therefore 'isinstance' check.
                    description.decode('utf8', 'ignore') if isinstance(description, str) else description,
                    severity,
                )
            )
            diagnostics_id = cursor.lastrowid
        except sqlite3.ProgrammingError as e:
            logging.error(
                'Failed to insert \'[{0}, {1}, {2}, {3}, {4}]\' into the database. Exception details: \'{5}\''.format(
                    filename, line, column, description, severity, e
                )
            )
        except sqlite3.IntegrityError:
            pass # NOTE Very much expected to be triggered during indexer operation and not an error
        except:
            logging.error('Unexpected exception {0}'.format(sys.exc_info()))
        return diagnostics_id

    def insert_diagnostics_details_entry(self, diagnostics_id, filename, line, column, description, severity):
        try:
            self.db_connection.cursor().execute('INSERT INTO diagnostics_details VALUES (?, ?, ?, ?, ?, ?)',
                (
                    diagnostics_id,
                    filename.decode('utf8', 'ignore') if isinstance(filename, str) else filename,     # NOTE Decoding an already UTF-8 encoded
                    line,                                                                   #      string (unicode) raises an exception.
                    column,                                                                 #      Therefore 'isinstance' check.
                    description.decode('utf8', 'ignore') if isinstance(description, str) else description,
                    severity,
                )
            )
        except sqlite3.ProgrammingError as e:
            logging.error(
                'Failed to insert \'[{0}, {1}, {2}, {3}, {4}, {5}]\' into the database. Exception details: \'{5}\''.format(
                    diagnostics_id, filename, line, column, description, severity, e
                )
            )
        except sqlite3.IntegrityError:
            pass # NOTE Very much expected to be triggered during indexer operation and not an error
        except:
            logging.error('Unexpected exception {0}'.format(sys.exc_info()))

    def copy_all_entries_from(self, symbol_db_filename_list):
        for db in symbol_db_filename_list:
            symbol_db = SymbolDatabase(db)
            rows = symbol_db.fetch_all_symbols()
            if rows:
                for row in rows:
                    self.insert_symbol_entry(
                        symbol_db.get_symbol_filename(row),
                        symbol_db.get_symbol_line(row),
                        symbol_db.get_symbol_column(row),
                        symbol_db.get_symbol_usr(row),
                        symbol_db.get_symbol_context(row),
                        symbol_db.get_symbol_kind(row),
                        symbol_db.get_symbol_is_definition(row)
                    )
            rows = symbol_db.fetch_all_diagnostics(DiagnosticsSortingStrategyId.BY_NONE)
            if rows:
                for row in rows:
                    self.insert_diagnostics_entry(
                        symbol_db.get_diagnostics_filename(row),
                        symbol_db.get_diagnostics_line(row),
                        symbol_db.get_diagnostics_column(row),
                        symbol_db.get_diagnostics_description(row),
                        symbol_db.get_diagnostics_severity(row)
                    )
            rows = symbol_db.fetch_all_diagnostics_details()
            if rows:
                for row in rows:
                    self.insert_diagnostics_details_entry(
                        symbol_db.get_diagnostics_details_id(row),
                        symbol_db.get_diagnostics_details_filename(row),
                        symbol_db.get_diagnostics_details_line(row),
                        symbol_db.get_diagnostics_details_column(row),
                        symbol_db.get_diagnostics_details_description(row),
                        symbol_db.get_diagnostics_details_severity(row)
                    )
            self.flush()
            symbol_db.close()

    def flush(self):
        try:
            self.db_connection.commit()
        except:
            logging.error(sys.exc_info())

    def delete_entry(self, filename):
        self.delete_symbol_entry(filename);
        self.delete_diagnostics_entry(filename)

    def delete_symbol_entry(self, filename):
        try:
            self.db_connection.cursor().execute('DELETE FROM symbol WHERE filename=?', (filename,))
        except:
            logging.error(sys.exc_info())

    def delete_diagnostics_entry(self, filename):
        try:
            self.db_connection.cursor().execute('DELETE FROM diagnostics WHERE filename=?', (filename,))
        except:
            logging.error(sys.exc_info())

    def delete_all_entries(self):
        try:
            self.db_connection.cursor().execute('DELETE FROM symbol')
            self.db_connection.cursor().execute('DELETE FROM diagnostics')
        except:
            logging.error(sys.exc_info())

    def create_data_model(self):
        try:
            self.db_connection.cursor().execute(
                'CREATE TABLE IF NOT EXISTS symbol ( \
                    filename        text,            \
                    line            integer,         \
                    column          integer,         \
                    usr             text,            \
                    context         text,            \
                    kind            integer,         \
                    is_definition   boolean,         \
                    PRIMARY KEY(filename, usr, line) \
                 )'
            )
            self.db_connection.cursor().execute(
                'CREATE TABLE IF NOT EXISTS diagnostics ( \
                    id              integer,         \
                    filename        text,            \
                    line            integer,         \
                    column          integer,         \
                    description     text,            \
                    severity        integer,         \
                    PRIMARY KEY(id),                 \
                    UNIQUE(filename, line, column, description) \
                 )'
            )
            self.db_connection.cursor().execute(
                'CREATE TABLE IF NOT EXISTS diagnostics_details ( \
                    diagnostics_id  integer,         \
                    filename        text,            \
                    line            integer,         \
                    column          integer,         \
                    description     text,            \
                    severity        integer,         \
                    PRIMARY KEY(filename, line, column, description), \
                    FOREIGN KEY(diagnostics_id) REFERENCES diagnostics(id) ON DELETE CASCADE \
                 )'
            )
            self.db_connection.cursor().execute(
                'CREATE TABLE IF NOT EXISTS version ( \
                    major integer,            \
                    minor integer,            \
                    PRIMARY KEY(major, minor) \
                 )'
            )
            self.db_connection.cursor().execute(
                'INSERT INTO version VALUES (?, ?)', (SymbolDatabase.VERSION_MAJOR, SymbolDatabase.VERSION_MINOR,)
            )
        except:
            logging.error(sys.exc_info())
