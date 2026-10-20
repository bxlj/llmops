"""
@Time    : 2026-03-10 10:09
@AUthor  : jiachengjie
@File    : OpenAI嵌入模型示例.py
"""
import os

import dotenv
import numpy as np
from langchain_classic.embeddings import CacheBackedEmbeddings
from langchain_classic.storage import LocalFileStore
from langchain_community.embeddings import ZhipuAIEmbeddings

dotenv.load_dotenv()

# 初始化Embedding模型
embeddings = ZhipuAIEmbeddings(
    model='embedding-2',
    api_key=os.environ['ZHIPU_API_KEY'],
)
file_store = LocalFileStore("./cache/")  # 缓存文件存储路径

cache_embeddings = CacheBackedEmbeddings.from_bytes_store(
    underlying_embeddings=embeddings,
    document_embedding_cache=file_store,
    namespace="embedding-2",
    batch_size=None,
    query_embedding_cache=True,
    key_encoder="sha256"

)

# 把文本转换成向量
text1 = "苹果发布了最新款iPhone"
text2 = "我想要一个Mac Studio M5 MAX的电脑"
text3 = "华为发布了新款Mate手机"

# 单文本转向量
vec1 = cache_embeddings.embed_query(text1)

# 多文本转向量
vecs = cache_embeddings.embed_documents([text3, text2, text1])

print(f"单个向量维度：{len(vec1)}")
print(f"多个向量维度：{len(vecs)}")


# 计算相似度
# 计算相似度
def cosine_similarity(vec_a, vec_b):
    dot_product = np.dot(vec_a, vec_b)
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)
    return dot_product / (norm_a * norm_b)


sim1_2 = cosine_similarity(vecs[0], vecs[1])
sim1_3 = cosine_similarity(vecs[0], vecs[2])

print(f"text1和text2相似度：{sim1_2:.4f}")  # 约0.9+
print(f"text1和text3相似度：{sim1_3:.4f}")  # 约0.2-
