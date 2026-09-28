# Local multilingual retrieval

The pinned `intfloat/multilingual-e5-small` model is distributed under the MIT
license, as declared by its publisher's [model card](https://huggingface.co/intfloat/multilingual-e5-small/blob/614241f622f53c4eeff9890bdc4f31cfecc418b3/README.md).
Authors: Liang Wang, Nan Yang, Xiaolong Huang, Linjun Yang, Rangan Majumder,
Furu Wei. Multilingual E5 Text Embeddings: A Technical Report (2024),
https://arxiv.org/abs/2402.05672. The original model card is retained in the image.
Model weights are not included in this Git repository.

The implementation follows the publisher's documented query/passage prefixes,
attention-mask mean pooling, normalization and 512-token limit. PyTorch,
Transformers, FastAPI, Uvicorn and safetensors retain their installed upstream
license notices. The Helvetic Lens adapter is Apache-2.0.

NoMIRACL data is used only in a separate local evaluation, never loaded by this
service. Its publisher declares Apache-2.0; underlying Wikipedia material retains
its own attribution/share-alike rights. Public reports contain dataset URLs,
revision, file hashes, document/query IDs, judgments and metrics, not copied
articles. See https://huggingface.co/datasets/miracl/nomiracl and
https://github.com/project-miracl/nomiracl for the authors and original license.
