#!/usr/bin/env python3

import argparse
import json
import logging
import multiprocessing
import os
import sys
import threading
import time

if __name__ == "__main__":
    # We need to add 'lib' to sys.path so we can import 'server'
    # (the wrapper in lib/) so that we can access frontend-specific
    # get_instance(handle, project_root, target_config) which actually
    # builds the bindings for source-code model and other plugins.
    current_dir = os.path.dirname(os.path.abspath(__file__))
    lib_dir = os.path.dirname(current_dir)
    if lib_dir not in sys.path:
        sys.path.insert(0, lib_dir)

from cxxd.server import ServerRequestId

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
            # Default header is SEND_SERVICE if not specified
            header = req.get("header", ServerRequestId.SEND_SERVICE) 
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
    # Trigger shutdown of the server and services
    server_queue.put([ServerRequestId.SHUTDOWN_AND_EXIT, 0, []])

def get_server_instance(handle, project_root_directory, target_configuration):
    import server # This is lib/server.py
    return server.get_instance(handle, project_root_directory, target_configuration, None)

def main():
    parser = argparse.ArgumentParser(description="cxxd Vim backend server")
    parser.add_argument("--project-root", required=True, help="Path to project root")
    parser.add_argument("--log-file", required=True, help="Path to log file")
    parser.add_argument("--target-config", default="", help="Target configuration (optional)")

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        filename=args.log_file,
        filemode='w',
        format='[%(asctime)s] [%(levelname)s] %(message)s',
        level=logging.INFO
    )

    logging.info(f"Starting cxxd server for {args.project_root}")

    def run_server_process(queue, project_root, target_config, log_file):
        # Re-configure logging in child process
        logging.basicConfig(filename=log_file, filemode='a', level=logging.INFO)
        try:
            srv = get_server_instance(queue, project_root, target_config)
            keep_listening = True
            while keep_listening:
                keep_listening = srv.process_request()
            logging.info("Server listener shut down ...")
        except Exception as e:
            logging.critical(f"Server process died: {e}", exc_info=True)

    # Create the server Queue
    server_queue = multiprocessing.Queue()
    # and main server process
    server_process = multiprocessing.Process(
        target=run_server_process,
        args=(server_queue, args.project_root, args.target_config, args.log_file),
        name="cxxd_server_proc_main"
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

