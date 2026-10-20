"""
@Time    : 2026-03-11 15:15
@AUthor  : jiachengjie
@File    : 1.Markdown文档加载器.py
"""
import os

os.environ["UNSTRUCTURED_SKIP_NLTK_DOWNLOAD"] = "True"
from langchain_community.document_loaders import UnstructuredMarkdownLoader

loader = UnstructuredMarkdownLoader("./项目API资料.md",
                                    # #按元素拆分（标题/段落/列表等）
                                    mode="elements")

markdown = loader.load()

print(markdown)

print(len(markdown))

print(markdown[0].metadata)
