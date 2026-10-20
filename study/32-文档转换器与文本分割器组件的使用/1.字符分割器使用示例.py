"""
@Time    : 2026-03-12 16:00
@AUthor  : jiachengjie
@File    : 1.字符分割器使用示例.py
"""

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import CharacterTextSplitter

# 加载对应的文档
loader = TextLoader("./项目API文档.md", encoding="utf-8")
documents = loader.load()

# 创建文本分割器
text_splitter = CharacterTextSplitter(
    separator="\n\n",
    chunk_size=500,
    chunk_overlap=50,
    add_start_index=True

)

chunks = text_splitter.split_documents(documents)

for chunk in chunks:
    print(f"块大小:{len(chunk.page_content)}, 元数据:{chunk.metadata}")

print(len(chunks))
