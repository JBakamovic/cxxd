import sys
import json
import logging
from utils import Utils

class Messenger:
    """
    Abstracts the communication mechanism with Vim.
    Supports both legacy 'clientserver' (remote-expr) and modern 'job' (stdout/JSON).
    """

    MODE_LEGACY = 'legacy'
    MODE_JOB    = 'job'

    def __init__(self, mode, servername=None):
        self.mode = mode
        self.servername = servername

    def send_call(self, function_name, *args):
        """
        Sends a function call to Vim.
        """
        if self.mode == self.MODE_JOB:
            self._send_job_call(function_name, args)
        elif self.mode == self.MODE_LEGACY:
            self._send_legacy_call(function_name, args)
        else:
            logging.error(f"Unknown messenger mode: {self.mode}")

    def _send_job_call(self, function_name, args):
        """
        Writes a JSON object to stdout.
        Format: {"call": "function_name", "args": [arg1, arg2, ...]}
        """
        message = {
            "call": function_name,
            "args": list(args)
        }
        try:
            # We use compact separators to save bytes, though not strictly necessary
            json_str = json.dumps(message, separators=(',', ':'))
            sys.stdout.write(json_str + "\n")
            sys.stdout.flush()
        except Exception as e:
            logging.error(f"Failed to send job call: {e}")

    def _send_legacy_call(self, function_name, args):
        """
        Uses Utils.call_vim_remote_function (clientserver).
        """
        # We need to construct the function call string string like "Func(arg1, 'arg2', ...)"
        # This implementation requires arguments to be properly stringified for Vimscript
        # which Utils.call_vim_remote_function logic expected the caller to do usually.
        #
        # However, checking the existing codebase (go_to_definition.py),
        # it did string concatenation manually:
        # "func(" + str(int(status)) + ", '" + filename + "', ...)"
        #
        # To support legacy mode correctly here, we would need a robust serializer.
        # But since we are incrementally migrating, legacy calls might still be done
        # via the manual way if we don't migrate everything at once.
        #
        # For this specific refactor, if we want to support legacy via this class,
        # we need to mimic that manual string building or improve Utils.
        
        # NOTE: For now, assuming args are simple types (int, string).
        serialized_args = []
        for arg in args:
            if isinstance(arg, str):
                serialized_args.append(f"'{arg}'")
            elif isinstance(arg, bool):
                serialized_args.append('v:true' if arg else 'v:false')
            else:
                serialized_args.append(str(arg))
        
        call_str = f"{function_name}({', '.join(serialized_args)})"
        
        if self.servername:
            Utils.call_vim_remote_function(self.servername, call_str)
        else:
            logging.error("Servername required for legacy mode")
