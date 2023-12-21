from abc import ABC, abstractmethod
import abc
from enum import Enum
import logging
import time

from overrides import final




from modules.Core import Core
from parallel.AsyncJob import AsyncJobManager, POCJobManager, AsyncStatus
from tqpm.devices.QLM_Default_QPU import QLM_Default_QPU

class ModuleStage(Enum):
    """enum to classify preprocessing or postprocessing stage of a Core Module"""
    PRE = 1
    POST = 2
     

class AsyncCore(Core, ABC):
    """Base class for asynchrous QUARK module. 
    implement submit_preprocess or submit_postprocess analogously to 
    preprocess or postprocess to make use of the asynchronous functionality
    additionally 
    
    
    implement
    ```
    def submit_preprocess(self, input_data: any, config: dict, **kwargs):
        return foo()
    def collect_preprocess(server_result):
        return bar(server_result)
    ```

    instead of 
    
    ```
    def preprocess(self, input_data: any, config: dict, **kwargs):
        server_result = foo()
        return bar(server_result)
    ```
    
    requires the redefinition of MODULE.JobManager, e.g.
    ```
    JobManager = POCAsyncJobManager
    ```
    
    """
    
    JobManager = AsyncJobManager

    def get_parameter_options(self) -> dict:
        return {"async":
                    {"values": ["preprocess","postprocess","both","all sequencially"],
                     "description":"Choose which process should run in parallel mode"}
                }
    
    #@ not final, since it is possible to define preprocess async and postprocess sequencially and v.v.           
    def preprocess(self, input_data: any, config: dict, **kwargs) -> (any, float):
        """preprocess must not be overwritten in an async module. Use submit_preprocess
        instead"""
        return self._process(ModuleStage.PRE, input_data, config, **kwargs)
    
    #@ not final, since it is possible to define preprocess async and postprocess sequencially and v.v.          
    def postprocess(self, input_data: any, config: dict, **kwargs) -> (any, float):
        """postprocess must not be overwritten in an async module. Use submit_postprocess
        instead"""
        return self._process(ModuleStage.POST,input_data, config, **kwargs)
        
    def _process(self, stage: ModuleStage, input_data: any, config: dict, **kwargs) -> (any, float): 
        """ Input data is the job
        returns the AsyncJobManager or the result
        """
        
        # check if *process is configured to run asynchron, else fallback to Core
        async_mode = config.get("async", "none")
        if not async_mode != "both" and async_mode != stage.name:
            if stage == ModuleStage.PRE:
                return super().preprocess(input_data, config, **kwargs)
            if stage == ModuleStage.POST:
                return super().postprocess(input_data, config, **kwargs)
            
        
        
        asynchronous_job_info =  kwargs.get("asynchronous_job_info", dict())
        synchron_mode = config.get("async",None) == "all sequencially"
        prev_run_job_info = None if not asynchronous_job_info else asynchronous_job_info.get("job_info", False)
        is_submit_job = not prev_run_job_info
        is_collect_job = not is_submit_job or synchron_mode
        
        job_manager =  self.JobManager (self.name, input_data,
                                        config, **kwargs)
        if is_submit_job:
            return self._submit(stage, job_manager)
            
       
        if is_collect_job:
            logging.info("Resuming previous run with job_info = %s", prev_run_job_info)
            job_manager.set_info( **prev_run_job_info)
            return self._collect(stage,job_manager)
            
    
    
    def _submit(self, stage: ModuleStage, job_manager: AsyncJobManager):
        """calls the corresponding submit_pre or postprocess function with arguments
        filled from job_manager"""
        submit = self.submit_preprocess \
            if stage == ModuleStage.PRE \
                else self.submit_postprocess
        job_manager.job_info = submit(job_manager.input, 
                                        job_manager.config, 
                                        **job_manager.kwargs)
        
        self.metrics.add_metric("job_info", 
                                job_manager.get_json_serializable_info())
        
        return job_manager, 0.0
    
    
    def _collect(self, stage: ModuleStage, job_manager: AsyncJobManager):
        """calls the corresponding collect_pre or postprocess function with arguments
        filled from job_manager"""
        collect = self.collect_preprocess \
            if stage == ModuleStage.PRE \
                else self.collect_postprocess
               
        try:
            while job_manager.status == AsyncStatus.SUBMITTED:
                time.sleep(1)
            if job_manager.status == AsyncStatus.DONE:
                logging.info(f"job {job_manager} done")
        except KeyboardInterrupt: #TODO: this does not work in my (debugging) setup
            pass
        
        self.metrics.add_metric("parallel_job_info", job_manager.job_info)
        return collect(job_manager.result), job_manager.runtime
    
    def submit_preprocess(self, job, config, **kwargs):
        """interface: overwrite this method to a module specific submission.
        return value is supposed to be the answer of the server call when submitting 
        
        e.g.
        ```
        qpu = self._get_qpu_plugin()
        server_response = qpu.submit(job)
        return server_response
        ```
        """
        raise NotImplementedError("If you want to run preprocess asynchron, "
        "you need to implement a submit_preprocess method in {self.__class__.__name__}")
    
    def collect_preprocess(self, server_result):
        """interface: overwrite this method to a module specific collect-call"""
        return server_result
    
    def submit_postprocess(self, job, config, **kwargs):
        raise NotImplementedError("If you want to run postprocess asynchron, "
        "you need to implement a submit_postprocess method in {self.__class__.__name__}")
    
    def collect_postprocess(self, server_result):
        return server_result

     


class AsyncPOCDevice(AsyncCore, QLM_Default_QPU):
     
    
    JobManager = POCJobManager
    def submit_preprocess(self, job, config, **kwargs):
        qpu = self._get_qpu_plugin()
        server_response = qpu.submit(job)
        return server_response
            

class AsyncQaptivaDevice(AsyncCore):
    pass
