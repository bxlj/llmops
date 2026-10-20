"""
@Time    : 2026-03-11 15:46
@AUthor  : jiachengjie
@File    : 1.自定义加载器使用技巧.py
"""

from typing import Iterator, AsyncIterator

from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document


class CustomBaseLoader(BaseLoader):

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path

    def lazy_load(self) -> Iterator[Document]:
        """逐行读取文件的数据并使用yield返回文档"""
        with open(self.file_path, encoding='utf-8') as f:
            line_num = 0
            for line in f:
                yield Document(
                    page_content=line,
                    metadata={'line_num': line_num, "source": self.file_path}
                )
                line_num += 1

    async def alazy_load(self) -> AsyncIterator[Document]:
        """逐行读取文件的数据并使用yield返回文档"""
        import aiofiles
        async with aiofiles.open(self.file_path, encoding='utf-8') as f:
            line_num = 0
            async for line in f:
                yield Document(
                    page_content=line,
                    metadata={'line_num': line_num, "source": self.file_path}
                )
                line_num += 1


loader = CustomBaseLoader("./喵喵.txt")

document = loader.load()

print(document)

print(len(document))

print(document[0].metadata)
