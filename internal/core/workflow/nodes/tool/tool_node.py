"""
@Time    : 2026-10-07 12:02
@Author  : JiaChengJie
@File    : tool_node.py
"""
import json
import time
from typing import Any

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from pydantic import PrivateAttr

from internal.core.tool.api_tools.entities import ToolEntity
from internal.core.workflow.entities.node_entity import NodeResult, NodeStatus
from internal.core.workflow.entities.workflow_entity import WorkflowState
from internal.core.workflow.nodes import BaseNode
from internal.core.workflow.untils.helper import extract_variables_from_state
from internal.exception import NotFoundException, FailException
from internal.model import ApiTool
from .tool_entity import ToolNodeData


class ToolNode(BaseNode):
    """工具使用节点"""
    node_data: ToolNodeData
    _tool: BaseTool = PrivateAttr(None)

    def __init__(self, *args: Any, **kwargs: Any):
        """构造函数完成对内置函数的初始化"""
        # 1.调用父类构造函数完成初始化
        super().__init__(*args, **kwargs)

        # 2. 导入依赖注入及工具提供者
        from app.http.model import injector

        # 3. 判断是内置插件还是系统插件
        if self.node_data.tool_type == "builtin_tool":
            from internal.core.tool.builtin_tools.providers import BuiltinProviderManager
            builtin_provider_manager = injector.get(BuiltinProviderManager)

            # 4. 调用内置提供者获取内置插件
            _tool = builtin_provider_manager.get_tool(self.node_data.provider_id, self.node_data.tool_id)
            if not _tool:
                raise NotFoundException("内置插件不存在，请核实后重试")
            self._tool = _tool(**self.node_data.params)
        else:
            # 4. 系统插件从数据库中去获取
            from pkg.sqlalchemy import SQLAlchemy
            db = injector.get(SQLAlchemy)

            # 5. 根据传递者的名字 + 工具名字查询工具
            api_tool = db.session.query(ApiTool).filter(
                ApiTool.id == self.node_data.tool_id,
                ApiTool.provider_id == self.node_data.provider_id,
            ).one_or_none()

            if not api_tool:
                raise NotFoundException("Api插件不存在，请核实后重试")

            # 7. 导入插件提供者
            from internal.core.tool.api_tools.providers import ApiProviderManager
            api_provider_manager = injector.get(ApiProviderManager)

            # 8. 创建API工具提供者并赋值
            # 注意:ApiTool模型上的字段是name/method/description(没有tool_前缀)，
            # 请求头headers定义在ApiToolProvider表上，需要通过provider关联获取
            self._tool = api_provider_manager.get_tool(ToolEntity(
                id=str(api_tool.id),
                name=api_tool.name,
                url=api_tool.url,
                method=api_tool.method,
                description=api_tool.description,
                parameters=api_tool.parameters,
                headers=api_tool.provider.headers,
            ))

    def invoke(self, state: WorkflowState, config: RunnableConfig | None = None, **kwargs: Any) -> WorkflowState:
        """工具执行节点函数"""
        start_time = time.perf_counter()
        # 1. 循环遍历获取输入值
        inputs_dict = extract_variables_from_state(self.node_data.inputs, state)
        # 4.调用invoke方法
        try:
            result = self._tool.invoke(inputs_dict)
        except Exception as e:
            raise FailException("插件节点执行出错，请稍后重试")

        # 5. 检测result是否为字符串，如果不是则转换
        if not isinstance(result, str):
            result = json.dumps(result, ensure_ascii=False)

        # 6.提取结果并构造输出结构
        outputs = {}
        if self.node_data.outputs:
            outputs[self.node_data.outputs[0].name] = result
        else:
            outputs["text"] = result

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
