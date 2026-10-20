"""
@Time    : 2026-10-06 10:20
@Author  : JiaChengJie
@File    : code_node.py
"""
import ast
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import Optional

from langchain_core.runnables import RunnableConfig

from internal.core.workflow.entities.node_entity import NodeResult, NodeStatus
from internal.core.workflow.entities.variable_entity import VARIABLE_TYPE_DEFAULT_VALUE_MAP
from internal.core.workflow.entities.workflow_entity import WorkflowState
from internal.core.workflow.nodes import BaseNode
from internal.core.workflow.untils.helper import extract_variables_from_state
from internal.exception import FailException
from .code_entity import CodeNodeData

# main函数最长执行时间(秒)，超时后请求线程不再等待
CODE_EXECUTE_TIMEOUT = 30


class CodeNode(BaseNode):
    """Python代码运行节点"""
    node_data: CodeNodeData

    def invoke(self, state: WorkflowState, config: Optional[RunnableConfig] = None) -> WorkflowState:
        """Python代码运行节点，执行的代码函数名字必须为main，参数名为params且有且只有一个参数，不允许有额外的其他语句"""
        # 1.记录开始时间并从状态中提取输入数据(与其他节点保持一致)
        start_at = time.perf_counter()
        inputs_dict = extract_variables_from_state(self.node_data.inputs, state)

        # 4.执行Python代码，并把输入变量打包成params字典传给main函数
        # todo:该方法目前可以执行任意的Python代码，所以非常危险，后期需要单独将这部分功能迁移到沙箱中或者指定容器中运行和项目分离
        result = self._execute_function(self.node_data.code, params=inputs_dict)

        # 5.检测函数的返回值是否为字典
        if not isinstance(result, dict):
            raise FailException("main函数的返回值必须是一个字典")

        # 6.提取输出数据(非严格校验，输出变量名在返回字典中找不到时填默认值)
        outputs_dict = {}
        for output in self.node_data.outputs:
            outputs_dict[output.name] = result.get(
                output.name,
                VARIABLE_TYPE_DEFAULT_VALUE_MAP.get(output.type),
            )

        # 7.构建状态数据并返回
        return {
            "node_results": [
                NodeResult(
                    node_data=self.node_data,
                    status=NodeStatus.SUCCEEDED,
                    inputs=inputs_dict,
                    outputs=outputs_dict,
                    latency=(time.perf_counter() - start_at),
                )
            ]
        }

    @classmethod
    def _execute_function(cls, code: str, **kwargs) -> dict:
        """执行Python函数代码"""
        # 1.先做AST结构校验(放在try外面，保证校验报错能原样抛出而不是被吞掉)   ← ↓↓↓ 补丁1
        cls._validate_code_structure(code)

        # 2.执行代码并调用main函数，施加超时保护                              ← ↓↓↓ 补丁2
        #   说明:Python线程无法强制杀死，超时后请求线程不再等待，
        #   但失控线程仍会占用一个工作线程直至自然结束，真正的硬超时需要子进程/容器隔离
        local_vars = {}
        executor = ThreadPoolExecutor(max_workers=1)
        try:
            exec(code, {}, local_vars)

            # 3.校验main函数存在且可调用
            main_func = local_vars.get("main")
            if main_func is None or not callable(main_func):
                raise FailException("main函数必须是一个可调用的函数")

            # 4.调用main函数并等待执行结果
            future = executor.submit(main_func, **kwargs)
            return future.result(timeout=CODE_EXECUTE_TIMEOUT)
        except FutureTimeoutError:
            raise FailException(f"代码执行超时，最长允许{CODE_EXECUTE_TIMEOUT}秒")
        except FailException:
            # 5.主动抛出的FailException原样向上抛，不能被下面的统一捕获覆盖      ← ↓↓↓ 补丁1
            raise
        except Exception as e:
            # 6.保留原始错误类型和信息，方便用户定位代码问题                     ← ↓↓↓ 补丁3
            raise FailException(f"Python代码执行出错: {type(e).__name__}: {e}")
        finally:
            executor.shutdown(wait=False)

    @classmethod
    def _validate_code_structure(cls, code: str) -> None:
        """校验代码结构：只能有一个main(params)函数，不允许其他语句"""
        # 1.解析代码为AST(抽象语法树)，语法错误单独提示
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            raise FailException(f"代码语法错误: {e}")

        # 2.定义变量用于记录是否找到main函数
        main_func = None

        # 3.循环遍历语法树顶层节点
        for node in tree.body:
            # 4.判断节点类型是否为函数定义
            if isinstance(node, ast.FunctionDef):
                # 5.检查函数名称是否为main
                if node.name == "main":
                    if main_func:
                        raise FailException("代码中只能有一个main函数")
                    # 6.校验main函数的参数必须为params且有且只有一个
                    if len(node.args.args) != 1 or node.args.args[0].arg != "params":
                        raise FailException("main函数必须只有一个参数，且参数为params")
                    main_func = node
                else:
                    # 7.其他函数的情况，直接抛出错误
                    raise FailException("代码中不能包含其他函数，只能有main函数")
            else:
                # 8.非函数的情况，直接抛出错误
                raise FailException("代码中只能包含main函数定义，不允许其他语句存在")

        # 9.判断是否找到main函数
        if not main_func:
            raise FailException("代码中必须包含名为main的函数")
