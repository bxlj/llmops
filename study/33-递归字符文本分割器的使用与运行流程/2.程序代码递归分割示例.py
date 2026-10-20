"""
@Time    : 2026-03-12 16:16
@AUthor  : jiachengjie
@File    : 2.程序代码递归分割示例.py
"""

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# 加载文档
loader = TextLoader("./项目API文档.md", encoding="utf-8")
documents = loader.load()

splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
    add_start_index=True,
)

# 分隔文档
chunks = splitter.split_documents(documents)

for chunk in chunks:
    print(f"块大小: {len(chunk.page_content)}, 元数据: {chunk.metadata}")
