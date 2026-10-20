"""
@Time    : 2026-09-30 11:06
@Author  : JiaChengJie
@File    : template_transform_node.py
"""
import time
from typing import Any

from jinja2 import Template
from langchain_core.runnables import RunnableConfig

from internal.core.workflow.entities.node_entity import NodeResult, NodeStatus
from internal.core.workflow.entities.workflow_entity import WorkflowState
from internal.core.workflow.nodes import BaseNode
from internal.core.workflow.untils.helper import extract_variables_from_state
from .template_transform_entity import TemplateTransformNodeData


class TemplateTransformNode(BaseNode):
    """模板转换节点"""
    node_data: TemplateTransformNodeData

    def invoke(self, state: WorkflowState, config: RunnableConfig | None = None, **kwargs: Any) -> WorkflowState:
        """模板转换节点执行函数，将传递的多个变量合并成字符串后返回"""
        start_time = time.perf_counter()
        # 1.获取输入数据
        input_dict = extract_variables_from_state(self.node_data.inputs, state)

        # 使用jinja2格式模板信息
        template_data = Template(self.node_data.template).render(**input_dict)

        # 构建输出数据结构
        outputs = {}
        if self.node_data.outputs:
            outputs[self.node_data.outputs[0].name] = template_data
        else:
            outputs["output"] = template_data

        # 组装数据
        return {
            "node_results": [
                NodeResult(
                    node_data=self.node_data,
                    status=NodeStatus.SUCCEEDED,
                    outputs=outputs,
                    inputs=input_dict,
                    latency=(time.perf_counter() - start_time),
                )
            ]
        }
