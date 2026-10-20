"""
@Time    : 2026-03-12 10:07
@AUthor  : jiachengjie
@File    : GenericLoader示例.py
"""
from langchain_community.document_loaders.blob_loaders import FileSystemBlobLoader
from langchain_community.document_loaders.generic import GenericLoader
from langchain_community.document_loaders.parsers.txt import TextParser


# 生产级配置，批量加载 + 基础解析 + 异常捕获
def create_generic_loader(doc_dir: str) -> GenericLoader:
    blob_loader = FileSystemBlobLoader(
        path=doc_dir,
        glob="**/*.txt",
        show_progress=True  # 生产环境可选：显示加载进度
    )
    # 2. 配置Parser
    blob_parser = TextParser()
    # 3. 生成GenericLoader
    loader = GenericLoader(blob_loader=blob_loader, blob_parser=blob_parser)
    return loader


loader = create_generic_loader("./喵喵.txt")
docs = loader.load()
print(docs)
print(len(docs))
