FROM node:22-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Same-origin /api proxy keeps the built client independent of host port settings.
ENV VITE_API_BASE_URL=/api
RUN npm run build
RUN npm prune --omit=dev

FROM node:22-alpine
ENV NODE_ENV=production PORT=5173 API_UPSTREAM=http://api:8000
WORKDIR /app
COPY --from=build /app/dist ./dist
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/package.json ./package.json
COPY frontend/serve.mjs ./serve.mjs
EXPOSE 5173
USER node
CMD ["node", "serve.mjs"]
