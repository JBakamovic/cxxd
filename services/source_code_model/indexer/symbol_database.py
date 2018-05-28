import logging
import sqlite3
import sys

class SymbolDatabase(object):
    VERSION_MAJOR = 0
    VERSION_MINOR = 1

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

    def get_filename(self, row):
        return row[0].encode('utf8', 'ignore')

    def get_line(self, row):
        return row[1]

    def get_column(self, row):
        return row[2]

    def get_usr(self, row):
        return row[3].encode('utf8', 'ignore')

    def get_context(self, row):
        return row[4].encode('utf8', 'ignore')

    def get_kind(self, row):
        return row[5]

    def get_is_definition(self, row):
        return row[6]

    def get_all(self):
        rows = []
        try:
            # TODO Use generators
            rows = self.db_connection.cursor().execute('SELECT * FROM symbol').fetchall()
        except:
            logging.error(sys.exc_info())
        return rows

    def get_by_usr(self, usr):
        rows = []
        try:
            rows = self.db_connection.cursor().execute('SELECT * FROM symbol WHERE usr=?', (usr,)).fetchall()
        except:
            logging.error(sys.exc_info())
        return rows

    def get_definition(self, usr):
        rows = []
        try:
            rows = self.db_connection.cursor().execute('SELECT * FROM symbol WHERE usr=? AND is_definition=1',(usr,)).fetchall()
        except:
            logging.error(sys.exc_info())
        return rows

    def insert_single(self, filename, line, column, unique_id, context, symbol_kind, is_definition):
        try:
            if unique_id != '':
                self.db_connection.cursor().execute('INSERT INTO symbol VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (
                        filename.decode('utf8') if isinstance(filename, str) else filename,     # NOTE Decoding an already UTF-8 encoded
                        line,                                                                   #      string (unicode) raises an exception.
                        column,                                                                 #      Therefore 'isinstance' check.
                        unique_id.decode('utf8') if isinstance(unique_id, str) else unique_id,
                        context.decode('utf8') if isinstance(context, str) else context,
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

    def insert_from(self, symbol_db_filename_list):
        for db in symbol_db_filename_list:
            symbol_db = SymbolDatabase(db)
            rows = symbol_db.get_all()
            if rows:
                for row in rows:
                    self.insert_single(
                        symbol_db.get_filename(row),
                        symbol_db.get_line(row),
                        symbol_db.get_column(row),
                        symbol_db.get_usr(row),
                        symbol_db.get_context(row),
                        symbol_db.get_kind(row),
                        symbol_db.get_is_definition(row)
                    )
                self.flush()
            symbol_db.close()

    def flush(self):
        try:
            self.db_connection.commit()
        except:
            logging.error(sys.exc_info())

    def delete(self, filename):
        try:
            self.db_connection.cursor().execute('DELETE FROM symbol WHERE filename=?', (filename,))
        except:
            logging.error(sys.exc_info())

    def delete_all(self):
        try:
            self.db_connection.cursor().execute('DELETE FROM symbol')
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
