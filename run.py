
import uvicorn

# 这里的 "src.api.server:app" 应该指向你的 FastAPI 实例
if __name__ == "__main__":
    uvicorn.run("src.api.server:app", host="127.0.0.1", port=8008, reload=False)