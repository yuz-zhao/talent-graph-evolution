FROM node:22-bookworm-slim

WORKDIR /app
ENV NODE_ENV=production \
    TESSERACT_PATH=/usr/bin/tesseract \
    PDFTOPPM_PATH=/usr/bin/pdftoppm

# Scanned PDF resumes require Tesseract OCR and Poppler's pdftoppm.
# Language data is supplied by server/tessdata so the image does not depend on
# a distribution-specific Chinese language package.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY package.json package-lock.json ./
RUN npm ci --omit=dev

COPY --chown=node:node server ./server
COPY --chown=node:node crawler/data ./crawler/data
COPY --chown=node:node knowledge_graph/import ./knowledge_graph/import
COPY --chown=node:node knowledge_graph/gnn_models ./knowledge_graph/gnn_models
RUN mkdir -p /app/uploads && chown node:node /app/uploads

EXPOSE 3001
USER node
CMD ["node", "server/index.js"]
