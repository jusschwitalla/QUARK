from abc import ABC, abstractmethod
from enum import Enum
import logging
import time


from BenchmarkManager import Instruction
from modules.Core import Core
from async_modules.AsyncJob import AsyncJobManager, AsyncStatus


class ModuleStage(Enum):
    """enum to classify preprocessing or postprocessing stage of a Core Module"""

    PRE = 1
    POST = 2


class AsyncCore(Core, ABC):
    """Base class for asynchronous QUARK module.
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

    def __init__(self, interruptable, name: str = None):
        """
        :param interruptable: a single ModuleStage, or a single stage name or a list of these
        """
        Core.__init__(self, name)
        if isinstance(interruptable, ModuleStage ):
            self.interruptable_stages = [interruptable]
        else:
            # note that this also works if interruptable is a single string
            self.interruptable_stages = [
                stage for stage in ModuleStage if stage.name in interruptable or stage in interruptable
            ]
        assert len(self.interruptable_stages) in (1, 2)
        self.use_param_name_postfix = len(self.interruptable_stages) == 2

    def get_parameter_options(self) -> dict:
        return {
            f"async-{interruptable_stage.name.lower()}" if self.use_param_name_postfix else "async": dict(
                {
                    "values": [True, False],
                    "description": f"Choose if {interruptable_stage.name.lower()}_process should run in asynchronous mode",
                }
            )
            for interruptable_stage in self.interruptable_stages
        }

    # @ not final, since it is possible to define preprocess async and postprocess sequentially and v.v.
    def preprocess(self, input_data: any, config: dict, **kwargs) -> (any, float):
        """preprocess must not be overwritten in an async module. Use submit_preprocess
        instead"""
        return self._process(ModuleStage.PRE, input_data, config, **kwargs)

    # @ not final, since it is possible to define preprocess async and postprocess sequentially and v.v.
    def postprocess(self, input_data: any, config: dict, **kwargs) -> (any, float):
        """postprocess must not be overwritten in an async module. Use submit_postprocess
        instead"""
        return self._process(ModuleStage.POST, input_data, config, **kwargs)

    def _process(
        self, stage: ModuleStage, input_data: any, config: dict, **kwargs
    ) -> (any, float):
        """Input data is the job
        returns the AsyncJobManager or the result
        """

        # check if *process is configured to support async-mode, else fallback to Core
        if stage not in self.interruptable_stages:
            if stage == ModuleStage.PRE:
                return Instruction.PROCEED, *super().preprocess(
                    input_data, config, **kwargs
                )
            if stage == ModuleStage.POST:
                return Instruction.PROCEED, *super().postprocess(
                    input_data, config, **kwargs
                )

        async_mode_conf_key = f"async-{stage.name.lower()}" if self.use_param_name_postfix else "async"
        async_mode = config.get(async_mode_conf_key, False)

        previous_job_info = kwargs.get("previous_job_info", dict())

        prev_run_job_info = (
            None
            if not previous_job_info
            else previous_job_info.get("job_info", False)
        )

        is_interrupted_here = (
            bool(prev_run_job_info)
            and prev_run_job_info.get("interrupted_at") == stage.name
        )

        is_submit_job = async_mode and not is_interrupted_here
        is_collect_job = async_mode and is_interrupted_here

        job_manager = self.JobManager(self.name, input_data, config, **kwargs)

        if not async_mode:
            return self.sync_run(stage, job_manager)

        elif is_submit_job:
            return self._submit(stage, job_manager)

        elif is_collect_job:
            logging.info("Resuming previous run with job_info = %s", prev_run_job_info)
            job_manager.set_info(**prev_run_job_info)
            return self._collect(stage, job_manager)
        assert False, "Not expected to be here."

    def _submit(
        self, stage: ModuleStage, job_manager: AsyncJobManager
    ) -> [Instruction, AsyncJobManager, float]:
        """calls the corresponding submit_pre or postprocess function with arguments
        filled from job_manager"""
        submit = (
            self.submit_preprocess
            if stage == ModuleStage.PRE
            else self.submit_postprocess
        )
        job_manager.job_info = submit(
            job_manager.input, job_manager.config, **job_manager.kwargs
        )
        job_manager.set_info(interrupted_at=stage)

        self.metrics.add_metric("job_info", job_manager.get_json_serializable_info())

        return Instruction.INTERRUPT, job_manager, 0.0

    def _collect(
        self, stage: ModuleStage, job_manager: AsyncJobManager, wait_until_finish=False
    ) -> [Instruction, any, float]:
        """calls the corresponding collect_pre or postprocess function with arguments
        filled from job_manager"""
        collect_if_done = (
            self.collect_preprocess
            if stage == ModuleStage.PRE
            else self.collect_postprocess
        )

        status = job_manager.status()
        while status == AsyncStatus.SUBMITTED:
            if not wait_until_finish:
                break
            time.sleep(1)
            status = job_manager.status()

        if status == AsyncStatus.DONE:
            logging.info(f"{job_manager} done")
            instruction = Instruction.PROCEED
        elif status == AsyncStatus.FAILED:
            # TODO: implement exception/ assert that the exception is catched elsewhere
            instruction = Instruction.INTERRUPT
            # raise NotImplementedError("serverside failure is not yet implemented")
        else:
            logging.info(
                f"Async module {self.name} is not yet finished. Status={status}"
            )
            self.metrics.add_metric("job_info", job_manager.get_json_serializable_info())
            return Instruction.INTERRUPT, job_manager, 0.

        result = collect_if_done(job_manager.result())

        self.metrics.add_metric("job_info", job_manager.get_json_serializable_info())

        return Instruction.PROCEED, result, job_manager.runtime

    # TODO: currently inconsistent: sync_run is one method which gets the stage as argument
    # whereas submit and collect exist in two variants one or PRE and one for POST
    # It probably would be better to make it the same way as with sync_run - i.e. one submit and
    # one collect method which both get the stage as argument.

    def sync_run(self, stage: ModuleStage, job_manager: AsyncJobManager) -> [Instruction, any, float]:
        """default method is running submit and collect consecutively
        but for some applications a more efficient implementation can be written
        by overwriting this function"""
        self._submit(stage, job_manager)
        return self._collect(stage, job_manager, wait_until_finish=True)

    def submit_preprocess(self, input, config, **kwargs):
        """interface: overwrite this method to a module specific submission.
        return value is supposed to be the answer of the server call when submitting

        e.g.
        ```
        qpu = self._get_qpu_plugin()
        server_response = qpu.submit(job)
        return server_response
        ```
        """
        raise NotImplementedError(
            "If you want to run preprocess asynchron, "
            "you need to implement a submit_preprocess method in {self.__class__.__name__}"
        )

    def collect_preprocess(self, server_result):
        """interface: overwrite this method to a module specific collect-call"""
        return server_result

    def submit_postprocess(self, input, config, **kwargs):
        raise NotImplementedError(
            "If you want to run postprocess asynchron, "
            "you need to implement a submit_postprocess method in {self.__class__.__name__}"
        )

    def collect_postprocess(self, server_result):
        return server_result
    