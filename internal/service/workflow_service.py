"""
@Time    : 2026-10-12 14:23
@Author  : JiaChengJie
@File    : workflow_service.py
"""

import json
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Generator
from uuid import UUID

from flask import request
from injector import inject
from sqlalchemy import desc, update

from internal.core.tool.builtin_tools.providers import BuiltinProviderManager
from internal.core.workflow import Workflow as WorkflowTool
from internal.core.workflow.entities.edge_entity import BaseEdgeData
from internal.core.workflow.entities.node_entity import NodeType, BaseNodeData
from internal.core.workflow.entities.workflow_entity import WorkflowConfig
from internal.core.workflow.nodes import StartNodeData, LLMNodeData, HttpRequestNodeData, CodeNodeData, \
    DatasetRetrievalNodeData, TemplateTransformNodeData, EndNodeData, ToolNodeData
from internal.entity.workflow_entity import DEFAULT_WORKFLOW_CONFIG, WorkflowStatus, WorkflowResultStatus
from internal.exception import ValidateErrorException, NotFoundException, FailException
from internal.lib.helper import convert_model_to_dict
from internal.model import Account, Workflow, Dataset, ApiTool, WorkflowResult
from internal.schema.workflow_schema import GetDatasetWithPageReq, CreateWorkflowReq, UpdateWorkflowReq
from internal.service import BaseService
from pkg.paginator import PaginatorReq, Paginator
from pkg.sqlalchemy.sqlalchemy import SQLAlchemy


@inject
@dataclass
class WorkflowService(BaseService):
    """工作流服务"""
    db: SQLAlchemy
    builtin_provider_manager: BuiltinProviderManager

    def create_workflow(self, req: CreateWorkflowReq, account: Account) -> Workflow:
        """创建工作流信息数据"""
        # 1. 判断是否存在重名工作流信息
        check_workflow = self.db.session.query(Workflow).filter(
            Workflow.account_id == account.id,
            Workflow.tool_call_name == req.tool_call_name.data.strip(),
        ).one_or_none()

        if check_workflow:
            raise ValidateErrorException(f"该账号下以及创建{req.tool_call_name.data}，工作流信息")

        return self.create(Workflow, **{
            **req.data,
            **DEFAULT_WORKFLOW_CONFIG,
            "account_id": account.id,
            "is_debug_passed": False,
            "status": WorkflowStatus.DRAFT,
            "tool_call_name": req.tool_call_name.data.strip(),
        })

    def get_workflow(self, workflow_id: UUID, account: Account) -> Workflow:
        """根据workflow_id获取Workflow信息"""
        workflow = self.query(Workflow, workflow_id)

        if workflow is None or workflow.account_id != account.id:
            raise NotFoundException(f"工作流信息{workflow_id}不存在")

        return workflow

    def update_workflow(self, workflow_id: UUID, req: UpdateWorkflowReq, account: Account) -> Workflow:
        """修改用户信息"""
        # 1. 判断用户是否有权修改
        workflow = self.get_workflow(workflow_id, account)

        # 2.根据传递的工具调用名字查询是否存在重名工作流
        check_workflow = self.db.session.query(Workflow).filter(
            Workflow.tool_call_name == req.tool_call_name.data.strip(),
            Workflow.account_id == account.id,
            Workflow.id != workflow_id,
        ).one_or_none()

        if check_workflow:
            raise ValidateErrorException(f"工作流工具名称{req.tool_call_name.data}不能重复")

        # 3. 修改用户信息
        self.update(workflow, **req.data)

        return workflow

    def get_workflows_with_page(
            self, req: GetDatasetWithPageReq, account: Account) -> tuple[list[Any], PaginatorReq]:
        """获取账号下的工作流分页数据"""
        # 1. 获取分页组件
        paginator = Paginator(db=self.db, req=req)

        # 2. 构建筛选器
        filters = [Workflow.account_id == account.id]
        # 3. 判断工作流状态status/工作流名字name,是否有值
        if req.status.data:
            filters.append(Workflow.status == req.status.data)
        if req.search_word.data:
            filters.append(Workflow.name.ilike(f"%{req.search_word.data}%"))

        # 4. 执行分页并获取数据
        workflow_entity = paginator.paginate(
            self.db.session.query(Workflow).filter(*filters).order_by(desc("created_at"))
        )

        return workflow_entity, paginator

    def delete_workflow(self, workflow_id: UUID, account: Account) -> Workflow:
        """根据workflow_id删除指定工作流信息"""
        workflow = self.get_workflow(workflow_id, account)
        self.delete(workflow)
        return workflow

    def update_draft_graph(self, workflow_id: UUID, draft_graph: dict[str, Any], account: Account) -> Workflow:
        """修改工作流草稿配置信息（节点+边配置）"""
        # 1. 获取工作流信息
        workflow = self.get_workflow(workflow_id, account)
        # 2. 校验节点信息和边信息
        draft_graph_config = self._validate_graph(draft_graph, account)

        # 3.修改草稿配置信息，若草稿内容没有变化则不重置调试状态（避免前端刷新画布误重置）
        if draft_graph_config != workflow.draft_graph:
            print("[TRACE] 草稿判定为有变化，准备重置调试状态", flush=True)
            # 输出差异细节，定位"误判有变化"的原因
            old_nodes = {n.get("id"): n for n in (workflow.draft_graph or {}).get("nodes", [])}
            new_nodes = {n.get("id"): n for n in draft_graph_config.get("nodes", [])}
            if old_nodes.keys() != new_nodes.keys():
                print(
                    f"[TRACE] 节点id集合不同: 新增{set(new_nodes) - set(old_nodes)} 删除{set(old_nodes) - set(new_nodes)}",
                    flush=True)
            else:
                for nid, new_node in new_nodes.items():
                    if new_node != old_nodes[nid]:
                        diff_keys = [k for k in set(new_node) | set(old_nodes[nid])
                                     if new_node.get(k) != old_nodes[nid].get(k)]
                        print(f"[TRACE] 节点{new_node.get('title')}({nid}) 变化的字段: {diff_keys}", flush=True)
            old_edges = {e.get("id"): e for e in (workflow.draft_graph or {}).get("edges", [])}
            new_edges = {e.get("id"): e for e in draft_graph_config.get("edges", [])}
            if old_edges.keys() != new_edges.keys():
                print(
                    f"[TRACE] 边id集合不同: 新增{set(new_edges) - set(old_edges)} 删除{set(old_edges) - set(new_edges)}",
                    flush=True)
            self.update(workflow, **{
                "draft_graph": draft_graph_config,
                "is_debug_passed": False
            })
        else:
            print("[TRACE] 草稿内容未变化，保留调试状态", flush=True)

        return workflow

    def get_draft_graph(self, workflow_id: UUID, account: Account) -> dict[str, Any]:
        """获取指定工作流的graph图草稿配置"""
        # 1. 根据指定的id获取工作流信息
        workflow = self.get_workflow(workflow_id, account)

        # 2.获取draft_graph信息
        draft_graph = workflow.draft_graph
        validate_draft_graph = self._validate_graph(draft_graph, account)

        # 3.循环遍历节点信息，为工具节点/知识库节点附加元数据
        for node in validate_draft_graph["nodes"]:
            if node["node_type"] == NodeType.TOOL:
                # 4.判断工具的类型执行不同的操作
                if node["tool_type"] == "builtin_tool":
                    # 5.节点类型为工具，则附加工具的名称、图标、参数等额外信息
                    provider = self.builtin_provider_manager.get_provider(node["provider_id"])
                    if not provider:
                        continue
                    # 6.获取提供者下的工具实体，并检测是否存在
                    tool_entity = provider.get_tool_entity(node["tool_id"])
                    if not tool_entity:
                        continue
                    # 7.判断工具的params和草稿中的params是否一致，如果不一致则全部重置为默认值（或者考虑删除这个工具的引用）
                    param_keys = set([param.name for param in tool_entity.params])
                    params = node["params"]
                    if set(params.keys()) - param_keys:
                        params = {
                            param.name: param.default
                            for param in params.keys()
                            if param.default is not None
                        }
                    # 8.数据校验成功附加展示信息
                    provider_entity = provider.provider_entity
                    node["meta"] = {
                        "type": "builtin_tool",
                        "provider": {
                            "id": provider_entity.name,
                            "name": provider_entity.name,
                            "label": provider_entity.label,
                            "icon": f"{request.scheme}://{request.host}/builtin-tools/{provider_entity.name}/icon",
                            "description": provider_entity.description,
                        },
                        "tool": {
                            "id": tool_entity.name,
                            "name": tool_entity.name,
                            "label": tool_entity.label,
                            "description": tool_entity.description,
                            "params": params,
                        }
                    }


                else:
                    # 9.查询数据库获取对应的工具记录，并检测是否存在
                    tool_record = self.db.session.query(ApiTool).filter(
                        ApiTool.account_id == account.id,
                        ApiTool.provider_id == node["provider_id"],
                        ApiTool.name == node["tool_id"],
                    ).one_or_none()
                    if not tool_record:
                        continue

                    # 10.组装api工具展示信息
                    provider = tool_record.provider
                    node["meta"] = {
                        "type": "api_tool",
                        "provider": {
                            "id": str(provider.id),
                            "name": provider.name,
                            "label": provider.name,
                            "icon": provider.icon,
                            "description": provider.description,
                        },
                        "tool": {
                            "id": str(tool_record.id),
                            "name": tool_record.name,
                            "label": tool_record.name,
                            "description": tool_record.description,
                            "params": {},
                        },
                    }

            # 5.节点类型为知识库检索，需要附加知识库的名称、图标等信息
            elif node.get("node_type") == NodeType.DATASET_RETRIEVAL:
                # 5.节点类型为知识库检索，需要附加知识库的名称、图标等信息
                datasets = self.db.session.query(Dataset).filter(
                    Dataset.id.in_(node.get("dataset_ids", [])),
                    Dataset.account_id == account.id,
                ).all()
                node["meta"] = {
                    "datasets": [{
                        "id": dataset.id,
                        "name": dataset.name,
                        "icon": dataset.icon,
                        "description": dataset.description,
                    } for dataset in datasets]
                }

        return validate_draft_graph

    def debug_workflow(self, workflow_id: UUID, inputs: dict[str, Any], account: Account) -> Generator:
        """调试指定的工作流API接口，该接口为流式事件输出"""
        # 1.根据传递的id获取工作流并校验权限
        workflow = self.get_workflow(workflow_id, account)

        # 2.创建工作流工具
        workflow_tool = WorkflowTool(workflow_config=WorkflowConfig(
            account_id=account.id,
            name=workflow.tool_call_name,
            description=workflow.description,
            nodes=workflow.draft_graph.get("nodes", []),
            edges=workflow.draft_graph.get("edges", []),
        ))

        def handle_stream() -> Generator:
            print("[TRACE] handle_stream 生成器启动（新代码已加载）", flush=True)
            # 3.定义变量存储所有节点运行结果
            node_results = []

            # 4.添加数据库工作流运行结果记录
            workflow_result = self.create(WorkflowResult, **{
                "app_id": None,
                "account_id": account.id,
                "workflow_id": workflow.id,
                "graph": workflow.draft_graph,
                "state": [],
                "latency": 0,
                "status": WorkflowResultStatus.RUNNING,
            })

            # 4.调用stream服务获取工具信息
            start_at = time.perf_counter()
            try:
                for chunk in workflow_tool.stream(inputs):
                    # 5.chunk的格式为:{"node_name": WorkflowState}，所以需要取出节点响应结构的第1个key
                    first_key = next(iter(chunk))

                    # 6.取出各个节点的运行结果
                    node_result = chunk[first_key]["node_results"][0]
                    node_result_dict = convert_model_to_dict(node_result)
                    node_results.append(node_result_dict)

                    # 7.组装响应数据并流式事件输出
                    data = {
                        "id": str(uuid.uuid4()),
                        **node_result_dict,
                    }
                    yield f"event: workflow\ndata: {json.dumps(data)}\n\n"

                # 7.流式输出完毕后，将结果存储到数据库中
                print("[TRACE] 流结束，开始更新 workflow_result 为 SUCCEEDED", flush=True)
                self.update(workflow_result, **{
                    "status": WorkflowResultStatus.SUCCEEDED,
                    "state": node_results,
                    "latency": (time.perf_counter() - start_at),
                })
                print("[TRACE] workflow_result 已提交，准备更新 is_debug_passed", flush=True)
                # 使用UPDATE语句直接更新，避免流式阶段ORM实例与session脱钩导致静默失败
                with self.db.auto_commit():
                    self.db.session.execute(
                        update(Workflow)
                        .where(Workflow.id == workflow_id)
                        .values(is_debug_passed=True)
                    )
                print("[TRACE] is_debug_passed 更新代码执行完毕", flush=True)
            except Exception as e:
                print(f"[TRACE] !!! except 捕获到异常: {type(e).__name__}: {e}", flush=True)
                logging.exception("工作流调试执行出错")  # 打印完整堆栈，定位不执行的真正原因
                self.update(workflow_result, **{
                    "status": WorkflowResultStatus.FAILED,
                    "state": node_results,
                    "latency": (time.perf_counter() - start_at)
                })
                raise FailException(str(e))

        return handle_stream()

    def publish_workflow(self, workflow_id: UUID, account: Account) -> Workflow:
        """发布工作流信息 """
        # 1. 获取工作流信息
        workflow = self.get_workflow(workflow_id, account)
        # 2.校验工作流是否调试通过
        if not workflow.is_debug_passed:
            raise FailException("工作流调试未通过，不能发布服务")
        if workflow.status == WorkflowStatus.PUBLISHED:
            raise FailException("工作流已发布，不能重复发布")
        try:
            # 3.使用WorkflowConfig二次校验，如果校验失败则不发布
            WorkflowConfig(
                account_id=account.id,
                name=workflow.tool_call_name,
                description=workflow.description,
                edges=workflow.draft_graph.get("edges", []),
                nodes=workflow.draft_graph.get("nodes", []),
            )
        except Exception as e:
            self.update(workflow, **{
                "is_debug_passed": False,
            })
            raise ValidateErrorException("工作流配置信息校验失败，无法发布！")

        # 4.更新工作流的发布状态
        self.update(workflow, **{
            "graph": workflow.draft_graph,
            "published_at": datetime.now(),
            "status": WorkflowStatus.PUBLISHED,
        })

        return workflow

    def cancel_publish_workflow(self, workflow_id: UUID, account: Account) -> Workflow:
        """取消工作流信息"""
        # 1. 获取工作流信息
        workflow = self.get_workflow(workflow_id, account)

        # 2.校验工作流是否为已发布的状态
        if workflow.status != WorkflowStatus.PUBLISHED:
            raise FailException("该工作流未发布无法取消发布")

        # 3. 修改工作流状态和运行时图配置
        self.update(workflow, **{
            "graph": {},
            "status": WorkflowStatus.DRAFT,
            "published_at": None,
        })

        return workflow

    def _validate_graph(self, graph: dict[str, Any], account: Account) -> dict[str, Any]:
        """校验传递的graph信息，涵盖nodes和edges对应的数据，该函数使用相对宽松的校验方式，并且因为是草稿，不需要校验节点与边的关系"""
        # 1.提取nodes和edges数据
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])

        # 2.构建节点类型与节点数据类映射
        node_data_classes = {
            NodeType.START: StartNodeData,
            NodeType.END: EndNodeData,
            NodeType.LLM: LLMNodeData,
            NodeType.TEMPLATE_TRANSFORM: TemplateTransformNodeData,
            NodeType.DATASET_RETRIEVAL: DatasetRetrievalNodeData,
            NodeType.CODE: CodeNodeData,
            NodeType.TOOL: ToolNodeData,
            NodeType.HTTP_REQUEST: HttpRequestNodeData,
        }

        # 3.循环校验nodes中各个节点对应的数据
        node_data_dict: dict[UUID, BaseNodeData] = {}
        start_nodes = 0
        end_nodes = 0
        for node in nodes:
            try:
                # 4.校验传递的node数据是不是字典，如果不是则跳过当前数据
                if not isinstance(node, dict):
                    raise ValidateErrorException("工作流节点数据类型出错，请核实后重试")

                # 5.提取节点的node_type类型，并判断类型是否正确
                node_type = node.get("node_type", "")
                node_data_cls = node_data_classes.get(node_type, None)
                if node_data_cls is None:
                    raise ValidateErrorException("工作流节点类型出错，请核实后重试")

                # 6.实例化节点数据类型，如果出错则跳过当前数据
                node_data = node_data_cls(**node)

                # 7.判断节点id是否唯一，如果不唯一，则将当前节点清除
                if node_data.id in node_data_dict:
                    raise ValidateErrorException("工作流节点id必须唯一，请核实后重试")

                # 8.判断节点title是否唯一，如果不唯一，则将当前节点清除
                if any(item.title.strip() == node_data.title.strip() for item in node_data_dict.values()):
                    raise ValidateErrorException("工作流节点title必须唯一，请核实后重试")

                # 9.对特殊节点进行判断，涵盖开始/结束/知识库检索/工具
                if node_data.node_type == NodeType.START:
                    if start_nodes >= 1:
                        raise ValidateErrorException("工作流中只允许有1个开始节点")
                    start_nodes += 1
                elif node_data.node_type == NodeType.END:
                    if end_nodes >= 1:
                        raise ValidateErrorException("工作流中只允许有1个结束节点")
                    end_nodes += 1
                elif node_data.node_type == NodeType.DATASET_RETRIEVAL:
                    # 10.剔除关联知识库列表中不属于当前账户的数据
                    datasets = self.db.session.query(Dataset).filter(
                        Dataset.id.in_(node_data.dataset_ids[:5]),
                        Dataset.account_id == account.id,
                    ).all()
                    node_data.dataset_ids = [dataset.id for dataset in datasets]
                elif node_data.node_type == NodeType.TOOL:
                    # 11.判断工具的类型执行不同的操作
                    if node_data.tool_type == "builtin_tool":
                        tool = self.builtin_provider_manager.get_tool(node_data.provider_id, node_data.tool_id)
                        if not tool:
                            raise ValidateErrorException("工具节点绑定的内置工具不存在")
                    else:
                        # 12.API工具，查询当前工具是否属于当前账号
                        tool_record = self.db.session.query(ApiTool).filter(
                            ApiTool.provider_id == node_data.provider_id,
                            ApiTool.name == node_data.tool_id,
                            ApiTool.account_id == account.id,
                        ).one_or_none()
                        if not tool_record:
                            raise ValidateErrorException("工具节点绑定的API工具不存在")

                # 13.将数据添加到node_data_dict中
                node_data_dict[node_data.id] = node_data
            except Exception:
                continue

        # 14.循环校验edges中各个节点对应的数据
        edge_data_dict: dict[UUID, BaseEdgeData] = {}
        for edge in edges:
            try:
                # 15.边类型为非字典则抛出错误，否则转换成BaseEdgeData
                if not isinstance(edge, dict):
                    raise ValidateErrorException("工作流边数据类型出错，请核实后重试")
                edge_data = BaseEdgeData(**edge)

                # 16.校验边edges的id是否唯一
                if edge_data.id in edge_data_dict:
                    raise ValidateErrorException("工作流边数据id必须唯一，请核实后重试")

                # 17.校验边中的source/target/source_type/target_type必须和nodes对得上
                if (
                        edge_data.source not in node_data_dict
                        or edge_data.source_type != node_data_dict[edge_data.source].node_type
                        or edge_data.target not in node_data_dict
                        or edge_data.target_type != node_data_dict[edge_data.target].node_type
                ):
                    raise ValidateErrorException("工作流边起点/终点对应的节点不存在或类型错误，请核实后重试")

                # 18.校验边Edges里的边必须唯一(source+target必须唯一)
                if any(
                        (item.source == edge_data.source and item.target == edge_data.target)
                        for item in edge_data_dict.values()
                ):
                    raise ValidateErrorException("工作流边数据不能重复添加")

                # 19.基础数据校验通过，将数据添加到edge_data_dict中
                edge_data_dict[edge_data.id] = edge_data
            except Exception:
                continue

        return {
            "nodes": [convert_model_to_dict(node_data) for node_data in node_data_dict.values()],
            "edges": [convert_model_to_dict(edge_data) for edge_data in edge_data_dict.values()],
        }
