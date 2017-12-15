import logging
import sqlite3

class SymbolDatabase(object):
    VERSION_MAJOR = 0
    VERSION_MINOR = 1

    def __init__(self, db_filename = None):
        self.filename = db_filename
        if db_filename:
            self.db_connection = sqlite3.connect(db_filename)
        else:
            self.db_connection = None

    def __del__(self):
        if self.db_connection:
            self.db_connection.close()

    def open(self, db_filename):
        if not self.db_connection:
            self.db_connection = sqlite3.connect(db_filename)
            self.filename = db_filename

    def close(self):
        if self.db_connection:
            self.db_connection.close()
            self.db_connection = None

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
        # TODO Use generators
        return self.db_connection.cursor().execute('SELECT * FROM symbol')

    def get_by_usr(self, usr):
        return self.db_connection.cursor().execute('SELECT * FROM symbol WHERE usr=?', (usr,))

    def get_definition(self, usr):
        return self.db_connection.cursor().execute('SELECT * FROM symbol WHERE usr=? AND is_definition=1', (usr,))

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
        self.db_connection.commit()

    def delete(self, filename):
        self.db_connection.cursor().execute('DELETE FROM symbol WHERE filename=?', (filename,))

    def delete_all(self):
        self.db_connection.cursor().execute('DELETE FROM symbol')

    def create_data_model(self):
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
