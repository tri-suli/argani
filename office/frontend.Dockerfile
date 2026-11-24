FROM node:24-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html tsconfig.json vite.config.ts ./
COPY src ./src
RUN npx vite build

FROM nginxinc/nginx-unprivileged:alpine
ENV OFFICE_FRONTEND_PORT=1222 OFFICE_BACKEND_PORT=2212
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
