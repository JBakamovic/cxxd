from builtins import object
class Diagnostics(object):
    def __init__(self, parser):
        self.parser = parser

    def __fixit_visitor__(self, fixits_iterator, client_callback, client_data):
        for fixit in fixits_iterator:
            client_callback(
                fixit.range,
                fixit.value,
                client_data
            )

    def __diagnostics_visitor__(self, diagnostics_iterator, client_callback, client_data):
        for diag in diagnostics_iterator:
            client_callback(
                diag.location.file.name if diag.location.file else '',
                diag.location.line,
                diag.location.column,
                diag.spelling,
                diag.severity,
                diag.category_number,
                diag.category_name,
                diag.fixits,
                client_data
                # TODO add ranges(?) and children(?)
            )

    def __call__(self, args):
        original_filename, contents_filename = args
        diag_iter = self.parser.get_diagnostics(
            self.parser.parse(contents_filename, original_filename)
        )
        return diag_iter is not None, [diag_iter, self.__diagnostics_visitor__, self.__fixit_visitor__]
