"""
@Time    : 2026-09-18 9:34
@Author  : JiaChengJie
@File    : start_node.py
"""
import time
from typing import Optional

from internal.core.workflow.nodes import BaseNode
from langchain_core.runnables import RunnableConfig

from internal.core.workflow.entities.node_entity import NodeStatus, NodeResult
from internal.core.workflow.entities.variable_entity import VARIABLE_TYPE_DEFAULT_VALUE_MAP
from internal.core.workflow.entities.workflow_entity import WorkflowState
from internal.exception import FailException
from .start_entity import StartNodeData


class StartNode(BaseNode):
    """开始节点"""
    node_data: StartNodeData

    def invoke(self, state: WorkflowState, config: Optional[RunnableConfig] = None) -> WorkflowState:
        """开始节点执行函数，该函数会提取状态中的输入信息并生成节点结果"""
        # 1. 获取开始节点中的数据
        start_time = time.perf_counter()
        inputs = self.node_data.inputs

        # 2. 循环遍历取值，同时校验字段是否为空
        outputs = {}
        for input in inputs:
            input_value = state["inputs"].get(input.name, None)

            # 3. 判断字段是否为必填
            if input_value is None:
                if input.required:
                    raise FailException(f"该字段是必填字段，字段名称是{input.name}")
                else:
                    input_value = VARIABLE_TYPE_DEFAULT_VALUE_MAP.get(input.type)

            # 4.提取输出数据
            outputs[input.name] = input_value

        # 5. 组装数据返回
        return {
            "node_results": [
                NodeResult(
                    node_data=self.node_data,
                    status=NodeStatus.SUCCEEDED,
                    inputs=state["inputs"],
                    outputs=outputs,
                    latency=(time.perf_counter() - start_time),
                )
            ]
        }
