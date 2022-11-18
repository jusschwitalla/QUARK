import logging

from devices.Device import *

from qat.qpus import get_default_qpu
from qat.plugins import ScipyMinimizePlugin



class MY_QLM(Device):
    def __init__(self, device_name: str):
        super().__init__(device_name)
        self.device = self
        self.qpu = get_default_qpu() 
        logging.getLogger("qat").setLevel(logging.WARN)
        
    def get_plugin(self, plugin_id):
        if plugin_id == "qat.plugins:ScipyMinimizePlugin":
            return ScipyMinimizePlugin
        return None
        
    def getQPU(self):
        return self.qpu
        
    def submit(self, stack, job):
        return stack.submit(job)
        
    
