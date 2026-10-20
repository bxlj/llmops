"""
@Time    : 2026-03-12 9:51
@AUthor  : jiachengjie
@File    : 1.Blob解析器示例.py
"""
from typing import Iterator

from langchain_core.document_loaders import BaseBlobParser
from langchain_core.documents import Document
from langchain_core.documents.base import Blob


class CustomBlobParser(BaseBlobParser):

    def lazy_parse(self, blob: Blob) -> Iterator[Document]:
        """自定义解析器，用于将传入的文本二进制数据的每一行解析成Document组件"""
        line_number = 0
        with blob.as_bytes_io() as f:
            for line in f:
                yield Document(page_content=line,
                               metadata={'source': blob.source, "line_number": line_number}
                               )
                line_number += 1


# 加载blob数据
blob = Blob.from_path("./喵喵.txt")
parser = CustomBlobParser()

# 解析得到文档数据
document = list(parser.lazy_parse(blob))

print(document)

print(len(document))

print(document[0].metadata)
