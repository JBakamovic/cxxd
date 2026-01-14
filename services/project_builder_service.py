import logging
import os
import subprocess
import tempfile
import time
import cxxd.service

class ProjectBuilderRequestId():
    LIST_TARGETS             = 0x0
    RUN_TARGET               = 0x1

class ProjectBuilder(cxxd.service.Service):
    def __init__(self, project_root_directory, cxxd_config_parser, service_plugin):
        cxxd.service.Service.__init__(self, service_plugin)
        self.project_root_directory = project_root_directory
        self.cxxd_config_parser = cxxd_config_parser
        self.service = {
            ProjectBuilderRequestId.LIST_TARGETS             : self._list_targets,
            ProjectBuilderRequestId.RUN_TARGET               : self._build_by_target_name,
        }
        logging.info("ProjectBuilder initialized for root: {0}".format(self.project_root_directory))

    def __unknown_service(self, args):
        logging.error("Unknown service triggered! Valid services are: {0}".format(self.service))
        return False, None

    def _ensure_build_dir(self, directory):
        full_path = os.path.join(self.project_root_directory, directory)
        if not os.path.exists(full_path):
             try:
                 os.makedirs(full_path)
             except OSError as e:
                 logging.error(f"Failed to create build directory {full_path}: {e}")
                 return None
        return full_path

    def _list_targets(self, args):
        targets_dict = self.cxxd_config_parser.get_project_builder_targets()
        formatted_targets = []
        for name, details in targets_dict.items():
            cmd = details.get('cmd', 'No command')
            formatted_targets.append(f"{name} [{cmd}]")
        logging.info(f"ProjectBuilder: Listing {len(formatted_targets)} targets.")
        return True, formatted_targets

    def _build_by_target_name(self, args):
        if not args:
            return False, "No target name provided"
        
        target_name = args[0]
        logging.info(f"ProjectBuilder: Request to build target '{target_name}'")
        
        build_dir = self.cxxd_config_parser.get_project_builder_build_dir(target_name)
        build_cmd_str = self.cxxd_config_parser.get_project_builder_build_cmd(target_name)
        
        if not build_dir or not build_cmd_str:
             return False, f"Target '{target_name}' not found or invalid config."
        
        build_dir_path = self._ensure_build_dir(build_dir)
        if not build_dir_path:
             return False, f"Failed to create build directory for {target_name}"
             
        full_cmd = f"cd {build_dir_path} && {build_cmd_str}"
        return True, [full_cmd]

    def startup_callback(self, args):
        logging.info('Project-builder service started.')
        return True, []

    def shutdown_callback(self, args):
        logging.info('Project-builder service stopped.')
        return True, []

    def __call__(self, args):
        return self.service.get(int(args[0]), self.__unknown_service)(args[1:len(args)])
