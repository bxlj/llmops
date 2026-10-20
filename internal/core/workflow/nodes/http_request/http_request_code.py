"""
@Time    : 2026-10-08 16:03
@Author  : JiaChengJie
@File    : http_request_code.py
"""
import time
from typing import Any

import requests
from langchain_core.runnables import RunnableConfig

from internal.core.workflow.entities.node_entity import NodeResult, NodeStatus
from internal.core.workflow.entities.workflow_entity import WorkflowState
from internal.core.workflow.nodes import BaseNode
from internal.core.workflow.untils.helper import extract_variables_from_state
from .http_request_entity import HttpRequestNodeData, HttpRequestInputType, HttpRequestMethod


class HttpRequestNode(BaseNode):
    """http请求节点"""
    node_data: HttpRequestNodeData

    def invoke(self, state: WorkflowState, config: RunnableConfig | None = None, **kwargs: Any) -> WorkflowState:
        """http请求节点执行函数"""
        start_time = time.perf_counter()
        _inputs_dict = extract_variables_from_state(self.node_data.inputs, state)

        # 4.提取数据，涵盖params、headers、body的数据
        inputs_dict = {
            HttpRequestInputType.PARAMS: {},
            HttpRequestInputType.HEADERS: {},
            HttpRequestInputType.BODY: {},
        }

        # 5. 根据input里面的传入的的值，填充params、headers、body数据
        for input in self.node_data.inputs:
            inputs_dict[input.meta.get("type")][input.name] = _inputs_dict[input.name]

        # 6.请求方法映射
        request_methods = {
            HttpRequestMethod.GET: requests.get,
            HttpRequestMethod.POST: requests.post,
            HttpRequestMethod.PUT: requests.put,
            HttpRequestMethod.DELETE: requests.delete,
            HttpRequestMethod.PATCH: requests.patch,
            HttpRequestMethod.HEAD: requests.head,
            HttpRequestMethod.OPTIONS: requests.options,
        }

        # 7. 根据传入的method选择合适的方法
        request_method = request_methods[self.node_data.method]
        if self.node_data.method == HttpRequestMethod.GET:
            response = request_method(
                url=self.node_data.url,
                headers=inputs_dict[HttpRequestInputType.HEADERS],
                params=inputs_dict[HttpRequestInputType.PARAMS],
            )
        else:
            response = request_method(
                url=self.node_data.url,
                headers=inputs_dict[HttpRequestInputType.HEADERS],
                params=inputs_dict[HttpRequestInputType.PARAMS],
                data=inputs_dict[HttpRequestInputType.BODY],
            )

        # 8. 完善输出返回值outputs
        status_code = response.status_code
        text = response.text

        outputs = {
            "status_code": status_code,
            "text": text,
        }

        # 9. 组装返回结果
        return {
            "node_results": [
                NodeResult(
                    node_data=self.node_data,
                    status=NodeStatus.SUCCEEDED,
                    inputs=inputs_dict,
                    outputs=outputs,
                    latency=(time.perf_counter() - start_time),
                )
            ]
        }
