"""
@Time    : 2026/3/2 13:19
@Author  : jiachengjie
@File    : app_handler.py
"""
from dataclasses import dataclass
from uuid import UUID

from flask import request
from flask_login import login_required, current_user
from injector import inject

from internal.core.language_model import LanguageModelManager
from internal.schema.app_schema import CreateAppReq, GetAppResp, GetPublishHistoriesWithPage, \
    GetPublishHistoriesWithPageResp, FallbackHistoryToDraftReq, UpdateDebugConversationSummary, \
    DebugChatReq, GetDebugConversationMessagesWithPageResp, \
    GetDebugConversationMessagesWithPageReq, GetAppWithPageReq, GetAppWithPageResp, UpdateAppReq
from internal.service import (AppService)
from pkg.paginator import PageModel
from pkg.response import (success_message,
                          validate_error_json, success_json, compact_generate_response)


@inject
@dataclass
class AppHandler:
    """应用控制器"""
    app_service: AppService
    language_model_manager: LanguageModelManager

    @login_required
    def create_app(self):
        """在个人空间下新增应用"""
        req = CreateAppReq()
        if not req.validate():
            raise validate_error_json(req.errors)

        app = self.app_service.create_app(req, current_user)

        return success_message(f"应用服务创建成功,id为{app.id}")

    @login_required
    def get_app(self, app_id: UUID):
        app = self.app_service.get_app(app_id, current_user)
        resp = GetAppResp()
        return success_json(resp.dump(app))

    @login_required
    def get_draft_app_config(self, app_id: UUID):
        """根据传递的应用id获取应用的最新草稿配置"""
        draft_config = self.app_service.get_draft_app_config(app_id, current_user)
        return success_json(draft_config)

    @login_required
    def update_draft_app_config(self, app_id: UUID):
        """根据传递的应用id+草稿配置更新应用的最新草稿配置"""
        # 1.获取草稿请求json数据
        draft_app_config = request.get_json(force=True, silent=True) or {}

        # 2.调用服务更新应用的草稿配置
        self.app_service.update_draft_app_config(app_id, draft_app_config, current_user)

        return success_message("更新应用草稿配置成功")

    @login_required
    def publish(self, app_id: UUID):
        """发布/更新应用发布信息"""
        self.app_service.publish_draft_app_config(app_id, current_user)
        return success_message("发布/更新应用发布信息成功")

    @login_required
    def cancel_publish(self, app_id: UUID):
        """取消发布信息"""
        self.app_service.cancel_publish_draft_app_config(app_id, current_user)
        return success_message("取消发布信息成功")

    @login_required
    def get_publish_histories_with_page(self, app_id: UUID):

        """获取应用的发布历史列表"""
        req = GetPublishHistoriesWithPage(request.args)
        if not req.validate():
            raise validate_error_json(req.errors)

        # 2.调用服务获取分页列表数据
        app_config_versions, paginator = self.app_service.get_publish_histories_with_page(app_id, current_user, req)

        # 3.创建响应结构并返回
        resp = GetPublishHistoriesWithPageResp(many=True)

        return success_json(PageModel(list=resp.dump(app_config_versions), paginator=paginator))

    @login_required
    def fallback_history_to_draft(self, app_id: UUID):
        """回退指定的历史配置到草稿"""
        req = FallbackHistoryToDraftReq()
        if not req.validate():
            raise validate_error_json(req.errors)

        self.app_service.fallback_history_to_draft(app_id, req.app_config_version_id.data, current_user)

        return success_message("回退历史版本成功")

    @login_required
    def get_debug_conversation_summary(self, app_id: UUID):
        """获取应用调试长记忆"""
        summary = self.app_service.get_debug_conversation_summary(app_id, current_user)

        return success_json({"summary": summary})

    @login_required
    def update_debug_conversation_summary(self, app_id: UUID):
        """更新应用调试长记忆"""
        req = UpdateDebugConversationSummary()
        if not req.validate():
            raise validate_error_json(req.errors)

        summary = self.app_service.update_debug_conversation_summary(app_id, req.summary.data, current_user)

        return success_message("更新AI应用长记忆成功")

    @login_required
    def delete_debug_conversation(self, app_id: UUID):
        """清空应用的调试会话记录"""
        self.app_service.delete_debug_conversation(app_id, current_user)

        return success_message("清空应用调试长记录成功")

    @login_required
    def debug_chat(self, app_id: UUID):
        """根据传递的应用id+query，发起调试对话"""
        # 1.提取数据并校验数据
        req = DebugChatReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.调用服务发起会话调试
        response = self.app_service.debug_chat(app_id, req.query.data, current_user)

        return compact_generate_response(response)

    @login_required
    def stop_debug_chat(self, app_id: UUID, task_id: UUID):
        """根据传递的应用id+任务id停止某个应用的指定调试会话"""
        self.app_service.stop_debug_chat(app_id, task_id, current_user)
        return success_message("停止应用调试会话成功")

    @login_required
    def get_debug_conversation_messages_with_page(self, app_id: UUID):
        """根据传递的应用id，获取该应用的调试会话分页列表记录"""
        # 1.提取请求并校验数据
        req = GetDebugConversationMessagesWithPageReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        messages, paginator = self.app_service.get_debug_conversation_messages_with_page(app_id, req, current_user)

        resp = GetDebugConversationMessagesWithPageResp(many=True)

        return success_json(PageModel(list=resp.dump(messages), paginator=paginator))

    @login_required
    def delete_app(self, app_id: UUID):
        """删除指定的应用"""
        self.app_service.delete_app(app_id, current_user)
        return success_message("删除Agent智能体应用成功")

    @login_required
    def get_apps_with_page(self):
        """获取应用分页列表"""
        req = GetAppWithPageReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        apps, paginator = self.app_service.get_app_with_page(req, current_user)

        resp = GetAppWithPageResp(many=True)

        return success_json(PageModel(list=resp.dump(apps), paginator=paginator))

    @login_required
    def update_app(self, app_id: UUID):
        """修改应用基础信息"""
        req = UpdateAppReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.app_service.update_app(app_id, current_user, **req.data)

        return success_message("修改Agent智能体应用成功")

    @login_required
    def copy_app(self, app_id: UUID):
        """创建应用副本API"""
        app = self.app_service.copy_app(app_id, current_user)
        return success_json({"app_id": app.id})

    # @login_required
    # def ping(self):
    #     from internal.core.workflow import Workflow
    #     from internal.core.workflow.entities.workflow_entity import WorkflowConfig
    #
    #     # 该测试配置包含5条并行分支，LangGraph中从同一个起点引出多条边即为并行分支:
    #     #   分支1: start -> dataset_retrieval -> llm -> code -> end
    #     #   分支2: start -> template_transform -> end
    #     #   分支3: start -> tool(谷歌搜索) -> end
    #     #   分支4: start -> tool(高德天气) -> end
    #     #   分支5: start -> http_request -> end
    #     # WorkflowState的node_results字段使用Annotated自定义reducer(list拼接)，
    #     # 所以并行分支各自返回的NodeResult会自动汇聚合并，不会互相覆盖
    #     nodes = [
    #         {
    #             "id": "18d938c4-ecd7-4a6b-9403-3625224b96cc",
    #             "node_type": "start",
    #             "title": "开始",
    #             "description": "工作流的起点节点，支持定义工作流的起点输入等信息。",
    #             "inputs": [
    #                 {
    #                     "name": "query",
    #                     "type": "string",
    #                     "description": "用户输入的query信息",
    #                     "required": True,
    #                     "value": {
    #                         "type": "generated",
    #                         "content": "",
    #                     },
    #                 },
    #                 {
    #                     "name": "location",
    #                     "type": "string",
    #                     "description": "需要查询的城市地址信息",
    #                     "required": False,
    #                     "value": {
    #                         "type": "generated",
    #                         "content": "",
    #                     },
    #                 },
    #             ],
    #         },
    #         # ========== 分支1: 知识库检索节点 ==========
    #         {
    #             "id": "868b5769-1925-4e7b-8aa4-af7c3d444d91",
    #             "node_type": "dataset_retrieval",
    #             "title": "知识库检索",
    #             "description": "",
    #             "inputs": [
    #                 {
    #                     "name": "query",
    #                     "type": "string",
    #                     "value": {
    #                         "type": "ref",
    #                         "content": {
    #                             "ref_node_id": "18d938c4-ecd7-4a6b-9403-3625224b96cc",
    #                             "ref_var_name": "query"
    #                         }
    #                     }
    #                 }
    #             ],
    #             "dataset_ids": [
    #                 "7e77c5c0-3380-414e-8f57-799d27645a9f"
    #             ]
    #         },
    #         # ========== 分支1: LLM节点 ==========
    #         {
    #             "id": "eba75e0b-21b7-46ed-8d21-791724f0740f",
    #             "node_type": "llm",
    #             "title": "大语言模型",
    #             "description": "",
    #             "inputs": [
    #                 {
    #                     "name": "query",
    #                     "type": "string",
    #                     "value": {
    #                         "type": "ref",
    #                         "content": {
    #                             "ref_node_id": "18d938c4-ecd7-4a6b-9403-3625224b96cc",
    #                             "ref_var_name": "query",
    #                         },
    #                     },
    #                 },
    #                 {
    #                     "name": "context",
    #                     "type": "string",
    #                     "value": {
    #                         "type": "ref",
    #                         "content": {
    #                             "ref_node_id": "868b5769-1925-4e7b-8aa4-af7c3d444d91",
    #                             "ref_var_name": "combine_documents"
    #                         }
    #                     }
    #                 }
    #
    #             ],
    #             "prompt": ("你是一个强有力的AI机器人，请根据用户的提问回复特定的内容，用户的提问是：{{query}}。\n\n"
    #                        "如果有必要，可以使用上下文内容进行回复，上下文内容:\n\n<context>{{context}}</context>"
    #                        ),
    #
    #             "model_config": {
    #                 "provider": "openai",
    #                 "model": "kimi-k2.6",
    #                 "parameters": {
    #                     "temperature": 1,
    #                     "top_p": 0.95,
    #                     "frequency_penalty": 0,
    #                     "presence_penalty": 0,
    #                     "max_tokens": 8192,
    #                 },
    #             },
    #         },
    #         # ========== 分支1: 代码执行节点 ==========
    #         {
    #             "id": "a1b2c3d4-1111-2222-3333-444455556666",
    #             "node_type": "code",
    #             "title": "代码执行",
    #             "description": "",
    #             # main函数约定：有且只有一个参数params(字典，key为输入变量名)，返回一个字典
    #             "code": (
    #                 "def main(params):\n"
    #                 "    price = 100\n"
    #                 "    discount = 0.8\n"
    #                 "    final_price = price * discount\n"
    #                 "    return {\n"
    #                 "        'final_price': final_price,\n"
    #                 "        'city': params.get('location', ''),\n"
    #                 "        'query_length': len(params.get('query', '')),\n"
    #                 "    }\n"
    #             ),
    #             "inputs": [
    #                 {
    #                     "name": "location",
    #                     "type": "string",
    #                     "value": {
    #                         "type": "ref",
    #                         "content": {
    #                             "ref_node_id": "18d938c4-ecd7-4a6b-9403-3625224b96cc",
    #                             "ref_var_name": "location"
    #                         }
    #                     }
    #                 },
    #                 {
    #                     "name": "query",
    #                     "type": "string",
    #                     "value": {
    #                         "type": "ref",
    #                         "content": {
    #                             "ref_node_id": "18d938c4-ecd7-4a6b-9403-3625224b96cc",
    #                             "ref_var_name": "query"
    #                         }
    #                     }
    #                 }
    #             ],
    #             # 输出变量声明：名字需与main函数返回dict的key对应，供下游节点(end)引用校验
    #             "outputs": [
    #                 {
    #                     "name": "final_price",
    #                     "type": "float",
    #                     "value": {
    #                         "type": "generated",
    #                         "content": "",
    #                     },
    #                 },
    #                 {
    #                     "name": "city",
    #                     "type": "string",
    #                     "value": {
    #                         "type": "generated",
    #                         "content": "",
    #                     },
    #                 },
    #                 {
    #                     "name": "query_length",
    #                     "type": "int",
    #                     "value": {
    #                         "type": "generated",
    #                         "content": "",
    #                     },
    #                 }
    #             ],
    #         },
    #         # ========== 分支2: 模板转换节点(直接从start引出，与分支1并行) ==========
    #         {
    #             "id": "623b7671-0bc2-446c-bf5e-5e25032a522e",
    #             "node_type": "template_transform",
    #             "title": "模板转换",
    #             "description": "",
    #             "template": "这里填写你的Jinja2模板，例如：用户位置：{{location}}，查询内容：{{query}}",
    #             "inputs": [
    #                 {
    #                     "name": "location",
    #                     "type": "string",
    #                     "value": {
    #                         "type": "ref",
    #                         "content": {
    #                             "ref_node_id": "18d938c4-ecd7-4a6b-9403-3625224b96cc",
    #                             "ref_var_name": "location"
    #                         }
    #                     }
    #                 },
    #                 {
    #                     "name": "query",
    #                     "type": "string",
    #                     "value": {
    #                         "type": "ref",
    #                         "content": {
    #                             "ref_node_id": "18d938c4-ecd7-4a6b-9403-3625224b96cc",
    #                             "ref_var_name": "query"
    #                         }
    #                     }
    #                 }
    #             ]
    #         },
    #         # ========== 分支3: 工具节点(内置工具: 谷歌Serper搜索) ==========
    #         {
    #             "id": "c9d0e1f2-1111-2222-3333-444455558888",
    #             "node_type": "tool",
    #             "title": "谷歌搜索",
    #             "description": "",
    #             # 注意:ToolNodeData的tool_type字段设置了alias="type"，所以JSON里的key是type
    #             "type": "builtin_tool",
    #             "provider_id": "google",  # 服务提供商名，对应providers.yaml里的name
    #             "tool_id": "google_serper",  # 工具名，对应google/positions.yaml里声明的工具
    #             "params": {},
    #             "inputs": [
    #                 {
    #                     # 输入变量名必须和工具args_schema定义的参数名一致(谷歌搜索工具参数是query)
    #                     "name": "query",
    #                     "type": "string",
    #                     "value": {
    #                         "type": "ref",
    #                         "content": {
    #                             "ref_node_id": "18d938c4-ecd7-4a6b-9403-3625224b96cc",
    #                             "ref_var_name": "query"
    #                         }
    #                     }
    #                 }
    #             ],
    #         },
    #         # ========== 分支4: 工具节点(内置工具: 高德天气查询) ==========
    #         {
    #             "id": "b7c8d9e0-1111-2222-3333-444455557777",
    #             "node_type": "tool",
    #             "title": "高德天气查询",
    #             "description": "",
    #             "type": "builtin_tool",
    #             "provider_id": "gaode",
    #             "tool_id": "gaode_weather",
    #             "params": {},
    #             "inputs": [
    #                 {
    #                     # 高德天气工具args_schema的参数名是city
    #                     "name": "city",
    #                     "type": "string",
    #                     "value": {
    #                         "type": "ref",
    #                         "content": {
    #                             "ref_node_id": "18d938c4-ecd7-4a6b-9403-3625224b96cc",
    #                             "ref_var_name": "location"
    #                         }
    #                     }
    #                 }
    #             ],
    #         },
    #         # ========== 分支5: HTTP请求节点 ==========
    #         {
    #             "id": "675fca50-1228-8008-82dc-0c714158534c",
    #             "node_type": "http_request",
    #             "title": "HTTP请求",
    #             "description": "",
    #             "url": "https://www.langchain.com/",
    #             "method": "get",
    #             # inputs为空表示不带任何params/headers/body，等价于requests.get("https://www.langchain.com/")
    #             "inputs": [],
    #         },
    #         # ========== 结束节点(5条并行分支在此汇聚) ==========
    #         {
    #             "id": "860c8411-37ed-4872-b53f-30afa0290211",
    #             "node_type": "end",
    #             "title": "结束",
    #             "description": "工作流的结束节点，支持定义工作流最终输出的变量等信息。",
    #             "outputs": [
    #                 {
    #                     "name": "query",
    #                     "type": "string",
    #                     "value": {
    #                         "type": "ref",
    #                         "content": {
    #                             "ref_node_id": "18d938c4-ecd7-4a6b-9403-3625224b96cc",
    #                             "ref_var_name": "query",
    #                         },
    #                     },
    #                 },
    #                 {
    #                     "name": "location",
    #                     "type": "string",
    #                     "value": {
    #                         "type": "ref",
    #                         "content": {
    #                             "ref_node_id": "18d938c4-ecd7-4a6b-9403-3625224b96cc",
    #                             "ref_var_name": "location",
    #                         },
    #                     },
    #                 },
    #                 {
    #                     "name": "username",
    #                     "type": "string",
    #                     "value": {
    #                         "type": "literal",
    #                         "content": "泽辉呀",
    #                     },
    #                 },
    #                 # 引用LLM节点输出，验证分支1的运行结果
    #                 {
    #                     "name": "llm_result",
    #                     "type": "string",
    #                     "value": {
    #                         "type": "ref",
    #                         "content": {
    #                             "ref_node_id": "eba75e0b-21b7-46ed-8d21-791724f0740f",
    #                             "ref_var_name": "output",
    #                         },
    #                     },
    #                 },
    #                 # 引用代码执行节点输出，验证分支1的运行结果
    #                 {
    #                     "name": "final_price",
    #                     "type": "float",
    #                     "value": {
    #                         "type": "ref",
    #                         "content": {
    #                             "ref_node_id": "a1b2c3d4-1111-2222-3333-444455556666",
    #                             "ref_var_name": "final_price",
    #                         },
    #                     },
    #                 },
    #                 # 引用模板转换节点输出，验证分支2的运行结果
    #                 {
    #                     "name": "template_combine",
    #                     "type": "string",
    #                     "value": {
    #                         "type": "ref",
    #                         "content": {
    #                             "ref_node_id": "623b7671-0bc2-446c-bf5e-5e25032a522e",
    #                             "ref_var_name": "output",
    #                         },
    #                     },
    #                 },
    #                 # 引用工具节点输出，验证分支3的运行结果
    #                 {
    #                     "name": "search_result",
    #                     "type": "string",
    #                     "value": {
    #                         "type": "ref",
    #                         "content": {
    #                             "ref_node_id": "c9d0e1f2-1111-2222-3333-444455558888",
    #                             "ref_var_name": "text",
    #                         },
    #                     },
    #                 },
    #                 # 引用工具节点输出，验证分支4的运行结果
    #                 {
    #                     "name": "weather",
    #                     "type": "string",
    #                     "value": {
    #                         "type": "ref",
    #                         "content": {
    #                             "ref_node_id": "b7c8d9e0-1111-2222-3333-444455557777",
    #                             "ref_var_name": "text",
    #                         },
    #                     },
    #                 },
    #                 # 引用HTTP请求节点输出，验证分支5的运行结果
    #                 {
    #                     "name": "http_request_text",
    #                     "type": "string",
    #                     "value": {
    #                         "type": "ref",
    #                         "content": {
    #                             "ref_node_id": "675fca50-1228-8008-82dc-0c714158534c",
    #                             "ref_var_name": "text",
    #                         },
    #                     },
    #                 },
    #                 {
    #                     "name": "http_request_status_code",
    #                     "type": "int",
    #                     "value": {
    #                         "type": "ref",
    #                         "content": {
    #                             "ref_node_id": "675fca50-1228-8008-82dc-0c714158534c",
    #                             "ref_var_name": "status_code",
    #                         },
    #                     },
    #                 }
    #             ],
    #         },
    #     ]
    #     edges = [
    #         # ===== 分支1: start -> dataset_retrieval -> llm -> code -> end =====
    #         {
    #             "id": "a1000000-0000-0000-0000-000000000001",
    #             "source": "18d938c4-ecd7-4a6b-9403-3625224b96cc",
    #             "source_type": "start",
    #             "target": "868b5769-1925-4e7b-8aa4-af7c3d444d91",
    #             "target_type": "dataset_retrieval",
    #         },
    #         {
    #             "id": "a1000000-0000-0000-0000-000000000002",
    #             "source": "868b5769-1925-4e7b-8aa4-af7c3d444d91",
    #             "source_type": "dataset_retrieval",
    #             "target": "eba75e0b-21b7-46ed-8d21-791724f0740f",
    #             "target_type": "llm"
    #         },
    #         {
    #             "id": "a1000000-0000-0000-0000-000000000003",
    #             "source": "eba75e0b-21b7-46ed-8d21-791724f0740f",
    #             "source_type": "llm",
    #             "target": "a1b2c3d4-1111-2222-3333-444455556666",
    #             "target_type": "code"
    #         },
    #         {
    #             "id": "a1000000-0000-0000-0000-000000000004",
    #             "source": "a1b2c3d4-1111-2222-3333-444455556666",
    #             "source_type": "code",
    #             "target": "860c8411-37ed-4872-b53f-30afa0290211",
    #             "target_type": "end"
    #         },
    #         # ===== 分支2: start -> template_transform -> end =====
    #         {
    #             "id": "a1000000-0000-0000-0000-000000000005",
    #             "source": "18d938c4-ecd7-4a6b-9403-3625224b96cc",
    #             "source_type": "start",
    #             "target": "623b7671-0bc2-446c-bf5e-5e25032a522e",
    #             "target_type": "template_transform"
    #         },
    #         {
    #             "id": "a1000000-0000-0000-0000-000000000006",
    #             "source": "623b7671-0bc2-446c-bf5e-5e25032a522e",
    #             "source_type": "template_transform",
    #             "target": "860c8411-37ed-4872-b53f-30afa0290211",
    #             "target_type": "end"
    #         },
    #         # ===== 分支3: start -> tool(谷歌搜索) -> end =====
    #         {
    #             "id": "a1000000-0000-0000-0000-000000000007",
    #             "source": "18d938c4-ecd7-4a6b-9403-3625224b96cc",
    #             "source_type": "start",
    #             "target": "c9d0e1f2-1111-2222-3333-444455558888",
    #             "target_type": "tool"
    #         },
    #         {
    #             "id": "a1000000-0000-0000-0000-000000000008",
    #             "source": "c9d0e1f2-1111-2222-3333-444455558888",
    #             "source_type": "tool",
    #             "target": "860c8411-37ed-4872-b53f-30afa0290211",
    #             "target_type": "end"
    #         },
    #         # ===== 分支4: start -> tool(高德天气) -> end =====
    #         {
    #             "id": "a1000000-0000-0000-0000-000000000009",
    #             "source": "18d938c4-ecd7-4a6b-9403-3625224b96cc",
    #             "source_type": "start",
    #             "target": "b7c8d9e0-1111-2222-3333-444455557777",
    #             "target_type": "tool"
    #         },
    #         {
    #             "id": "a1000000-0000-0000-0000-000000000010",
    #             "source": "b7c8d9e0-1111-2222-3333-444455557777",
    #             "source_type": "tool",
    #             "target": "860c8411-37ed-4872-b53f-30afa0290211",
    #             "target_type": "end"
    #         },
    #         # ===== 分支5: start -> http_request -> end =====
    #         {
    #             "id": "a1000000-0000-0000-0000-000000000011",
    #             "source": "18d938c4-ecd7-4a6b-9403-3625224b96cc",
    #             "source_type": "start",
    #             "target": "675fca50-1228-8008-82dc-0c714158534c",
    #             "target_type": "http_request"
    #         },
    #         {
    #             "id": "a1000000-0000-0000-0000-000000000012",
    #             "source": "675fca50-1228-8008-82dc-0c714158534c",
    #             "source_type": "http_request",
    #             "target": "860c8411-37ed-4872-b53f-30afa0290211",
    #             "target_type": "end"
    #         }
    #     ]
    #
    #     workflow = Workflow(workflow_config=WorkflowConfig(
    #         account_id=current_user.id,
    #         name="workflow",
    #         description="工作流组件",
    #         nodes=nodes,
    #         edges=edges,
    #     ))
    #
    #     result = workflow.invoke({"query": "关于前端的prompt有哪些?", "location": "广州"})
    #
    #     return success_json({
    #         **result,
    #         "info": {
    #             "name": workflow.name,
    #             "description": workflow.description,
    #             "args_schema": workflow.args_schema.schema(),
    #         },
    #         # model_dump(mode="json")会把UUID、枚举等对象转成JSON兼容的类型
    #         "node_results": [node_result.model_dump(mode="json") for node_result in result["node_results"]]
    #     })

    @login_required
    def ping(self):
        provider = self.language_model_manager.get_provider("tongyi")
        model_entity = provider.get_model_entity("qwen3.8-flash")
        model_class = provider.get_model_class(model_entity.model_type)

        llm = model_class(**{
            **model_entity.attributes,
            "features": model_entity.features,
            "metadata": model_entity.metadata,
        })
        return success_json({
            "content": llm.invoke("你好，你是？").content,
            "features": llm.features,
            "metadata": llm.metadata,
        })
