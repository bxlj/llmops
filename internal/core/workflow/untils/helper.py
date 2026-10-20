"""
@Time    : 2026-10-12 9:37
@Author  : JiaChengJie
@File    : helper.py
"""
from typing import Any

from internal.core.workflow.entities.variable_entity import VariableEntity, VARIABLE_TYPE_MAP, VariableValueType, \
    VARIABLE_TYPE_DEFAULT_VALUE_MAP
from internal.core.workflow.entities.workflow_entity import WorkflowState


def extract_variables_from_state(variables: list[VariableEntity], state: WorkflowState) -> dict[str, Any]:
    """从状态中提取变量映射值信息"""
    # 1.构建变量字典信息
    variables_dict = {}
    # 2. 循环获取变量输入值，判断是直接赋值还是引用值
    for variable in variables:
        # 3. 获取变量类型
        variable_type_cls = VARIABLE_TYPE_MAP.get(variable.type)

        # 4. 直接赋值
        if variable.value.type == VariableValueType.LITERAL:
            variables_dict[variable.name] = variable_type_cls(variable.value.content)
        else:
            # 5. 引用值
            for node_result in state["node_results"]:
                if variable.value.content.ref_node_id == node_result.node_data.id:
                    variables_dict[variable.name] = variable_type_cls(node_result.outputs.get(
                        variable.value.content.ref_var_name,
                        VARIABLE_TYPE_DEFAULT_VALUE_MAP.get(variable.type)
                    ))

    return variables_dict
