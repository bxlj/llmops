"""
@Time    : 2026-07-24 11:23
@Author  : JiaChengJie
@File    : app_config_service.py
"""
from dataclasses import dataclass
from typing import Union, Any

from flask import request
from injector import inject

from internal.core.tool.api_tools.entities import ToolEntity
from internal.core.tool.api_tools.providers import ApiProviderManager
from internal.core.tool.builtin_tools.providers import BuiltinProviderManager
from internal.lib.helper import datetime_to_timestamp
from internal.model import App, Dataset, ApiTool, AppConfig, AppConfigVersion, AppDatasetJoin
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService


@inject
@dataclass
class AppConfigService(BaseService):
    """应用配置服务"""

    db: SQLAlchemy
    api_provider_manager: ApiProviderManager
    builtin_provider_manager: BuiltinProviderManager

    def get_draft_app_config(self, app: App):
        # 2. 获取草稿配置信息
        draft_app_config = app.draft_app_config

        # todo:3.校验model_config配置信息，等待多LLM实现的时候再来完成

        # 4. 获取获取草稿配置信息中的工具字段
        draft_tools = draft_app_config.tools

        # 5. 判断草稿配置信息中tool是否存在，是否已经修改，如果已经修改，则修改草稿配置信息中tool中的配置
        tools, validate_tools = self._process_and_validate_tools(draft_tools)

        # 6.判断是否需要更新草稿配置中的工具列表信息
        if draft_app_config.tools != validate_tools:
            # 7.更新草稿配置中的工具列表
            self.update(draft_app_config, tools=validate_tools)

        datasets, exist_dataset_ids = self._process_and_validate_datasets(draft_app_config.datasets)

        # 8.判断是否存在已删除的知识库，如果存在则更新
        if set(exist_dataset_ids) != set(draft_app_config.datasets):
            self.update(draft_app_config, datasets=exist_dataset_ids)

        # todo:19.校验工作流列表对应的数据
        workflows = []

        # 20.将数据转换成字典后返回
        return self._process_and_transformer_app_config(tools, workflows, datasets, draft_app_config)

    def get_app_config(self, app: App) -> dict[str, Any]:
        """根据传递的应用获取该应用的运行配置"""
        # 1.提取应用的草稿配置
        app_config = app.app_config

        # todo:2.校验model_config配置信息，等待多LLM实现的时候再来完成

        # 3.循环遍历工具列表删除已经被删除的工具信息
        tools, validate_tools = self._process_and_validate_tools(app_config.tools)

        # 4.判断是否需要更新草稿配置中的工具列表信息
        if app_config.tools != validate_tools:
            # 14.更新草稿配置中的工具列表
            self.update(app_config, tools=validate_tools)

        # 5.校验知识库列表，如果引用了不存在/被删除的知识库，需要剔除数据并更新，同时获取知识库的额外信息
        app_dataset_joins = app_config.app_dataset_joins
        origin_datasets = [str(app_dataset_join.dataset_id) for app_dataset_join in app_dataset_joins]
        datasets, validate_datasets = self._process_and_validate_datasets(origin_datasets)

        # 6.判断是否存在已删除的知识库，如果存在则更新
        for dataset_id in (set(origin_datasets) - set(validate_datasets)):
            with self.db.auto_commit():
                self.db.session.query(AppDatasetJoin).filter(AppDatasetJoin.dataset_id == dataset_id).delete()

        # todo:7.校验工作流列表对应的数据
        workflows = []

        # 20.将数据转换成字典后返回
        return self._process_and_transformer_app_config(tools, workflows, datasets, app_config)

    @classmethod
    def _process_and_transformer_app_config(
            cls,
            tools: list[dict],
            workflows: list[dict],
            datasets: list[dict],
            app_config: Union[AppConfig, AppConfigVersion]
    ) -> dict[str, Any]:
        """根据传递的插件列表、工作流列表、知识库列表以及应用配置创建字典信息"""
        return {
            "id": str(app_config.id),
            "model_config": app_config.model_config,
            "dialog_round": app_config.dialog_round,
            "preset_prompt": app_config.preset_prompt,
            "tools": tools,
            "workflows": workflows,
            "datasets": datasets,
            "retrieval_config": app_config.retrieval_config,
            "long_term_memory": app_config.long_term_memory,
            "opening_statement": app_config.opening_statement,
            "opening_questions": app_config.opening_questions,
            "speech_to_text": app_config.speech_to_text,
            "text_to_speech": app_config.text_to_speech,
            "suggested_after_answer": app_config.suggested_after_answer,
            "review_config": app_config.review_config,
            "updated_at": datetime_to_timestamp(app_config.updated_at),
            "created_at": datetime_to_timestamp(app_config.created_at),
        }

    def _process_and_validate_tools(self, draft_tools: list[dict]) -> tuple[list[dict], list[dict]]:
        validate_tools = []
        tools = []
        for draft_tool in draft_tools:
            # 6. 判断是内置插件还是api插件
            if draft_tool["type"] == "builtin_tool":
                # 7. 调用内置插件服务，获取对应供应商信息
                provider = self.builtin_provider_manager.get_provider(draft_tool["provider_id"])
                if not provider:
                    continue

                tool_entity = provider.get_tool_entity(draft_tool["tool_id"])
                if not tool_entity:
                    continue

                # 7.判断工具的params和草稿中的params是否一致，如果不一致则全部重置为默认值（或者考虑删除这个工具的引用）
                param_keys = set([param.name for param in tool_entity.params])
                params = draft_tool["params"]
                if set(draft_tool["params"].keys()) - param_keys:
                    params = {
                        param.name: param.default
                        for param in tool_entity.params
                        if param.default is not None
                    }
                # 8. 将校验后的参数值添加到validate_tools中去
                validate_tools.append({**draft_tool, "params": params})

                # 9. 组装内置根据参数
                provider_entity = provider.provider_entity
                tools.append({
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
                        "params": draft_tool["params"],

                    }

                })
            elif draft_tool["type"] == "api_tool":
                # 10.查询数据库获取对应的工具记录，并检测是否存在
                api_tool = self.db.session.query(ApiTool).filter(
                    ApiTool.name == draft_tool["tool_id"],
                    ApiTool.provider_id == draft_tool["provider_id"],
                ).one_or_none()

                if not api_tool:
                    continue

                # 11. 数据校验通过，往validate_tools中添加数据
                validate_tools.append(draft_tool)

                # 12. 组装api_tool数据
                provider = api_tool.provider

                tools.append({
                    "type": "api_tool",
                    "provider": {
                        "id": str(provider.id),
                        "name": provider.name,
                        "label": provider.name,
                        "icon": provider.icon,
                        "description": provider.description,
                    },
                    "tool": {
                        "id": str(api_tool.id),
                        "name": api_tool.name,
                        "label": api_tool.name,
                        "description": api_tool.description,
                        "params": {}
                    },

                })

        return tools, validate_tools

    def _process_and_validate_datasets(self, draft_datasets: list[dict]) -> tuple[list[dict], list[dict]]:
        # 15. 校验知识库列表，如果引用了不存在/被删除的知识库，需要剔除数据并更新，同时获取知识库的额外信息
        datasets = []

        dataset_records = self.db.session.query(Dataset).filter(Dataset.id.in_(draft_datasets)).all()

        dataset_dict = {str(dataset_record.id): dataset_record for dataset_record in dataset_records}

        dataset_set = set(dataset_dict.keys())

        # 16.计算存在的知识库id列表，为了保留原始顺序，使用列表循环的方式来判断
        exist_dataset_ids = [dataset_id for dataset_id in draft_datasets if dataset_id in dataset_set]

        # 18. 循环获取知识库数据
        for dataset_id in exist_dataset_ids:
            dataset = dataset_dict.get(str(dataset_id))
            datasets.append({
                "id": str(dataset.id),
                "name": dataset.name,
                "icon": dataset.icon,
                "description": dataset.description,
            })

        return datasets, exist_dataset_ids

    def get_langchain_tools_by_tools_config(self, tools_config: list[dict]) -> list[dict]:
        tools = []
        draft_app_config_tools = tools_config
        for tool in draft_app_config_tools:
            if tool["type"] == "builtin_tool":
                # 8.内置工具，通过builtin_provider_manager获取工具实例
                builtin_tool = self.builtin_provider_manager.get_tool(
                    tool["provider"]["id"],
                    tool["tool"]["name"]
                )
                if not builtin_tool:
                    continue
                tools.append(builtin_tool(**tool["tool"]["params"]))
            else:
                # 获取API工具
                api_tool = self.get(ApiTool, tool["tool"]["id"])
                if not api_tool:
                    continue
                tools.append(
                    self.api_provider_manager.get_tool(
                        ToolEntity(
                            id=str(api_tool.id),
                            name=api_tool.name,
                            url=api_tool.url,
                            mother=api_tool.mother,
                            description=api_tool.description,
                            parameters=api_tool.parameters,
                            headers=api_tool.provider.headers,

                        )
                    )
                )
        return tools
