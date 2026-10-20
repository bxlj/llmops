"""
@Time    : 2026-03-11 14:54
@AUthor  : jiachengjie
@File    : 1.Document与TextLoader.py
"""
from langchain_community.document_loaders import TextLoader

loader = TextLoader("./电商产品数据.txt", encoding="utf-8")

document = loader.load()

print(document)

print(len(document))

print(document[0].metadata)
