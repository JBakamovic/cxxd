#!/usr/bin/env python3

import sys
import os
import logging
import json
import threading
import argparse
import time
from multiprocessing import Queue

# Setup Path to include 'lib'
if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # lib/cxxd -> lib
    lib_dir = os.path.dirname(current_dir)
    if lib_dir not in sys.path:
        sys.path.insert(0, lib_dir)

from cxxd.server import Server

#
# This script acts as a bridge between Vim Jobs (Stdin/Stdout)
# and the existing Multiprocessing Server architecture.
#

def stdin_reader(server_queue):
    """
    Reads lines (NDJSON) from stdin and pushes them to the server queue.
    Translates JSON Requests -> Internal Requests.
    """
    logging.info("Stdin reader thread started")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            # Protocol Translation:
            # External JSON: {"header": int, "service_id": int, "payload": list}
            # Internal List: [header, service_id, payload]
            # Default header is SEND_SERVICE (0xF2) if not specified
            
            header = req.get("header", 0xF2) 
            service_id = req.get("service_id")
            payload = req.get("payload", [])
            
            if service_id is None:
                logging.error("Missing service_id in request")
                continue

            internal_request = [header, service_id, payload]
            server_queue.put(internal_request)
            
        except json.JSONDecodeError as e:
            logging.error(f"JSON decode error: {e}")
        except Exception as e:
            logging.error(f"Stdin reader error: {e}")
    
    logging.info("Stdin closed, shutting down...")
    # Trigger shutdown if stdin closes (Parent Vim died)
    server_queue.put([0xFF, 0, []]) # SHUTDOWN_AND_EXIT

def get_server_instance(handle, project_root_directory, target_configuration, args):
    """
    Factory function to create the Server instance.
    Aligned with how lib/server.py and lib/cxxd/server.py expect it.
    """
    # args passed here is 'vim_instance' usually, but in Job mode we might pass None or a special flag.
    # However, existing services import 'server' from 'lib/' (not lib/cxxd/server.py).
    # We need to make sure we import the right things.
    
    # We need to add 'lib' to sys.path so we can import 'server' (the wrapper in lib/)
    # and 'services.*'
    import server # This is lib/server.py
    
    # In lib/server.py: get_instance(handle, project_root, target_config, args)
    # The 'args' is passed as 'vim_instance' to VimSourceCodeModel etc.
    # Since we are in Job mode, we pass None as vim_instance (servername).
    # Services should handle None by using Messenger.MODE_JOB.
    return server.get_instance(handle, project_root_directory, target_configuration, None)

def main():
    parser = argparse.ArgumentParser(description="cxxd Vim backend server")
    parser.add_argument("--project-root", required=True, help="Path to project root")
    parser.add_argument("--log-file", required=True, help="Path to log file")
    parser.add_argument("--target-config", default="", help="Target configuration (optional)")
    
    args = parser.parse_args()

    # Configure logging
    # We must NOT log to stdout as that is used for communication
    logging.basicConfig(
        filename=args.log_file,
        filemode='w',
        format='[%(asctime)s] [%(levelname)s] %(message)s',
        level=logging.INFO
    )
    
    logging.info(f"Starting cxxd server for {args.project_root}")
    
    # Create the Server Queue
    server_queue = Queue()

    # Start the Server Process
    # We use the existing mechanism from cxxd.api.server_start logic
    # but implemented manually here to control the process directly 
    # and NOT use a separate multiprocessing.Process for the run_impl 
    # if we want this script to BE the main manager.
    #
    # However, existing cxxd.server.Server is designed to run in a loop.
    # We can run Server in a separate process (as before) or thread.
    # Given GIL and Libclang, Multiprocessing is better.
    
    from cxxd.server import server_listener
    
    # We need to wrap construction of the Server object because it needs to happen 
    # inside the process.
    
    def run_server_process(queue, project_root, target_config, log_file):
        # Re-configure logging in child process
        logging.basicConfig(filename=log_file, filemode='a', level=logging.INFO)
        try:
            srv = get_server_instance(queue, project_root, target_config, None)
            server_listener(srv)
        except Exception as e:
            logging.critical(f"Server process died: {e}", exc_info=True)

    import multiprocessing
    server_process = multiprocessing.Process(
        target=run_server_process,
        args=(server_queue, args.project_root, args.target_config, args.log_file),
        name="cxxd_server_proc"
    )
    server_process.start()

    # Start Stdin Reader Thread
    reader_thread = threading.Thread(target=stdin_reader, args=(server_queue,), daemon=True)
    reader_thread.start()

    # Join server process
    server_process.join()
    logging.info("Exiting...")


if __name__ == "__main__":
    main()

