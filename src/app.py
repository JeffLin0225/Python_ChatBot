from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
from PIL import Image
import numpy as np
import time

from blip_processor import BLIPProcessor
from llama_handler import LlamaHandler
from ocr_processor import PaddleOCR

# 初始化 Flask
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB 限制
app.config['JSON_AS_ASCII'] = False  # 禁用 ASCII 編碼，讓中文直接輸出
CORS(app)  # 啟用 CORS

# 初始化處理器
try:
    blip_processor = BLIPProcessor()
    llama_handler = LlamaHandler()
    ocr_processor = PaddleOCR()
except Exception as e:
    print(f"初始化失敗：{str(e)}")
    exit(1)

@app.route('/jaxiapi/ask', methods=['POST'])
def generate_caption():
    # 取得圖片和問題
    image_file = request.files.get('image')
    question = request.form.get('question', '').strip()
    print(f"User Question: {question}")  # 監控：顯示問題

    if not image_file and not question:
        return jsonify({"error": "請輸入文字或是圖片"}), 400

    if image_file and image_file.content_type not in ['image/jpeg', 'image/png']:
        return jsonify({"error": "僅支援 JPEG 或 PNG 圖片"}), 400

    blipDescription = None
    ocrDescription = None

    if image_file:
        try:
            image = Image.open(image_file.stream).convert("RGB")
            image_np = np.array(image)
            success, ocrDescription = ocr_processor.process_ocr(image_np)
            if not success:
                ocrDescription = None
            blipDescription = blip_processor.blip_analyze(image)
        except Exception as e:
            print(f"圖片處理失敗：{str(e)}")
            return jsonify({"error": "圖片處理失敗"}), 400

    def generate_stream():
        # 在函數內部初始化回應用變數
        full_response = ""
        try:
            if question:
                if blipDescription:
                    for chunk in llama_handler.ask_llama(question, ocrDescription, blipDescription):
                        full_response += chunk
                        yield f"data: {chunk}\n\n"
                else:
                    for chunk in llama_handler.ask_llama(question):
                        full_response += chunk
                        yield f"data: {chunk}\n\n"
                        time.sleep(0.05)  # 保留模擬打字效果
            else:
                full_response = blipDescription or ""
                yield f"data: {full_response}\n\n"
            yield "data: [DONE]\n\n"
        finally:
            # 監控：顯示完整回應
            print(f"Bot Response: {full_response}")

    # 使用 SSE 格式返回流式回應
    return Response(stream_with_context(generate_stream()), mimetype='text/event-stream')

# 錯誤處理 (413 圖片超出規範大小)
@app.errorhandler(413)
def request_entity_too_large(error):
    print("檔案大小超過 10MB 限制")
    return jsonify({"error": "檔案大小超過 10MB 限制"}), 413

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)