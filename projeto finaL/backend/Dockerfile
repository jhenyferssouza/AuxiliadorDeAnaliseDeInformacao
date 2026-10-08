FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && python -m spacy download pt_core_news_lg

COPY . .
RUN useradd -m -u 1000 user && chown -R user /app
USER user

EXPOSE 7860