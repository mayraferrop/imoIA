FROM node:20-alpine

RUN apk add --no-cache git python3 make g++

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install --omit=dev --no-audit --no-fund

COPY server.js store.js ./

ENV DATA_DIR=/data
VOLUME ["/data"]

EXPOSE 3000

CMD ["node", "server.js"]
