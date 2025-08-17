import torch
from transformers import AutoModel, AutoTokenizer
import gc

print('Testing Qwen3-Embedding model with GPU...')
try:
      device = 'cuda' if torch.cuda.is_available() else 'cpu'
      print(f'Using device: {device}')

      # 下载并加载模型到GPU
      tokenizer = AutoTokenizer.from_pretrained('Qwen/Qwen3-Embedding-0.6B', trust_remote_code=True)
      model = AutoModel.from_pretrained('Qwen/Qwen3-Embedding-0.6B', trust_remote_code=True).to(device)

      print('Model loaded successfully on GPU!')
      print(f'Model device: {next(model.parameters()).device}')

      # 清理内存
      del model
      del tokenizer
      gc.collect()
      torch.cuda.empty_cache()

except Exception as e:
      print(f'Error: {e}')