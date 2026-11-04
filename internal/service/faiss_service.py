"""
@Time    : 2026-11-02 11:21
@Author  : JiaChengJie
@File    : faiss_service.py
"""
import os

from injector import inject
from langchain_community.vectorstores import FAISS
from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from internal.core.agent.entities.agent_entity import DATASET_RETRIEVAL_TOOL_NAME
from internal.lib.helper import combine_documents
from internal.service.embeddings_service import EmbeddingsService
from .base_service import BaseService


@inject
class FaissService(BaseService):
    """faiss 向量数据库服务"""
    faiss: FAISS
    embeddings_service: EmbeddingsService

    def __init__(self, embeddings_service: EmbeddingsService):
        """初始化faiss向量数据库"""
        self.embeddings_service = embeddings_service

        # 2. 获取向量索引文件路径（`index.faiss` + `index.pkl`）
        internal_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        vector_store_path = os.path.join(internal_path, "core", "vector_store")

        # 3. 初始化faiss,加载数据
        self.faiss = FAISS.load_local(
            folder_path=vector_store_path,
            embeddings=self.embeddings_service.embeddings,
            allow_dangerous_deserialization=True,
        )

    def convert_faiss_to_tool(self) -> BaseTool:
        """将向量数据库检索工具转换为BaseTool"""
        faiss_retriever = self.faiss.as_retriever(
            search_type="mmr", search_kwargs={"k": 5, "fetch_k": 20}
        )

        # 2.构建检索链，并将检索的结果合并成字符串
        search_chain = faiss_retriever | combine_documents

        class DatasetRetrievalInput(BaseModel):
            """知识库检索输入查询语句"""
            query: str = Field(description="知识库检索query语句，类型为字符串")

        @tool(DATASET_RETRIEVAL_TOOL_NAME, args_schema=DatasetRetrievalInput)
        def dataset_retrieval(query: str) -> str:
            """如果需要检索扩展的知识库内容，当你觉得用户的提问超过你的知识范围时，可以尝试调用该工具，输入为搜索query语句，返回数据为检索内容字符串"""
            return search_chain.invoke(query)

        return dataset_retrieval