from __future__ import absolute_import
import argparse
import logging
import os
import sys

# As this script is executed externally, from multiple processes, we have to make sure
# we setup a correct PYTHONPATH. It _must_ include parent directory of 'cxxd'.
sys.path.append(
    os.path.dirname(                                # <path_to_cxxd>
        os.path.dirname(                            # <path_to_cxxd>/cxxd
            os.path.dirname(                        # <path_to_cxxd>/cxxd/services
                os.path.dirname(                    # <path_to_cxxd>/cxxd/services/source_code_model
                    os.path.dirname(                # <path_to_cxxd>/cxxd/services/source_code_model/indexer
                        os.path.realpath(__file__)
                    )
                )
            )
        )
    )
)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Index given list of files.')
    parser.add_argument('--project_root_directory', required=True, help='a root directory of project to be indexed')
    parser.add_argument('--compiler_args_filename', required=True, help='a file containing a list of compiler args to be used while indexing')
    parser.add_argument('--input_list',             required=True, help='input file containing all source filenames to be indexed (one filename per each line)')
    parser.add_argument('--output_db_filename',     required=True, help='indexing result will be recorded in this file (SQLite db)')
    parser.add_argument('--log_file',               required=True, help='log file to log indexing actions')

    args = parser.parse_args()

    FORMAT = '[%(asctime)s.%(msecs)03d] [%(levelname)s] [%(filename)s:%(lineno)s] %(funcName)25s(): %(message)s'
    logging.basicConfig(filename=args.log_file, filemode='w', format=FORMAT, datefmt='%H:%M:%S', level=logging.INFO)
 
    from . import clang_indexer
    clang_indexer.index_file_list(
        args.project_root_directory,
        args.input_list,
        args.compiler_args_filename,
        args.output_db_filename
    )
