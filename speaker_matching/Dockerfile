FROM public.ecr.aws/lambda/python:3.11
RUN pip install --no-cache-dir torch==2.5.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cpu
RUN pip install --only-binary=:all: --no-cache-dir sentencepiece==0.2.0 numpy==1.26.4 scipy==1.13.1 speechbrain==1.0.3 huggingface-hub==0.28.1 imageio-ffmpeg==0.6.0 \
 && ln -s "$(python -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')" /usr/local/bin/ffmpeg \
 && python -c 'from huggingface_hub import snapshot_download; snapshot_download("speechbrain/spkrec-ecapa-voxceleb", revision="2bf922ef11463ccbdd9f5f04fec18f48b236115a", local_dir="/var/task/model")'
COPY __init__.py worker.py /var/task/speaker_matching/
ENV HF_HUB_OFFLINE=1 OMP_NUM_THREADS=1
CMD ["speaker_matching.worker.handler"]
