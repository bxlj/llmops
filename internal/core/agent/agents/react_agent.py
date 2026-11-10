"""
@Time    : 2026-11-08 17:40
@Author  : JiaChengJie
@File    : react_agent.py
"""
import uuid

from langchain_core.messages import SystemMessage
from langchain_core.tools import render_text_description_and_args

from internal.core.agent.agents import FunctionCallAgent
from internal.core.agent.entities.agent_entity import AgentState, AGENT_SYSTEM_PROMPT_TEMPLATE, \
    REACT_AGENT_SYSTEM_PROMPT_TEMPLATE
from internal.core.agent.entities.queue_entity import AgentThought, QueueEvent
from internal.core.language_model.entities.model_entity import ModelFeature


class ReACTAgent(FunctionCallAgent):
    """基于ReACT的推理智能体，继承FunctionCallAgent，并重写long_term_memory_node和llm_node两个节点"""

    def _long_term_memory_recall_node(self, state: AgentState) -> AgentState:
        """重写长期记忆召回节点，使用prompt实现工具调用及规范数据生成"""

        # 1.判断是否支持工具调用，如果支持工具调用，则可以直接使用工具智能体的长期记忆召回节点
        if ModelFeature.TOOL_CALL in self.llm.features:
            return super()._long_term_memory_recall_node(state)

        # 2.根据传递的智能体配置判断是否需要召回长期记忆
        long_term_memory = ""
        if self.agent_config.enable_long_term_memory:
            long_term_memory = state["long_term_memory"]
            self.agent_queue_manager.publish(state["task_id"], AgentThought(
                id=uuid.uuid4(),
                task_id=state["task_id"],
                event=QueueEvent.LONG_TERM_MEMORY_RECALL,
                observation=long_term_memory,
            ))

        # 3.检测是否支持AGENT_THOUGHT，如果不支持，则使用没有工具描述的prompt
        if ModelFeature.AGENT_THOUGHT not in self.llm.features:
            preset_messages = [
                SystemMessage(AGENT_SYSTEM_PROMPT_TEMPLATE.format(
                    preset_prompt=self.agent_config.preset_prompt,
                    long_term_memory=long_term_memory,
                ))
            ]

        else:
            # 4.支持智能体推理，则使用REACT_AGENT_SYSTEM_PROMPT_TEMPLATE并添加工具描述
            preset_messages = [
                SystemMessage(REACT_AGENT_SYSTEM_PROMPT_TEMPLATE.format(
                    preset_prompt=self.agent_config.preset_prompt,
                    long_term_memory=long_term_memory,
                    tool_description=render_text_description_and_args(self.agent_config.tools),
                ))
            ]

        # 5.将短期历史消息添加到消息列表中

        # 6.校验历史消息是不是复数形式，也就是[人类消息, AI消息, 人类消息, AI消息, ...]

        # 7.拼接历史消息

        # 8.拼接当前用户的提问消息

        # 9.处理预设消息，将预设消息添加到用户消息前，先去删除用户的原始消息，然后补充一个新的代替
