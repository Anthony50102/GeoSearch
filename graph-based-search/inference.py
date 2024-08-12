from main import create_search_engine, get_config
from model_handler_extend import ModelHandlerExtend
from utils.search_engine import *
import os
import sys

config = '/config/search_python.yml'

class CodeSearch():
    def __init__(self, config_path, model_path) -> None:
        config = get_config(config_path)
        config['pretrained'] = model_path
        if not (os.path.exists(config['pretrained'])):
            sys.exit(0)
        
        self.model_handle = ModelHandlerExtend(config)
        self.se = search_engine(model_handle=self.model_handle, config=config)
    
    def search(self, query: list, search_size=10):
      return self.se.search_single_query(query, search_size) 
        