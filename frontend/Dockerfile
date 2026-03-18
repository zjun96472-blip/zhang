ARG BASE_IMAGE=node:22-alpine
FROM ${BASE_IMAGE}

ARG BASE_IMAGE

WORKDIR /app

COPY package.json package-lock.json ./
RUN if [ "$BASE_IMAGE" = "agent-frontend:latest" ]; then \
      echo "Reusing frontend dependencies from local image cache"; \
    else \
      npm ci; \
    fi

COPY next-env.d.ts next.config.ts tsconfig.json ./
COPY app ./app
COPY components ./components
COPY lib ./lib

RUN npm run build

EXPOSE 3000

CMD ["npm", "run", "start"]
