from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import json
import av
import numpy as np
import torch
from transformers import VivitImageProcessor, VivitForVideoClassification
import requests
import io

np.random.seed(0)

def read_video_pyav(container, indices):
    frames = []
    container.seek(0)
    start_index = indices[0]
    end_index = indices[-1]
    for i, frame in enumerate(container.decode(video=0)):
        if i > end_index:
            break
        if i >= start_index and i in indices:
            frames.append(frame)
    return np.stack([x.to_ndarray(format="rgb24") for x in frames])

def sample_frame_indices(clip_len, frame_sample_rate, seg_len):
    converted_len = int(clip_len * frame_sample_rate)
    end_idx = np.random.randint(converted_len, seg_len)
    start_idx = end_idx - converted_len
    indices = np.linspace(start_idx, end_idx, num=clip_len)
    indices = np.clip(indices, start_idx, end_idx - 1).astype(np.int64)
    return indices

def vivit(file_path):
    response = requests.get(file_path, stream=True)
    file_stream = io.BytesIO(response.content)
    container = av.open(file_stream)
    indices = sample_frame_indices(clip_len=32, frame_sample_rate=4, seg_len=container.streams.video[0].frames)
    video = read_video_pyav(container=container, indices=indices)
    image_processor = VivitImageProcessor.from_pretrained("ltkien2003/vit")
    model = VivitForVideoClassification.from_pretrained("ltkien2003/vit")
    inputs = image_processor(list(video), return_tensors="pt")
    with torch.no_grad():
        outputs = model(**inputs)
        logits = outputs.logits
    predicted_label = logits.argmax(-1).item()
    return model.config.id2label[predicted_label]

class VivitAPI(APIView):
    def post(self, request):
        try:
            # Nhận file_path từ request data
            request_data = json.loads(request.body.decode('utf-8'))
            file_path = request_data.get('file_path')

            # Gọi hàm vivit với file path
            result = vivit(file_path)

            # Trả về kết quả dưới dạng JSON response
            response_data = {'result': result}
            return Response(response_data, status=status.HTTP_200_OK)
        except Exception as e:
            # Xử lý các ngoại lệ theo cách cần thiết
            error_message = str(e)
            return Response({'error': error_message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
