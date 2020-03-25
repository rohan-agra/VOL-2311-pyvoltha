import structlog
from pyvoltha.common.config.config_backend import EtcdStore
from pyvoltha.common.structlog_setup import setup_logging, update_logging, validate_loglevel, string_to_int
import os

COMPONENT_NAME = os.environ.get("COMPONENT_NAME")
GLOBAL_CONFIG_ROOT_NODE = "global"
DEFAULT_KV_STORE_CONFIG_PATH = "config"
KV_STORE_DATA_PATH_PREFIX = "service/voltha"
KV_STORE_PATH_SEPARATOR = "/"
CONFIG_TYPE = "loglevel"
DEFAULT_PACKAGE_NAME = "default"
GLOBAL_DEFAULT_LOGLEVEL = "WARN"

class LogController():
    instance_id = None
    etcd_client = None
    active_log_hash = None
    component_default_loglevel = None

    def __init__(self, etcd_host, etcd_port):
        self.log = structlog.get_logger()
        self.etcd_host = etcd_host
        self.etcd_port = etcd_port

    def create_kv_client(self):
        client = EtcdStore(self.etcd_host, self.etcd_port, KV_STORE_DATA_PATH_PREFIX)
        LogController.etcd_client = client 
        return client  

    def make_config_path(self, key):
        return (DEFAULT_KV_STORE_CONFIG_PATH + KV_STORE_PATH_SEPARATOR + key + KV_STORE_PATH_SEPARATOR + CONFIG_TYPE + KV_STORE_PATH_SEPARATOR + DEFAULT_PACKAGE_NAME)

    def get_global_config(self):
        global_default_loglevel = ""
        global_config_path = self.make_config_path(GLOBAL_CONFIG_ROOT_NODE)
        try:
            self.log_level= LogController.etcd_client.__getitem__(global_config_path)
            level = validate_loglevel(str(self.log_level, 'utf-8'))

            if level == "":
                self.log.warn("unsupported loglevel at global config", self.log_level)
            else:
                global_default_loglevel = level 
        
        except KeyError:
            self.log.warn("Failed-to-retrive-default-global-loglevel")

        return global_default_loglevel


    def get_component_config(self, global_default_loglevel):
    
        component_default_loglevel = ""
        component_config_path = self.make_config_path(COMPONENT_NAME)

        try:
            self.log_level = LogController.etcd_client.__getitem__(component_config_path)
            level = validate_loglevel(str(self.log_level, 'utf-8'))
            if level == "":
                self.log.warn("unsupported loglevel at global config", self.log_level)
            else:
                component_default_loglevel = level 
     
        except KeyError:
            self.log.warn("Failed-to-retrive-default-component-loglevel")
            component_default_loglevel = global_default_loglevel

        return component_default_loglevel


    def start_watch_log_config_change(self, instance_id, component_default_loglevel):
      
        self.component_name = None
        self.component_name = COMPONENT_NAME
        LogController.instance_id = instance_id
        LogController.component_default_loglevel = component_default_loglevel
        if self.component_name == None:
            raise Exception("Unable-to-retrive-pod-component-name-from-runtime-env")
        self.client = self.create_kv_client()
        self.global_config_path = self.make_config_path(GLOBAL_CONFIG_ROOT_NODE)
        self.component_config_path = self.make_config_path(self.component_name)
        self.set_default_loglevel(self.global_config_path, self.component_config_path)
        self.process_log_config_change()
        self.client.__watch_callback__(self.global_config_path)
        self.client.__watch_callback__(self.component_config_path)
   

    def process_log_config_change(self):
        self.global_default_level = self.get_global_config()
        self.loglevel = string_to_int(self.get_component_config(self.global_default_level))
        current_log_hash = hash(self.loglevel)
        if LogController.active_log_hash != current_log_hash:
            LogController.active_log_hash = current_log_hash
            update_logging(LogController.instance_id, None, verbosity_adjust=self.loglevel)


    def set_default_loglevel(self, global_config_path, component_config_path):
        if not LogController.etcd_client.__contains__(global_config_path):
            LogController.etcd_client.__setitem__(global_config_path, GLOBAL_DEFAULT_LOGLEVEL)

        if not LogController.etcd_client.__contains__(component_config_path):
            LogController.etcd_client.__setitem__(component_config_path, LogController.component_default_loglevel)
