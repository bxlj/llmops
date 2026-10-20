"""
@Time    : 2026-09-30 16:24
@Author  : JiaChengJie
@File    : dataset_retrieval_node.py
"""
import time
from typing import Any
from uuid import UUID

from flask import Flask
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from pydantic import PrivateAttr

from internal.core.workflow.entities.node_entity import NodeResult, NodeStatus
from internal.core.workflow.entities.workflow_entity import WorkflowState
from internal.core.workflow.nodes import BaseNode
from internal.core.workflow.untils.helper import extract_variables_from_state
from .dataset_retrieval_entity import DatasetRetrievalNodeData


class DatasetRetrievalNode(BaseNode):
    """知识库检索节点"""
    node_data: DatasetRetrievalNodeData
    _retrieval_tool: BaseTool = PrivateAttr(None)

    def __init__(self,
                 *args,
                 flask_app: Flask,
                 account_id: UUID,
                 **kwargs):
        """构造函数，完成知识库检索节点的初始化"""
        # 1. 调用父类构造函数完成数据初始化
        super().__init__(*args, **kwargs)

        # 2.导入依赖注入及检索服务
        from app.http.model import injector
        from internal.service import RetrievalService

        retrieval_service = injector.get(RetrievalService)

        # 3. 调用工具检索工具
        self._retrieval_tool = retrieval_service.create_langchain_tool_from_search(
            flask_app=flask_app,
            dataset_ids=self.node_data.dataset_ids,
            account_id=account_id,
            **self.node_data.retrieval_config.model_dump(),
        )

    def invoke(self, state: WorkflowState, config: RunnableConfig | None = None, **kwargs: Any) -> WorkflowState:
        """知识库检索执行函数"""
        start_time = time.perf_counter()
        # 1. 提取输入变量，判断是直接取值还是引用
        input_dict = extract_variables_from_state(self.node_data.inputs, state)
        # 4. 调用知识库检索工具
        combine_documents = self._retrieval_tool.invoke(input_dict)

        # 5. 提取并构建输出数据结构
        outputs = {}
        if self.node_data.outputs:
            outputs[self.node_data.outputs[0].name] = combine_documents
        else:
            outputs["combine_documents"] = combine_documents

        # 6. 组装输出函数
        return {
            "node_results": [
                NodeResult(
                    node_data=self.node_data,
                    status=NodeStatus.SUCCEEDED,
                    inputs=input_dict,
                    outputs=outputs,
                    latency=(time.perf_counter() - start_time),
                )
            ]
        }
