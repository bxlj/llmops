"""
@Time    : 2026-09-29 15:12
@Author  : JiaChengJie
@File    : llm_node.py
"""
import time
from typing import Any

from jinja2 import Template
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI

from internal.core.workflow.entities.node_entity import NodeResult, NodeStatus
from internal.core.workflow.entities.workflow_entity import WorkflowState
from internal.core.workflow.nodes import BaseNode
from internal.core.workflow.untils.helper import extract_variables_from_state
from .llm_entity import LLMNodeData


class LLMNode(BaseNode):
    """大语言模型节点"""
    node_data: LLMNodeData

    def invoke(self, state: WorkflowState, config: RunnableConfig | None = None, **kwargs: Any) -> WorkflowState:
        """大语言模型执行函数"""
        # 1. 获取输入数据
        start_time = time.perf_counter()
        inputs = self.node_data.inputs

        # 2. 提取数据
        inputs_dict = extract_variables_from_state(self.node_data.inputs, state)

        # 5.使用jinja2格式模板信息
        prompt_value = Template(self.node_data.prompt).render(**inputs_dict)

        # todo:6.根据配置创建LLM实例，等待多LLM接入时需要完善
        llm = ChatOpenAI(
            model=self.node_data.language_model_config.get("model", "kimi-k2.6"),
            **self.node_data.language_model_config.get("parameters", {}),
        )

        # 7.使用stream来代替invoke，避免接口长时间未响应超时
        content = ""
        for chunk in llm.stream(prompt_value):
            content += chunk.content

        # 8. 构建输出数据结构
        outputs = {}
        if self.node_data.outputs:
            outputs[self.node_data.outputs[0].name] = content
        else:
            outputs["output"] = content

        # 9.组装输出数据结构
        return {
            "node_results": [
                NodeResult(
                    node_data=self.node_data,
                    status=NodeStatus.SUCCEEDED,
                    outputs=outputs,
                    inputs=inputs_dict,
                    latency=(time.perf_counter() - start_time),
                )
            ]
        }
